#!/usr/bin/env python3
"""Build the standalone MiMaMoo web app (PWA) from the Claude artifact source.

The artifact keeps its data in Claude's runtime. The standalone build swaps that for
Firebase (Firestore + anonymous sign-in) when config.js holds a Firebase config, and for
on-device storage when it does not. Everything else — UI, logic, styles — is the artifact
source, untouched, so the two never drift apart: rebuild after every artifact change.

  python3 build.py <artifact.html> <out_dir>
"""
import json, pathlib, shutil, sys

SRC = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
HERE = pathlib.Path(__file__).parent
FIREBASE_SDK = '10.14.1'
VERSION = sys.argv[3] if len(sys.argv) > 3 else '1'

s = SRC.read_text(encoding='utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f'expected {count} match(es), found {n}: {old[:80]!r}'
    s = s.replace(old, new)


# ---------- document head: a real page with install metadata ----------
rep('<title>MiMaMoo</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n', '''<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<title>MiMaMoo</title>
<meta name="description" content="מי מביא מה: רשימות משותפות לטיולים ולאירועים">
<meta name="theme-color" content="#FAF9FC">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="MiMaMoo">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
<link rel="icon" type="image/svg+xml" href="icons/icon.svg">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<script src="config.js"></script>
<script>
/* Groups ("spaces"): each event lives in a space of its own, and its link (…/#<space>/<event>) is the invitation.
   This device remembers every space it has been invited to (they all show together), plus a home space of its own
   for templates, settings and the events made before spaces were per event. */
(function () {
  var h = (location.hash || '').replace(/^#/, '').split('/'), sid = null, deep = '';
  if (/^[A-Za-z0-9]{16,40}$/.test(h[0] || '')) { sid = h[0]; deep = h[1] || ''; }
  var standalone = false; try { standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true; } catch (e) {}
  var get = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var put = function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} };
  var newId = function () {
    var a = new Uint8Array(15), abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789', s = '';
    crypto.getRandomValues(a); for (var i = 0; i < a.length; i++) s += abc[a[i] % abc.length];
    return s + 'mm' + Date.now().toString(36).slice(-4);
  };
  // arriving from the old address: take over its groups and settings, then carry on as if opened normally
  if (/^import=/.test(location.hash.slice(1))) {
    try {
      var raw = location.hash.slice(8).replace(/-/g, '+').replace(/_/g, '/'), pay = JSON.parse(decodeURIComponent(escape(atob(raw))));
      Object.keys(pay.ls || {}).forEach(function (k) { if (/^(wbw:|mm:(home|spaces)$)/.test(k)) put(k, pay.ls[k]); });
      window.MM_IMPORT = {move: pay.move || ''};
      h = String(pay.at || '').split('/'); sid = null; deep = '';
      if (/^[A-Za-z0-9]{16,40}$/.test(h[0] || '')) { sid = h[0]; deep = h[1] || ''; }
    } catch (e) {}
  }
  var list = []; try { list = JSON.parse(get('mm:spaces') || '[]'); if (!Array.isArray(list)) list = []; } catch (e) { list = []; }
  var home = get('mm:home') || get('mm:space');  // a device from before keeps its one group as home
  // opened from the home screen with nothing stored: on iPhone that storage is separate from Safari's, so offer to rejoin
  window.MM_FRESH = !home && !list.length && !sid && standalone;
  if (!home) home = newId();
  put('mm:home', home); put('mm:space', home);
  [home, sid].forEach(function (x) { if (x && list.indexOf(x) < 0) list.push(x); });
  put('mm:spaces', JSON.stringify(list.slice(-80)));
  window.MM_SPACE = home; window.MM_SPACES = list; window.MM_DEEP = deep; window.MM_DEEP_SPACE = sid || '';
  window.MM_NEWID = newId;
  // the invitation stays in the address, so a page added to the home screen keeps it
  var keepHash = sid ? sid + (deep ? '/' + deep : '') : home;
  try { history.replaceState(null, '', location.pathname + location.search + '#' + keepHash); } catch (e) {}
  // iPhone saves the manifest's start address: give it one that carries the invitation
  try {
    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (ios && !standalone) {
      var base = location.origin + location.pathname, ml = document.querySelector('link[rel="manifest"]');
      var man = {name: 'MiMaMoo', short_name: 'MiMaMoo', lang: 'he', dir: 'rtl', id: base, start_url: base + '#' + keepHash, scope: base, display: 'standalone', background_color: '#FAF9FC', theme_color: '#FAF9FC',
        icons: [{src: base + 'icons/icon-192.png', sizes: '192x192', type: 'image/png'}, {src: base + 'icons/icon-512.png', sizes: '512x512', type: 'image/png'}]};
      if (ml) ml.href = 'data:application/manifest+json,' + encodeURIComponent(JSON.stringify(man));
    }
  } catch (e) {}
})();
</script>
''')
rep('</style>\n\n<div id="app"></div>', '</style>\n</head>\n<body>\n<div id="app"></div>')
assert s.rstrip().endswith('</script>')
s = s.rstrip() + '''
<script>
if ('serviceWorker' in navigator) window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
</script>
</body>
</html>
'''

# ---------- deep link comes from the space link ----------
rep("  deep: (location.hash || '').replace(/^#/, '')", "  deep: window.MM_DEEP || ''")

# ---------- on-device storage for local mode (no Firebase yet) ----------
rep("  _emit(col) { const set = this.ls.get(col); if (!set) return;",
    "  _emit(col) { saveLocal(); const set = this.ls.get(col); if (!set) return;")
rep("/* ---------- Store: shared db when available, in-memory otherwise ---------- */", """/* ---------- Store: Firebase when configured, this device's storage otherwise ---------- */
const LOCAL_KEY = 'mm:local:v1';
let saveT = 0;
function saveLocal() {
  if (Store.db) return;
  clearTimeout(saveT);
  saveT = setTimeout(() => {
    try { const o = {}; Store.local.forEach((m, col) => { o[col] = Object.fromEntries(m); }); localStorage.setItem(LOCAL_KEY, JSON.stringify(o)); } catch (e) {}
  }, 150);
}
function loadLocal() {
  try { const o = JSON.parse(localStorage.getItem(LOCAL_KEY) || '{}'); for (const col in o) Store.local.set(col, new Map(Object.entries(o[col]))); } catch (e) {}
}

/* Firebase adapter with the same surface as Claude's db: collection().onSnapshot/get, doc().set/update/delete/get/acquire.
   App paths stay as they are. "events" is every event in every space this device knows, as one list; an event's own data
   lives in its space; a new event gets a new space; templates and settings live in the home space; personal lists
   under the signed-in user. */
async function connectFire(cfg, home, spaceList) {
  const base = 'https://www.gstatic.com/firebasejs/""" + FIREBASE_SDK + """/';
  const [A, AU, F] = await Promise.all([import(base + 'firebase-app.js'), import(base + 'firebase-auth.js'), import(base + 'firebase-firestore.js')]);
  // on Firebase's own address sign-in runs on the same address, so it works inside an iPhone home-screen app too
  const onFbHost = /\\.(firebaseapp\\.com|web\\.app)$/.test(location.hostname);
  if (onFbHost) cfg = Object.assign({}, cfg, {authDomain: location.hostname});
  const standalone = (() => { try { return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true; } catch (e) { return false; } })();
  const app = A.initializeApp(cfg);
  const auth = AU.getAuth(app);
  let fs;
  try { fs = F.initializeFirestore(app, {ignoreUndefinedProperties: true, localCache: F.persistentLocalCache({tabManager: F.persistentMultipleTabManager()})}); }
  catch (e) { fs = F.initializeFirestore(app, {ignoreUndefinedProperties: true}); }
  let redirectErr = null;
  try { await AU.getRedirectResult(auth); } catch (e) { redirectErr = e; }
  try { await auth.authStateReady(); } catch (e) {}
  if (!auth.currentUser) await AU.signInAnonymously(auth);
  const user = auth.currentUser;
  // the lists this (anonymous) device keeps, to carry them into an account or to a new address
  const listsRoot = (uid, h) => 'users/' + uid + '/s/' + h + '/lists';
  async function ownDocs(uid, h) {
    const out = [], root = listsRoot(uid, h);
    const top = await F.getDocs(F.collection(fs, root)).catch(() => null); if (!top) return out;
    for (const d of top.docs) {
      out.push({r: d.id, d: d.data()});
      const its = await F.getDocs(F.collection(fs, root + '/' + d.id + '/items')).catch(() => null);
      if (its) its.docs.forEach(x => out.push({r: d.id + '/items/' + x.id, d: x.data()}));
    }
    return out;
  }
  const putDocs = (uid, h, docs) => Promise.all(docs.map(x => F.setDoc(F.doc(fs, listsRoot(uid, h) + '/' + x.r), x.d).catch(() => {})));
  // the Google account already has a home elsewhere: bring this device's lists into it, then switch to it
  async function adopt(cred) {
    const anon = auth.currentUser, carry = anon && anon.isAnonymous ? await ownDocs(anon.uid, home) : [];
    const r = await AU.signInWithCredential(auth, cred);
    const ps = await F.getDoc(F.doc(fs, 'users/' + r.user.uid + '/meta/profile')).catch(() => null);
    await putDocs(r.user.uid, (ps && ps.exists() && ps.data().home) || home, carry);
  }
  if (redirectErr && redirectErr.code === 'auth/credential-already-in-use') {
    const cred = AU.GoogleAuthProvider.credentialFromError(redirectErr);
    if (cred) { await adopt(cred); location.reload(); await new Promise(() => {}); }
  }
  // signed in: the account keeps the home and the list of groups, for every device
  const profRef = user.isAnonymous ? null : F.doc(fs, 'users/' + user.uid + '/meta/profile');
  if (profRef) {
    const ps = await F.getDoc(profRef).catch(() => null), prof = ps && ps.exists() ? ps.data() : {};
    if (prof.home) home = prof.home;
    spaceList = [...new Set([...(Array.isArray(prof.spaces) ? prof.spaces : []), ...(spaceList || []), home])];
    try { localStorage.setItem('mm:home', home); localStorage.setItem('mm:space', home); localStorage.setItem('mm:spaces', JSON.stringify(spaceList.slice(-80))); } catch (e) {}
    F.setDoc(profRef, {home, spaces: spaceList.slice(-200), updated: Date.now()}, {merge: true}).catch(() => {});
  }
  window.MM_SPACE = home;
  const provider = new AU.GoogleAuthProvider();
  try { provider.setCustomParameters({prompt: 'select_account'}); } catch (e) {}
  window.MM_AUTH = {
    user: () => { const u = auth.currentUser; return u && !u.isAnonymous ? {name: u.displayName || '', email: u.email || ''} : null; },
    signIn: async () => {
      const u = auth.currentUser;
      try {
        if (standalone && onFbHost) { if (u && u.isAnonymous) await AU.linkWithRedirect(u, provider); else await AU.signInWithRedirect(auth, provider); return; }
        if (u && u.isAnonymous) await AU.linkWithPopup(u, provider); else await AU.signInWithPopup(auth, provider);
      } catch (e) {
        if (e && e.code === 'auth/credential-already-in-use') { const cred = AU.GoogleAuthProvider.credentialFromError(e); if (!cred) throw e; await adopt(cred); }
        else if (e && /popup-closed-by-user|cancelled-popup-request/.test(e.code || '')) return;
        else throw e;
      }
      location.reload();
    },
    signOut: async () => {
      await AU.signOut(auth);
      try { ['mm:home', 'mm:space', 'mm:spaces'].forEach(k => localStorage.removeItem(k)); } catch (e) {}
      location.replace(location.pathname); location.reload();
    }
  };
  const mine = 'data/users/';
  const spaces = new Set((spaceList || []).filter(Boolean)); spaces.add(home);
  const evSpace = new Map(), watchers = new Set();
  const remember = sid => {
    if (spaces.has(sid)) return;
    spaces.add(sid);
    try { localStorage.setItem('mm:spaces', JSON.stringify([...spaces].slice(-80))); } catch (e) {}
    if (profRef) F.setDoc(profRef, {spaces: F.arrayUnion(sid)}, {merge: true}).catch(() => {});
    watchers.forEach(w => w.add(sid));
  };
  const spaceOf = eid => evSpace.get(eid) || (eid && eid === window.MM_DEEP && window.MM_DEEP_SPACE) || home;
  window.MM_SPACEOF = spaceOf;
  // a brand-new event (its first write) gets a space of its own
  const map = (p, creating) => {
    if (p.indexOf(mine) === 0) { const r = p.slice(mine.length), i = r.indexOf('/'); return 'users/' + (i < 0 ? r : r.slice(0, i)) + '/s/' + home + '/lists' + (i < 0 ? '' : r.slice(i)); }
    const seg = p.split('/');
    if (seg[0] === 'events' && seg[1]) {
      if (creating && seg.length === 2 && !evSpace.has(seg[1])) { const sid = window.MM_NEWID(); evSpace.set(seg[1], sid); remember(sid); }
      return 'spaces/' + spaceOf(seg[1]) + '/' + p;
    }
    return 'spaces/' + home + '/' + p;
  };
  // Firestore keeps no arrays inside arrays: wrap inner ones as {_a: [...]}
  const enc = v => Array.isArray(v) ? v.map(x => Array.isArray(x) ? {_a: enc(x)} : enc(x))
    : (v && typeof v === 'object') ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, enc(x)])) : v;
  const dec = v => Array.isArray(v) ? v.map(dec)
    : (v && typeof v === 'object') ? (Object.keys(v).length === 1 && Array.isArray(v._a) ? dec(v._a) : Object.fromEntries(Object.entries(v).map(([k, x]) => [k, dec(x)]))) : v;
  const CODES = {'not-found': 'invalid_argument', 'invalid-argument': 'invalid_argument', 'permission-denied': 'not_granted', 'unauthenticated': 'not_granted', 'unavailable': 'unavailable', 'resource-exhausted': 'resource_exhausted', 'deadline-exceeded': 'unavailable'};
  const wrap = e => { console.warn(e); throw {code: CODES[e && e.code] || (e && e.code) || 'unknown'}; };
  const snap = s => ({docs: s.docs.map(d => ({id: d.id, data: () => dec(d.data())}))});
  const flat = (o, pre, out) => {
    for (const k in o) {
      const v = o[k], p = pre.concat(k);
      if (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length) flat(v, p, out); else out.push([p, v]);
    }
    return out;
  };
  // every space's events, merged; the first answer waits (briefly) for all spaces, so nothing flickers in and out
  const allEvents = {
    onSnapshot: (cb, err) => {
      const per = new Map(), offs = new Map(), waiting = new Set();
      let ready = false;
      const emit = () => { if (!ready) return; const docs = []; per.forEach((list, sid) => list.forEach(d => { evSpace.set(d.id, sid); docs.push(d); })); cb({docs}); };
      const w = {add: sid => {
        if (offs.has(sid)) return;
        waiting.add(sid);
        offs.set(sid, F.onSnapshot(F.collection(fs, 'spaces/' + sid + '/events'),
          s => { per.set(sid, snap(s).docs); waiting.delete(sid); if (!waiting.size) ready = true; emit(); },
          e => { console.warn(e); per.set(sid, []); waiting.delete(sid); if (!waiting.size) ready = true; emit(); }));
      }};
      watchers.add(w); spaces.forEach(sid => w.add(sid));
      setTimeout(() => { if (!ready) { ready = true; emit(); } }, 2500);
      return () => { watchers.delete(w); offs.forEach(off => { try { off(); } catch (e) {} }); };
    },
    get: async () => {
      const lists = await Promise.all([...spaces].map(sid => F.getDocs(F.collection(fs, 'spaces/' + sid + '/events')).then(s => snap(s).docs.map(d => { evSpace.set(d.id, sid); return d; }), () => [])));
      return {docs: lists.flat()};
    }
  };
  const db = {
    collection: col => col === 'events' ? allEvents : ({
      onSnapshot: (cb, err) => F.onSnapshot(F.collection(fs, map(col)), s => cb(snap(s)), e => { console.warn(e); if (err) err({code: CODES[e && e.code] || 'unknown'}); }),
      get: () => F.getDocs(F.collection(fs, map(col))).then(snap, wrap)
    }),
    doc: path => {
      const ref = F.doc(fs, map(path));
      return {
        set: d => F.setDoc(F.doc(fs, map(path, true)), enc(d)).catch(wrap),
        update: d => {
          const args = []; flat(enc(d), [], []).forEach(([p, v]) => { args.push(new F.FieldPath(...p), v); });
          return args.length ? F.updateDoc(ref, ...args).catch(wrap) : Promise.resolve();
        },
        delete: () => F.deleteDoc(ref).catch(wrap),
        get: () => F.getDoc(ref).then(s => ({exists: s.exists(), id: s.id, data: () => dec(s.data())}), wrap),
        // a short lease kept in its own document, so the item itself is never touched
        acquire: ({holder, ttlMs}) => {
          const lk = F.doc(fs, map(path).split('/').slice(0, 2).join('/') + '/_locks/' + path.replace(/\\//g, '~'));
          return F.runTransaction(fs, async tx => {
            const s = await tx.get(lk), now = Date.now(), d = s.exists() ? s.data() : null;
            if (d && d.holder !== holder && d.until > now) return {acquired: false};
            tx.set(lk, {holder, until: now + ttlMs}); return {acquired: true};
          }).catch(wrap);
        }
      };
    }
  };
  // moving between addresses: this device's lists wait in a hidden note in its home group, picked up on the other side
  const stash = async () => {
    const docs = await ownDocs(user.uid, home); if (!docs.length) return '';
    const token = window.MM_NEWID();
    await F.setDoc(F.doc(fs, 'spaces/' + home + '/_moves/' + token), {docs: enc(docs), created: Date.now()});
    return token;
  };
  const unstash = async token => {
    const ref = F.doc(fs, 'spaces/' + home + '/_moves/' + token), s = await F.getDoc(ref).catch(() => null);
    if (!s || !s.exists()) return;
    const docs = dec(s.data().docs || []);
    await putDocs(user.uid, home, docs);
    await F.deleteDoc(ref).catch(() => {});
  };
  return {db, uid: user.uid, home, stash, unstash};
}

/* MiMaMoo moved to Firebase's address. From the old one: carry this device's groups, settings and lists across.
   A home-screen app can't leave its address, so it shows the way instead (and the new one is added to the home screen). */
async function moveHouse(c, to) {
  let token = ''; try { token = await c.stash(); } catch (e) {}
  const ls = {}; try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (/^(wbw:|mm:(home|spaces)$)/.test(k)) ls[k] = localStorage.getItem(k); } } catch (e) {}
  const pay = btoa(unescape(encodeURIComponent(JSON.stringify({ls, move: token, at: location.hash.slice(1)})))).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
  const url = to + '#import=' + pay;
  const standalone = (() => { try { return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true; } catch (e) { return false; } })();
  if (!standalone) { location.replace(url); return; }
  document.body.innerHTML = '<div style="min-height:100vh;display:flex;flex-direction:column;justify-content:center;gap:16px;padding:32px 24px;direction:rtl;font-family:system-ui,sans-serif;background:#FAF9FC;color:#2B2833">'
    + '<h1 style="font-size:26px;margin:0">MiMaMoo עברה לבית חדש</h1>'
    + '<p style="font-size:17px;line-height:1.5;margin:0">כל האירועים והרשימות שלך עוברים איתך. לוחצים על הכפתור, ובדפדפן שנפתח: שיתוף ← "הוספה למסך הבית". אחר כך אפשר למחוק את האייקון הישן.</p>'
    + '<a href="' + url + '" target="_blank" rel="noopener" style="align-self:flex-start;padding:14px 22px;border-radius:999px;background:#FFE08F;color:#5A4410;font-weight:700;font-size:17px;text-decoration:none">פתיחה בכתובת החדשה</a></div>';
}

/* The first time this device connects to the cloud, what it kept on its own (before the cloud existed)
   moves up into this space, as long as the space is still empty: nothing already shared is overwritten.
   The on-device copy stays where it is, untouched. */
async function moveLocalUp(db, uid) {
  const flag = 'mm:moved:' + window.MM_SPACE, done = () => { try { localStorage.setItem(flag, '1'); } catch (e) {} };
  let o = null;
  try { if (localStorage.getItem(flag)) return; o = JSON.parse(localStorage.getItem(LOCAL_KEY) || 'null'); } catch (e) { return; }
  if (!o || !Object.keys(o).some(c => o[c] && Object.keys(o[c]).length)) return done();
  try { if ((await db.collection('events').get()).docs.length) return done(); } catch (e) { return; }
  const mine = 'data/users/' + uid, to = c => c === 'solo' ? mine : c.indexOf('solo/') === 0 ? mine + c.slice(4) : c;
  let failed = 0;
  await Promise.all(Object.keys(o).flatMap(c => Object.keys(o[c] || {}).map(id =>
    db.doc(to(c) + '/' + id).set(o[c][id]).catch(e => { failed++; console.warn('move up', c, id, e); }))));
  if (!failed) done();
}
""")

# ---------- start-up: Claude runtime (inside Claude), else Firebase, else this device ----------
rep("""  } catch (e) {}
  if (db) {
    Store.db = db; S.mode = 'db';""", """  } catch (e) {}
  const fcfg = window.MM_CONFIG && window.MM_CONFIG.firebase;
  if (!db && fcfg && fcfg.apiKey) {
    try {
      const c = await connectFire(fcfg, window.MM_SPACE, window.MM_SPACES); db = c.db; S.uid = c.uid; S.canWrite = true; await moveLocalUp(db, c.uid);
      const au = window.MM_AUTH && window.MM_AUTH.user(); if (au && au.name) S.profileName = au.name.trim().split(/\\s+/)[0];
      if (window.MM_IMPORT && window.MM_IMPORT.move) await c.unstash(window.MM_IMPORT.move).catch(() => {});
      const to = window.MM_CONFIG.moveTo;
      if (to && /github\\.io$/.test(location.hostname)) { await moveHouse(c, to); return; }
    }
    catch (e) { console.warn(e); toast('אין חיבור לענן כרגע. עובדים על המכשיר הזה.', true); }
  }
  if (db) {
    Store.db = db; S.mode = 'db';""")
rep("  } else S.mode = 'local';", "  } else { S.mode = 'local'; loadLocal(); }")

# ---------- local mode really does keep things now: say where they live ----------
rep("<div class=\"banner\"><div class=\"wrap\">אין חיבור. שום דבר כאן לא נשמר.</div></div>",
    "<div class=\"banner\"><div class=\"wrap\">נשמר רק במכשיר הזה. השיתוף עם חברים יופעל אחרי החיבור לענן.</div></div>")

# ---------- invite: a link anyone can open, shared with the phone's share sheet ----------
i = s.index('function openInvite() {')
j = s.index('\n}\n', i) + 3
s = s[:i] + r"""const spaceLink = eid => location.origin + location.pathname + '#' + ((eid && window.MM_SPACEOF) ? window.MM_SPACEOF(eid) : window.MM_SPACE) + (eid ? '/' + eid : '');
function openInvite() {
  const ev = tripData().ev; if (!ev) return;
  if (S.mode !== 'db') {
    openSheet('<h2 class="sheet-title">הזמנה</h2><p>השיתוף עם חברים יעבוד אחרי שהאפליקציה תחובר לענן. בינתיים הכול נשמר רק במכשיר הזה.</p><div class="sheet-actions"><button type="button" class="btn primary" data-close>סגירה</button></div>');
    return;
  }
  const link = spaceLink(S.tripId);
  openSheet('<h2 class="sheet-title">הזמנה ל״' + esc(ev.name) + '״</h2><p>מי שפותח את הקישור מצטרף לאירוע הזה, רואה אותו ויכול לערוך.</p>'
    + '<div class="field"><span>קישור</span><div class="code-row"><code id="trip-code" dir="ltr">' + esc(link) + '</code><button type="button" class="btn sm" data-copy="' + esc(link) + '">העתקה</button></div></div>'
    + '<div class="sheet-actions"><button type="button" class="btn" data-close>סגירה</button>' + (navigator.share ? '<button type="button" class="btn primary" data-act="share-link">שיתוף</button>' : '') + '</div>');
}
async function shareLink() {
  const ev = tripData().ev; if (!ev || !navigator.share) return;
  try { await navigator.share({title: 'MiMaMoo', text: 'מצטרפים ל״' + ev.name + '״ ב־MiMaMoo.\nבאייפון עם MiMaMoo במסך הבית: מעתיקים את הקישור, פותחים את האפליקציה ולוחצים "הדבקת קישור ההזמנה".', url: spaceLink(S.tripId)}); } catch (e) {}
}
""" + s[j:]
rep("    case 'invite': return openInvite();", "    case 'invite': return openInvite();\n    case 'share-link': return shareLink();")

# ---------- write the app ----------
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / 'icons').mkdir(parents=True)
(OUT / 'index.html').write_text(s, encoding='utf-8')

static = HERE / 'static'
for f in static.rglob('*'):
    if f.is_file():
        dest = OUT / f.relative_to(static)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
sw = (OUT / 'sw.js').read_text(encoding='utf-8').replace('__VERSION__', VERSION)
(OUT / 'sw.js').write_text(sw, encoding='utf-8')
print('built', OUT, 'version', VERSION, len(s), 'bytes')
