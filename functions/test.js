/* node functions/test.js — the notification logic against a fake database and a fake FCM. */
const assert = require('assert');
const L = require('./lib');
const N = require('./notify');

// ---- what counts as news
const it = (o) => Object.assign({name: 'פחמים', scope: 'g', owner: null}, o);
assert.deepStrictEqual(L.itemChange(null, it()), {kind: 'add', name: 'פחמים'});
assert.deepStrictEqual(L.itemChange(null, it({owner: 'g1'})), {kind: 'claim', owner: 'g1', name: 'פחמים'});
assert.deepStrictEqual(L.itemChange(it(), it({owner: 'g1'})), {kind: 'claim', owner: 'g1', name: 'פחמים'});
assert.deepStrictEqual(L.itemChange(it({owner: 'g1'}), it()), {kind: 'free', name: 'פחמים'});
assert.deepStrictEqual(L.itemChange(it({owner: 'g1'}), it({owner: 'g2'})), {kind: 'claim', owner: 'g2', name: 'פחמים'});
assert.strictEqual(L.itemChange(it(), it({packed: true})), null);
assert.strictEqual(L.itemChange(it({owner: 'g1'}), it({owner: 'g1', qty: 3})), null);
assert.strictEqual(L.itemChange(it(), null), null, 'deleted');
assert.strictEqual(L.itemChange(null, it({scope: 'p'})), null, 'personal');
assert.deepStrictEqual(L.itemChange(it({scope: 'p', owner: 'g1'}), it()), {kind: 'add', name: 'פחמים'}, 'personal to shared');
assert.strictEqual(L.label({name: 'שתייה קלה', detail: 'קולה'}), 'שתייה קלה · קולה');
assert.deepStrictEqual(L.dishChange(null, {name: 'סלט'}), {kind: 'add', name: 'סלט'});
assert.deepStrictEqual(L.dishChange({name: 'סלט'}, {name: 'סלט', owner: 'g2'}), {kind: 'claim', owner: 'g2', name: 'סלט'});
assert.strictEqual(L.dishChange({name: 'סלט'}, {name: 'סלט', items: [1]}), null);

// ---- words
assert.strictEqual(L.body('add', ['פחמים'], 'נירו'), 'חדש ברשימה: פחמים (נירו)');
assert.strictEqual(L.body('add', ['פחמים', 'צלחות'], ''), 'חדש ברשימה: פחמים, צלחות');
assert.strictEqual(L.body('claim', ['פחמים', 'צלחות'], 'דנה'), 'על דנה: פחמים, צלחות');
assert.strictEqual(L.body('free', ['פחמים'], 'דנה'), 'פחמים חזר לרשימה. עוד מחפשים מי יביא');
assert.strictEqual(L.body('add', ['א', 'ב', 'ג', 'ד', 'ה', 'ו'], ''), 'חדש ברשימה: א, ב, ג, ד ועוד 2');
assert.strictEqual(L.actorName([{id: 'g1', name: 'נירו', dev: {u1: 5}}, {id: 'g2', name: 'דנה', dev: {u1: 9}}], 'u1'), 'דנה', 'latest pick wins');
const m1 = L.merge(null, 'א', 1000), m2 = L.merge(m1, 'ב', 2000), m3 = L.merge(m2, 'ג', 2000 + L.WINDOW_MS + 1);
assert.deepStrictEqual([m1.names, m2.names, m2.at, m3.names], [['א'], ['א', 'ב'], 1000, ['ג']]);

// ---- a fake Firestore (just enough) and FCM
function fakeDb(init) {
  const S = new Map(Object.entries(init || {}));
  const snap = (p) => ({exists: S.has(p), id: p.split('/').pop(), data: () => S.has(p) ? JSON.parse(JSON.stringify(S.get(p))) : undefined});
  const ref = p => ({
    get: async () => snap(p),
    set: async d => { S.set(p, d); },
    update: async (fp, v) => { const d = S.get(p); if (!d) throw new Error('missing'); let o = d; const segs = fp.segs; segs.slice(0, -1).forEach(s => { o = o[s] = o[s] || {}; }); if (v === DEL) delete o[segs[segs.length - 1]]; else o[segs[segs.length - 1]] = v; }
  });
  const DEL = {del: 1};
  const db = {
    S, DEL,
    doc: ref,
    collection: p => ({get: async () => ({docs: [...S.keys()].filter(k => k.startsWith(p + '/') && k.split('/').length === p.split('/').length + 1).map(snap)})}),
    runTransaction: async fn => fn({get: r => r.get(), set: (r, d) => r.set(d)})
  };
  return db;
}
class FP { constructor(...s) { this.segs = s; } }
const fakeFcm = (dead) => { const sent = []; return {sent, sendEachForMulticast: async m => { sent.push(m); const responses = m.tokens.map(t => dead.includes(t) ? {success: false, error: {code: 'messaging/registration-token-not-registered'}} : {success: true}); return {responses, successCount: responses.filter(r => r.success).length, failureCount: responses.filter(r => !r.success).length}; }}; };

(async () => {
  const base = {
    'spaces/S1/events/E1': {name: 'קמפינג בגולן'},
    'spaces/S1/events/E1/guests/g1': {name: 'נירו', dev: {uA: 1}},
    'spaces/S1/events/E1/guests/g2': {name: 'דנה', dev: {uB: 1}},
    'spaces/S1/push/uA': {at: 1}, 'spaces/S1/push/uB': {at: 1}, 'spaces/S1/push/uC': {at: 1},
    'users/uA/meta/push': {tokens: {h1: {t: 'TA'}}},
    'users/uB/meta/push': {tokens: {h2: {t: 'TB'}, h3: {t: 'TB-old'}}},
    'users/uC/meta/push': {tokens: {h4: {t: 'TC'}}, add: false},
    'users/uOld/meta/push': {tokens: {h5: {t: 'TA'}}}  // Niro's phone under its earlier, anonymous sign-in
  };
  const db = fakeDb(base), fcm = fakeFcm(['TB-old']);
  const ctx = {db, messaging: fcm, FieldPath: FP, FieldValue: {delete: () => db.DEL}, wait: async () => {}};
  db.S.set('spaces/S1/push/uOld', {at: 1});
  // Niro adds charcoal: Dana hears (both her phones, one of them gone), uC wants no "added" news, Niro's own phone (also under uOld) is skipped
  let r = await N.onChange(ctx, {space: 'S1', eid: 'E1', col: 'items', before: null, after: it(), actor: 'uA'});
  assert.deepStrictEqual(fcm.sent[0].tokens.sort(), ['TB', 'TB-old']);
  assert.strictEqual(r.data.body, 'חדש ברשימה: פחמים (נירו)');
  assert.strictEqual(r.data.title, 'קמפינג בגולן');
  assert.strictEqual(r.data.url, '#S1/E1');
  assert.deepStrictEqual(Object.keys(db.S.get('users/uB/meta/push').tokens), ['h2'], 'a dead address is removed');
  // a second item in the same burst: one notification with both names, same tag
  r = await N.onChange(ctx, {space: 'S1', eid: 'E1', col: 'items', before: null, after: it({name: 'צלחות'}), actor: 'uA'});
  assert.strictEqual(r.data.body, 'חדש ברשימה: פחמים, צלחות (נירו)');
  assert.strictEqual(r.data.tag, fcm.sent[0].data.tag);
  // Dana takes the charcoal: uC hears this kind, Dana does not
  r = await N.onChange(ctx, {space: 'S1', eid: 'E1', col: 'items', before: it(), after: it({owner: 'g2'}), actor: 'uB'});
  assert.deepStrictEqual(fcm.sent[2].tokens.sort(), ['TA', 'TC']);
  assert.strictEqual(r.data.body, 'על דנה: פחמים');
  // a burst where a later change is still coming: the earlier one stays quiet
  let release;
  const slow = Object.assign({}, ctx, {wait: () => new Promise(res => { release = res; })});
  const p1 = N.onChange(slow, {space: 'S1', eid: 'E1', col: 'dishes', before: {name: 'סלט'}, after: {name: 'סלט', owner: 'g1'}, actor: 'uA'});
  await new Promise(res => setTimeout(res, 10));
  const first = release;
  const p2 = N.onChange(slow, {space: 'S1', eid: 'E1', col: 'dishes', before: {name: 'שקשוקה'}, after: {name: 'שקשוקה', owner: 'g1'}, actor: 'uA'});
  await new Promise(res => setTimeout(res, 10));
  first(); release();
  const [a1, a2] = await Promise.all([p1, p2]);
  assert.strictEqual(a1.skip, 'a later change sends');
  assert.strictEqual(a2.data.body, 'על נירו: סלט, שקשוקה');
  // nothing to say: packing something
  r = await N.onChange(ctx, {space: 'S1', eid: 'E1', col: 'items', before: it({owner: 'g1'}), after: it({owner: 'g1', packed: true}), actor: 'uA'});
  assert.strictEqual(r.skip, 'no news');
  // a group where no one else switched notifications on
  r = await N.onChange(ctx, {space: 'S2', eid: 'E9', col: 'items', before: null, after: it(), actor: 'uA'});
  assert.strictEqual(r.skip, 'no one to tell');
  // the test button
  r = await N.onTest(ctx, 'uB');
  assert.deepStrictEqual(fcm.sent[fcm.sent.length - 1].tokens, ['TB']);
  // every value FCM gets is text
  fcm.sent.forEach(m => Object.values(m.data).forEach(v => assert.strictEqual(typeof v, 'string')));
  console.log('functions: all checks passed (' + fcm.sent.length + ' messages)');
})().catch(e => { console.error(e); process.exit(1); });
