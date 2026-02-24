/**
 * 统一 API 客户端 - Unified API Client
 * 
 * 功能：
 * - 统一管理所有后端服务的连接
 * - 请求去重（避免重复请求）
 * - 智能缓存（减少网络请求）
 * - 自动重试（提升可靠性）
 * - 请求队列管理（控制并发）
 * - 健康监控集成
 */

const UnifiedAPIClient = (function() {
    
    const ServiceConfig = {
        ollama: {
            baseUrl: `http://${window.location.hostname || 'localhost'}:11434`,
            timeout: 120000,
            healthEndpoint: '/api/tags',
            priority: 1
        },
        backend: {
            baseUrl: `http://${window.location.hostname || 'localhost'}:5001`,
            timeout: 60000,
            healthEndpoint: '/api/health',
            priority: 2
        },
        summary: {
            baseUrl: `http://${window.location.hostname || 'localhost'}:5002`,
            timeout: 30000,
            healthEndpoint: '/api/summary/health',
            priority: 3
        },
        vision: {
            baseUrl: `http://${window.location.hostname || 'localhost'}:5003`,
            timeout: 60000,
            healthEndpoint: '/api/vision/status',
            priority: 3
        },
        nativeImage: {
            baseUrl: `http://${window.location.hostname || 'localhost'}:5004`,
            timeout: 60000,
            healthEndpoint: '/api/native_llama_cpp_image/health',
            priority: 4
        }
    };

    const CacheConfig = {
        maxSize: 100,
        defaultTTL: 30000,
        methods: ['GET']
    };

    const RetryConfig = {
        maxRetries: 3,
        retryDelay: 1000,
        retryableErrors: ['ECONNREFUSED', 'ETIMEDOUT', 'ENETUNREACH', 'NetworkError']
    };

    const QueueConfig = {
        maxConcurrent: 6,
        maxQueueSize: 100
    };

    let state = {
        cache: new Map(),
        pendingRequests: new Map(),
        requestQueue: [],
        activeRequests: 0,
        serviceHealth: {},
        metrics: {
            totalRequests: 0,
            cacheHits: 0,
            cacheMisses: 0,
            errors: 0,
            avgResponseTime: 0
        },
        responseTimes: [],
        isInitialized: false
    };

    function init() {
        if (state.isInitialized) return;
        
        state.isInitialized = true;
        
        loadCacheFromStorage();
        
        startCacheCleanup();
        
        console.log('[UnifiedAPIClient] 初始化完成');
    }

    function loadCacheFromStorage() {
        try {
            const saved = localStorage.getItem('api_cache');
            if (saved) {
                const data = JSON.parse(saved);
                const now = Date.now();
                
                Object.entries(data).forEach(([key, value]) => {
                    if (value.expires > now) {
                        state.cache.set(key, value);
                    }
                });
                
                console.log(`[UnifiedAPIClient] 从存储加载 ${state.cache.size} 条缓存`);
            }
        } catch (e) {
            console.warn('[UnifiedAPIClient] 加载缓存失败:', e);
        }
    }

    function saveCacheToStorage() {
        try {
            const data = {};
            state.cache.forEach((value, key) => {
                data[key] = value;
            });
            localStorage.setItem('api_cache', JSON.stringify(data));
        } catch (e) {
            console.warn('[UnifiedAPIClient] 保存缓存失败:', e);
        }
    }

    function startCacheCleanup() {
        setInterval(() => {
            const now = Date.now();
            let cleaned = 0;
            
            state.cache.forEach((value, key) => {
                if (value.expires <= now) {
                    state.cache.delete(key);
                    cleaned++;
                }
            });
            
            if (cleaned > 0) {
                console.log(`[UnifiedAPIClient] 清理 ${cleaned} 条过期缓存`);
            }
        }, 60000);
    }

    function generateCacheKey(service, endpoint, method, data) {
        const dataHash = data ? JSON.stringify(data) : '';
        return `${service}:${method}:${endpoint}:${dataHash}`;
    }

    function getFromCache(key) {
        const cached = state.cache.get(key);
        if (cached && cached.expires > Date.now()) {
            state.metrics.cacheHits++;
            return cached.data;
        }
        
        if (cached) {
            state.cache.delete(key);
        }
        
        state.metrics.cacheMisses++;
        return null;
    }

    function setCache(key, data, ttl = CacheConfig.defaultTTL) {
        if (state.cache.size >= CacheConfig.maxSize) {
            const oldestKey = state.cache.keys().next().value;
            state.cache.delete(oldestKey);
        }
        
        state.cache.set(key, {
            data: data,
            expires: Date.now() + ttl,
            created: Date.now()
        });
        
        saveCacheToStorage();
    }

    function invalidateCache(pattern = null) {
        if (pattern) {
            state.cache.forEach((value, key) => {
                if (key.includes(pattern)) {
                    state.cache.delete(key);
                }
            });
        } else {
            state.cache.clear();
        }
        saveCacheToStorage();
    }

    function shouldRetry(error) {
        return RetryConfig.retryableErrors.some(e => 
            error.name?.includes(e) || error.message?.includes(e)
        );
    }

    async function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function executeRequest(service, endpoint, options = {}) {
        const config = ServiceConfig[service];
        if (!config) {
            throw new Error(`未知服务: ${service}`);
        }

        const {
            method = 'GET',
            data = null,
            headers = {},
            timeout = config.timeout,
            useCache = method === 'GET',
            cacheTTL = CacheConfig.defaultTTL,
            skipQueue = false
        } = options;

        const cacheKey = generateCacheKey(service, endpoint, method, data);
        
        if (useCache && method === 'GET') {
            const cached = getFromCache(cacheKey);
            if (cached !== null) {
                console.log(`[UnifiedAPIClient] 缓存命中: ${cacheKey}`);
                return cached;
            }
        }

        if (state.pendingRequests.has(cacheKey)) {
            console.log(`[UnifiedAPIClient] 等待进行中的请求: ${cacheKey}`);
            return state.pendingRequests.get(cacheKey);
        }

        const execute = async () => {
            const url = `${config.baseUrl}${endpoint}`;
            let lastError = null;

            for (let attempt = 0; attempt < RetryConfig.maxRetries; attempt++) {
                const startTime = Date.now();
                
                try {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), timeout);

                    const fetchOptions = {
                        method: method,
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            ...headers
                        },
                        signal: controller.signal
                    };

                    if (data && ['POST', 'PUT', 'PATCH'].includes(method)) {
                        fetchOptions.body = JSON.stringify(data);
                    }

                    const response = await fetch(url, fetchOptions);
                    clearTimeout(timeoutId);

                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`HTTP ${response.status}: ${errorText}`);
                    }

                    const responseData = await response.json();
                    const responseTime = Date.now() - startTime;
                    
                    updateMetrics(responseTime, true);
                    updateServiceHealth(service, true, responseTime);

                    if (useCache && method === 'GET') {
                        setCache(cacheKey, responseData, cacheTTL);
                    }

                    return responseData;

                } catch (error) {
                    lastError = error;
                    updateMetrics(0, false);
                    updateServiceHealth(service, false, 0);

                    if (shouldRetry(error) && attempt < RetryConfig.maxRetries - 1) {
                        console.warn(
                            `[UnifiedAPIClient] 请求失败，重试 ${attempt + 1}/${RetryConfig.maxRetries}:`,
                            error.message
                        );
                        await delay(RetryConfig.retryDelay * (attempt + 1));
                    } else {
                        break;
                    }
                }
            }

            throw lastError || new Error('请求失败');
        };

        if (!skipQueue && state.activeRequests >= QueueConfig.maxConcurrent) {
            console.log(`[UnifiedAPIClient] 请求排队，当前并发: ${state.activeRequests}`);
            
            return new Promise((resolve, reject) => {
                if (state.requestQueue.length >= QueueConfig.maxQueueSize) {
                    reject(new Error('请求队列已满'));
                    return;
                }

                state.requestQueue.push({
                    execute: () => {
                        state.pendingRequests.set(cacheKey, execute());
                        return state.pendingRequests.get(cacheKey);
                    },
                    resolve,
                    reject,
                    cacheKey
                });
            });
        }

        state.pendingRequests.set(cacheKey, execute());
        
        try {
            const result = await state.pendingRequests.get(cacheKey);
            return result;
        } finally {
            state.pendingRequests.delete(cacheKey);
            processQueue();
        }
    }

    function processQueue() {
        if (state.requestQueue.length === 0) return;
        if (state.activeRequests >= QueueConfig.maxConcurrent) return;

        const item = state.requestQueue.shift();
        state.activeRequests++;

        item.execute()
            .then(result => {
                item.resolve(result);
            })
            .catch(error => {
                item.reject(error);
            })
            .finally(() => {
                state.activeRequests--;
                processQueue();
            });
    }

    function updateMetrics(responseTime, success) {
        state.metrics.totalRequests++;
        
        if (!success) {
            state.metrics.errors++;
        }
        
        if (responseTime > 0) {
            state.responseTimes.push(responseTime);
            if (state.responseTimes.length > 100) {
                state.responseTimes.shift();
            }
            state.metrics.avgResponseTime = 
                state.responseTimes.reduce((a, b) => a + b, 0) / state.responseTimes.length;
        }
    }

    function updateServiceHealth(service, success, responseTime) {
        if (!state.serviceHealth[service]) {
            state.serviceHealth[service] = {
                status: 'unknown',
                lastCheck: 0,
                responseTime: 0,
                consecutiveFailures: 0
            };
        }

        const health = state.serviceHealth[service];
        health.lastCheck = Date.now();
        
        if (success) {
            health.status = 'healthy';
            health.responseTime = responseTime;
            health.consecutiveFailures = 0;
        } else {
            health.consecutiveFailures++;
            if (health.consecutiveFailures >= 3) {
                health.status = 'unhealthy';
            } else {
                health.status = 'degraded';
            }
        }
    }

    async function checkHealth(service = null) {
        const services = service ? [service] : Object.keys(ServiceConfig);
        const results = {};

        for (const svc of services) {
            const config = ServiceConfig[svc];
            if (!config.healthEndpoint) {
                results[svc] = { status: 'unknown', reason: '无健康检查端点' };
                continue;
            }

            try {
                const startTime = Date.now();
                await executeRequest(svc, config.healthEndpoint, {
                    timeout: 5000,
                    skipQueue: true
                });
                const responseTime = Date.now() - startTime;
                
                results[svc] = {
                    status: 'healthy',
                    responseTime: responseTime
                };
            } catch (error) {
                results[svc] = {
                    status: 'unhealthy',
                    error: error.message
                };
            }
        }

        return results;
    }

    function getMetrics() {
        return {
            ...state.metrics,
            cacheSize: state.cache.size,
            queueSize: state.requestQueue.length,
            activeRequests: state.activeRequests,
            cacheHitRate: state.metrics.totalRequests > 0 
                ? (state.metrics.cacheHits / state.metrics.totalRequests * 100).toFixed(2) + '%'
                : '0%'
        };
    }

    function getServiceHealth() {
        return { ...state.serviceHealth };
    }

    function getServices() {
        return Object.keys(ServiceConfig).map(name => ({
            name,
            baseUrl: ServiceConfig[name].baseUrl,
            priority: ServiceConfig[name].priority
        }));
    }

    init();

    return {
        request: executeRequest,
        get: (service, endpoint, options = {}) => 
            executeRequest(service, endpoint, { ...options, method: 'GET' }),
        post: (service, endpoint, data, options = {}) => 
            executeRequest(service, endpoint, { ...options, method: 'POST', data }),
        put: (service, endpoint, data, options = {}) => 
            executeRequest(service, endpoint, { ...options, method: 'PUT', data }),
        delete: (service, endpoint, options = {}) => 
            executeRequest(service, endpoint, { ...options, method: 'DELETE' }),
        
        checkHealth,
        getMetrics,
        getServiceHealth,
        getServices,
        invalidateCache,
        
        get ollama() { return 'ollama'; },
        get backend() { return 'backend'; },
        get summary() { return 'summary'; },
        get vision() { return 'vision'; },
        get nativeImage() { return 'nativeImage'; }
    };
})();

if (typeof window !== 'undefined') {
    window.UnifiedAPIClient = UnifiedAPIClient;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = UnifiedAPIClient;
}
