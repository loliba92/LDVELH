// Test de bout en bout des notes dans le relais (relais/Code.gs + relais/logique.gs) avec des services Apps Script simulés.
//   node pipeline/test_relais_notes.js
const assert = require('assert'), fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const CLIENT = 'abc.apps.googleusercontent.com';
const sha = (a) => 'sha256:' + crypto.createHash('sha256').update(a).digest('hex');

function monde() {
  const props = {}, cache = {}, appels = [];
  const admins = { equipe: { [sha('chef@gmail.com')]: { nom: 'loliba (superadmin)', role: 'superadmin' } }, bloques: [sha('bloque@gmail.com')] };
  const comptes = {                                 // jeton d'accès -> réponse de tokeninfo
    'ya29.alice': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'alice@gmail.com', email_verified: 'true', given_name: 'Alice' },
    'ya29.bob': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'bob@gmail.com', email_verified: 'true', given_name: 'Bob' },
    'ya29.chef': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'chef@gmail.com', email_verified: 'true' },
    'ya29.bloque': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'bloque@gmail.com', email_verified: 'true' },
    'ya29.vieux': { azp: CLIENT, aud: CLIENT, expires_in: '0', email: 'alice@gmail.com', email_verified: 'true' },
  };
  const reponseHttp = (code, texte) => ({ getResponseCode: () => code, getContentText: () => texte });
  const ctx = {
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); }, deleteProperty: (k) => { delete props[k]; }, getProperties: () => Object.assign({}, props) }) },
    CacheService: { getScriptCache: () => ({ get: (k) => (k in cache ? cache[k] : null), put: (k, v) => { cache[k] = String(v); }, remove: (k) => { delete cache[k]; } }) },
    LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
    ContentService: { createTextOutput: (t) => ({ texte: t, setMimeType() { return this; } }), MimeType: { JSON: 'json' } },
    Utilities: {
      DigestAlgorithm: { SHA_256: 'sha256' }, Charset: { UTF_8: 'utf8' },
      computeDigest: (algo, texte) => [...crypto.createHash('sha256').update(texte).digest()].map((b) => (b > 127 ? b - 256 : b)),
      base64Decode: (t) => [...Buffer.from(t, 'base64')], base64Encode: (t) => Buffer.from(t).toString('base64'),
      newBlob: (octets) => ({ getDataAsString: () => Buffer.from(octets).toString('utf8') }),
    },
    UrlFetchApp: { fetch: (url) => {
      appels.push(url);
      if (url.indexOf('oauth2.googleapis.com/tokeninfo') >= 0) {
        const jeton = decodeURIComponent(url.split('=').slice(1).join('='));
        return comptes[jeton] ? reponseHttp(200, JSON.stringify(comptes[jeton])) : reponseHttp(400, JSON.stringify({ error: 'invalid_token', error_description: 'Invalid Value' }));
      }
      if (url.indexOf('/contents/data/admins.json') >= 0) return reponseHttp(200, JSON.stringify({ content: Buffer.from(JSON.stringify(admins)).toString('base64'), sha: 'abc' }));
      return reponseHttp(404, '{}');
    } },
  };
  props.CLIENT_ID = CLIENT; props.GITHUB_TOKEN = 'secret'; props.DEPOT = 'loliba92/LDVELH';
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(__dirname + '/../relais/logique.gs', 'utf8') + '\n' + fs.readFileSync(__dirname + '/../relais/Code.gs', 'utf8'), ctx);
  const post = (corps) => JSON.parse(ctx.doPost({ postData: { contents: JSON.stringify(corps) } }).texte);
  const get = (parametres) => JSON.parse(ctx.doGet({ parameter: parametres }).texte);
  return { post, get, props, cache, appels };
}

let n = 0; const test = (nom, f) => { f(); n++; console.log('ok  ' + nom); };

test('un compte connecté note un livre ; la moyenne publique se met à jour', () => {
  const m = monde();
  assert.deepStrictEqual(m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 4 }), { ok: true, moyenne: 4, nombre: 1, note: 4 });
  assert.deepStrictEqual(m.post({ action: 'noter', jeton: 'ya29.bob', livre: 'livre-x', note: 5 }), { ok: true, moyenne: 4.5, nombre: 2, note: 5 });
  assert.deepStrictEqual(m.get({ notes: '1' }), { ok: true, notes: { 'livre-x': [4.5, 2] } });
});
test('la lecture publique ne demande aucune connexion', () => {
  const m = monde(); m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-y', note: 3 });
  const avant = m.appels.length;
  assert.deepStrictEqual(m.get({ notes: '1' }).notes, { 'livre-y': [3, 1] });
  assert.strictEqual(m.appels.length, avant, 'aucun appel à Google ni à GitHub pour une simple lecture');
  assert.strictEqual(m.get({}).service, 'relais La Cote du Héros');
});
test('le même compte modifie sa note au lieu d\'en ajouter une', () => {
  const m = monde();
  m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 2 });
  const r = m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 5 });
  assert.deepStrictEqual([r.moyenne, r.nombre], [5, 1]);
});
test('note 0 : la personne retire sa note ; sans plus aucun vote, le livre disparaît de la liste', () => {
  const m = monde();
  m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 3 });
  const r = m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 0 });
  assert.deepStrictEqual([r.moyenne, r.nombre], [0, 0]);
  assert.deepStrictEqual(m.get({ notes: '1' }).notes, {});
  assert.ok(!Object.keys(m.props).some((k) => k.indexOf('n:') === 0), 'propriété supprimée');
});
test('mes_notes : chacun retrouve ses propres notes, pas celles des autres', () => {
  const m = monde();
  m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 4 });
  m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-y', note: 2 });
  m.post({ action: 'noter', jeton: 'ya29.bob', livre: 'livre-x', note: 1 });
  assert.deepStrictEqual(m.post({ action: 'mes_notes', jeton: 'ya29.alice' }).notes, { 'livre-x': 4, 'livre-y': 2 });
  assert.deepStrictEqual(m.post({ action: 'mes_notes', jeton: 'ya29.bob' }).notes, { 'livre-x': 1 });
});
test('refus : sans connexion valide, connexion expirée, compte bloqué', () => {
  const m = monde();
  assert.strictEqual(m.post({ action: 'noter', jeton: 'ya29.inconnu', livre: 'livre-x', note: 4 }).ok, false);
  assert.strictEqual(m.post({ action: 'noter', jeton: '', livre: 'livre-x', note: 4 }).ok, false);
  assert.strictEqual(m.post({ action: 'noter', jeton: 'ya29.vieux', livre: 'livre-x', note: 4 }).erreur, 'connexion expirée');
  assert.strictEqual(m.post({ action: 'noter', jeton: 'ya29.bloque', livre: 'livre-x', note: 4 }).erreur, 'compte bloqué');
  assert.deepStrictEqual(m.get({ notes: '1' }).notes, {});
});
test('refus : livre ou note invalides, rien n\'est enregistré', () => {
  const m = monde();
  [[ 'livre-x', 9 ], [ 'livre-x', 'zéro' ], [ 'livre-x', null ], [ 'Livre X', 3 ], [ '../x', 3 ], [ '', 3 ]].forEach(([livre, note]) => {
    assert.strictEqual(m.post({ action: 'noter', jeton: 'ya29.alice', livre, note }).ok, false, livre + ' ' + note);
  });
  assert.deepStrictEqual(m.get({ notes: '1' }).notes, {});
});
test('rien d\'identifiable n\'est stocké : ni adresse ni nom', () => {
  const m = monde(); m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 4 });
  const stocke = JSON.stringify(m.props);
  assert.ok(!/alice/i.test(stocke) && !/@/.test(stocke.replace(/loliba92/g, '')), stocke);
  assert.ok(/"n:livre-x":"\{\\"[0-9a-f]{16}\\":4\}"/.test(stocke), stocke);
});
test('le plafond de votes par livre est respecté', () => {
  const m = monde(); const votes = {}; for (let i = 0; i < 400; i++) votes['v' + String(i).padStart(15, '0')] = 3;
  m.props['n:livre-x'] = JSON.stringify(votes);
  assert.strictEqual(m.post({ action: 'noter', jeton: 'ya29.alice', livre: 'livre-x', note: 5 }).ok, false);
});
test('les autres actions du relais fonctionnent toujours (moi, action inconnue)', () => {
  const m = monde();
  assert.deepStrictEqual([m.post({ action: 'moi', jeton: 'ya29.chef' }).role, m.post({ action: 'moi', jeton: 'ya29.alice' }).role], ['superadmin', 'heros']);
  assert.strictEqual(m.post({ action: 'inconnue', jeton: 'ya29.chef' }).erreur, 'droits insuffisants');
});
console.log(n + ' tests passés');
