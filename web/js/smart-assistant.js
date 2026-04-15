/**
 * 轻量级智能情境学习助手
 * 融合方案3（情境感知）和方案5（个性化学习）
 */

class SmartContextLearningAssistant {
    constructor() {
        this.storageKey = 'smart_assistant_data';
        this.maxRecords = 30; // 限制存储记录数
        this.confidenceThreshold = 0.6;
        
        // 初始化各个组件
        this.contextDetector = new SimpleContextDetector();
        this.personalizer = new BasicPersonalizer();
        this.fusionEngine = new LightweightFusionEngine();
        
        // 加载历史数据
        this.loadData();
        
        console.log('🧠 智能情境学习助手已初始化');
    }
    
    // 主要入口方法
    async provideSmartAssistance(userInput, context = {}) {
        try {
            // 获取当前情境
            const currentContext = await this.contextDetector.getCurrentContext(context);
            
            // 获取融合建议
            const recommendation = await this.fusionEngine.getSmartRecommendation(
                userInput, currentContext
            );
            
            // 记录这次交互
            this.recordInteraction(userInput, currentContext, recommendation);
            
            return {
                suggestion: recommendation.action,
                reason: recommendation.reason,
                confidence: recommendation.confidence,
                context: currentContext
            };
            
        } catch (error) {
            console.error('智能助手出错:', error);
            return {
                suggestion: 'default_help',
                reason: '系统暂时无法提供智能建议',
                confidence: 0,
                error: error.message
            };
        }
    }
    
    // 记录用户反馈
    recordUserFeedback(interactionId, feedback) {
        const record = this.findRecordById(interactionId);
        if (record) {
            record.userFeedback = feedback;
            record.feedbackTime = Date.now();
            this.saveData();
        }
    }
    
    // 获取学习统计
    getLearningStats() {
        const records = this.getRecords();
        const totalInteractions = records.length;
        const positiveFeedback = records.filter(r => r.userFeedback === 'positive').length;
        const learningAccuracy = totalInteractions > 0 ? (positiveFeedback / totalInteractions) : 0;
        
        return {
            totalInteractions,
            positiveFeedback,
            learningAccuracy: Math.round(learningAccuracy * 100),
            contextTypes: this.getContextDistribution(records)
        };
    }
    
    // 私有方法
    loadData() {
        try {
            const data = localStorage.getItem(this.storageKey);
            this.records = data ? JSON.parse(data) : [];
        } catch (error) {
            console.warn('加载历史数据失败:', error);
            this.records = [];
        }
    }
    
    saveData() {
        try {
            // 限制数据量
            if (this.records.length > this.maxRecords) {
                this.records = this.records.slice(-this.maxRecords);
            }
            localStorage.setItem(this.storageKey, JSON.stringify(this.records));
        } catch (error) {
            console.warn('保存数据失败:', error);
        }
    }
    
    getRecords() {
        return this.records || [];
    }
    
    recordInteraction(input, context, recommendation) {
        const record = {
            id: this.generateId(),
            timestamp: Date.now(),
            userInput: input,
            context: context,
            recommendation: recommendation,
            userFeedback: null,
            feedbackTime: null
        };
        
        this.records = this.records || [];
        this.records.push(record);
        this.saveData();
    }
    
    findRecordById(id) {
        return this.records.find(r => r.id === id);
    }
    
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    getContextDistribution(records) {
        const distribution = {};
        records.forEach(record => {
            const contextType = this.categorizeContext(record.context);
            distribution[contextType] = (distribution[contextType] || 0) + 1;
        });
        return distribution;
    }
    
    categorizeContext(context) {
        if (context.apps && context.apps.includes('IDE')) return 'coding';
        if (context.timeSlot === 'evening') return 'leisure';
        if (context.topic && context.topic.includes('学习')) return 'study';
        return 'general';
    }
}

// 简单情境检测器
class SimpleContextDetector {
    async getCurrentContext(additionalContext = {}) {
        const context = {
            timeSlot: this.getTimeSlot(),
            apps: this.getOpenApps(),
            topic: this.getCurrentTopic(),
            recentActions: this.getRecentActions(3),
            ...additionalContext
        };
        
        return context;
    }
    
    getTimeSlot() {
        const hour = new Date().getHours();
        if (hour >= 6 && hour < 12) return 'morning';
        if (hour >= 12 && hour < 18) return 'afternoon';
        if (hour >= 18 && hour < 22) return 'evening';
        return 'night';
    }
    
    getOpenApps() {
        // 简化实现：基于当前焦点元素推测
        const activeElement = document.activeElement;
        const apps = [];
        
        if (activeElement && activeElement.id) {
            if (activeElement.id.includes('chat')) apps.push('chat');
            if (activeElement.id.includes('model')) apps.push('model_management');
            if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                apps.push('text_editing');
            }
        }
        
        // 检查当前页面状态
        if (document.querySelector('.chat-overlay.active')) {
            apps.push('fullscreen_chat');
        }
        
        return apps;
    }
    
    getCurrentTopic() {
        // 从聊天历史中提取主题关键词
        const chatMessages = document.querySelectorAll('.message-content');
        if (chatMessages.length === 0) return 'general';
        
        const lastMessages = Array.from(chatMessages)
            .slice(-3)
            .map(el => el.textContent.toLowerCase());
        
        const topics = {
            'coding': ['代码', '编程', 'code', 'program', 'debug'],
            'study': ['学习', 'study', '笔记', 'note', '知识'],
            'creative': ['创意', 'creative', '设计', 'design', '写作'],
            'technical': ['技术', 'tech', '配置', 'setup', '安装']
        };
        
        for (const [topic, keywords] of Object.entries(topics)) {
            if (lastMessages.some(msg => 
                keywords.some(keyword => msg.includes(keyword))
            )) {
                return topic;
            }
        }
        
        return 'general';
    }
    
    getRecentActions(limit) {
        // 从本地存储获取最近的操作记录
        try {
            const actions = JSON.parse(localStorage.getItem('recent_actions') || '[]');
            return actions.slice(-limit);
        } catch {
            return [];
        }
    }
}

// 基础个性化学习器
class BasicPersonalizer {
    constructor() {
        this.patternKey = 'user_patterns';
        this.maxPatterns = 20;
    }
    
    getPersonalizedAction(context) {
        const patterns = this.getStoredPatterns();
        const contextSignature = this.createContextSignature(context);
        
        // 寻找相似的情境模式
        const similarPatterns = patterns.filter(pattern => 
            this.similarity(pattern.contextSignature, contextSignature) > 0.7
        );
        
        if (similarPatterns.length === 0) return null;
        
        // 基于历史反馈选择最佳行动
        const actionScores = {};
        similarPatterns.forEach(pattern => {
            if (pattern.feedback === 'positive') {
                actionScores[pattern.action] = (actionScores[pattern.action] || 0) + 1;
            }
        });
        
        const bestAction = Object.keys(actionScores).reduce((a, b) => 
            actionScores[a] > actionScores[b] ? a : b, null
        );
        
        return bestAction ? {
            action: bestAction,
            confidence: actionScores[bestAction] / similarPatterns.length
        } : null;
    }
    
    recordPattern(context, action, feedback) {
        const patterns = this.getStoredPatterns();
        const newPattern = {
            contextSignature: this.createContextSignature(context),
            action: action,
            feedback: feedback,
            timestamp: Date.now()
        };
        
        patterns.push(newPattern);
        
        // 维护数据量限制
        if (patterns.length > this.maxPatterns) {
            patterns.shift();
        }
        
        localStorage.setItem(this.patternKey, JSON.stringify(patterns));
    }
    
    getStoredPatterns() {
        try {
            return JSON.parse(localStorage.getItem(this.patternKey) || '[]');
        } catch {
            return [];
        }
    }
    
    createContextSignature(context) {
        return [
            context.timeSlot,
            context.apps.join(','),
            context.topic
        ].join('|');
    }
    
    similarity(sig1, sig2) {
        if (sig1 === sig2) return 1;
        
        const parts1 = sig1.split('|');
        const parts2 = sig2.split('|');
        
        let matches = 0;
        for (let i = 0; i < Math.min(parts1.length, parts2.length); i++) {
            if (parts1[i] === parts2[i]) matches++;
        }
        
        return matches / Math.max(parts1.length, parts2.length);
    }
}

// 轻量级融合引擎
class LightweightFusionEngine {
    constructor() {
        this.personalizer = new BasicPersonalizer();
        this.confidenceWeights = {
            personalization: 0.7,
            context: 0.3
        };
    }
    
    async getSmartRecommendation(userInput, context) {
        // 获取个性化建议
        const personalSuggestion = this.personalizer.getPersonalizedAction(context);
        
        // 获取基于规则的建议
        const ruleBasedSuggestion = this.getRuleBasedSuggestion(context);
        
        // 融合决策
        if (personalSuggestion && personalSuggestion.confidence > 0.6) {
            return {
                action: personalSuggestion.action,
                reason: "基于您的使用习惯推荐",
                confidence: personalSuggestion.confidence
            };
        }
        
        if (ruleBasedSuggestion) {
            return {
                action: ruleBasedSuggestion.action,
                reason: ruleBasedSuggestion.reason,
                confidence: ruleBasedSuggestion.confidence
            };
        }
        
        // 默认建议
        return {
            action: 'ask_for_help',
            reason: "需要更多信息来提供帮助",
            confidence: 0.3
        };
    }
    
    getRuleBasedSuggestion(context) {
        const rules = [
            {
                condition: ctx => ctx.timeSlot === 'morning' && ctx.apps.includes('text_editing'),
                action: 'morning_coding_setup',
                reason: "早上编码时间，为您准备开发环境",
                confidence: 0.8
            },
            {
                condition: ctx => ctx.topic === 'coding' && ctx.apps.includes('chat'),
                action: 'code_help_mode',
                reason: "检测到编程相关对话，启用代码协助模式",
                confidence: 0.9
            },
            {
                condition: ctx => ctx.timeSlot === 'evening' && ctx.topic === 'general',
                action: 'relaxation_mode',
                reason: "晚上休闲时间，为您推荐轻松内容",
                confidence: 0.7
            }
        ];
        
        for (const rule of rules) {
            if (rule.condition(context)) {
                return rule;
            }
        }
        
        return null;
    }
}

// 全局实例
window.SmartAssistant = new SmartContextLearningAssistant();

// 便捷方法
window.getSmartSuggestion = async function(userInput, context = {}) {
    return await window.SmartAssistant.provideSmartAssistance(userInput, context);
};

window.recordFeedback = function(interactionId, feedback) {
    window.SmartAssistant.recordUserFeedback(interactionId, feedback);
};

window.getAssistantStats = function() {
    return window.SmartAssistant.getLearningStats();
};

console.log('✅ 智能情境学习助手已就绪');
console.log('使用方法:');
console.log('- await getSmartSuggestion("需要帮助")');
console.log('- recordFeedback(interactionId, "positive"/"negative")');
console.log('- getAssistantStats() 查看学习统计');