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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
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
/* Shared space: everyone who opens the same link shares the same events (like sharing the artifact).
   Link shape: …/#<space> or …/#<space>/<event>. The space is remembered on this device. */
(function () {
  var h = (location.hash || '').replace(/^#/, '').split('/'), sid = null, deep = '';
  if (/^[A-Za-z0-9]{16,40}$/.test(h[0] || '')) { sid = h[0]; deep = h[1] || ''; }
  try { if (sid) localStorage.setItem('mm:space', sid); else sid = localStorage.getItem('mm:space'); } catch (e) {}
  if (!sid) {
    var a = new Uint8Array(15), abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    crypto.getRandomValues(a); sid = ''; for (var i = 0; i < a.length; i++) sid += abc[a[i] % abc.length];
    sid += 'mm' + Date.now().toString(36).slice(-4);
    try { localStorage.setItem('mm:space', sid); } catch (e) {}
  }
  window.MM_SPACE = sid; window.MM_DEEP = deep;
  try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
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
   App paths stay as they are; they are placed under the shared space, and personal lists under the signed-in user. */
async function connectFire(cfg, sid) {
  const base = 'https://www.gstatic.com/firebasejs/""" + FIREBASE_SDK + """/';
  const [A, AU, F] = await Promise.all([import(base + 'firebase-app.js'), import(base + 'firebase-auth.js'), import(base + 'firebase-firestore.js')]);
  const app = A.initializeApp(cfg);
  const auth = AU.getAuth(app);
  let fs;
  try { fs = F.initializeFirestore(app, {ignoreUndefinedProperties: true, localCache: F.persistentLocalCache({tabManager: F.persistentMultipleTabManager()})}); }
  catch (e) { fs = F.initializeFirestore(app, {ignoreUndefinedProperties: true}); }
  const user = await new Promise((res, rej) => {
    const off = AU.onAuthStateChanged(auth, u => { if (u) { off(); res(u); } });
    AU.signInAnonymously(auth).catch(e => { off(); rej(e); });
  });
  const mine = 'data/users/';
  const map = p => {
    if (p.indexOf(mine) === 0) { const r = p.slice(mine.length), i = r.indexOf('/'); return 'users/' + (i < 0 ? r : r.slice(0, i)) + '/s/' + sid + '/lists' + (i < 0 ? '' : r.slice(i)); }
    return 'spaces/' + sid + '/' + p;
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
  const db = {
    collection: col => ({
      onSnapshot: (cb, err) => F.onSnapshot(F.collection(fs, map(col)), s => cb(snap(s)), e => { console.warn(e); if (err) err({code: CODES[e && e.code] || 'unknown'}); }),
      get: () => F.getDocs(F.collection(fs, map(col))).then(snap, wrap)
    }),
    doc: path => {
      const ref = F.doc(fs, map(path));
      return {
        set: d => F.setDoc(ref, enc(d)).catch(wrap),
        update: d => {
          const args = []; flat(enc(d), [], []).forEach(([p, v]) => { args.push(new F.FieldPath(...p), v); });
          return args.length ? F.updateDoc(ref, ...args).catch(wrap) : Promise.resolve();
        },
        delete: () => F.deleteDoc(ref).catch(wrap),
        get: () => F.getDoc(ref).then(s => ({exists: s.exists(), id: s.id, data: () => dec(s.data())}), wrap),
        // a short lease kept in its own document, so the item itself is never touched
        acquire: ({holder, ttlMs}) => {
          const lk = F.doc(fs, 'spaces/' + sid + '/_locks/' + path.replace(/\\//g, '~'));
          return F.runTransaction(fs, async tx => {
            const s = await tx.get(lk), now = Date.now(), d = s.exists() ? s.data() : null;
            if (d && d.holder !== holder && d.until > now) return {acquired: false};
            tx.set(lk, {holder, until: now + ttlMs}); return {acquired: true};
          }).catch(wrap);
        }
      };
    }
  };
  return {db, uid: user.uid};
}
""")

# ---------- start-up: Claude runtime (inside Claude), else Firebase, else this device ----------
rep("""  } catch (e) {}
  if (db) {
    Store.db = db; S.mode = 'db';""", """  } catch (e) {}
  const fcfg = window.MM_CONFIG && window.MM_CONFIG.firebase;
  if (!db && fcfg && fcfg.apiKey) {
    try { const c = await connectFire(fcfg, window.MM_SPACE); db = c.db; S.uid = c.uid; S.canWrite = true; }
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
s = s[:i] + r"""const spaceLink = eid => location.origin + location.pathname + '#' + window.MM_SPACE + (eid ? '/' + eid : '');
function openInvite() {
  const ev = tripData().ev; if (!ev) return;
  if (S.mode !== 'db') {
    openSheet('<h2 class="sheet-title">הזמנה</h2><p>השיתוף עם חברים יעבוד אחרי שהאפליקציה תחובר לענן. בינתיים הכול נשמר רק במכשיר הזה.</p><div class="sheet-actions"><button type="button" class="btn primary" data-close>סגירה</button></div>');
    return;
  }
  const link = spaceLink(S.tripId);
  openSheet('<h2 class="sheet-title">הזמנה ל״' + esc(ev.name) + '״</h2><p>כל מי שפותח את הקישור מצטרף לרשימות המשותפות שלכם ויכול לערוך.</p>'
    + '<div class="field"><span>קישור</span><div class="code-row"><code id="trip-code" dir="ltr">' + esc(link) + '</code><button type="button" class="btn sm" data-copy="' + esc(link) + '">העתקה</button></div></div>'
    + '<div class="sheet-actions">' + (navigator.share ? '<button type="button" class="btn primary" data-act="share-link">שיתוף</button>' : '') + '<button type="button" class="btn" data-close>סגירה</button></div>');
}
async function shareLink() {
  const ev = tripData().ev; if (!ev || !navigator.share) return;
  try { await navigator.share({title: 'MiMaMoo', text: 'מצטרפים ל״' + ev.name + '״ ב־MiMaMoo', url: spaceLink(S.tripId)}); } catch (e) {}
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
