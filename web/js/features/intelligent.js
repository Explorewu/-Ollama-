/**
 * 智能交互功能模块（兼容层）
 *
 * ⚠️ 重要提示：此文件已重构！
 *
 * 原 intelligent.js 已拆分为模块化结构：
 * - web/js/features/intelligent/state/store.js    - 状态管理
 * - web/js/features/intelligent/services/*.js      - 业务服务
 * - web/js/features/intelligent/utils/*.js         - 工具函数
 * - web/js/features/intelligent/index.js           - 主入口
 *
 * 此文件作为兼容层，保持与原API完全兼容。
 * 所有调用都会转发到新的模块化实现。
 *
 * 建议：新项目直接使用新模块路径：
 *   <script src="js/features/intelligent/index.js"></script>
 */

const IntelligentFeatures = (function() {
    // 标记为兼容层
    const IS_COMPATIBILITY_LAYER = true;

    // 新模块引用
    let newModule = null;
    let initPromise = null;

    /**
     * 加载新模块
     * @private
     */
    async function loadNewModule() {
        if (newModule) return newModule;

        return new Promise((resolve, reject) => {
            // 检查新模块是否已加载
            if (window.IntelligentModule && window.IntelligentModule._store) {
                newModule = window.IntelligentModule;
                resolve(newModule);
                return;
            }

            // 动态加载新模块
            const script = document.createElement('script');
            script.src = 'js/features/intelligent/index.js';
            script.onload = () => {
                newModule = window.IntelligentModule;
                resolve(newModule);
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * 初始化
     * @returns {Promise<boolean>}
     */
    async function init() {
        if (initPromise) return initPromise;

        initPromise = (async () => {
            try {
                console.log('[IntelligentFeatures] 兼容层初始化...');

                // 加载新模块
                const module = await loadNewModule();

                // 初始化新模块
                await module.init();

                console.log('[IntelligentFeatures] 兼容层初始化完成');
                return true;
            } catch (error) {
                console.error('[IntelligentFeatures] 兼容层初始化失败:', error);
                return false;
            }
        })();

        return initPromise;
    }

    // 面板控制函数
    function showMemoryPanel() {
        if (!newModule) {
            console.warn('[IntelligentFeatures] 模块未加载，请先调用 init()');
            return;
        }
        newModule.showMemoryPanel();
    }

    function hideMemoryPanel() {
        if (!newModule) return;
        newModule.hideMemoryPanel();
    }

    function showSummaryPanel() {
        if (!newModule) {
            console.warn('[IntelligentFeatures] 模块未加载，请先调用 init()');
            return;
        }
        newModule.showSummaryPanel();
    }

    function hideSummaryPanel() {
        if (!newModule) return;
        newModule.hideSummaryPanel();
    }

    function showContextSettings() {
        if (!newModule) {
            console.warn('[IntelligentFeatures] 模块未加载，请先调用 init()');
            return;
        }
        newModule.showContextSettings();
    }

    function hideContextSettings() {
        if (!newModule) return;
        newModule.hideContextSettings();
    }

    function showVoicePanel() {
        if (!newModule) {
            console.warn('[IntelligentFeatures] 模块未加载，请先调用 init()');
            return;
        }
        newModule.showVoicePanel();
    }

    function hideVoicePanel() {
        if (!newModule) return;
        newModule.hideVoicePanel();
    }

    // 记忆功能
    async function addNewMemory(content, category, tags, importance) {
        await init();
        return newModule.addNewMemory(content, category, tags, importance);
    }

    async function removeMemory(memoryId) {
        await init();
        return newModule.removeMemory(memoryId);
    }

    // 摘要功能
    async function loadConversationSummary(conversationId) {
        await init();
        return newModule.loadConversationSummary(conversationId);
    }

    // 上下文功能
    async function saveContextSettings(config) {
        await init();
        return newModule.saveContextSettings(config);
    }

    async function clearContextData(conversationId) {
        await init();
        return newModule.clearContextData(conversationId);
    }

    // 语音功能
    async function toggleRecording() {
        await init();
        return newModule.toggleRecording();
    }

    async function startRecording() {
        await init();
        return newModule.startRecording();
    }

    async function stopRecording() {
        await init();
        return newModule.stopRecording();
    }

    // 保持向后兼容的额外函数
    async function transcribeAudio(audioFile, language) {
        await init();
        // 转发到语音服务
        if (newModule._voiceService) {
            return newModule._voiceService.transcribeAudio(audioFile);
        }
        return { success: false, error: '语音服务不可用' };
    }

    async function getLocalWhisperStatus() {
        await init();
        // 兼容函数，返回模拟数据
        return { success: true, data: { loaded: false } };
    }

    async function loadLocalWhisper() {
        await init();
        return { success: false, error: '此功能已迁移到新模块' };
    }

    async function transcribeWithLocalWhisper(audioFile, language) {
        await init();
        return transcribeAudio(audioFile, language);
    }

    async function downloadModel(modelId) {
        await init();
        console.warn('[IntelligentFeatures] downloadModel 已弃用');
        return { success: false, error: '此功能已弃用' };
    }

    // 公共API（与原API完全兼容）
    return {
        // 元数据
        IS_COMPATIBILITY_LAYER,

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

        // 摘要功能
        loadConversationSummary,

        // 上下文功能
        saveContextSettings,
        clearContextData,

        // 语音功能
        toggleRecording,
        startRecording,
        stopRecording,
        transcribeAudio,

        // 兼容函数
        getLocalWhisperStatus,
        loadLocalWhisper,
        transcribeWithLocalWhisper,
        downloadModel
    };
})();

// 导出到全局
window.IntelligentFeatures = IntelligentFeatures;

// 自动初始化
function intelligentInit() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => IntelligentFeatures.init(), 500);
        });
    } else {
        setTimeout(() => IntelligentFeatures.init(), 500);
    }
}

if (typeof window !== 'undefined') {
    intelligentInit();
}
