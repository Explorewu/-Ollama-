/**
 * 智能功能状态管理模块
 * 
 * 提供集中式的状态管理，支持：
 * - 状态获取和更新
 * - 状态变更订阅
 * - 状态持久化（可选）
 */

const IntelligentStore = (function() {
    // 初始状态
    const initialState = {
        // 录音相关状态
        isRecording: false,
        mediaRecorder: null,
        audioChunks: [],
        
        // 服务状态
        serviceStatus: 'checking', // 'checking' | 'connected' | 'disconnected'
        retryCount: 0,
        
        // UI状态
        panels: {
            memory: { visible: false, loading: false },
            summary: { visible: false, loading: false },
            context: { visible: false, loading: false },
            voice: { visible: false, loading: false }
        },
        
        // 数据缓存
        memories: [],
        conversations: [],
        contextConfig: null,
        
        // 初始化状态
        isInitialized: false,
        initPromise: null
    };
    
    // 当前状态
    let state = { ...initialState };
    
    // 订阅者集合
    const subscribers = new Set();
    
    /**
     * 获取当前状态（深拷贝）
     * @returns {Object} 当前状态的深拷贝
     */
    function getState() {
        return JSON.parse(JSON.stringify(state));
    }
    
    /**
     * 获取特定路径的状态
     * @param {string} path - 状态路径，如 'panels.memory.visible'
     * @returns {any} 状态值
     */
    function getStateByPath(path) {
        const keys = path.split('.');
        let value = state;
        
        for (const key of keys) {
            if (value === null || value === undefined) {
                return undefined;
            }
            value = value[key];
        }
        
        return value;
    }
    
    /**
     * 更新状态
     * @param {Object} updates - 要更新的状态对象
     * @param {string} [source] - 更新来源，用于调试
     */
    function setState(updates, source = 'unknown') {
        const prevState = { ...state };
        state = deepMerge(state, updates);
        
        // 通知所有订阅者
        notifySubscribers(prevState, state, source);
    }
    
    /**
     * 设置特定路径的状态
     * @param {string} path - 状态路径
     * @param {any} value - 状态值
     * @param {string} [source] - 更新来源
     */
    function setStateByPath(path, value, source = 'unknown') {
        const keys = path.split('.');
        const updates = {};
        let current = updates;
        
        for (let i = 0; i < keys.length - 1; i++) {
            current[keys[i]] = {};
            current = current[keys[i]];
        }
        
        current[keys[keys.length - 1]] = value;
        setState(updates, source);
    }
    
    /**
     * 订阅状态变更
     * @param {Function} callback - 回调函数，接收 (newState, prevState, source)
     * @returns {Function} 取消订阅函数
     */
    function subscribe(callback) {
        if (typeof callback !== 'function') {
            console.warn('[IntelligentStore] 订阅者必须是函数');
            return () => {};
        }
        
        subscribers.add(callback);
        
        // 立即执行一次，让订阅者获取初始状态
        callback(state, state, 'init');
        
        // 返回取消订阅函数
        return () => {
            subscribers.delete(callback);
        };
    }
    
    /**
     * 订阅特定路径的状态变更
     * @param {string} path - 状态路径
     * @param {Function} callback - 回调函数
     * @returns {Function} 取消订阅函数
     */
    function subscribeToPath(path, callback) {
        let prevValue = getStateByPath(path);
        
        return subscribe((newState, prevState, source) => {
            const newValue = getStateByPath(path);
            if (newValue !== prevValue) {
                prevValue = newValue;
                callback(newValue, prevValue, source);
            }
        });
    }
    
    /**
     * 通知所有订阅者
     * @private
     */
    function notifySubscribers(prevState, newState, source) {
        subscribers.forEach(callback => {
            try {
                callback(newState, prevState, source);
            } catch (error) {
                console.error('[IntelligentStore] 订阅者执行失败:', error);
            }
        });
    }
    
    /**
     * 深度合并对象
     * @private
     */
    function deepMerge(target, source) {
        const result = { ...target };
        
        for (const key in source) {
            if (source.hasOwnProperty(key)) {
                if (isPlainObject(source[key]) && isPlainObject(result[key])) {
                    result[key] = deepMerge(result[key], source[key]);
                } else {
                    result[key] = source[key];
                }
            }
        }
        
        return result;
    }
    
    /**
     * 检查是否为普通对象
     * @private
     */
    function isPlainObject(value) {
        return Object.prototype.toString.call(value) === '[object Object]';
    }
    
    /**
     * 重置状态到初始值
     * @param {string} [path] - 可选，指定要重置的路径
     */
    function resetState(path = null) {
        if (path) {
            const keys = path.split('.');
            let initialValue = initialState;
            
            for (const key of keys) {
                if (initialValue === undefined) {
                    return;
                }
                initialValue = initialValue[key];
            }
            
            setStateByPath(path, JSON.parse(JSON.stringify(initialValue)), 'reset');
        } else {
            state = { ...initialState };
            notifySubscribers(state, state, 'reset');
        }
    }
    
    /**
     * 获取订阅者数量
     * @returns {number}
     */
    function getSubscriberCount() {
        return subscribers.size;
    }
    
    // 公共API
    return {
        getState,
        getStateByPath,
        setState,
        setStateByPath,
        subscribe,
        subscribeToPath,
        resetState,
        getSubscriberCount
    };
})();

// 导出模块
window.IntelligentStore = IntelligentStore;
