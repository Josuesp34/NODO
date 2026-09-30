const STATIC_CACHE = "nodo-static-v1";
const SHELL = ["/", "/offline", "/icons/nodo.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(SHELL)));
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

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith(fetch(request).catch(async () => (await caches.match(request)) || (await caches.match("/offline"))));
});
