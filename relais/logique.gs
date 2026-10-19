/* Règles du relais : qui est qui, qui peut quoi, et ce que l'on accepte d'envoyer à GitHub.
   Calcul pur, sans appel réseau : le même fichier tourne dans Apps Script et dans les tests (pipeline/test_relais.js). */

var ROLES = ['heros', 'admin', 'superadmin'];
var ROLE_DE = { heros: 0, admin: 1, superadmin: 2 };
var ACTIONS = {                       // niveau minimal pour chaque action
  moi: 'heros',
  envoyer: 'admin',
  journal: 'admin',
  equipe_lire: 'superadmin',
  equipe_ajouter: 'superadmin',
  equipe_retirer: 'superadmin',
  equipe_bloquer: 'superadmin',
  releve: 'superadmin',
  demande: 'heros',               // tout compte connecté peut demander l'ajout d'un livre
  demandes_lire: 'admin',
  demande_traiter: 'admin',
  noter: 'heros',                 // tout compte connecté peut noter un livre de 1 à 5
  mes_notes: 'heros'
};                                       // « contact » n'est pas ici : il est ouvert à tous les visiteurs (voir contacter dans Code.gs)
var LOTS = { 'corriger-prix.yml': ['corrections'], 'ajout-isbn.yml': ['liste', 'releve'], 'corriger-fiche.yml': ['corrections'] };   // lots que le relais accepte de lancer, avec leurs champs
var LIMITE_CHAMP = 20000;
var EMETTEURS = ['accounts.google.com', 'https://accounts.google.com'];

function nettoyerNom(brut) {
  return String(brut == null ? '' : brut).replace(/[\u0000-\u001f|;\s]+/g, ' ').trim().slice(0, 30);
}
function minuscules(s) { return String(s == null ? '' : s).trim().toLowerCase(); }

/* Réponse de https://oauth2.googleapis.com/tokeninfo : Google a déjà vérifié la signature ; on contrôle le reste.
   Deux formes : jeton d'identité (champs iss, exp) ou jeton d'accès (champs azp, expires_in, scope), que le site utilise. */
function decider(infos, fichier, clientId, empreinteDe, maintenantSec) {
  if (!infos || infos.error_description || infos.error) return { ok: false, raison: 'jeton refusé par Google' };
  if (infos.aud !== clientId && infos.azp !== clientId) return { ok: false, raison: 'jeton émis pour un autre site' };
  if (infos.iss != null && EMETTEURS.indexOf(infos.iss) < 0) return { ok: false, raison: 'émetteur inattendu' };
  if (infos.iss == null && infos.expires_in == null) return { ok: false, raison: 'jeton incomplet' };
  if (infos.iss != null && Number(infos.exp) < maintenantSec) return { ok: false, raison: 'connexion expirée' };
  if (infos.iss == null && Number(infos.expires_in) <= 0) return { ok: false, raison: 'connexion expirée' };
  if (String(infos.email_verified) !== 'true') return { ok: false, raison: 'adresse non vérifiée par Google' };
  var adresse = minuscules(infos.email);
  var empreinte = empreinteDe(adresse);
  var bloques = (fichier.bloques || []).map(minuscules);
  if (bloques.indexOf(adresse) >= 0 || bloques.indexOf(empreinte) >= 0) return { ok: false, raison: 'compte bloqué' };
  var equipe = fichier.equipe || {}, membre = null;
  Object.keys(equipe).forEach(function (k) { var c = minuscules(k); if (c === adresse || c === empreinte) membre = equipe[k]; });
  if (membre && ROLE_DE[membre.role] != null) return { ok: true, role: membre.role, nom: nettoyerNom(membre.nom) || 'Admin', empreinte: empreinte };
  var prenom = nettoyerNom(infos.given_name || infos.name || adresse.split('@')[0]).slice(0, 20) || 'Héros';
  return { ok: true, role: 'heros', nom: prenom + ' #' + empreinte.slice(7, 11), empreinte: empreinte };
}

function peut(role, action) {
  var requis = ACTIONS[action];
  return !!requis && ROLE_DE[role] != null && ROLE_DE[role] >= ROLE_DE[requis];
}

/* Lot à lancer : seuls les lots connus, avec leurs champs connus, de taille raisonnable. */
function validerEnvoi(lot, entrees) {
  if (!LOTS.hasOwnProperty(lot)) return { ok: false, raison: 'lot inconnu' };
  var permis = LOTS[lot], propres = {};
  entrees = entrees || {};
  for (var k in entrees) {
    if (!entrees.hasOwnProperty(k)) continue;
    if (permis.indexOf(k) < 0) return { ok: false, raison: 'champ inconnu : ' + k };
    if (typeof entrees[k] !== 'string') return { ok: false, raison: 'champ invalide : ' + k };
    if (entrees[k].length > LIMITE_CHAMP) return { ok: false, raison: 'champ trop long : ' + k };
    propres[k] = entrees[k];
  }
  if (!propres[permis[0]]) return { ok: false, raison: 'champ manquant : ' + permis[0] };
  return { ok: true, entrees: propres };
}

function copie(o) { return JSON.parse(JSON.stringify(o)); }
function nbSuperAdmins(equipe) { return Object.keys(equipe).filter(function (k) { return equipe[k].role === 'superadmin'; }).length; }

/* Modifications de data/admins.json : renvoient { ok, fichier } ou { ok:false, raison }. `par` est l'empreinte de l'auteur. */
function ajouterMembre(fichier, empreinte, nom, role, par) {
  if (!/^sha256:[0-9a-f]{64}$/.test(empreinte)) return { ok: false, raison: 'empreinte invalide' };
  if (role !== 'admin' && role !== 'superadmin') return { ok: false, raison: 'niveau invalide' };
  var n = nettoyerNom(nom);
  if (!n) return { ok: false, raison: 'nom manquant' };
  var f = copie(fichier); f.equipe = f.equipe || {};
  f.equipe[empreinte] = { nom: n, role: role };
  f.bloques = (f.bloques || []).filter(function (b) { return minuscules(b) !== empreinte; });
  return { ok: true, fichier: f };
}
function retirerMembre(fichier, empreinte, par) {
  var f = copie(fichier); f.equipe = f.equipe || {};
  if (!f.equipe[empreinte]) return { ok: false, raison: 'membre introuvable' };
  if (empreinte === par) return { ok: false, raison: 'vous ne pouvez pas vous retirer vous-même' };
  if (f.equipe[empreinte].role === 'superadmin' && nbSuperAdmins(f.equipe) <= 1) return { ok: false, raison: 'il faut garder au moins un SuperAdmin' };
  delete f.equipe[empreinte];
  return { ok: true, fichier: f };
}
function bloquerCompte(fichier, empreinte, par) {
  if (!/^sha256:[0-9a-f]{64}$/.test(empreinte)) return { ok: false, raison: 'empreinte invalide' };
  if (empreinte === par) return { ok: false, raison: 'vous ne pouvez pas vous bloquer vous-même' };
  var f = copie(fichier); f.equipe = f.equipe || {}; f.bloques = f.bloques || [];
  if (f.equipe[empreinte] && f.equipe[empreinte].role === 'superadmin' && nbSuperAdmins(f.equipe) <= 1) return { ok: false, raison: 'il faut garder au moins un SuperAdmin' };
  delete f.equipe[empreinte];
  if (f.bloques.map(minuscules).indexOf(empreinte) < 0) f.bloques.push(empreinte);
  return { ok: true, fichier: f };
}

/* ---------- Demandes d'ajout de livres ----------
   Un Héros écrit un titre ou un ISBN ; le relais en fait un signalement GitHub (étiquette « demande-ajout ») au nom de la personne.
   Les admins les lisent, corrigent la ligne si besoin, puis acceptent (le lot « Ajouter des livres » est lancé) ou refusent. */
var PREFIXE_DEMANDE = "Demande d'ajout : ";
var ETIQUETTE_DEMANDE = 'demande-ajout';
var LIMITE_DEMANDES = 6;               // par personne (Héros) et par fenêtre de six heures (mémoire du script) ; pas de limite pour les admins

/* Texte sans retour à la ligne ni mise en forme : un signalement GitHub est public et interprète le markdown, les liens et les mentions. */
function nettoyerTexteDemande(brut, max) {
  return String(brut == null ? '' : brut).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/[@<>`*_#\[\]|\\]/g, ' ').replace(/https?:\/\/\S+/gi, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
}
function validerDemande(texte, note) {
  var t = nettoyerTexteDemande(texte, 150), n = nettoyerTexteDemande(note, 300);
  if (t.length < 3) return { ok: false, raison: 'indiquez un titre ou un ISBN (3 caractères au moins)' };
  return { ok: true, texte: t, note: n };
}
function formaterDemande(texte, note, nom) {
  return { titre: PREFIXE_DEMANDE + texte, corps: 'Demandé par ' + nom + (note ? '\n\n' + note : '') + "\n\n_Demande faite depuis le site. Un administrateur peut l'accepter ou la refuser depuis l'espace administrateur._" };
}
/* Signalement GitHub -> demande lisible par la page des admins (null si ce n'est pas une de nos demandes) */
function lireDemande(issue) {
  if (!issue || issue.pull_request || String(issue.title || '').indexOf(PREFIXE_DEMANDE) !== 0) return null;
  var lignes = String(issue.body || '').split('\n'), premiere = lignes[0] || '';
  var par = premiere.indexOf('Demandé par ') === 0 ? premiere.slice('Demandé par '.length).trim() : '';
  var note = lignes.slice(1).join('\n').split('\n\n').map(function (x) { return x.trim(); }).filter(function (x) { return x && x.charAt(0) !== '_'; }).join(' ');
  return { numero: issue.number, texte: issue.title.slice(PREFIXE_DEMANDE.length), par: par, note: note.slice(0, 300), date: String(issue.created_at || '').slice(0, 10) };
}
function peutDemander(compteur, role) { return (ROLE_DE[role] != null && ROLE_DE[role] >= ROLE_DE.admin) || (Number(compteur) || 0) < LIMITE_DEMANDES; }

/* ---------- Notes des livres (1 à 5) ----------
   Une voix par compte et par livre (le livre, pas l'édition). Les votes sont rangés sous une empreinte courte du compte : ni adresse ni nom.
   La moyenne et le nombre de votes sont publics ; qui a voté quoi ne l'est pas. */
var LIMITE_VOTES = 400;                // par livre (une propriété du script tient 9 Ko)
function validerNote(livre, note) {
  var l = String(livre == null ? '' : livre);
  if (!/^[a-z0-9][a-z0-9_-]{2,119}$/.test(l)) return { ok: false, raison: 'livre inconnu' };
  if (note === null || note === undefined || note === '' || typeof note === 'boolean') return { ok: false, raison: 'la note doit être un nombre entier de 1 à 5' };
  var n = Number(note);
  if (n !== 0 && !(n >= 1 && n <= 5 && n % 1 === 0)) return { ok: false, raison: 'la note doit être un nombre entier de 1 à 5' };
  return { ok: true, livre: l, note: n };
}
function votant(empreinte) { return String(empreinte).replace('sha256:', '').slice(0, 16); }
/* votes : { votant: note }. Note 0 = retirer sa note. Renvoie { ok, votes } ou { ok:false, raison }. */
function appliquerNote(votes, qui, note) {
  var v = copie(votes || {});
  if (note === 0) { delete v[qui]; return { ok: true, votes: v }; }
  if (v[qui] == null && Object.keys(v).length >= LIMITE_VOTES) return { ok: false, raison: 'ce livre a déjà reçu le maximum de notes' };
  v[qui] = note;
  return { ok: true, votes: v };
}
/* [moyenne arrondie au dixième, nombre de votes] */
function resumerNotes(votes) {
  var k = Object.keys(votes || {});
  if (!k.length) return [0, 0];
  var somme = 0; k.forEach(function (x) { somme += votes[x]; });
  return [Math.round(somme / k.length * 10) / 10, k.length];
}

/* ---------- Formulaire de contact ----------
   Ouvert à tout visiteur, sans connexion : le message est envoyé par courriel à l'éditeur (adresse jamais montrée sur le site).
   Limites : trois messages par adresse et par six heures, trente par heure pour tout le site. */
var LIMITE_CONTACT_ADRESSE = 3;
var LIMITE_CONTACT_HEURE = 30;
function texteContact(brut, max) {
  return String(brut == null ? '' : brut).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]+/g, ' ').replace(/\r\n?/g, '\n').trim().slice(0, max);
}
function validerContact(q) {
  q = q || {};
  if (q.piege) return { ok: false, raison: 'refusé' };                       // champ caché rempli : un robot
  var email = minuscules(q.email).slice(0, 120), message = texteContact(q.message, 4000), nom = texteContact(q.nom, 80).replace(/\n+/g, ' ');
  if (!/^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]{2,}$/.test(email)) return { ok: false, raison: 'adresse électronique invalide' };
  if (message.length < 5) return { ok: false, raison: 'le message est trop court' };
  return { ok: true, nom: nom, email: email, message: message };
}
function contactAutorise(compteurAdresse, compteurHeure) {
  return (Number(compteurAdresse) || 0) < LIMITE_CONTACT_ADRESSE && (Number(compteurHeure) || 0) < LIMITE_CONTACT_HEURE;
}
function formaterContact(c) {
  return { sujet: 'Nouveau message via La Cote du Héros', corps: 'De : ' + (c.nom || '(sans nom)') + ' <' + c.email + '>\n\n' + c.message };
}
