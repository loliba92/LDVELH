// Tests des règles du relais (relais/logique.gs).   node pipeline/test_relais.js
const assert = require('assert'), fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const ctx = {}; vm.createContext(ctx); vm.runInContext(fs.readFileSync(__dirname + '/../relais/logique.gs', 'utf8'), ctx);
const L = (nom) => ctx[nom];
const J = (o) => JSON.parse(JSON.stringify(o));   // les objets venus du contexte vm n'ont pas le même prototype
const h = (a) => 'sha256:' + crypto.createHash('sha256').update(a).digest('hex');
const CLIENT = 'abc.apps.googleusercontent.com', NOW = 1_800_000_000;
const SUPER = h('chef@gmail.com'), ADM = h('admin@gmail.com');
const fichier = () => ({ equipe: { [SUPER]: { nom: 'loliba (superadmin)', role: 'superadmin' }, [ADM]: { nom: 'Marie', role: 'admin' } }, bloques: [] });
const infos = (sur = {}) => Object.assign({ aud: CLIENT, iss: 'https://accounts.google.com', exp: String(NOW + 600), email: 'inconnu@gmail.com', email_verified: 'true', given_name: 'Paul' }, sur);
const decider = (i, f = fichier()) => L('decider')(i, f, CLIENT, h, NOW);
let n = 0; const test = (nom, f) => { f(); n++; console.log('ok  ' + nom); };

test('un compte inconnu est un Héros, avec un suffixe qui le distingue', () => {
  const d = decider(infos()); assert.strictEqual(d.ok, true); assert.strictEqual(d.role, 'heros');
  assert.strictEqual(d.nom, 'Paul #' + h('inconnu@gmail.com').slice(7, 11));
});
test('la liste donne le niveau et le nom, sans tenir compte de la casse', () => {
  assert.deepStrictEqual([decider(infos({ email: 'Admin@Gmail.com' })).role, decider(infos({ email: 'Admin@Gmail.com' })).nom], ['admin', 'Marie']);
  assert.strictEqual(decider(infos({ email: 'chef@gmail.com' })).role, 'superadmin');
});
test('adresse en clair dans la liste : reconnue aussi', () => {
  const f = { equipe: { 'clair@gmail.com': { nom: 'Clair', role: 'admin' } } };
  assert.strictEqual(decider(infos({ email: 'clair@gmail.com' }), f).role, 'admin');
});
test('jeton d\'accès (celui du site) : mêmes règles', () => {
  const acces = (sur = {}) => Object.assign({ azp: CLIENT, aud: CLIENT, expires_in: '3000', scope: 'openid', email: 'admin@gmail.com', email_verified: 'true' }, sur);
  assert.strictEqual(decider(acces()).role, 'admin');
  assert.strictEqual(decider(acces({ azp: 'autre', aud: 'autre' })).ok, false);
  assert.strictEqual(decider(acces({ expires_in: '0' })).ok, false);
  assert.strictEqual(decider(acces({ expires_in: undefined })).ok, false);
  assert.strictEqual(decider(acces({ email_verified: 'false' })).ok, false);
  assert.strictEqual(decider(acces({ email: 'nouveau@gmail.com', given_name: 'Paul' })).role, 'heros');
});
test('refus : autre site, expiré, adresse non vérifiée, autre émetteur, erreur Google, bloqué', () => {
  const cas = [infos({ aud: 'autre' }), infos({ exp: String(NOW - 5000) }), infos({ email_verified: 'false' }), infos({ iss: 'https://evil.example' }), { error_description: 'Invalid Value' }, null];
  cas.forEach((c) => assert.strictEqual(decider(c).ok, false));
  const f = fichier(); f.bloques = [h('inconnu@gmail.com')];
  assert.strictEqual(decider(infos(), f).ok, false);
  assert.strictEqual(decider(infos({ email: 'admin@gmail.com' }), Object.assign(fichier(), { bloques: ['admin@gmail.com'] })).ok, false);
});
test('un compte bloqué qui figure dans l\'équipe est refusé', () => {
  const f = fichier(); f.bloques = [ADM]; assert.strictEqual(decider(infos({ email: 'admin@gmail.com' }), f).ok, false);
});
test('droits par niveau', () => {
  const p = L('peut');
  assert.ok(p('heros', 'moi')); assert.ok(!p('heros', 'envoyer')); assert.ok(!p('heros', 'equipe_lire'));
  assert.ok(p('admin', 'envoyer')); assert.ok(p('admin', 'journal')); assert.ok(!p('admin', 'equipe_ajouter')); assert.ok(!p('admin', 'releve'));
  assert.ok(p('superadmin', 'envoyer')); assert.ok(p('superadmin', 'equipe_ajouter')); assert.ok(p('superadmin', 'releve'));
  assert.ok(!p('superadmin', 'inconnue')); assert.ok(!p('inconnu', 'moi'));
});
test('envoi : seuls les lots et champs connus passent', () => {
  const v = L('validerEnvoi');
  assert.strictEqual(v('corriger-prix.yml', { corrections: '9782070 ; 25' }).ok, true);
  assert.strictEqual(v('ajout-isbn.yml', { liste: '978', releve: 'oui' }).ok, true);
  assert.strictEqual(v('pages.yml', { x: 'y' }).ok, false);
  assert.strictEqual(v('corriger-prix.yml', { corrections: 'a', auteur: 'Chef' }).ok, false);   // le nom est posé par le relais, jamais par le site
  assert.strictEqual(v('corriger-prix.yml', {}).ok, false);
  assert.strictEqual(v('corriger-prix.yml', { corrections: 12 }).ok, false);
  assert.strictEqual(v('corriger-prix.yml', { corrections: 'x'.repeat(20001) }).ok, false);
  assert.strictEqual(v('../../etc', { corrections: 'x' }).ok, false);
});
test('ajouter un membre : empreinte, niveau, nom ; un compte bloqué est débloqué', () => {
  const a = L('ajouterMembre'), nouveau = h('nouveau@gmail.com');
  const r = a(fichier(), nouveau, '  Paul | Dupont ', 'admin', SUPER);
  assert.strictEqual(r.ok, true); assert.deepStrictEqual(J(r.fichier.equipe[nouveau]), { nom: 'Paul Dupont', role: 'admin' });
  assert.strictEqual(a(fichier(), 'nouveau@gmail.com', 'P', 'admin', SUPER).ok, false);
  assert.strictEqual(a(fichier(), nouveau, 'P', 'heros', SUPER).ok, false);
  assert.strictEqual(a(fichier(), nouveau, '   ', 'admin', SUPER).ok, false);
  const f = fichier(); f.bloques = [nouveau];
  assert.deepStrictEqual(J(a(f, nouveau, 'P', 'admin', SUPER).fichier.bloques), []);
});
test('retirer : jamais soi-même, jamais le dernier SuperAdmin', () => {
  const r = L('retirerMembre');
  assert.strictEqual(r(fichier(), ADM, SUPER).ok, true);
  assert.strictEqual(r(fichier(), SUPER, SUPER).ok, false);
  assert.strictEqual(r(fichier(), h('absent'), SUPER).ok, false);
  const f = fichier(); f.equipe[ADM].role = 'superadmin';
  assert.strictEqual(r(f, SUPER, ADM).ok, true);                       // deux SuperAdmins : l'un peut retirer l'autre
  const seul = fichier(); assert.strictEqual(r(seul, SUPER, ADM).ok, false);
});
test('bloquer : retire de l\'équipe et ajoute à la liste ; pas soi-même ni le dernier SuperAdmin', () => {
  const b = L('bloquerCompte'), x = b(fichier(), ADM, SUPER);
  assert.strictEqual(x.ok, true); assert.ok(!x.fichier.equipe[ADM]); assert.deepStrictEqual(J(x.fichier.bloques), [ADM]);
  assert.strictEqual(b(fichier(), SUPER, SUPER).ok, false);
  assert.strictEqual(b(fichier(), SUPER, ADM).ok, false);
  assert.deepStrictEqual(J(b(x.fichier, ADM, SUPER).fichier.bloques), [ADM]);          // pas de doublon
});
test('les modifications ne touchent pas au fichier d\'origine', () => {
  const f = fichier(), avant = JSON.stringify(f); L('ajouterMembre')(f, h('z@gmail.com'), 'Z', 'admin', SUPER); L('retirerMembre')(f, ADM, SUPER); L('bloquerCompte')(f, ADM, SUPER);
  assert.strictEqual(JSON.stringify(f), avant);
});
console.log(n + ' tests passés');
