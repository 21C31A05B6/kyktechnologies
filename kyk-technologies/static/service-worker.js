const CACHE_NAME = "kyk-shell-v29-cursor-fix";
const APP_SHELL = [
  "/",
  "/index.html",
  "/hrms-portal.html",
  "/communication.html",
  "/css/style.css",
  "/css/dashboard.css",
  "/css/communication.css",
  "/js/main.js",
  "/js/dash-common.js",
  "/js/communication.js",
  "/js/socket.io.min.js",
  "/js/pwa.js",
  "/manifest.webmanifest",
  "/kyk_logo.webp"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Bypass API calls, media streaming (MP4/video), and HTTP range requests to allow native, unbuffered streaming
  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.endsWith(".mp4") ||
    url.pathname.endsWith(".webm") ||
    url.pathname.endsWith(".ogv") ||
    request.headers.has("range")
  ) {
    return;
  }

  // Network-first for HTML, JS and CSS to guarantee instant updates
  event.respondWith(
    fetch(request).then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }
      return response;
    }).catch(() => caches.match(request).then((cached) => cached || (request.mode === "navigate" ? caches.match("/index.html") : null)))
  );
});
