/**
 * 对话摘要服务模块
 * 
 * 提供对话摘要相关的业务逻辑，包括：
 * - 生成对话摘要
 * - 获取摘要列表
 * - 导出摘要
 * - 删除摘要
 */

const SummaryService = (function() {
    // API基础URL
    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001`;
    
    /**
     * 初始化摘要服务
     * @returns {Promise<boolean>}
     */
    async function init() {
        try {
            console.log('[SummaryService] 初始化完成');
            return true;
        } catch (error) {
            console.error('[SummaryService] 初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 生成对话摘要
     * @param {string} conversationId - 会话ID
     * @param {Object} options - 可选参数
     * @returns {Promise<Object>}
     */
    async function generateSummary(conversationId, options = {}) {
        if (!conversationId) {
            return {
                success: false,
                error: '会话ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    max_length: options.maxLength || 500,
                    style: options.style || 'concise' // concise, detailed, bullet_points
                })
            });
            
            const result = await response.json();
            
            if (result.success && result.data) {
                // 更新本地状态
                const currentSummaries = window.IntelligentStore.getStateByPath('summaries') || [];
                window.IntelligentStore.setState({
                    summaries: [result.data, ...currentSummaries]
                }, 'SummaryService.generateSummary');
            }
            
            return result;
        } catch (error) {
            console.error('[SummaryService] 生成摘要失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 获取对话摘要列表
     * @param {string} conversationId - 会话ID
     * @returns {Promise<Object>}
     */
    async function getSummaries(conversationId) {
        if (!conversationId) {
            return {
                success: false,
                error: '会话ID不能为空',
                data: []
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary?conversation_id=${conversationId}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success && result.data) {
                // 更新本地状态
                window.IntelligentStore.setState({
                    summaries: result.data
                }, 'SummaryService.getSummaries');
            }
            
            return result;
        } catch (error) {
            console.error('[SummaryService] 获取摘要失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接',
                data: []
            };
        }
    }
    
    /**
     * 获取单个摘要详情
     * @param {string} summaryId - 摘要ID
     * @returns {Promise<Object>}
     */
    async function getSummaryById(summaryId) {
        if (!summaryId) {
            return {
                success: false,
                error: '摘要ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary/${summaryId}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            return await response.json();
        } catch (error) {
            console.error('[SummaryService] 获取摘要详情失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 删除摘要
     * @param {string} summaryId - 摘要ID
     * @returns {Promise<Object>}
     */
    async function deleteSummary(summaryId) {
        if (!summaryId) {
            return {
                success: false,
                error: '摘要ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary/${summaryId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                const currentSummaries = window.IntelligentStore.getStateByPath('summaries') || [];
                window.IntelligentStore.setState({
                    summaries: currentSummaries.filter(s => s.id !== summaryId)
                }, 'SummaryService.deleteSummary');
            }
            
            return result;
        } catch (error) {
            console.error('[SummaryService] 删除摘要失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 导出摘要
     * @param {string} summaryId - 摘要ID
     * @param {string} format - 导出格式 (markdown, text, json)
     * @returns {Promise<Object>}
     */
    async function exportSummary(summaryId, format = 'markdown') {
        if (!summaryId) {
            return {
                success: false,
                error: '摘要ID不能为空'
            };
        }
        
        const validFormats = ['markdown', 'text', 'json'];
        if (!validFormats.includes(format)) {
            return {
                success: false,
                error: `不支持的导出格式: ${format}`
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary/${summaryId}/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format })
            });
            
            return await response.json();
        } catch (error) {
            console.error('[SummaryService] 导出摘要失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 批量导出摘要
     * @param {Array<string>} summaryIds - 摘要ID数组
     * @param {string} format - 导出格式
     * @returns {Promise<Object>}
     */
    async function batchExportSummaries(summaryIds, format = 'markdown') {
        if (!Array.isArray(summaryIds) || summaryIds.length === 0) {
            return {
                success: false,
                error: '请选择要导出的摘要'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/summary/batch_export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    summary_ids: summaryIds,
                    format
                })
            });
            
            return await response.json();
        } catch (error) {
            console.error('[SummaryService] 批量导出摘要失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    // 公共API
    return {
        init,
        generateSummary,
        getSummaries,
        getSummaryById,
        deleteSummary,
        exportSummary,
        batchExportSummaries
    };
})();

// 导出模块
window.SummaryService = SummaryService;
