// Lecture des annonces et du Butin par le relais (relais/Code.gs) avec des services Apps Script simulés.   node pipeline/test_relais_annonces.js
// GitHub ne renvoie pas le contenu en base 64 d'un fichier de plus de 1 Mo : le relais lit donc le contenu brut.
const assert = require('assert'), fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const CLIENT = 'abc.apps.googleusercontent.com';
const sha = (a) => 'sha256:' + crypto.createHash('sha256').update(a).digest('hex');
const GROS = { date: '2026-11-02', annonces: { '9782070334018': { bon: [[8, 'Le château de Dracula é', 'https://www.vinted.fr/items/1-x', 'vinted', '2026-11-02', null]] } }, remplissage: 'x'.repeat(1_200_000) };
const PETIT = { date: '2026-11-02', annonces: { '9782070334018': { bon: [[8, 'Le château', 'https://www.vinted.fr/items/1-x', 'vinted', '2026-11-02', null]] } }, offre: {} };

function monde() {
  const props = {}, cache = {}, appels = [];
  const admins = { equipe: { [sha('chef@gmail.com')]: { nom: 'loliba (superadmin)', role: 'superadmin' }, [sha('marie@gmail.com')]: { nom: 'Marie', role: 'admin' } }, bloques: [] };
  const comptes = {
    'ya29.chef': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'chef@gmail.com', email_verified: 'true' },
    'ya29.marie': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'marie@gmail.com', email_verified: 'true', given_name: 'Marie' },
    'ya29.alice': { azp: CLIENT, aud: CLIENT, expires_in: '3000', email: 'alice@gmail.com', email_verified: 'true', given_name: 'Alice' },
  };
  const reponseHttp = (code, texte) => ({ getResponseCode: () => code, getContentText: () => texte });
  const ctx = {
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
    UrlFetchApp: { fetch: (url, options) => {
      const accept = ((options || {}).headers || {}).Accept || '';
      appels.push({ url, accept });
      if (url.indexOf('oauth2.googleapis.com/tokeninfo') >= 0) {
        const jeton = decodeURIComponent(url.split('=').slice(1).join('='));
        return comptes[jeton] ? reponseHttp(200, JSON.stringify(comptes[jeton])) : reponseHttp(400, '{}');
      }
      if (url.indexOf('/contents/data/admins.json') >= 0) return reponseHttp(200, JSON.stringify({ content: Buffer.from(JSON.stringify(admins)).toString('base64'), sha: 'abc' }));
      const fichier = url.indexOf('/contents/data/processed/annonces.json') >= 0 ? GROS : url.indexOf('/contents/data/processed/butin.json') >= 0 ? PETIT : null;
      if (!fichier) return reponseHttp(404, '{}');
      const texte = JSON.stringify(fichier);
      if (accept.indexOf('raw') >= 0) return reponseHttp(200, texte);
      return reponseHttp(200, JSON.stringify({ encoding: 'none', size: texte.length, content: texte.length > 1_000_000 ? '' : Buffer.from(texte).toString('base64') }));      // comme GitHub : vide au-delà de 1 Mo
    } },
  };
  props.CLIENT_ID = CLIENT; props.GITHUB_TOKEN = 'secret'; props.DEPOT = 'loliba92/LDVELH';
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(__dirname + '/../relais/logique.gs', 'utf8') + '\n' + fs.readFileSync(__dirname + '/../relais/Code.gs', 'utf8'), ctx);
  return { post: (corps) => JSON.parse(ctx.doPost({ postData: { contents: JSON.stringify(corps) } }).texte), appels };
}

let n = 0; const test = (nom, f) => { f(); n++; console.log('ok  ' + nom); };

test('le Zagor et un sorcier lisent un fichier d\'annonces de plus de 1 Mo, accents compris', () => {
  const m = monde();
  for (const jeton of ['ya29.chef', 'ya29.marie']) {
    const r = m.post({ action: 'annonces_lire', jeton });
    assert.strictEqual(r.ok, true, jeton);
    assert.strictEqual(r.annonces.annonces['9782070334018'].bon[0][1], 'Le château de Dracula é');
    assert.strictEqual(r.annonces.remplissage.length, 1_200_000);
  }
  assert.ok(m.appels.filter((a) => a.url.indexOf('annonces.json') >= 0).every((a) => a.accept.indexOf('raw') >= 0), 'contenu brut demandé');
});
test('le Butin se lit de la même façon', () => {
  const r = monde().post({ action: 'butin_lire', jeton: 'ya29.marie' });
  assert.strictEqual(r.ok, true);
  assert.deepStrictEqual(r.annonces.offre, {});
});
test('un compte sans niveau ne lit rien', () => {
  const m = monde();
  for (const action of ['annonces_lire', 'butin_lire']) assert.strictEqual(m.post({ action, jeton: 'ya29.alice' }).ok, false, action);
  assert.ok(!m.appels.some((a) => a.url.indexOf('/processed/') >= 0), 'GitHub n\'est pas interrogé');
});

console.log(n + ' tests');
