/**
 * API帮助工具模块 - API Helper
 * 
 * 提供前端API调用的统一封装，包括：
 * - 统一请求处理
 * - 错误处理
 * - 响应格式化
 * - 请求拦截
 * 
 * 此模块不依赖任何外部框架，仅使用原生JavaScript
 * 
 * 作者：AI Assistant
 * 日期：2026-02-03
 * 版本：v1.0
 */

const ApiHelper = (function() {
    'use strict';

    // 默认配置
    const DEFAULT_CONFIG = {
        baseURL: `http://${window.location.hostname || 'localhost'}:5001`,
        timeout: 30000,
        retries: 3,
        retryDelay: 1000,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    // 当前配置
    let config = { ...DEFAULT_CONFIG };

    // 请求拦截器
    const requestInterceptors = [];
    // 响应拦截器
    const responseInterceptors = [];

    /**
     * 配置API帮助工具
     * @param {Object} options - 配置选项
     */
    function configure(options) {
        config = { ...config, ...options };
    }

    /**
     * 添加请求拦截器
     * @param {Function} interceptor - 拦截器函数
     */
    function addRequestInterceptor(interceptor) {
        requestInterceptors.push(interceptor);
    }

    /**
     * 添加响应拦截器
     * @param {Function} interceptor - 拦截器函数
     */
    function addResponseInterceptor(interceptor) {
        responseInterceptors.push(interceptor);
    }

    /**
     * 构建完整URL
     * @param {string} url - 相对或绝对URL
     * @returns {string} 完整URL
     */
    function buildURL(url) {
        if (url.startsWith('http')) {
            return url;
        }
        const baseURL = config.baseURL.replace(/\/$/, '');
        const path = url.startsWith('/') ? url : '/' + url;
        return baseURL + path;
    }

    /**
     * 应用请求拦截器
     * @param {Object} requestConfig - 请求配置
     * @returns {Object} 处理后的配置
     */
    async function applyRequestInterceptors(requestConfig) {
        let result = requestConfig;
        for (const interceptor of requestInterceptors) {
            result = await interceptor(result);
        }
        return result;
    }

    /**
     * 应用响应拦截器
     * @param {Object} response - 响应对象
     * @returns {Object} 处理后的响应
     */
    async function applyResponseInterceptors(response) {
        let result = response;
        for (const interceptor of responseInterceptors) {
            result = await interceptor(result);
        }
        return result;
    }

    /**
     * 延迟函数
     * @param {number} ms - 延迟毫秒数
     * @returns {Promise}
     */
    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 发送HTTP请求
     * @param {string} url - 请求URL
     * @param {Object} options - 请求选项
     * @returns {Promise} 响应Promise
     */
    async function request(url, options = {}) {
        const requestConfig = {
            method: 'GET',
            headers: { ...config.headers },
            ...options,
            url: buildURL(url)
        };

        // 应用请求拦截器
        const finalConfig = await applyRequestInterceptors(requestConfig);

        // 构建fetch选项
        const fetchOptions = {
            method: finalConfig.method,
            headers: finalConfig.headers,
            signal: finalConfig.signal
        };

        // 添加请求体
        if (finalConfig.body) {
            if (finalConfig.body instanceof FormData) {
                delete fetchOptions.headers['Content-Type'];
                fetchOptions.body = finalConfig.body;
            } else if (typeof finalConfig.body === 'object') {
                fetchOptions.body = JSON.stringify(finalConfig.body);
            } else {
                fetchOptions.body = finalConfig.body;
            }
        }

        // 创建AbortController用于超时
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), config.timeout);
        fetchOptions.signal = controller.signal;

        let lastError;
        
        // 重试逻辑
        for (let attempt = 0; attempt < config.retries; attempt++) {
            try {
                const response = await fetch(finalConfig.url, fetchOptions);
                clearTimeout(timeoutId);

                // 解析响应
                let data;
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    data = await response.json();
                } else {
                    data = await response.text();
                }

                // 构建响应对象
                const responseObj = {
                    status: response.status,
                    statusText: response.statusText,
                    headers: response.headers,
                    data: data,
                    ok: response.ok,
                    url: response.url
                };

                // 应用响应拦截器
                const finalResponse = await applyResponseInterceptors(responseObj);

                // 检查HTTP错误
                if (!response.ok) {
                    throw new ApiError(
                        data.message || data.error || `HTTP ${response.status}`,
                        response.status,
                        data
                    );
                }

                return finalResponse;

            } catch (error) {
                lastError = error;
                
                // 如果是AbortError（超时），直接抛出
                if (error.name === 'AbortError') {
                    throw new ApiError('请求超时', 408);
                }
                
                // 如果不是网络错误，直接抛出
                if (error instanceof ApiError) {
                    throw error;
                }

                // 等待后重试
                if (attempt < config.retries - 1) {
                    await delay(config.retryDelay * (attempt + 1));
                }
            }
        }

        throw lastError || new ApiError('请求失败', 0);
    }

    /**
     * GET请求
     * @param {string} url - 请求URL
     * @param {Object} params - 查询参数
     * @param {Object} options - 其他选项
     * @returns {Promise} 响应Promise
     */
    function get(url, params = null, options = {}) {
        let fullURL = url;
        if (params) {
            const queryString = new URLSearchParams(params).toString();
            fullURL += (url.includes('?') ? '&' : '?') + queryString;
        }
        return request(fullURL, { ...options, method: 'GET' });
    }

    /**
     * POST请求
     * @param {string} url - 请求URL
     * @param {Object} data - 请求数据
     * @param {Object} options - 其他选项
     * @returns {Promise} 响应Promise
     */
    function post(url, data = null, options = {}) {
        return request(url, { ...options, method: 'POST', body: data });
    }

    /**
     * PUT请求
     * @param {string} url - 请求URL
     * @param {Object} data - 请求数据
     * @param {Object} options - 其他选项
     * @returns {Promise} 响应Promise
     */
    function put(url, data = null, options = {}) {
        return request(url, { ...options, method: 'PUT', body: data });
    }

    /**
     * DELETE请求
     * @param {string} url - 请求URL
     * @param {Object} options - 其他选项
     * @returns {Promise} 响应Promise
     */
    function del(url, options = {}) {
        return request(url, { ...options, method: 'DELETE' });
    }

    /**
     * API错误类
     */
    class ApiError extends Error {
        constructor(message, status = 0, data = null) {
            super(message);
            this.name = 'ApiError';
            this.status = status;
            this.data = data;
        }
    }

    /**
     * 处理API错误
     * @param {Error} error - 错误对象
     * @param {Object} options - 处理选项
     * @returns {Object} 错误信息对象
     */
    function handleError(error, options = {}) {
        const defaultOptions = {
            showToast: true,
            logError: true,
            defaultMessage: '操作失败，请稍后重试'
        };
        const opts = { ...defaultOptions, ...options };

        let errorInfo = {
            message: opts.defaultMessage,
            status: 0,
            type: 'unknown'
        };

        if (error instanceof ApiError) {
            errorInfo = {
                message: error.message,
                status: error.status,
                type: 'api',
                data: error.data
            };
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            errorInfo = {
                message: '网络连接失败，请检查网络',
                status: 0,
                type: 'network'
            };
        } else if (error.name === 'AbortError') {
            errorInfo = {
                message: '请求超时，请稍后重试',
                status: 408,
                type: 'timeout'
            };
        }

        // 记录错误
        if (opts.logError) {
            console.error('[ApiHelper] 请求错误:', errorInfo, error);
        }

        // 显示提示
        if (opts.showToast && typeof Toast !== 'undefined') {
            Toast.error(errorInfo.message);
        }

        return errorInfo;
    }

    /**
     * 创建API客户端
     * @param {string} baseURL - 基础URL
     * @param {Object} defaultOptions - 默认选项
     * @returns {Object} API客户端对象
     */
    function createClient(baseURL, defaultOptions = {}) {
        const clientConfig = {
            baseURL,
            ...DEFAULT_CONFIG,
            ...defaultOptions
        };

        return {
            get: (url, params, options) => {
                const originalConfig = config;
                config = clientConfig;
                const promise = get(url, params, options);
                config = originalConfig;
                return promise;
            },
            post: (url, data, options) => {
                const originalConfig = config;
                config = clientConfig;
                const promise = post(url, data, options);
                config = originalConfig;
                return promise;
            },
            put: (url, data, options) => {
                const originalConfig = config;
                config = clientConfig;
                const promise = put(url, data, options);
                config = originalConfig;
                return promise;
            },
            delete: (url, options) => {
                const originalConfig = config;
                config = clientConfig;
                const promise = del(url, options);
                config = originalConfig;
                return promise;
            }
        };
    }

    // 公共API
    return {
        // 配置
        configure,
        addRequestInterceptor,
        addResponseInterceptor,
        
        // 请求方法
        request,
        get,
        post,
        put,
        delete: del,
        
        // 错误处理
        ApiError,
        handleError,
        
        // 客户端
        createClient,
        
        // 工具
        buildURL
    };
})();

// 如果支持模块导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ApiHelper;
}
