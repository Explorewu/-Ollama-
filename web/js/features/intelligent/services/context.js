/**
 * 上下文配置服务模块
 * 
 * 提供上下文配置相关的业务逻辑，包括：
 * - 获取配置
 * - 保存配置
 * - 重置配置
 * - 清空上下文
 */

const ContextService = (function() {
    // API基础URL
    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001`;
    
    // 默认配置
    const DEFAULT_CONFIG = {
        max_total_tokens: 8000,
        regular_window_size: 10,
        core_messages_max: 5,
        min_importance_threshold: 0.7,
        enable_memory: true,
        enable_summary: true,
        enable_auto_save: true
    };
    
    /**
     * 初始化上下文服务
     * @returns {Promise<boolean>}
     */
    async function init() {
        try {
            // 加载配置
            await loadConfig();
            return true;
        } catch (error) {
            console.error('[ContextService] 初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 获取当前配置
     * @returns {Object}
     */
    function getConfig() {
        return window.IntelligentStore.getStateByPath('contextConfig') || DEFAULT_CONFIG;
    }
    
    /**
     * 从服务器加载配置
     * @returns {Promise<Object>}
     */
    async function loadConfig() {
        try {
            const response = await fetch(`${API_BASE}/api/context/config`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success && result.data) {
                // 合并默认配置和服务器配置
                const config = { ...DEFAULT_CONFIG, ...result.data };
                window.IntelligentStore.setState({
                    contextConfig: config
                }, 'ContextService.loadConfig');
                return { success: true, data: config };
            }
            
            // 如果服务器没有配置，使用默认配置
            window.IntelligentStore.setState({
                contextConfig: DEFAULT_CONFIG
            }, 'ContextService.loadConfig');
            
            return { success: true, data: DEFAULT_CONFIG };
        } catch (error) {
            console.error('[ContextService] 加载配置失败:', error);
            // 使用默认配置
            window.IntelligentStore.setState({
                contextConfig: DEFAULT_CONFIG
            }, 'ContextService.loadConfig');
            
            return {
                success: false,
                error: '网络错误，使用默认配置',
                data: DEFAULT_CONFIG
            };
        }
    }
    
    /**
     * 保存配置
     * @param {Object} config - 配置对象
     * @returns {Promise<Object>}
     */
    async function saveConfig(config) {
        // 验证配置
        const validation = window.IntelligentValidators.validateContextConfig(config);
        
        if (!validation.valid) {
            return {
                success: false,
                error: Object.values(validation.errors).flat().join(', ')
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/context/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                window.IntelligentStore.setState({
                    contextConfig: config
                }, 'ContextService.saveConfig');
            }
            
            return result;
        } catch (error) {
            console.error('[ContextService] 保存配置失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 重置配置为默认值
     * @returns {Promise<Object>}
     */
    async function resetConfig() {
        try {
            const response = await fetch(`${API_BASE}/api/context/config/reset`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                window.IntelligentStore.setState({
                    contextConfig: DEFAULT_CONFIG
                }, 'ContextService.resetConfig');
            }
            
            return result;
        } catch (error) {
            console.error('[ContextService] 重置配置失败:', error);
            // 即使服务器请求失败，也重置本地配置
            window.IntelligentStore.setState({
                contextConfig: DEFAULT_CONFIG
            }, 'ContextService.resetConfig');
            
            return {
                success: true,
                data: DEFAULT_CONFIG
            };
        }
    }
    
    /**
     * 清空上下文数据
     * @param {string} conversationId - 可选，指定会话ID
     * @returns {Promise<Object>}
     */
    async function clearContext(conversationId = null) {
        try {
            const body = conversationId ? { conversation_id: conversationId } : {};
            
            const response = await fetch(`${API_BASE}/api/context/clear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            return await response.json();
        } catch (error) {
            console.error('[ContextService] 清空上下文失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 获取上下文统计信息
     * @param {string} conversationId - 会话ID
     * @returns {Promise<Object>}
     */
    async function getContextStats(conversationId) {
        if (!conversationId) {
            return {
                success: false,
                error: '会话ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/context/stats?conversation_id=${conversationId}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            return await response.json();
        } catch (error) {
            console.error('[ContextService] 获取上下文统计失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 获取默认配置
     * @returns {Object}
     */
    function getDefaultConfig() {
        return { ...DEFAULT_CONFIG };
    }
    
    // 公共API
    return {
        init,
        getConfig,
        loadConfig,
        saveConfig,
        resetConfig,
        clearContext,
        getContextStats,
        getDefaultConfig
    };
})();

// 导出模块
window.ContextService = ContextService;
