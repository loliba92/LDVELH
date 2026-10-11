/* Service worker de La Cote du Héros : l'application s'ouvre sans réseau.
   - pages, scripts, styles, données : réseau d'abord (toujours la version à jour), copie locale en secours ;
   - jaquettes, polices, icônes : copie locale d'abord (elles ne changent pas). */
const VERSION = 'cdh-v7';
const COEUR = ['./', 'index.html', 'app.js', 'plus.js', 'pages.js', 'collection.html', 'le-projet.html', 'confidentialite.html', 'mentions-legales.html', 'style.css', 'manifest.webmanifest', 'data/versions.json', 'data/meta.json',
  'fonts/cormorant-garamond.woff2', 'fonts/cormorant-garamond-italic.woff2', 'fonts/source-sans-3.woff2',
  'icons/icon-192.png', 'icons/apple-touch-icon.png', 'favicon-32.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(COEUR.map((u) => c.add(u).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((cles) => Promise.all(cles.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

const stable = (url) => /\/(covers|fonts|icons|images)\//.test(url.pathname);

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(VERSION);
    if (stable(url)) {
      const connu = await cache.match(req);
      if (connu) return connu;
      const rep = await fetch(req);
      if (rep.ok) cache.put(req, rep.clone());
      return rep;
    }
    try {
      const rep = await fetch(req);
      if (rep.ok) cache.put(req, rep.clone());
      return rep;
    } catch (err) {
      const copie = await cache.match(req, { ignoreSearch: true }) || (req.mode === 'navigate' ? await cache.match('index.html') : null);
      if (copie) return copie;
      throw err;
    }
  })());
});
