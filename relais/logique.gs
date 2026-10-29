// Version du 2026-10-29 09:08 (heure de Paris) : pépite Vinted, pépite « Marquer vendue », annonces reçues, indice de marché (indice_lire). Si cette ligne est ancienne dans Apps Script, le fichier n'est pas à jour.
/* Règles du relais : qui est qui, qui peut quoi, et ce que l'on accepte d'envoyer à GitHub.
   Calcul pur, sans appel réseau : le même fichier tourne dans Apps Script et dans les tests (pipeline/test_relais.js). */

var ROLES = ['heros', 'admin', 'superadmin'];
var ROLE_DE = { heros: 0, admin: 1, superadmin: 2 };
var LIMITE_ISBN_ENVOI = 20;         // ISBN au plus par envoi (sorciers)
var LIMITE_ENVOIS_JOUR = 3;         // envois par jour et par personne (sorciers)

function quotaAjout(role, nombre, envoisDuJour) {   // le Zagor n'est pas limité
  if (role === 'superadmin') return { ok: true };
  if (role !== 'admin') return { ok: false, raison: 'réservé aux sorciers et aux Zagors' };
  if (!(nombre > 0)) return { ok: false, raison: 'la liste est vide' };
  if (nombre > LIMITE_ISBN_ENVOI) return { ok: false, raison: LIMITE_ISBN_ENVOI + ' ISBN au plus par envoi' };
  if ((Number(envoisDuJour) || 0) >= LIMITE_ENVOIS_JOUR) return { ok: false, raison: LIMITE_ENVOIS_JOUR + ' envois par jour au plus : réessayez demain' };
  return { ok: true };
}

var ACTIONS = {                       // niveau minimal pour chaque action
  moi: 'heros',
  envoyer: 'superadmin',          // seul le Zagor corrige prix et fiches
  journal: 'superadmin',
  equipe_lire: 'superadmin',
  equipe_ajouter: 'superadmin',
  equipe_retirer: 'superadmin',
  equipe_bloquer: 'superadmin',
  equipe_periode: 'superadmin',   // dates de début et de fin d'un sorcier (facultatives)
  releve: 'superadmin',
  comptes_lire: 'superadmin',      // total des comptes et liste des prénoms, par ordre d'arrivée
  ajout_livres: 'admin',          // sorciers et Zagors : ajout de livres en série (liste d'ISBN), voir quotaAjout
  butin_lire: 'admin',            // Butin seul (bonnes affaires) : sorciers et Zagors
  annonces_lire: 'superadmin',    // toutes les annonces reçues : le Zagor seulement
  indice_lire: 'superadmin',      // indice de marché par version et éditeur : le Zagor seulement
  pepite_offrir: 'superadmin',    // le Zagor choisit la pépite du jour offerte aux Héros
  pepite_retirer: 'superadmin',   // et peut la retirer
  pepite_vendre: 'superadmin',    // ou la marquer vendue (barrée sur le site, plus proposée)
  noter: 'heros',                 // tout compte connecté peut noter un livre de 1 à 5
  mes_notes: 'heros',
  bienvenue: 'heros',             // premier passage d'un compte : l'éditeur est prévenu par courriel
  avis: 'heros'                   // un avis libre sur le site, envoyé par courriel à l'éditeur
};
var LOTS = { 'corriger-prix.yml': ['corrections'], 'ajout-isbn.yml': ['liste', 'releve'], 'corriger-fiche.yml': ['corrections'] };   // lots que le relais accepte de lancer, avec leurs champs
var LIMITE_CHAMP = 20000;
var EMETTEURS = ['accounts.google.com', 'https://accounts.google.com'];

/* Période d'un sorcier : dates de début et de fin (AAAA-MM-JJ, heure UTC, jours inclus). Sans date : sans limite de ce côté.
   Hors période, il est Héros. Un Zagor n'a jamais de période. */
function jourDe(secondes) { return new Date(secondes * 1000).toISOString().slice(0, 10); }
function estEchu(membre, aujourdhui) { return !!(membre && membre.role === 'admin' && membre.fin && membre.fin < aujourdhui); }
function estAVenir(membre, aujourdhui) { return !!(membre && membre.role === 'admin' && membre.debut && membre.debut > aujourdhui); }
function estEnPeriode(membre, aujourdhui) { return !(estEchu(membre, aujourdhui) || estAVenir(membre, aujourdhui)); }
function dateValide(t) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false;
  var d = new Date(t + 'T00:00:00Z');
  return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === t;
}

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
  if (membre && !estEnPeriode(membre, jourDe(maintenantSec))) membre = null;     // sorcier avant son début ou après sa fin : Héros
  if (membre && ROLE_DE[membre.role] != null) return { ok: true, role: membre.role, nom: nettoyerNom(membre.nom) || 'Admin', empreinte: empreinte, fin: membre.role === 'admin' ? (membre.fin || '') : '' };
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

/* Pépite du jour : le Zagor offre une annonce aux Héros. Le fichier public data/pepite-du-jour.json est écrit par le relais ;
   on n'accepte que des champs connus, un lien https et des valeurs plausibles. */
var ORIGINES_PEPITE = ['leboncoin', 'vinted', 'ebay', 'librairie', 'isbn', 'titre'];
function validerPepite(q) {
  q = q || {};
  var isbn = String(q.isbn13 || ''), prix = Number(q.prix), pub = q.pub == null || q.pub === '' ? null : Number(q.pub);
  var pct = q.pct == null || q.pct === '' ? null : Number(q.pct), lien = String(q.lien || '');
  if (!/^\d{13}$/.test(isbn)) return { ok: false, raison: 'ISBN invalide' };
  if (!(prix > 0 && prix < 10000)) return { ok: false, raison: 'prix invalide' };
  if (pub !== null && !(pub > 0 && pub < 10000)) return { ok: false, raison: 'cote invalide' };
  if (pct !== null && !(pct >= 0 && pct <= 100 && pct % 1 === 0)) return { ok: false, raison: 'pourcentage invalide' };
  if (['C', 'BE', 'TBE'].indexOf(String(q.etat)) < 0) return { ok: false, raison: 'état invalide' };
  if (ORIGINES_PEPITE.indexOf(String(q.origine)) < 0) return { ok: false, raison: 'origine invalide' };
  if (!/^https:\/\/[^\s"<>]{4,480}$/.test(lien)) return { ok: false, raison: 'lien invalide' };
  return { ok: true, pepite: { isbn13: isbn, prix: Math.round(prix * 100) / 100, pub: pub === null ? null : Math.round(pub * 100) / 100, pct: pct,
    etat: String(q.etat), origine: String(q.origine), lien: lien, solide: q.solide === true } };
}

function copie(o) { return JSON.parse(JSON.stringify(o)); }
function nbSuperAdmins(equipe) { return Object.keys(equipe).filter(function (k) { return equipe[k].role === 'superadmin'; }).length; }

/* Modifications de data/admins.json : renvoient { ok, fichier } ou { ok:false, raison }. `par` est l'empreinte de l'auteur. */
function verifierPeriode(role, debut, fin, aujourdhui) {
  debut = String(debut || '').trim(); fin = String(fin || '').trim();
  if ((debut || fin) && role !== 'admin') return { ok: false, raison: 'un Zagor n\'a pas de dates de début et de fin' };
  if (debut && !dateValide(debut)) return { ok: false, raison: 'date de début invalide' };
  if (fin && !dateValide(fin)) return { ok: false, raison: 'date de fin invalide' };
  if (debut && fin && fin < debut) return { ok: false, raison: 'la date de fin précède la date de début' };
  if (fin && aujourdhui && fin < aujourdhui) return { ok: false, raison: 'la date de fin est déjà passée' };
  return { ok: true, debut: debut, fin: fin };
}
function ajouterMembre(fichier, empreinte, nom, role, par, fin, aujourdhui, debut) {
  if (!/^sha256:[0-9a-f]{64}$/.test(empreinte)) return { ok: false, raison: 'empreinte invalide' };
  if (role !== 'admin' && role !== 'superadmin') return { ok: false, raison: 'niveau invalide' };
  var n = nettoyerNom(nom);
  if (!n) return { ok: false, raison: 'nom manquant' };
  var p = verifierPeriode(role, debut, fin, aujourdhui);
  if (!p.ok) return p;
  var f = copie(fichier); f.equipe = f.equipe || {};
  var ancien = f.equipe[empreinte];
  if (ancien && ancien.role === 'superadmin' && role !== 'superadmin') return { ok: false, raison: 'un SuperAdmin ne peut pas être rétrogradé' };
  var m = { nom: n, role: role };
  var depuis = (ancien && ancien.depuis) || aujourdhui;
  if (depuis) m.depuis = depuis;
  if (p.debut) m.debut = p.debut;
  if (p.fin) m.fin = p.fin;
  f.equipe[empreinte] = m;
  f.bloques = (f.bloques || []).filter(function (b) { return minuscules(b) !== empreinte; });
  return { ok: true, fichier: f };
}
/* Change ou efface (valeur vide) les dates de début et de fin d'un sorcier. */
function changerPeriode(fichier, empreinte, debut, fin, aujourdhui) {
  var f = copie(fichier); f.equipe = f.equipe || {};
  var m = f.equipe[empreinte];
  if (!m) return { ok: false, raison: 'membre introuvable' };
  if (m.role !== 'admin') return { ok: false, raison: 'seul un sorcier a une période' };
  var p = verifierPeriode('admin', debut, fin, aujourdhui);
  if (!p.ok) return p;
  if (p.debut) m.debut = p.debut; else delete m.debut;
  if (p.fin) m.fin = p.fin; else delete m.fin;
  return { ok: true, fichier: f };
}
function retirerMembre(fichier, empreinte, par) {
  var f = copie(fichier); f.equipe = f.equipe || {};
  if (!f.equipe[empreinte]) return { ok: false, raison: 'membre introuvable' };
  if (empreinte === par) return { ok: false, raison: 'vous ne pouvez pas vous retirer vous-même' };
  if (f.equipe[empreinte].role === 'superadmin') return { ok: false, raison: 'un SuperAdmin ne peut pas être retiré' };
  delete f.equipe[empreinte];
  return { ok: true, fichier: f };
}
function bloquerCompte(fichier, empreinte, par) {
  if (!/^sha256:[0-9a-f]{64}$/.test(empreinte)) return { ok: false, raison: 'empreinte invalide' };
  if (empreinte === par) return { ok: false, raison: 'vous ne pouvez pas vous bloquer vous-même' };
  var f = copie(fichier); f.equipe = f.equipe || {}; f.bloques = f.bloques || [];
  if (f.equipe[empreinte] && f.equipe[empreinte].role === 'superadmin') return { ok: false, raison: 'un SuperAdmin ne peut pas être bloqué' };
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

/* ---------- Nouveaux comptes et avis ----------
   Les deux envoient un courriel à l'éditeur. Jamais d'adresse : le prénom et quatre signes de l'empreinte du compte. */
var LIMITE_AVIS = 3;                   // par personne et par fenêtre de six heures
function texteLibre(brut, max) {          // texte multi-lignes : sans caractères de commande, retours à la ligne normalisés
  return String(brut == null ? '' : brut).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]+/g, ' ').replace(/\r\n?/g, '\n').trim().slice(0, max);
}
function validerAvis(note, texte) {
  var n = Number(note);
  if (note === null || note === undefined || note === '' || typeof note === 'boolean' || !(n >= 1 && n <= 5 && n % 1 === 0)) return { ok: false, raison: 'choisissez une note de 1 à 5 étoiles' };
  return { ok: true, note: n, texte: texteLibre(texte, 1500) };       // le commentaire est facultatif
}
function avisAutorise(compteur) { return (Number(compteur) || 0) < LIMITE_AVIS; }
function formaterNouveauCompte(nom, rang) {
  return { sujet: 'Nouveau compte sur La Cote du Héros', corps: 'Nouveau compte : ' + nom + ' (' + rang + (rang === 1 ? 'er' : 'e') + ' compte).' };
}
function ligneCompte(nom, date) { return nettoyerNom(nom) + '|' + String(date || '').slice(0, 10); }
/* valeurs : [{ rang, valeur }] lues dans les propriétés du script ; renvoie les comptes du plus récent au plus ancien et le nombre d'arrivées du jour */
function listerComptes(valeurs, aujourdhui, limite) {
  var liste = (valeurs || []).map(function (v) {
    var m = String(v.valeur || '').split('|');
    return { rang: Number(v.rang), nom: m[0] || '(sans prénom)', date: m[1] || '' };
  }).filter(function (c) { return c.rang > 0; }).sort(function (a, b) { return b.rang - a.rang; });
  return { liste: liste.slice(0, limite || 300), aujourdhui: liste.filter(function (c) { return c.date === aujourdhui; }).length, connus: liste.length };
}
function formaterAvis(nom, role, note, texte) {
  var etoiles = new Array(note + 1).join('★') + new Array(6 - note).join('☆');
  return { sujet: 'Avis ' + note + '/5 sur La Cote du Héros', corps: 'De : ' + nom + (role && role !== 'heros' ? ' (' + role + ')' : '') + '\nNote : ' + etoiles + ' (' + note + ' sur 5)' + (texte ? '\n\n' + texte : '\n\n(pas de commentaire)') };
}


/* ---------- Session de longue durée (le relais garde le jeton de renouvellement de Google) ----------
   Le navigateur ne reçoit qu'un identifiant de session, révocable. La session est prolongée à chaque renouvellement. */
var SESSION_JOURS = 30;
function creerSession(empreinte, renouvellement, maintenantSec) {
  return { e: empreinte, r: renouvellement, x: maintenantSec + SESSION_JOURS * 86400 };
}
function sessionExpiree(session, maintenantSec) { return !session || !session.x || maintenantSec >= session.x; }
function prolongerSession(session, maintenantSec) { session.x = maintenantSec + SESSION_JOURS * 86400; return session; }
