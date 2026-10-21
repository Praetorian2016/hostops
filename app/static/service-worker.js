const CACHE_NAME = 'hostops-pwa-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Strategia network-first per avere sempre i dati aggiornati
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});