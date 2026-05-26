const CACHE_NAME = "upgcexam-v1";
const STATIC_ASSETS = [
  "/static/manifest.json",
];

// Installation : pré-cache des assets essentiels
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

// Interception des requêtes : réseau d'abord, cache en fallback
self.addEventListener("fetch", (event) => {
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        if (
          event.request.method === "GET" &&
          (event.request.url.startsWith(self.location.origin) ||
            event.request.url.includes("cdn.tailwindcss.com"))
        ) {
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
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
