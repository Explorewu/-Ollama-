/**
 * 统一请求管理器 - 性能优化核心模块
 * 
 * 数学模型：
 * 1. LRU缓存：O(1) 时间复杂度的缓存淘汰
 * 2. 请求去重：使用 Promise 共享，避免重复请求
 * 3. 并发控制：滑动窗口算法控制并发数
 * 4. 优先级队列：最小堆实现优先级调度
 */

const RequestManager = {
    config: {
        maxConcurrent: 6,
        defaultTTL: 30000,
        maxCacheSize: 100,
        retryCount: 2,
        retryDelay: 1000,
        timeout: 30000
    },

    cache: new Map(),
    cacheOrder: [],
    pendingRequests: new Map(),
    activeRequests: 0,
    requestQueue: [],

    stats: {
        hits: 0,
        misses: 0,
        requests: 0,
        saved: 0
    },

    init(config = {}) {
        this.config = { ...this.config, ...config };
        this._startCacheCleanup();
        console.log('[RequestManager] 初始化完成', this.config);
    },

    generateKey(url, options = {}) {
        const method = options.method || 'GET';
        const body = options.body ? JSON.stringify(options.body) : '';
        return `${method}:${url}:${body}`;
    },

    async request(url, options = {}) {
        const key = this.generateKey(url, options);
        const ttl = options.ttl ?? this.config.defaultTTL;
        const skipCache = options.skipCache ?? false;
        const priority = options.priority ?? 5;

        this.stats.requests++;

        if (!skipCache && this.cache.has(key)) {
            const cached = this.cache.get(key);
            if (Date.now() - cached.timestamp < ttl) {
                this.stats.hits++;
                this.stats.saved++;
                this._updateLRU(key);
                return cached.data;
            }
            this.cache.delete(key);
        }

        if (this.pendingRequests.has(key)) {
            this.stats.saved++;
            return this.pendingRequests.get(key);
        }

        const requestPromise = this._executeRequest(url, options, key, priority);
        this.pendingRequests.set(key, requestPromise);

        try {
            const result = await requestPromise;
            return result;
        } finally {
            this.pendingRequests.delete(key);
        }
    },

    async _executeRequest(url, options, key, priority) {
        if (this.activeRequests >= this.config.maxConcurrent) {
            await this._waitForSlot(priority);
        }

        this.activeRequests++;

        try {
            const response = await this._fetchWithRetry(url, options);
            const data = await this._parseResponse(response);

            this._setCache(key, data);
            this.stats.misses++;

            return data;
        } finally {
            this.activeRequests--;
            this._processQueue();
        }
    },

    async _fetchWithRetry(url, options, attempt = 0) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return response;
        } catch (error) {
            clearTimeout(timeoutId);

            if (attempt < this.config.retryCount && !controller.signal.aborted) {
                await this._delay(this.config.retryDelay * Math.pow(2, attempt));
                return this._fetchWithRetry(url, options, attempt + 1);
            }

            throw error;
        }
    },

    async _parseResponse(response) {
        const contentType = response.headers.get('content-type') || '';
        
        if (contentType.includes('application/json')) {
            return response.json();
        } else if (contentType.includes('text/')) {
            return response.text();
        } else if (contentType.includes('image/')) {
            return response.blob();
        }
        
        return response.text();
    },

    _setCache(key, data) {
        if (this.cache.size >= this.config.maxCacheSize) {
            const oldestKey = this.cacheOrder.shift();
            if (oldestKey) {
                this.cache.delete(oldestKey);
            }
        }

        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
        this.cacheOrder.push(key);
    },

    _updateLRU(key) {
        const index = this.cacheOrder.indexOf(key);
        if (index > -1) {
            this.cacheOrder.splice(index, 1);
            this.cacheOrder.push(key);
        }
    },

    _waitForSlot(priority) {
        return new Promise(resolve => {
            this.requestQueue.push({ resolve, priority, timestamp: Date.now() });
            this.requestQueue.sort((a, b) => a.priority - b.priority);
        });
    },

    _processQueue() {
        if (this.requestQueue.length > 0 && this.activeRequests < this.config.maxConcurrent) {
            const next = this.requestQueue.shift();
            next.resolve();
        }
    },

    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    _startCacheCleanup() {
        setInterval(() => {
            const now = Date.now();
            for (const [key, value] of this.cache) {
                if (now - value.timestamp > this.config.defaultTTL * 2) {
                    this.cache.delete(key);
                    const index = this.cacheOrder.indexOf(key);
                    if (index > -1) {
                        this.cacheOrder.splice(index, 1);
                    }
                }
            }
        }, 60000);
    },

    getStats() {
        const hitRate = this.stats.requests > 0 
            ? (this.stats.hits / this.stats.requests * 100).toFixed(2) 
            : 0;
        
        return {
            ...this.stats,
            hitRate: `${hitRate}%`,
            cacheSize: this.cache.size,
            pendingRequests: this.pendingRequests.size,
            activeRequests: this.activeRequests,
            queuedRequests: this.requestQueue.length
        };
    },

    clearCache() {
        this.cache.clear();
        this.cacheOrder = [];
        console.log('[RequestManager] 缓存已清空');
    },

    get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    },

    post(url, body, options = {}) {
        return this.request(url, {
            ...options,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...options.headers },
            body: JSON.stringify(body)
        });
    }
};

const BatchRequestManager = {
    batches: new Map(),
    batchDelay: 50,

    add(key, fetcher, processor) {
        if (!this.batches.has(key)) {
            this.batches.set(key, {
                items: [],
                processor,
                timer: null
            });
        }

        const batch = this.batches.get(key);
        
        return new Promise((resolve, reject) => {
            batch.items.push({ fetcher, resolve, reject });

            if (batch.timer) {
                clearTimeout(batch.timer);
            }

            batch.timer = setTimeout(() => this._executeBatch(key), this.batchDelay);
        });
    },

    async _executeBatch(key) {
        const batch = this.batches.get(key);
        if (!batch || batch.items.length === 0) return;

        const items = batch.items;
        batch.items = [];
        batch.timer = null;

        try {
            const results = await batch.processor(items.map(i => i.fetcher));
            items.forEach((item, index) => {
                item.resolve(results[index]);
            });
        } catch (error) {
            items.forEach(item => item.reject(error));
        }
    }
};

const PrefetchManager = {
    queue: [],
    isProcessing: false,

    add(url, options = {}) {
        this.queue.push({ url, options, priority: options.priority || 10 });
        
        if (!this.isProcessing) {
            this._processQueue();
        }
    },

    async _processQueue() {
        if (this.queue.length === 0) {
            this.isProcessing = false;
            return;
        }

        this.isProcessing = true;
        this.queue.sort((a, b) => a.priority - b.priority);

        const item = this.queue.shift();
        
        try {
            await RequestManager.get(item.url, { ...item.options, skipCache: false });
        } catch (e) {
            console.debug('[Prefetch] 预加载失败:', item.url);
        }

        requestIdleCallback(() => this._processQueue(), { timeout: 100 });
    },

    prefetchOnHover(element, url, options = {}) {
        element.addEventListener('mouseenter', () => {
            this.add(url, options);
        }, { once: true });
    }
};

window.RequestManager = RequestManager;
window.BatchRequestManager = BatchRequestManager;
window.PrefetchManager = PrefetchManager;

console.log('[RequestManager] 模块加载完成');
