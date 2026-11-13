/* What a change in an event means for the rest of the group, and how a notification says it.
   Plain JavaScript with no Firebase in it, so it can be tested on its own (node test.js). */

// changes from the same person, of the same kind, within this time, grow one notification instead of sending new ones
const WINDOW_MS = 5 * 60 * 1000;
// how long to wait for more changes of a burst (adding five things in a row sends one notification)
const SETTLE_MS = 4000;

const shared = d => !!d && d.scope !== 'p';
const label = d => {
  const n = String((d && d.name) || '').trim(), x = String((d && d.detail) || '').trim();
  return (x ? (n ? n + ' · ' + x : x) : n).slice(0, 60);
};

// A shared-list item: added (no one brings it yet), taken (now someone brings it), or back on the list (no one again).
function itemChange(b, a) {
  if (!shared(a)) return null;
  const was = shared(b) ? (b.owner || null) : null, now = a.owner || null, name = label(a);
  if (!name) return null;
  if (now && now !== was) return {kind: 'claim', owner: now, name};
  if (!now && !shared(b)) return {kind: 'add', name};
  if (!now && was) return {kind: 'free', name};
  return null;
}

// A dish: new, taken by someone, or back to no one.
function dishChange(b, a) {
  if (!a) return null;
  const was = b ? (b.owner || null) : null, now = a.owner || null, name = String(a.name || '').trim().slice(0, 60);
  if (!name) return null;
  if (now && now !== was) return {kind: 'claim', owner: now, name};
  if (!now && !b) return {kind: 'add', name};
  if (!now && was) return {kind: 'free', name};
  return null;
}

const guestName = (guests, id) => { const g = guests.find(x => x.id === id); return g ? String(g.name || '').trim() : ''; };
// the participant this phone belongs to (the one it most recently picked as "me")
function actorName(guests, uid) {
  if (!uid) return '';
  let best = null;
  guests.forEach(g => { const t = g.dev && Number(g.dev[uid]); if (t && (!best || t > best.t)) best = {t, name: g.name}; });
  return best ? String(best.name || '').trim() : '';
}

// Which preference covers a kind of change
const prefOf = kind => kind === 'add' ? 'add' : 'claim';

// One burst's names: a fresh list after the window, otherwise the same list with the new name added
function merge(prev, name, now) {
  const fresh = !prev || !Array.isArray(prev.names) || now - (Number(prev.at) || 0) > WINDOW_MS;
  const names = fresh ? [name] : prev.names.filter(n => n !== name).concat(name).slice(-30);
  return {names, at: fresh ? now : prev.at};
}

function list(names) {
  const shown = names.slice(0, 4).join(', ');
  return names.length > 4 ? shown + ' ועוד ' + (names.length - 4) : shown;
}

// The words, kept free of he/she forms
function body(kind, names, who) {
  if (kind === 'claim') return (who ? 'על ' + who + ': ' : 'נלקח מהרשימה: ') + list(names);
  if (kind === 'free') return list(names) + (names.length > 1 ? ' חזרו' : ' חזר') + ' לרשימה. עוד מחפשים מי יביא';
  return 'חדש ברשימה: ' + list(names) + (who ? ' (' + who + ')' : '');
}

// FCM answers that mean an address is gone for good
const deadToken = code => /registration-token-not-registered|invalid-registration-token/.test(String(code || ''));

module.exports = {WINDOW_MS, SETTLE_MS, label, itemChange, dishChange, guestName, actorName, prefOf, merge, body, deadToken};
