/**
 * 离线缓存策略 - Service Worker
 * 
 * 功能：
 * - 静态资源缓存
 * - API 响应缓存
 * - 离线对话支持
 * - 智能缓存更新
 */

// Service Worker 离线缓存策略
const CACHE_NAME = 'ollma-offline-v1';
const STATIC_CACHE = 'ollma-static-v1';
const API_CACHE = 'ollma-api-v1';

// 缓存策略配置
const CACHE_STRATEGIES = {
    // 静态资源：Cache First（长期缓存）
    static: {
        patterns: [
            '/',
            '/index.html',
            '/css/style.css',
            '/js/core/app.js',
            '/js/features/intelligent.js'
        ],
        strategy: 'cache-first',
        maxAge: 7 * 24 * 60 * 60 * 1000 // 7天
    },
    
    // API 响应：Network First（优先网络）
    api: {
        patterns: [
            '/api/health',
            '/api/conversation',
            '/api/memory',
            '/api/summary',
            '/api/context'
        ],
        strategy: 'network-first',
        maxAge: 24 * 60 * 60 * 1000 // 1天
    },
    
    // 对话历史：Cache Only（离线时使用）
    conversation: {
        patterns: [
            '/api/conversation/history',
            '/api/memory/search'
        ],
        strategy: 'cache-only',
        maxAge: 30 * 24 * 60 * 60 * 1000 // 30天
    },
    
    // 图像资源：Cache First
    images: {
        patterns: [
            '/images/',
            '/assets/',
            '\.(png|jpg|jpeg|gif|svg|webp)$'
        ],
        strategy: 'cache-first',
        maxAge: 30 * 24 * 60 * 60 * 1000 // 30天
    }
};

// Service Worker 安装事件
self.addEventListener('install', (event) => {
    console.log('🔧 Service Worker 安装中...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => {
            // 预缓存关键静态资源
            const urlsToCache = [
                '/',
                '/index.html',
                '/css/style.css',
                '/js/core/app.js',
                '/js/features/intelligent.js'
            ];
            
            return cache.addAll(urlsToCache);
        }).then(() => {
            console.log('✅ 关键资源预缓存完成');
            return self.skipWaiting();
        })
    );
});

// Service Worker 激活事件
self.addEventListener('activate', (event) => {
    console.log('🚀 Service Worker 激活中...');
    
    event.waitUntil(
        Promise.all([
            // 清理旧缓存
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== STATIC_CACHE && cacheName !== API_CACHE) {
                            console.log('🗑️ 清理旧缓存:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            
            // 立即接管所有客户端
            self.clients.claim()
        ]).then(() => {
            console.log('✅ Service Worker 激活完成');
        })
    );
});

// 获取请求事件
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // 只处理同源请求
    if (url.origin !== location.origin) {
        return;
    }
    
    // 根据URL模式选择缓存策略
    const strategy = getCacheStrategy(url.pathname);
    
    if (strategy) {
        event.respondWith(handleRequest(event.request, strategy));
    }
});

/**
 * 根据URL路径获取缓存策略
 */
function getCacheStrategy(pathname) {
    for (const [strategyName, config] of Object.entries(CACHE_STRATEGIES)) {
        for (const pattern of config.patterns) {
            if (pathname.match(pattern) || 
                (pattern.startsWith('/') && pathname === pattern) ||
                (pattern.endsWith('$') && pathname.endsWith(pattern.slice(0, -1)))) {
                return { name: strategyName, ...config };
            }
        }
    }
    
    return null;
}

/**
 * 处理请求的缓存策略
 */
async function handleRequest(request, strategy) {
    const cache = await caches.open(getCacheName(strategy.name));
    
    try {
        switch (strategy.strategy) {
            case 'cache-first':
                return await cacheFirst(request, cache, strategy);
                
            case 'network-first':
                return await networkFirst(request, cache, strategy);
                
            case 'cache-only':
                return await cacheOnly(request, cache);
                
            default:
                return await fetch(request);
        }
    } catch (error) {
        console.error('缓存策略执行失败:', error);
        
        // 降级方案：尝试从缓存获取
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // 返回离线页面或错误响应
        return offlineResponse(request);
    }
}

/**
 * Cache First 策略
 */
async function cacheFirst(request, cache, strategy) {
    // 首先尝试从缓存获取
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        // 检查缓存是否过期
        if (!isCacheExpired(cachedResponse, strategy.maxAge)) {
            // 在后台更新缓存
            updateCacheInBackground(request, cache, strategy);
            return cachedResponse;
        }
    }
    
    // 缓存不存在或已过期，从网络获取
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // 缓存新响应
            const responseToCache = networkResponse.clone();
            cache.put(request, addCacheHeaders(responseToCache, strategy.maxAge));
        }
        
        return networkResponse;
    } catch (error) {
        // 网络失败，返回缓存内容（如果有）
        if (cachedResponse) {
            return cachedResponse;
        }
        
        throw error;
    }
}

/**
 * Network First 策略
 */
async function networkFirst(request, cache, strategy) {
    try {
        // 首先尝试网络请求
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // 缓存新响应
            const responseToCache = networkResponse.clone();
            cache.put(request, addCacheHeaders(responseToCache, strategy.maxAge));
        }
        
        return networkResponse;
    } catch (error) {
        // 网络失败，尝试从缓存获取
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse && !isCacheExpired(cachedResponse, strategy.maxAge)) {
            return cachedResponse;
        }
        
        throw error;
    }
}

/**
 * Cache Only 策略
 */
async function cacheOnly(request, cache) {
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    throw new Error('缓存中找不到资源');
}

/**
 * 获取缓存名称
 */
function getCacheName(strategyName) {
    switch (strategyName) {
        case 'static':
            return STATIC_CACHE;
        case 'api':
            return API_CACHE;
        default:
            return CACHE_NAME;
    }
}

/**
 * 添加缓存头信息
 */
function addCacheHeaders(response, maxAge) {
    const headers = new Headers(response.headers);
    headers.set('sw-cache-timestamp', Date.now().toString());
    headers.set('sw-cache-max-age', maxAge.toString());
    
    return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers
    });
}

/**
 * 检查缓存是否过期
 */
function isCacheExpired(cachedResponse, maxAge) {
    const timestamp = cachedResponse.headers.get('sw-cache-timestamp');
    if (!timestamp) return true;
    
    const age = Date.now() - parseInt(timestamp);
    return age > maxAge;
}

/**
 * 后台更新缓存
 */
async function updateCacheInBackground(request, cache, strategy) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            cache.put(request, addCacheHeaders(networkResponse.clone(), strategy.maxAge));
        }
    } catch (error) {
        console.log('后台缓存更新失败:', error);
    }
}

/**
 * 离线响应
 */
function offlineResponse(request) {
    // 对于HTML请求，返回离线页面
    if (request.headers.get('Accept').includes('text/html')) {
        return new Response(
            `
            <!DOCTYPE html>
            <html>
            <head>
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
                </style>
            </head>
            <body>
                <div class="offline-container">
                    <h1>🌐 离线模式</h1>
                    <p>当前处于离线状态，部分功能可能受限。</p>
                    <p>网络恢复后将自动同步数据。</p>
                    <button onclick="location.reload()">重新加载</button>
                </div>
            </body>
            </html>
            `,
            { 
                headers: { 'Content-Type': 'text/html' } 
            }
        );
    }
    
    // 对于API请求，返回离线错误
    return new Response(
        JSON.stringify({ 
            success: false, 
            error: 'offline',
            message: '当前处于离线状态，请检查网络连接'
        }),
        { 
            status: 503,
            headers: { 'Content-Type': 'application/json' } 
        }
    );
}

/**
 * 手动缓存管理API
 */
self.addEventListener('message', (event) => {
    const { type, data } = event.data;
    
    switch (type) {
        case 'CLEAR_CACHE':
            clearCache(data);
            break;
            
        case 'GET_CACHE_INFO':
            getCacheInfo(event);
            break;
            
        case 'PRE_CACHE':
            preCacheResources(data);
            break;
    }
});

/**
 * 清理缓存
 */
async function clearCache(cacheNames) {
    const namesToClear = cacheNames || [STATIC_CACHE, API_CACHE, CACHE_NAME];
    
    for (const cacheName of namesToClear) {
        await caches.delete(cacheName);
    }
    
    console.log('🗑️ 缓存已清理:', namesToClear);
}

/**
 * 获取缓存信息
 */
async function getCacheInfo(event) {
    const cacheInfo = {};
    
    for (const cacheName of [STATIC_CACHE, API_CACHE]) {
        const cache = await caches.open(cacheName);
        const keys = await cache.keys();
        cacheInfo[cacheName] = {
            size: keys.length,
            urls: keys.map(req => req.url)
        };
    }
    
    event.ports[0].postMessage(cacheInfo);
}

/**
 * 预缓存资源
 */
async function preCacheResources(urls) {
    const cache = await caches.open(STATIC_CACHE);
    
    try {
        await cache.addAll(urls);
        console.log('✅ 资源预缓存完成:', urls);
    } catch (error) {
        console.error('❌ 资源预缓存失败:', error);
    }
}

// 注册 Service Worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('✅ Service Worker 注册成功:', registration.scope);
            })
            .catch((error) => {
                console.error('❌ Service Worker 注册失败:', error);
            });
    });
}

// 导出缓存管理函数
window.OfflineCacheManager = {
    clearCache: () => {
        navigator.serviceWorker.controller.postMessage({
            type: 'CLEAR_CACHE'
        });
    },
    
    getCacheInfo: () => {
        return new Promise((resolve) => {
            const channel = new MessageChannel();
            channel.port1.onmessage = (event) => resolve(event.data);
            
            navigator.serviceWorker.controller.postMessage({
                type: 'GET_CACHE_INFO'
            }, [channel.port2]);
        });
    },
    
    preCache: (urls) => {
        navigator.serviceWorker.controller.postMessage({
            type: 'PRE_CACHE',
            data: urls
        });
    }
};