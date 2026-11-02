const CACHE_NAME = "kyk-shell-v31-turbo";
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

  // CRITICAL: NEVER intercept Socket.IO, real-time polling, APIs, WebSockets, or video streams
  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/socket.io/") ||
    url.pathname.includes("socket.io") ||
    url.pathname.endsWith(".mp4") ||
    url.pathname.endsWith(".webm") ||
    url.pathname.endsWith(".ogv") ||
    request.headers.has("range")
  ) {
    return; // Pass through cleanly to the network
  }

  // Network-first for static HTML/JS/CSS assets
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const fallback = await caches.match("/index.html");
          if (fallback) return fallback;
        }
        return new Response("Network unavailable", {
          status: 503,
          statusText: "Service Unavailable",
          headers: { "Content-Type": "text/plain" }
        });
      })
  );
});
