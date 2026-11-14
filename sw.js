/* MiMaMoo service worker: opens offline, picks up new versions on the next visit. */
const CACHE = 'mimamoo-202611141658';
const SHELL = ['./', 'index.html', 'config.js', 'manifest.webmanifest', 'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/favicon-32.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const keep = (req, res) => { if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); } return res; };

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // The app's own files: the network first, asking the server past the browser's short-term cache,
  // so an update (or a new config.js) shows at once; the saved copy when offline.
  if (url.origin === self.location.origin) {
    e.respondWith(fetch(req.url, {cache: 'no-cache'}).then(res => res.redirected ? fetch(req) : res).then(res => keep(req, res))
      .catch(() => caches.match(req, {ignoreSearch: true}).then(m => m || caches.match('index.html'))));
    return;
  }
  // Fonts and the Firebase library never change at a given address: the saved copy first.
  if (/^(fonts\.googleapis\.com|fonts\.gstatic\.com|www\.gstatic\.com)$/.test(url.hostname)) {
    e.respondWith(caches.match(req).then(m => m || fetch(req).then(res => keep(req, res))));
  }
  // Everything else (the Firebase database itself) goes straight to the network.
});

// Notifications from the group (sent by functions/ through Firebase Cloud Messaging, as data: title, body, tag, url).
// Every message shows: a phone may stop delivering to an app that receives messages without showing them.
self.addEventListener('push', e => {
  let m = {}; try { m = e.data ? e.data.json() : {}; } catch (x) {}
  const d = m.data || m, n = m.notification || {};
  e.waitUntil(self.registration.showNotification(d.title || n.title || 'MiMaMoo', {
    body: d.body || n.body || '', tag: d.tag || undefined, renotify: false, lang: 'he', dir: 'rtl',
    icon: 'icons/icon-192.png', badge: 'icons/badge-96.png', data: {url: d.url || '#', eid: d.eid || '', space: d.space || ''}
  }));
});
// Tapping it opens the event: in the app if it is open, otherwise a new window at the event's link
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const d = e.notification.data || {}, url = new URL(d.url || '#', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(list => {
    const w = list.find(c => c.url.indexOf(self.registration.scope) === 0);
    if (w) { w.postMessage({mm: 'open', eid: d.eid, space: d.space}); return w.focus(); }
    return self.clients.openWindow(url);
  }));
});
