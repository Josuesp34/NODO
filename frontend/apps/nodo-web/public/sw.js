const STATIC_CACHE = "nodo-static-v2";
const SHELL = ["/", "/offline", "/icons/nodo.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then(async (cache) => {
    await cache.addAll(SHELL);
    const offline = await cache.match("/offline");
    const html = await offline.text();
    const assets = [...html.matchAll(/(?:src|href)="(\/_next\/static\/[^"?#]+\.(?:js|css))"/g)].map((match) => match[1]);
    await cache.addAll([...new Set(assets)]);
  }));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== STATIC_CACHE).map((key) => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "CLEAR_AUTH_CACHE") {
    event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("nodo-auth")).map((key) => caches.delete(key)))));
  }
});

self.addEventListener("push", (event) => {
  // Never show athlete names, health metrics or arbitrary provider content on a locked screen.
  let payload = {};
  try { payload = event.data?.json() ?? {}; } catch { /* Generic fallback remains private. */ }
  const tag = typeof payload.tag === "string" && /^nodo-[a-f0-9]{24}$/.test(payload.tag) ? payload.tag : "nodo-update";
  event.waitUntil(self.registration.showNotification("NODO", {
    body: "Tienes una actualización. Abre NODO para revisarla.",
    icon: "/icons/nodo.svg",
    tag,
    data: { url: "/app" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const app = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (app) { await app.navigate("/app"); return app.focus(); }
    return self.clients.openWindow("/app");
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(caches.open(STATIC_CACHE).then(async (cache) => {
      const cached = await cache.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    }));
    return;
  }
  event.respondWith(fetch(request).catch(async () => (await caches.match(request)) || (await caches.match("/offline"))));
});
