const CACHE_NAME = "upgcexam-v1";
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/pwa/icon-192.png",
  "/static/pwa/icon-512.png",
];

// Extensions de fichiers statiques pouvant être mises en cache
const STATIC_EXTENSIONS = /\.(css|js|png|jpg|jpeg|svg|ico|woff2?|ttf|eot)$/;

// Installation : pré-cache des assets statiques essentiels
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activation : nettoyage des anciens caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Interception des requêtes : seuls les fichiers statiques sont mis en cache
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Ne pas intercepter les requêtes non-GET
  if (request.method !== "GET") return;

  // Ne pas intercepter les requêtes vers des pages HTML, admin, API, téléchargements, médias
  const url = new URL(request.url);
  
  // Exclure les pages HTML (navigation)
  if (request.mode === "navigate") return;

  // Exclure les chemins sensibles
  const excludePaths = ["/administration/", "/sujets/telecharger/", "/media/", "/pwa/"];
  if (excludePaths.some((p) => url.pathname.startsWith(p))) return;

  // Exclure les appels API
  if (url.pathname.startsWith("/pwa/")) return;

  // Mettre en cache uniquement les fichiers statiques (CSS, JS, images, polices)
  if (STATIC_EXTENSIONS.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return response;
      }))
    );
    return;
  }

  // Pour CDN (Tailwind, Google Fonts) : réseau d'abord, cache en fallback
  if (url.hostname.includes("cdn.") || url.hostname.includes("fonts.googleapis")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match(request))
    );
  }
});

// Notifications push
self.addEventListener("push", (event) => {
  let data = { title: "UPGCExam", body: "Nouvelle notification" };
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/pwa/icon-192.png",
      badge: "/static/pwa/icon-192.png",
      vibrate: [200, 100, 200],
      data: data.url ? { url: data.url } : {},
    })
  );
});

// Clic sur notification
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      const existing = windowClients.find((c) => c.url === url);
      if (existing) {
        existing.focus();
      } else {
        clients.openWindow(url);
      }
    })
  );
});
