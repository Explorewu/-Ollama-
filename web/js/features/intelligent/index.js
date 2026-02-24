/**
 * 智能功能模块主入口
 *
 * 重构后的 IntelligentFeatures 模块，采用职责分离设计：
 * - 状态管理：state/store.js
 * - 业务服务：services/*.js
 * - UI组件：ui/*.js
 * - 工具函数：utils/*.js
 *
 * 此文件作为兼容层，保持与原 intelligent.js 相同的API接口
 */

const IntelligentModule = (function() {
    // 模块加载状态
    let modulesLoaded = false;
    let initPromise = null;

    // 模块引用
    let store, formatters, validators;
    let memoryService, summaryService, contextService, voiceService;

    /**
     * 动态加载脚本
     * @private
     */
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * 加载所有依赖模块
     * @private
     */
    async function loadModules() {
        if (modulesLoaded) return;

        const basePath = 'js/features/intelligent';

        // 按依赖顺序加载模块
        const modules = [
            // 基础模块
            `${basePath}/state/store.js`,
            `${basePath}/utils/formatters.js`,
            `${basePath}/utils/validators.js`,

            // 服务模块
            `${basePath}/services/memory.js`,
            `${basePath}/services/summary.js`,
            `${basePath}/services/context.js`,
            `${basePath}/services/voice.js`
        ];

        for (const module of modules) {
            if (!window[module.split('/').pop().replace('.js', '')]) {
                await loadScript(module);
            }
        }

        // 获取模块引用
        store = window.IntelligentStore;
        formatters = window.IntelligentFormatters;
        validators = window.IntelligentValidators;
        memoryService = window.MemoryService;
        summaryService = window.SummaryService;
        contextService = window.ContextService;
        voiceService = window.VoiceService;

        modulesLoaded = true;
    }

    /**
     * 初始化智能功能模块
     * @returns {Promise<boolean>}
     */
    async function init() {
        if (initPromise) return initPromise;

        initPromise = (async () => {
            try {
                console.log('[IntelligentFeatures] 开始初始化...');

                // 加载模块
                await loadModules();

                // 初始化各个服务
                await Promise.all([
                    memoryService.init(),
                    summaryService.init(),
                    contextService.init(),
                    voiceService.init()
                ]);

                // 更新状态
                store.setState({ isInitialized: true }, 'IntelligentFeatures.init');

                console.log('[IntelligentFeatures] 初始化完成');
                return true;
            } catch (error) {
                console.error('[IntelligentFeatures] 初始化失败:', error);
                return false;
            }
        })();

        return initPromise;
    }

    /**
     * 显示记忆面板
     */
    function showMemoryPanel() {
        store.setStateByPath('panels.memory.visible', true, 'IntelligentFeatures.showMemoryPanel');
    }

    /**
     * 隐藏记忆面板
     */
    function hideMemoryPanel() {
        store.setStateByPath('panels.memory.visible', false, 'IntelligentFeatures.hideMemoryPanel');
    }

    /**
     * 显示摘要面板
     */
    function showSummaryPanel() {
        store.setStateByPath('panels.summary.visible', true, 'IntelligentFeatures.showSummaryPanel');
    }

    /**
     * 隐藏摘要面板
     */
    function hideSummaryPanel() {
        store.setStateByPath('panels.summary.visible', false, 'IntelligentFeatures.hideSummaryPanel');
    }

    /**
     * 显示上下文设置面板
     */
    function showContextSettings() {
        store.setStateByPath('panels.context.visible', true, 'IntelligentFeatures.showContextSettings');
    }

    /**
     * 隐藏上下文设置面板
     */
    function hideContextSettings() {
        store.setStateByPath('panels.context.visible', false, 'IntelligentFeatures.hideContextSettings');
    }

    /**
     * 显示语音输入面板
     */
    function showVoicePanel() {
        store.setStateByPath('panels.voice.visible', true, 'IntelligentFeatures.showVoicePanel');
    }

    /**
     * 隐藏语音输入面板
     */
    function hideVoicePanel() {
        store.setStateByPath('panels.voice.visible', false, 'IntelligentFeatures.hideVoicePanel');
    }

    /**
     * 添加新记忆
     * @param {string} content - 记忆内容
     * @param {string} category - 分类
     * @param {Array} tags - 标签
     * @param {number} importance - 重要性
     * @returns {Promise<Object>}
     */
    async function addNewMemory(content, category = 'general', tags = [], importance = 5) {
        await init();
        return memoryService.addMemory(content, category, tags, importance);
    }

    /**
     * 删除记忆
     * @param {string} memoryId - 记忆ID
     * @returns {Promise<Object>}
     */
    async function removeMemory(memoryId) {
        await init();
        return memoryService.deleteMemory(memoryId);
    }

    /**
     * 加载对话摘要
     * @param {string} conversationId - 会话ID
     * @returns {Promise<Object>}
     */
    async function loadConversationSummary(conversationId) {
        await init();
        return summaryService.getSummaries(conversationId);
    }

    /**
     * 保存上下文设置
     * @param {Object} config - 配置对象
     * @returns {Promise<Object>}
     */
    async function saveContextSettings(config) {
        await init();
        return contextService.saveConfig(config);
    }

    /**
     * 清空上下文数据
     * @param {string} conversationId - 可选，会话ID
     * @returns {Promise<Object>}
     */
    async function clearContextData(conversationId = null) {
        await init();
        return contextService.clearContext(conversationId);
    }

    /**
     * 切换录音状态
     * @returns {Promise<Object>}
     */
    async function toggleRecording() {
        await init();
        return voiceService.toggleRecording();
    }

    /**
     * 开始录音
     * @returns {Promise<Object>}
     */
    async function startRecording() {
        await init();
        return voiceService.startRecording();
    }

    /**
     * 停止录音
     * @returns {Promise<Object>}
     */
    async function stopRecording() {
        await init();
        return voiceService.stopRecording();
    }

    /**
     * 获取记忆列表
     * @param {string} category - 可选，分类筛选
     * @returns {Promise<Object>}
     */
    async function getMemories(category = null) {
        await init();
        return memoryService.getMemories(category);
    }

    /**
     * 搜索记忆
     * @param {string} query - 搜索关键词
     * @returns {Promise<Object>}
     */
    async function searchMemories(query) {
        await init();
        return memoryService.searchMemories(query);
    }

    /**
     * 生成对话摘要
     * @param {string} conversationId - 会话ID
     * @param {Object} options - 可选参数
     * @returns {Promise<Object>}
     */
    async function generateSummary(conversationId, options = {}) {
        await init();
        return summaryService.generateSummary(conversationId, options);
    }

    /**
     * 获取当前配置
     * @returns {Object}
     */
    function getContextConfig() {
        if (!contextService) return {};
        return contextService.getConfig();
    }

    /**
     * 重置配置
     * @returns {Promise<Object>}
     */
    async function resetContextConfig() {
        await init();
        return contextService.resetConfig();
    }

    /**
     * 获取服务状态
     * @returns {string}
     */
    function getServiceStatus() {
        return store.getStateByPath('serviceStatus') || 'checking';
    }

    /**
     * 检查是否正在录音
     * @returns {boolean}
     */
    function isRecording() {
        return store.getStateByPath('isRecording') || false;
    }

    // 公共API（保持与原 intelligent.js 兼容）
    return {
        // 初始化
        init,

        // 面板控制
        showMemoryPanel,
        hideMemoryPanel,
        showSummaryPanel,
        hideSummaryPanel,
        showContextSettings,
        hideContextSettings,
        showVoicePanel,
        hideVoicePanel,

        // 记忆功能
        addNewMemory,
        removeMemory,
        getMemories,
        searchMemories,

        // 摘要功能
        loadConversationSummary,
        generateSummary,

        // 上下文功能
        saveContextSettings,
        clearContextData,
        getContextConfig,
        resetContextConfig,

        // 语音功能
        toggleRecording,
        startRecording,
        stopRecording,
        isRecording,

        // 状态
        getServiceStatus,

        // 内部模块（供高级使用）
        get _store() { return store; },
        get _formatters() { return formatters; },
        get _validators() { return validators; },
        get _memoryService() { return memoryService; },
        get _summaryService() { return summaryService; },
        get _contextService() { return contextService; },
        get _voiceService() { return voiceService; }
    };
})();

// 导出到全局
window.IntelligentModule = IntelligentModule;

// 自动初始化（如果DOM已加载）
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        IntelligentModule.init().catch(console.error);
    });
} else {
    IntelligentModule.init().catch(console.error);
}
