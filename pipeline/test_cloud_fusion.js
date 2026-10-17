// Tests de la fusion de collection entre appareils.   node pipeline/test_cloud_fusion.js
const assert = require('assert');
const { etatLocal, fusionner, versLocal, meme } = require('../web/cloud.js');
const J = 86400000, T0 = Date.UTC(2026, 9, 17);
let n = 0; const test = (nom, f) => { f(); n++; console.log('ok  ' + nom); };
const vide = { m: {}, sup: {}, base: {} };

test('une première lecture date les livres et ne retire rien', () => {
  const { doc, meta } = etatLocal({ a: { etat: 'bon', qte: 1 } }, vide, T0);
  assert.deepStrictEqual(doc.items.a, { etat: 'bon', qte: 1, m: T0 });
  assert.strictEqual(meta.m.a, T0);
});
test('un livre inchangé garde sa date, un livre modifié est redaté', () => {
  const a = etatLocal({ a: { etat: 'bon', qte: 1 }, b: { etat: 'tbe', qte: 1 } }, vide, T0);
  const b = etatLocal({ a: { etat: 'bon', qte: 1 }, b: { etat: 'tbe', qte: 2 } }, a.meta, T0 + 1000);
  assert.strictEqual(b.doc.items.a.m, T0);
  assert.strictEqual(b.doc.items.b.m, T0 + 1000);
});
test('un livre retiré devient « supprimé » et un livre remis efface la suppression', () => {
  const a = etatLocal({ a: { etat: 'bon', qte: 1 } }, vide, T0);
  const b = etatLocal({}, a.meta, T0 + 5);
  assert.deepStrictEqual(b.doc.sup, { a: T0 + 5 }); assert.deepStrictEqual(b.doc.items, {});
  const c = etatLocal({ a: { etat: 'bon', qte: 1 } }, b.meta, T0 + 9);
  assert.deepStrictEqual(c.doc.sup, {}); assert.strictEqual(c.doc.items.a.m, T0 + 9);
});
test('première connexion : la collection locale rejoint un Drive vide', () => {
  const local = etatLocal({ a: { etat: 'bon', qte: 1 } }, vide, T0).doc;
  const f = fusionner(local, null, T0);
  assert.deepStrictEqual(Object.keys(f.items), ['a']);
});
test('nouvel appareil : le Drive remplit une collection locale vide', () => {
  const distant = etatLocal({ a: { etat: 'bon', qte: 1 }, b: { etat: 'tbe', qte: 3, prix: 12 } }, vide, T0).doc;
  const r = versLocal(fusionner(etatLocal({}, vide, T0 + 1).doc, distant, T0 + 2));
  assert.deepStrictEqual(r.coll, { a: { etat: 'bon', qte: 1 }, b: { etat: 'tbe', qte: 3, prix: 12 } });
});
test('deux appareils : la modification la plus récente l\'emporte, livre par livre', () => {
  const local = { v: 1, items: { a: { etat: 'bon', qte: 2, m: T0 + 20 }, b: { etat: 'tbe', qte: 1, m: T0 + 5 } }, sup: {} };
  const distant = { v: 1, items: { a: { etat: 'bon', qte: 1, m: T0 + 10 }, b: { etat: 'tbe', qte: 4, m: T0 + 30 }, c: { etat: 'bon', qte: 1, m: T0 } }, sup: {} };
  const f = fusionner(local, distant, T0 + 40);
  assert.strictEqual(f.items.a.qte, 2); assert.strictEqual(f.items.b.qte, 4); assert.ok(f.items.c);
});
test('un livre retiré sur un appareil ne revient pas depuis l\'autre', () => {
  const local = { v: 1, items: {}, sup: { a: T0 + 50 } };
  const distant = { v: 1, items: { a: { etat: 'bon', qte: 1, m: T0 + 10 } }, sup: {} };
  const f = fusionner(local, distant, T0 + 60);
  assert.deepStrictEqual(f.items, {}); assert.deepStrictEqual(f.sup, { a: T0 + 50 });
});
test('un livre remis après sa suppression revient', () => {
  const local = { v: 1, items: { a: { etat: 'bon', qte: 1, m: T0 + 80 } }, sup: {} };
  const distant = { v: 1, items: {}, sup: { a: T0 + 50 } };
  assert.ok(fusionner(local, distant, T0 + 90).items.a);
});
test('les suppressions de plus de 90 jours sont oubliées', () => {
  const distant = { v: 1, items: {}, sup: { vieux: T0 - 100 * J, recent: T0 - 5 * J } };
  const f = fusionner({ v: 1, items: {}, sup: {} }, distant, T0);
  assert.deepStrictEqual(Object.keys(f.sup), ['recent']);
});
test('la fusion est stable : refusionner le résultat ne change rien', () => {
  const local = { v: 1, items: { a: { etat: 'bon', qte: 2, m: T0 + 20 } }, sup: { z: T0 + 3 } };
  const distant = { v: 1, items: { a: { etat: 'bon', qte: 1, m: T0 + 10 }, b: { etat: 'tbe', qte: 1, m: T0 } }, sup: {} };
  const f = fusionner(local, distant, T0 + 40);
  assert.ok(meme(fusionner(f, f, T0 + 40), f)); assert.ok(meme(fusionner(f, distant, T0 + 40), f));
});
test('un document distant illisible est traité comme vide', () => {
  const f = fusionner(etatLocal({ a: { etat: 'bon', qte: 1 } }, vide, T0).doc, { n: 'x' }, T0);
  assert.deepStrictEqual(Object.keys(f.items), ['a']);
});
console.log(n + ' tests passés');
