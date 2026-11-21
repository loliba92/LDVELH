// Essai de trois mois au niveau sorcier (relais/Code.gs + relais/logique.gs) avec des services Apps Script simulés.   node pipeline/test_relais_essai.js
const assert = require('assert'), fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const CLIENT = 'abc.apps.googleusercontent.com';
const sha = (a) => 'sha256:' + crypto.createHash('sha256').update(a).digest('hex');
const jeton = (email, prenom) => ({ azp: CLIENT, aud: CLIENT, expires_in: '3000', email, email_verified: 'true', given_name: prenom });

function monde(debut = '2026-11-21T09:00:00Z', existants = false) {
  const props = {}, cache = {};
  let maintenant = Date.parse(debut);
  const admins = { equipe: { [sha('chef@gmail.com')]: { nom: 'loliba (superadmin)', role: 'superadmin' },
    [sha('ancien@gmail.com')]: { nom: 'Ancien', role: 'admin', debut: '2026-01-01', fin: '2026-02-01' },
    [sha('futur@gmail.com')]: { nom: 'Futur', role: 'admin', debut: '2027-01-01', fin: '2027-02-01' } }, bloques: [sha('bloque@gmail.com')] };
  const comptes = { 'ya29.chef': jeton('chef@gmail.com'), 'ya29.alice': jeton('alice@gmail.com', 'Alice'), 'ya29.vieille': jeton('vieille@gmail.com', 'Vieille'),
    'ya29.ancien': jeton('ancien@gmail.com', 'Ancien'), 'ya29.futur': jeton('futur@gmail.com', 'Futur'), 'ya29.bloque': jeton('bloque@gmail.com', 'Bloque') };
  const reponseHttp = (code, texte) => ({ getResponseCode: () => code, getContentText: () => texte });
  const ctx = {
    Date: class extends Date { static now() { return maintenant; } },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = String(v); }, deleteProperty: (k) => { delete props[k]; }, getProperties: () => Object.assign({}, props) }) },
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
      if (url.indexOf('oauth2.googleapis.com/tokeninfo') >= 0) { const j = decodeURIComponent(url.split('=').slice(1).join('=')); return comptes[j] ? reponseHttp(200, JSON.stringify(comptes[j])) : reponseHttp(400, '{}'); }
      if (url.indexOf('/contents/data/admins.json') >= 0) return reponseHttp(200, JSON.stringify({ content: Buffer.from(JSON.stringify(admins)).toString('base64'), sha: 'abc' }));
      return reponseHttp(404, '{}');
    } },
  };
  props.CLIENT_ID = CLIENT; props.GITHUB_TOKEN = 'secret'; props.DEPOT = 'loliba92/LDVELH';
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(__dirname + '/../relais/logique.gs', 'utf8') + '\n' + fs.readFileSync(__dirname + '/../relais/Code.gs', 'utf8') + (existants ? '\nESSAI_COMPTES_EXISTANTS = true;' : ''), ctx);
  const post = (corps) => JSON.parse(ctx.doPost({ postData: { contents: JSON.stringify(corps) } }).texte);
  return { post, props, cache, avancer: (jours) => { maintenant += jours * 86400000; cache.admins = undefined; delete cache.admins; } };
}
let n = 0; const test = (nom, f) => { f(); n++; console.log('ok  ' + nom); };

test('trois mois calendaires, fin de mois comprise', () => {
  const m = monde(); const f = (j) => vm.runInNewContext(fs.readFileSync(__dirname + '/../relais/logique.gs', 'utf8') + `;ajouterMois('${j}', 3)`);
  assert.strictEqual(f('2026-11-21'), '2027-02-21');
  assert.strictEqual(f('2026-11-30'), '2027-02-28');
  assert.strictEqual(f('2026-11-29'), '2027-02-28');
  assert.strictEqual(f('2026-12-31'), '2027-03-31');
  assert.strictEqual(f('2027-11-30'), '2028-02-29');
  assert.ok(m);
});
test('un compte jamais vu est sorcier jusqu\'à la fin du troisième mois, avec son nom de Héros', () => {
  const m = monde(); const r = m.post({ action: 'moi', jeton: 'ya29.alice' });
  assert.deepStrictEqual([r.ok, r.role, r.fin], [true, 'admin', '2027-02-21']);
  assert.ok(/^Alice #[0-9a-f]{4}$/.test(r.nom), r.nom);
  assert.notStrictEqual(m.post({ action: 'butin_lire', jeton: 'ya29.alice' }).erreur, 'droits insuffisants');          // niveau sorcier : droits ouverts (GitHub est simulé)
});
test('l\'essai ne se renouvelle pas et ne change pas de date aux connexions suivantes', () => {
  const m = monde(); m.post({ action: 'moi', jeton: 'ya29.alice' }); m.avancer(30);
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.alice' }).fin, '2027-02-21');
  assert.strictEqual(Object.keys(m.props).filter((k) => k.indexOf('es:') === 0).length, 1);
});
test('dernier jour inclus, puis Héros : pas de second essai', () => {
  const m = monde(); m.post({ action: 'moi', jeton: 'ya29.alice' });
  m.avancer(92); assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.alice' }).role, 'admin');           // 21 février
  m.avancer(1);  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.alice' }).role, 'heros');          // 22 février
  m.avancer(400); assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.alice' }).role, 'heros');
  assert.strictEqual(m.post({ action: 'butin_lire', jeton: 'ya29.alice' }).erreur, 'droits insuffisants');
});
test('un compte déjà connu (ligne « u: ») n\'a pas d\'essai, sauf réglage contraire', () => {
  const m = monde(); m.props['u:' + sha('vieille@gmail.com').slice(7, 23)] = '1';
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.vieille' }).role, 'heros');
  const e = monde('2026-11-21T09:00:00Z', true); e.props['u:' + sha('vieille@gmail.com').slice(7, 23)] = '1';
  assert.strictEqual(e.post({ action: 'moi', jeton: 'ya29.vieille' }).role, 'admin');
});
test('ni l\'équipe, ni les comptes bloqués : pas d\'essai', () => {
  const m = monde();
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.chef' }).role, 'superadmin');
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.ancien' }).role, 'heros');           // ancien sorcier : sa période est finie
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.futur' }).role, 'heros');            // sorcier à venir : pas d'accès anticipé
  assert.strictEqual(m.post({ action: 'moi', jeton: 'ya29.bloque' }).ok, false);
  assert.strictEqual(Object.keys(m.props).filter((k) => k.indexOf('es:') === 0).length, 0);
});
test('rien d\'identifiable n\'est gardé : ni adresse, ni nom, seulement l\'empreinte courte et la date', () => {
  const m = monde(); m.post({ action: 'moi', jeton: 'ya29.alice' });
  const lignes = Object.entries(m.props).filter(([k]) => k.indexOf('es:') === 0);
  assert.deepStrictEqual(lignes.map(([, v]) => v), ['2027-02-21']);
  assert.ok(!JSON.stringify(m.props).includes('alice'), 'ni adresse ni prénom');
});

console.log(n + ' tests');
