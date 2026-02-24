/**
 * 对话模式管理器
 * 处理成人模式的切换和参数应用
 */

const ConversationMode = {
    STANDARD: 'standard',
    ADULT: 'adult',
    
    async getMode() {
        try {
            const apiBase = window.API?.config?.apiBaseUrl || `http://${window.location.hostname || 'localhost'}:5001`;
            const response = await fetch(`${apiBase}/api/conversation/mode`);
            const data = await response.json();
            if (data.success) {
                return data.data;
            }
            return null;
        } catch (error) {
            console.error('获取对话模式失败:', error);
            return null;
        }
    },
    
    async setMode(mode) {
        try {
            const apiBase = window.API?.config?.apiBaseUrl || `http://${window.location.hostname || 'localhost'}:5001`;
            const response = await fetch(`${apiBase}/api/conversation/mode`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ mode: mode })
            });
            const data = await response.json();
            if (data.success) {
                // 重新加载系统提示词
                if (window.App && window.App.loadSystemPrompt) {
                    await window.App.loadSystemPrompt();
                }
                return data.data;
            }
            return null;
        } catch (error) {
            console.error('设置对话模式失败:', error);
            return null;
        }
    },
    
    async listModes() {
        try {
            const apiBase = window.API?.config?.apiBaseUrl || `http://${window.location.hostname || 'localhost'}:5001`;
            const response = await fetch(`${apiBase}/api/conversation/modes`);
            const data = await response.json();
            if (data.success) {
                return data.data;
            }
            return [];
        } catch (error) {
            console.error('获取对话模式列表失败:', error);
            return [];
        }
    },
    
    getModeDisplayName(mode) {
        const displayNames = {
            'standard': '标准模式',
            'adult': '成人模式'
        };
        return displayNames[mode] || mode;
    },
    
    getModeDescription(mode) {
        const descriptions = {
            'standard': '严格的内容过滤，适合通用场景',
            'adult': '宽松的交流政策，更自由的表达'
        };
        return descriptions[mode] || '';
    }
};

// 导出到全局
window.ConversationMode = ConversationMode;
