// Service worker da app TCAE. build_app.py substitui 20260912-1753 a cada build,
// por isso o nome da cache muda sempre que ha conteudo novo.
//
// Estrategia:
//   * navegacao/HTML -> NETWORK-FIRST (a app nova chega sempre que ha rede;
//     a cache so entra em jogo offline). A v4 usava cache-first e por isso a
//     PWA instalada ficou presa numa versao antiga com respostas erradas.
//   * icones/manifest -> cache-first (nao mudam e sao pesados).
const VERSION = '20260912-1828';
const CACHE = 'tcae-' + VERSION;
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.allSettled(ASSETS.map(a => c.add(a))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', e => {
  if (e.data === 'skipWaiting') self.skipWaiting();
  if (e.data === 'version' && e.source) e.source.postMessage({ version: VERSION });
});

function isDoc(req) {
  return req.mode === 'navigate' ||
         (req.destination === 'document') ||
         (req.headers.get('accept') || '').includes('text/html');
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== self.location.origin) return;

  if (isDoc(req)) {
    // network-first: a versao nova ganha sempre que houver rede
    e.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put('./index.html', copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match('./index.html').then(hit => hit || caches.match('./')))
    );
    return;
  }

  // resto (icones, manifest): cache-first com revalidacao em segundo plano
  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
