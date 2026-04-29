/**
 * EduBoost SA — Service Worker
 * Architectural recommendation #9: offline resilience for ZA 2G/3G learners.
 *
 * Strategy:
 *   - Cache lesson content, study plan, and diagnostic state on first load
 *   - Offline answer queue: buffer responses in IndexedDB, sync on reconnection
 *   - Sync replays through full API pipeline (not a bypass)
 *   - Progressive loading: never block first question on full bundle
 */

const CACHE_VERSION = "eduboost-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const LESSON_CACHE = `${CACHE_VERSION}-lessons`;
const OFFLINE_QUEUE_KEY = "offline-answer-queue";

// Resources to cache on install
const PRECACHE_URLS = [
  "/",
  "/diagnostic",
  "/lesson",
  "/study-plan",
  "/offline",
  "/_next/static/css/app.css",
];

// Routes that should use cache-first strategy
const CACHE_FIRST_PATTERNS = [
  /\/_next\/static\//,
  /\/api\/lesson\/content\//,
  /\/api\/study-plan\//,
];

// Routes that should queue when offline
const QUEUEABLE_API_PATTERNS = [
  /\/api\/diagnostic\/response/,
  /\/api\/lesson\/answer/,
  /\/api\/assessment\/submit/,
];

// ---------------------------------------------------------------------------
// Install: precache static assets
// ---------------------------------------------------------------------------
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ---------------------------------------------------------------------------
// Activate: clean up old cache versions
// ---------------------------------------------------------------------------
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("eduboost-") && key !== STATIC_CACHE && key !== LESSON_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ---------------------------------------------------------------------------
// Fetch: route interception
// ---------------------------------------------------------------------------
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only intercept same-origin requests
  if (url.origin !== self.location.origin) return;

  // Cache-first for static + lesson content
  if (CACHE_FIRST_PATTERNS.some((p) => p.test(url.pathname))) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Queue-if-offline for answer submission
  if (
    QUEUEABLE_API_PATTERNS.some((p) => p.test(url.pathname)) &&
    request.method === "POST"
  ) {
    event.respondWith(networkWithOfflineQueue(request));
    return;
  }

  // Network-first with fallback for everything else
  event.respondWith(networkFirst(request));
});

// ---------------------------------------------------------------------------
// Cache-first strategy
// ---------------------------------------------------------------------------
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(LESSON_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response(JSON.stringify({ error: "offline", cached: false }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

// ---------------------------------------------------------------------------
// Network-first strategy
// ---------------------------------------------------------------------------
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match("/offline") || new Response("Offline", { status: 503 });
  }
}

// ---------------------------------------------------------------------------
// Network with offline queue: buffer POST requests in IndexedDB
// ---------------------------------------------------------------------------
async function networkWithOfflineQueue(request) {
  try {
    return await fetch(request);
  } catch {
    // Offline: buffer the request
    const body = await request.clone().json();
    await enqueueRequest({
      url: request.url,
      method: request.method,
      body,
      headers: Object.fromEntries(request.headers.entries()),
      queuedAt: Date.now(),
    });

    return new Response(
      JSON.stringify({
        queued: true,
        message: "Your answer has been saved and will sync when you reconnect.",
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

// ---------------------------------------------------------------------------
// IndexedDB queue helpers
// ---------------------------------------------------------------------------
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("eduboost-offline", 1);
    req.onupgradeneeded = (e) => {
      e.target.result.createObjectStore("queue", {
        keyPath: "id",
        autoIncrement: true,
      });
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function enqueueRequest(entry) {
  const db = await openDB();
  const tx = db.transaction("queue", "readwrite");
  tx.objectStore("queue").add(entry);
  return new Promise((res, rej) => {
    tx.oncomplete = res;
    tx.onerror = rej;
  });
}

async function drainQueue() {
  const db = await openDB();
  const tx = db.transaction("queue", "readwrite");
  const store = tx.objectStore("queue");
  const entries = await new Promise((res, rej) => {
    const req = store.getAll();
    req.onsuccess = (e) => res(e.target.result);
    req.onerror = rej;
  });

  for (const entry of entries) {
    try {
      const response = await fetch(entry.url, {
        method: entry.method,
        headers: { "Content-Type": "application/json", ...entry.headers },
        body: JSON.stringify(entry.body),
      });

      if (response.ok) {
        // Remove from queue after successful sync
        const delTx = db.transaction("queue", "readwrite");
        delTx.objectStore("queue").delete(entry.id);
      }
    } catch {
      // Still offline — leave in queue for next sync
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// Background sync: replay queued requests on reconnection
// ---------------------------------------------------------------------------
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-answers") {
    event.waitUntil(drainQueue());
  }
});

// Also attempt drain on service worker activation (covers cases where
// Background Sync API is not available, e.g. older browsers)
self.addEventListener("activate", (event) => {
  event.waitUntil(drainQueue());
});
