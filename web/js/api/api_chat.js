/**
 * API Chat 配置模块
 * 提供 API 配置管理和 TOKEN 统计功能
 */

const ApiChat = (function() {
    // 默认配置
    const defaultConfig = {
        tokenTracking: {
            enabled: false
        }
    };

    // 当前配置
    let config = { ...defaultConfig };

    /**
     * 初始化模块
     */
    function init() {
        loadConfig();
        console.log('✅ ApiChat 初始化完成');
    }

    /**
     * 加载配置
     */
    function loadConfig() {
        try {
            const saved = localStorage.getItem('api_chat_config');
            if (saved) {
                config = { ...defaultConfig, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.error('加载 ApiChat 配置失败:', e);
        }
    }

    /**
     * 保存配置
     */
    function saveConfig() {
        try {
            localStorage.setItem('api_chat_config', JSON.stringify(config));
        } catch (e) {
            console.error('保存 ApiChat 配置失败:', e);
        }
    }

    /**
     * 获取配置
     * @returns {Object} 当前配置
     */
    function getConfig() {
        return config;
    }

    /**
     * 更新配置
     * @param {Object} newConfig - 新配置
     */
    function updateConfig(newConfig) {
        config = { ...config, ...newConfig };
        saveConfig();
    }

    // 公开 API
    return {
        init,
        getConfig,
        saveConfig,
        updateConfig
    };
})();

// 初始化
if (typeof window !== 'undefined') {
    window.ApiChat = ApiChat;
}
