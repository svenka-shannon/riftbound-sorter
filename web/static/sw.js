/*
 * Riftbound Sorter phone app: service worker.
 * Caches the APP SHELL ONLY (the page, CSS, JS, manifest, icons) so the app
 * opens even when the Pi is unreachable. Everything else, above all /api/
 * (status, camera, controls), exports and the desktop pages, is never
 * cached and never answered from a cache: it always goes to the network.
 * Shell requests are network-first, so a new version on the Pi is picked up
 * on the next load; the cache is only the offline fallback.
 * Note: browsers only run service workers on https:// or localhost. On
 * http://<pi>.local:5000 the app works the same, just without this cache.
 */
const CACHE = 'rb-shell-v1';
const SHELL = [
  '/',
  '/static/app.css',
  '/static/app.js',
  '/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable-512.png',
  '/static/icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;                      // controls: network only
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;          // never cache API responses
  if (!SHELL.includes(url.pathname)) return;             // desktop pages, exports: network only
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(url.pathname, copy));
        }
        return resp;
      })
      .catch(() => caches.match(url.pathname)));
});
