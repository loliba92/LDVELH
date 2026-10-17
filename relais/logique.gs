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
  releve: 'superadmin'
};
var LOTS = { 'corriger-prix.yml': ['corrections'], 'ajout-isbn.yml': ['liste', 'releve'] };   // lots que le relais accepte de lancer, avec leurs champs
var LIMITE_CHAMP = 20000;
var EMETTEURS = ['accounts.google.com', 'https://accounts.google.com'];

function nettoyerNom(brut) {
  return String(brut == null ? '' : brut).replace(/[\u0000-\u001f|;\s]+/g, ' ').trim().slice(0, 30);
}
function minuscules(s) { return String(s == null ? '' : s).trim().toLowerCase(); }

/* Réponse de https://oauth2.googleapis.com/tokeninfo : Google a déjà vérifié la signature ; on contrôle le reste. */
function decider(infos, fichier, clientId, empreinteDe, maintenantSec) {
  if (!infos || infos.error_description || infos.error) return { ok: false, raison: 'jeton refusé par Google' };
  if (infos.aud !== clientId) return { ok: false, raison: 'jeton émis pour un autre site' };
  if (EMETTEURS.indexOf(infos.iss) < 0) return { ok: false, raison: 'émetteur inattendu' };
  if (Number(infos.exp) < maintenantSec) return { ok: false, raison: 'connexion expirée' };
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
