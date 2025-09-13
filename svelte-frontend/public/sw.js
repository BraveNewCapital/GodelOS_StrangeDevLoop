const CACHE_NAME = 'godelos-v1';
const urlsToCache = [
  '/',
  '/src/main.js',
  '/manifest.json',
  // Cache critical assets for offline functionality
];

// Install event - cache resources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip caching for API calls - let them fail gracefully when offline
  if (event.request.url.includes('/api/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version if available, otherwise fetch from network
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
      .catch((error) => {
        // Handle fetch errors gracefully
        console.warn('Service Worker: Fetch failed for', event.request.url, error);
        // Return a basic offline page or just fail silently for API calls
        if (event.request.url.includes('/api/')) {
          return new Response('Offline', {
            status: 503,
            statusText: 'Service Unavailable'
          });
        }
        // For other resources, just let it fail
        throw error;
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});