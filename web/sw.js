/**
 * Service Worker - offline cache support.
 */

const CACHE_NAME = 'ollma-cache-v4';
const PRECACHE_URLS = [
    '/',
    '/index.html',
    '/js/services/storage.js',
    '/js/services/markdown.js',
    '/js/services/health_monitor.v3.js'
];

const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>离线模式 - Ollma</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }
        .offline-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 20px;
        }
        button:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <div class="offline-container">
        <h1>离线模式</h1>
        <p>当前处于离线状态，部分功能可能受限。</p>
        <p>网络恢复后将自动同步数据。</p>
        <button onclick="location.reload()">重新加载</button>
    </div>
</body>
</html>`;

self.addEventListener('install', (event) => {
    console.log('[SW] install');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    console.log('[SW] activate');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                    return Promise.resolve();
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (url.origin !== location.origin) {
        return;
    }
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    const acceptHeader = event.request.headers.get('Accept') || '';
    const isHtmlRequest = event.request.mode === 'navigate' || acceptHeader.includes('text/html');

    if (isHtmlRequest) {
        event.respondWith(
            fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.ok) {
                    const cloned = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
                }
                return networkResponse;
            }).catch(() => {
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    return new Response(OFFLINE_HTML, {
                        headers: { 'Content-Type': 'text/html' },
                        status: 200
                    });
                });
            })
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            return fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.ok) {
                    const cloned = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
                }
                return networkResponse;
            });
        }).catch(() => {
            if (acceptHeader.includes('text/html')) {
                return new Response(OFFLINE_HTML, {
                    headers: { 'Content-Type': 'text/html' },
                    status: 200
                });
            }
            return Response.error();
        })
    );
});

self.addEventListener('message', (event) => {
    const { type } = event.data || {};

    if (type === 'CLEAR_CACHE') {
        event.waitUntil(caches.delete(CACHE_NAME));
    }

    if (type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
