/**
 * 记忆管理服务模块
 * 
 * 提供记忆相关的业务逻辑，包括：
 * - 添加记忆
 * - 删除记忆
 * - 获取记忆列表
 * - 搜索记忆
 * - 获取相关记忆
 */

const MemoryService = (function() {
    // API基础URL
    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001`;
    
    // 记忆分类
    const MEMORY_CATEGORIES = [
        { id: 'general', name: '通用', icon: 'summary' },
        { id: 'personal', name: '个人', icon: 'user' },
        { id: 'work', name: '工作', icon: 'briefcase' },
        { id: 'learning', name: '学习', icon: 'book' },
        { id: 'idea', name: '想法', icon: 'tip' },
        { id: 'important', name: '重要', icon: 'star' }
    ];
    
    /**
     * 初始化记忆服务
     * @returns {Promise<boolean>}
     */
    async function init() {
        try {
            // 加载记忆分类
            window.IntelligentStore.setState({
                memoryCategories: MEMORY_CATEGORIES
            }, 'MemoryService.init');
            
            return true;
        } catch (error) {
            console.error('[MemoryService] 初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 添加记忆
     * @param {string} content - 记忆内容
     * @param {string} category - 分类
     * @param {Array} tags - 标签数组
     * @param {number} importance - 重要性(1-10)
     * @returns {Promise<Object>}
     */
    async function addMemory(content, category = 'general', tags = [], importance = 5) {
        // 验证输入
        const validation = window.IntelligentValidators.validateMemory({
            content, category, importance
        });
        
        if (!validation.valid) {
            return {
                success: false,
                error: Object.values(validation.errors).flat().join(', ')
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/memory`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content,
                    category,
                    tags,
                    importance
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                const currentMemories = window.IntelligentStore.getStateByPath('memories') || [];
                window.IntelligentStore.setState({
                    memories: [result.data, ...currentMemories]
                }, 'MemoryService.addMemory');
            }
            
            return result;
        } catch (error) {
            console.error('[MemoryService] 添加记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 删除记忆
     * @param {string} memoryId - 记忆ID
     * @returns {Promise<Object>}
     */
    async function deleteMemory(memoryId) {
        if (!memoryId) {
            return {
                success: false,
                error: '记忆ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/memory/${memoryId}/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                const currentMemories = window.IntelligentStore.getStateByPath('memories') || [];
                window.IntelligentStore.setState({
                    memories: currentMemories.filter(m => m.id !== memoryId)
                }, 'MemoryService.deleteMemory');
            }
            
            return result;
        } catch (error) {
            console.error('[MemoryService] 删除记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 获取记忆列表
     * @param {string} category - 可选，按分类筛选
     * @param {Object} options - 可选参数
     * @returns {Promise<Object>}
     */
    async function getMemories(category = null, options = {}) {
        try {
            let url = `${API_BASE}/api/memory`;
            const params = new URLSearchParams();
            
            if (category) {
                params.append('category', category);
            }
            
            if (options.limit) {
                params.append('limit', options.limit);
            }
            
            if (options.offset) {
                params.append('offset', options.offset);
            }
            
            if (params.toString()) {
                url += `?${params.toString()}`;
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success && result.data) {
                // 更新本地状态
                window.IntelligentStore.setState({
                    memories: result.data
                }, 'MemoryService.getMemories');
            }
            
            return result;
        } catch (error) {
            console.error('[MemoryService] 获取记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接',
                data: []
            };
        }
    }
    
    /**
     * 搜索记忆
     * @param {string} query - 搜索关键词
     * @param {Object} options - 可选参数
     * @returns {Promise<Object>}
     */
    async function searchMemories(query, options = {}) {
        if (!query || query.trim().length === 0) {
            return {
                success: true,
                data: []
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/memory/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query.trim(),
                    limit: options.limit || 10,
                    threshold: options.threshold || 0.7
                })
            });
            
            const result = await response.json();
            return result;
        } catch (error) {
            console.error('[MemoryService] 搜索记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接',
                data: []
            };
        }
    }
    
    /**
     * 获取相关记忆
     * @param {string} conversationId - 会话ID
     * @param {string} query - 查询内容
     * @param {number} limit - 返回数量限制
     * @returns {Promise<Object>}
     */
    async function getRelatedMemories(conversationId, query, limit = 5) {
        try {
            const response = await fetch(`${API_BASE}/api/memory/related`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    query: query,
                    limit: limit
                })
            });
            
            const result = await response.json();
            return result;
        } catch (error) {
            console.error('[MemoryService] 获取相关记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接',
                data: []
            };
        }
    }
    
    /**
     * 更新记忆
     * @param {string} memoryId - 记忆ID
     * @param {Object} updates - 更新内容
     * @returns {Promise<Object>}
     */
    async function updateMemory(memoryId, updates) {
        if (!memoryId) {
            return {
                success: false,
                error: '记忆ID不能为空'
            };
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/memory/${memoryId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地状态
                const currentMemories = window.IntelligentStore.getStateByPath('memories') || [];
                const updatedMemories = currentMemories.map(m => 
                    m.id === memoryId ? { ...m, ...updates } : m
                );
                window.IntelligentStore.setState({
                    memories: updatedMemories
                }, 'MemoryService.updateMemory');
            }
            
            return result;
        } catch (error) {
            console.error('[MemoryService] 更新记忆失败:', error);
            return {
                success: false,
                error: '网络错误，请检查服务连接'
            };
        }
    }
    
    /**
     * 获取记忆分类列表
     * @returns {Array}
     */
    function getCategories() {
        return MEMORY_CATEGORIES;
    }
    
    /**
     * 根据ID获取分类信息
     * @param {string} categoryId - 分类ID
     * @returns {Object|null}
     */
    function getCategoryById(categoryId) {
        return MEMORY_CATEGORIES.find(c => c.id === categoryId) || null;
    }
    
    // 公共API
    return {
        init,
        addMemory,
        deleteMemory,
        getMemories,
        searchMemories,
        getRelatedMemories,
        updateMemory,
        getCategories,
        getCategoryById
    };
})();

// 导出模块
window.MemoryService = MemoryService;
