/* Sending: who in the group hears about a change, and the message itself. Firebase is handed in (db, messaging),
   so test.js can run all of this against fakes. */
const L = require('./lib');

const sleep = ms => new Promise(r => setTimeout(r, ms));

// every phone address of these people (once each), for the kind of news each of them wants
async function addresses(db, uids, pref) {
  const snaps = await Promise.all(uids.map(u => db.doc('users/' + u + '/meta/push').get()));
  const out = new Map();  // token -> [{uid, h}]
  snaps.forEach((s, i) => {
    const d = s.exists ? s.data() : null;
    if (!d || (pref && d[pref] === false)) return;
    Object.entries(d.tokens || {}).forEach(([h, x]) => {
      if (!x || !x.t) return;
      if (!out.has(x.t)) out.set(x.t, []);
      out.get(x.t).push({uid: uids[i], h});
    });
  });
  return out;
}

async function send(db, messaging, FieldPath, FieldValue, targets, data) {
  const tokens = [...targets.keys()];
  if (!tokens.length) return {sent: 0, failed: 0};
  const res = await messaging.sendEachForMulticast({tokens, data, webpush: {headers: {Urgency: 'high', TTL: '86400'}}});
  const gone = [];
  res.responses.forEach((r, i) => { if (!r.success && L.deadToken(r.error && r.error.code)) gone.push(...targets.get(tokens[i])); });
  await Promise.all(gone.map(g => db.doc('users/' + g.uid + '/meta/push').update(new FieldPath('tokens', g.h), FieldValue.delete()).catch(() => {})));
  return {sent: res.successCount, failed: res.failureCount, removed: gone.length};
}

// A change to an item or a dish in an event. ctx: {db, messaging, FieldPath, FieldValue, wait}
async function onChange(ctx, {space, eid, col, before, after, actor}) {
  const ch = col === 'dishes' ? L.dishChange(before, after) : L.itemChange(before, after);
  if (!ch) return {skip: 'no news'};
  const {db} = ctx;
  const subs = (await db.collection('spaces/' + space + '/push').get()).docs.map(d => d.id).filter(u => u && u !== actor);
  if (!subs.length) return {skip: 'no one to tell'};
  const evRef = db.doc('spaces/' + space + '/events/' + eid);
  const [ev, gs] = await Promise.all([evRef.get(), db.collection('spaces/' + space + '/events/' + eid + '/guests').get()]);
  if (!ev.exists) return {skip: 'no event'};
  const guests = gs.docs.map(d => Object.assign({id: d.id}, d.data()));
  const who = ch.kind === 'claim' ? L.guestName(guests, ch.owner) : L.actorName(guests, actor);
  const key = [space, eid, ch.kind, ch.kind === 'claim' ? ch.owner : (actor || '-')].join('~');
  const ref = db.doc('_push/' + key), seq = Math.random().toString(36).slice(2);
  await db.runTransaction(async tx => {
    const s = await tx.get(ref), m = L.merge(s.exists ? s.data() : null, ch.name, Date.now());
    tx.set(ref, {names: m.names, at: m.at, seq, last: Date.now()});
  });
  // a burst: only the last change of it sends, with every name
  await (ctx.wait || sleep)(L.SETTLE_MS);
  const agg = (await ref.get()).data();
  if (!agg || agg.seq !== seq) return {skip: 'a later change sends'};
  const targets = await addresses(db, subs, L.prefOf(ch.kind));
  // the person who made the change hears nothing, on any of their phones (even under an older sign-in)
  if (actor) (await addresses(db, [actor], null)).forEach((_, t) => targets.delete(t));
  const data = {title: String(ev.data().name || 'MiMaMoo').slice(0, 60), body: L.body(ch.kind, agg.names, who), tag: key + '~' + agg.at, url: '#' + space + '/' + eid, space, eid};
  const r = await send(db, ctx.messaging, ctx.FieldPath, ctx.FieldValue, targets, data);
  return Object.assign({data}, r);
}

// "Send a test" from Settings: a notification to my own phones
async function onTest(ctx, uid) {
  const targets = await addresses(ctx.db, [uid], null);
  const data = {title: 'MiMaMoo', body: 'ההתראות עובדות. מעכשיו תדעו כשמשהו משתנה בקבוצה', tag: 'test', url: '#', space: '', eid: ''};
  return Object.assign({data}, await send(ctx.db, ctx.messaging, ctx.FieldPath, ctx.FieldValue, targets, data));
}

module.exports = {onChange, onTest, addresses};
