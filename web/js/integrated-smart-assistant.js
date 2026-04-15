/**
 * 智能情境学习助手 - 整合版
 * 集成了所有增强功能的一站式解决方案
 */

// 主模块封装
(function() {
    'use strict';
    
    console.log('🚀 智能情境学习助手启动中...');
    
    // ========================================
    // 核心智能助手类
    // ========================================
    class IntegratedSmartAssistant {
        constructor() {
            this.version = '2.0.0';
            this.storageKey = 'integrated_smart_assistant';
            this.maxRecords = 50;
            this.confidenceThreshold = 0.6;
            
            // 初始化所有组件
            this.contextDetector = new EnhancedContextDetector();
            this.personalizer = new AdvancedPersonalizer();
            this.recommendationEngine = new RecommendationEngine();
            this.uiManager = new UIManager();
            
            // 加载历史数据
            this.loadData();
            
            console.log(`🧠 智能助手 v${this.version} 已初始化`);
        }
        
        // 主要入口方法
        async provideSmartAssistance(userInput, context = {}) {
            try {
                // 获取增强情境
                const enhancedContext = await this.contextDetector.getCurrentContext(context);
                
                // 获取个性化建议
                const personalizedRecommendation = await this.personalizer.getRecommendation(
                    userInput, enhancedContext
                );
                
                // 融合决策
                const finalRecommendation = await this.recommendationEngine.makeDecision(
                    userInput, enhancedContext, personalizedRecommendation
                );
                
                // 记录交互
                const interactionId = this.recordInteraction(
                    userInput, enhancedContext, finalRecommendation
                );
                
                // 显示建议
                this.uiManager.displayRecommendation(finalRecommendation, interactionId);
                
                return {
                    ...finalRecommendation,
                    interactionId: interactionId,
                    context: enhancedContext
                };
                
            } catch (error) {
                console.error('智能助手出错:', error);
                return this.getFallbackRecommendation(error);
            }
        }
        
        // 用户反馈处理
        recordUserFeedback(interactionId, feedback, comments = '') {
            const record = this.findRecordById(interactionId);
            if (record) {
                record.userFeedback = feedback;
                record.feedbackComments = comments;
                record.feedbackTime = Date.now();
                this.personalizer.learnFromFeedback(record);
                this.saveData();
                
                console.log(`📝 反馈已记录: ${feedback}`);
            }
        }
        
        // 获取学习统计
        getLearningStats() {
            const records = this.getRecords();
            const stats = {
                totalInteractions: records.length,
                positiveFeedback: records.filter(r => r.userFeedback === 'positive').length,
                negativeFeedback: records.filter(r => r.userFeedback === 'negative').length,
                neutralFeedback: records.filter(r => r.userFeedback === 'neutral').length,
                contextTypes: this.getContextDistribution(records),
                featureUsage: this.getFeatureUsageStats(records),
                improvementTrend: this.calculateImprovementTrend(records)
            };
            
            stats.accuracy = stats.totalInteractions > 0 ? 
                Math.round((stats.positiveFeedback / stats.totalInteractions) * 100) : 0;
                
            return stats;
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
                feedbackComments: '',
                feedbackTime: null
            };
            
            this.records = this.records || [];
            this.records.push(record);
            this.saveData();
            
            return record.id;
        }
        
        findRecordById(id) {
            return this.records.find(r => r.id === id);
        }
        
        generateId() {
            return 'ia_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
        }
        
        getContextDistribution(records) {
            const distribution = {};
            records.forEach(record => {
                const contextType = this.categorizeContext(record.context);
                distribution[contextType] = (distribution[contextType] || 0) + 1;
            });
            return distribution;
        }
        
        getFeatureUsageStats(records) {
            const features = {};
            records.forEach(record => {
                const feature = record.recommendation?.feature || 'unknown';
                features[feature] = (features[feature] || 0) + 1;
            });
            return features;
        }
        
        calculateImprovementTrend(records) {
            if (records.length < 10) return 'insufficient_data';
            
            const recent = records.slice(-10);
            const older = records.slice(-20, -10);
            
            const recentPositive = recent.filter(r => r.userFeedback === 'positive').length;
            const olderPositive = older.filter(r => r.userFeedback === 'positive').length;
            
            if (recentPositive > olderPositive) return 'improving';
            if (recentPositive < olderPositive) return 'declining';
            return 'stable';
        }
        
        categorizeContext(context) {
            if (context?.apps?.includes('IDE') || context?.topic?.includes('coding')) return 'coding';
            if (context?.timeSlot === 'evening') return 'leisure';
            if (context?.topic?.includes('学习') || context?.topic?.includes('study')) return 'study';
            if (context?.productivityLevel < 50) return 'low_productivity';
            return 'general';
        }
        
        getFallbackRecommendation(error) {
            return {
                suggestion: 'default_help',
                reason: '系统暂时无法提供智能建议',
                confidence: 0,
                error: error.message,
                feature: 'fallback'
            };
        }
    }
    
    // ========================================
    // 增强情境检测器
    // ========================================
    class EnhancedContextDetector {
        constructor() {
            this.monitors = {
                system: new SystemActivityMonitor(),
                behavior: new UserBehaviorAnalyzer(),
                environment: new EnvironmentalContextMonitor(),
                emotion: new EmotionalStateDetector()
            };
        }
        
        async getCurrentContext(additionalContext = {}) {
            const context = {
                // 基础信息
                timeSlot: this.getTimeSlot(),
                weekDay: this.getWeekDay(),
                season: this.getSeason(),
                apps: this.getActiveApplications(),
                topic: this.getCurrentTopic(),
                
                // 增强信息
                systemMetrics: await this.monitors.system.getMetrics(),
                userPatterns: await this.monitors.behavior.getPatterns(),
                environmentalFactors: await this.monitors.environment.getFactors(),
                emotionalState: await this.monitors.emotion.detectState(),
                
                // 派生指标
                userEnergy: await this.estimateUserEnergy(),
                productivityLevel: await this.assessProductivity(),
                stressIndicators: await this.detectStressSignals(),
                
                // 传入的额外上下文
                ...additionalContext,
                
                timestamp: Date.now()
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
        
        getWeekDay() {
            const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
            return days[new Date().getDay()];
        }
        
        getSeason() {
            const month = new Date().getMonth();
            if (month >= 11 || month <= 1) return 'winter';
            if (month >= 2 && month <= 4) return 'spring';
            if (month >= 5 && month <= 7) return 'summer';
            return 'autumn';
        }
        
        getActiveApplications() {
            const apps = [];
            const activeElement = document.activeElement;
            
            if (activeElement) {
                if (activeElement.id?.includes('chat')) apps.push('chat');
                if (activeElement.id?.includes('model')) apps.push('model_management');
                if (['TEXTAREA', 'INPUT'].includes(activeElement.tagName)) apps.push('text_editing');
            }
            
            if (document.querySelector('.chat-overlay.active')) apps.push('fullscreen_chat');
            
            return apps;
        }
        
        getCurrentTopic() {
            const messages = document.querySelectorAll('.message-content');
            if (messages.length === 0) return 'general';
            
            const recentMessages = Array.from(messages).slice(-3).map(m => m.textContent.toLowerCase());
            const topics = {
                'coding': ['代码', '编程', 'code', 'program', 'debug', 'python', 'javascript'],
                'study': ['学习', 'study', '笔记', 'note', '知识', '教程'],
                'creative': ['创意', 'creative', '设计', 'design', '写作', '文章'],
                'technical': ['技术', 'tech', '配置', 'setup', '安装', '部署']
            };
            
            for (const [topic, keywords] of Object.entries(topics)) {
                if (recentMessages.some(msg => keywords.some(kw => msg.includes(kw)))) {
                    return topic;
                }
            }
            
            return 'general';
        }
        
        async estimateUserEnergy() {
            const hour = new Date().getHours();
            let energy = 50;
            
            // 时间因素
            if (hour >= 9 && hour <= 11) energy += 25;
            if (hour >= 14 && hour <= 16) energy += 20;
            if (hour >= 22 || hour <= 6) energy -= 35;
            
            // 活动模式
            const recentActivity = await this.getRecentActivity();
            if (recentActivity.intense) energy -= 15;
            if (recentActivity.consistent) energy += 10;
            
            return Math.max(0, Math.min(100, energy));
        }
        
        async assessProductivity() {
            const factors = {
                focus: await this.measureFocusLevel(),
                interruptions: await this.countRecentInterruptions(),
                completion: await this.getTaskCompletionRate(),
                timeEffect: this.getTimeOfDayProductivity()
            };
            
            return Math.round(
                factors.focus * 0.3 +
                (100 - factors.interruptions) * 0.25 +
                factors.completion * 0.25 +
                factors.timeEffect * 0.2
            );
        }
        
        async detectStressSignals() {
            const signals = [];
            
            const typingPattern = await this.analyzeTypingPattern();
            if (typingPattern.irregularity > 0.7) signals.push('typing_stress');
            if (typingPattern.speed > 120) signals.push('rushed_typing');
            
            const actionFreq = await this.getActionFrequency();
            if (actionFreq.veryHigh) signals.push('frantic_activity');
            
            return signals;
        }
        
        // 辅助方法
        async getRecentActivity() {
            try {
                const actions = JSON.parse(localStorage.getItem('recent_user_actions') || '[]');
                const recent = actions.slice(-20);
                return {
                    intense: recent.length > 30,
                    consistent: this.analyzeConsistency(recent),
                    lastActivity: actions.length > 0 ? actions[actions.length - 1].timestamp : 0
                };
            } catch {
                return { intense: false, consistent: false, lastActivity: 0 };
            }
        }
        
        async measureFocusLevel() {
            const activeApps = this.getActiveApplications();
            return activeApps.length === 1 ? 85 : activeApps.length === 2 ? 70 : 50;
        }
        
        async countRecentInterruptions() {
            // 简化实现
            return 20; // 假设中等干扰水平
        }
        
        async getTaskCompletionRate() {
            // 简化实现
            return 75; // 假设75%的任务完成率
        }
        
        getTimeOfDayProductivity() {
            const hour = new Date().getHours();
            if (hour >= 9 && hour <= 11) return 90;
            if (hour >= 14 && hour <= 16) return 85;
            if (hour >= 19 && hour <= 21) return 70;
            return 50;
        }
        
        async analyzeTypingPattern() {
            // 简化实现
            return { irregularity: 0.3, speed: 60 };
        }
        
        async getActionFrequency() {
            // 简化实现
            return { veryHigh: false, high: true, moderate: false, low: false };
        }
        
        analyzeConsistency(actions) {
            // 简化实现
            return actions.length > 10;
        }
    }
    
    // ========================================
    // 高级个性化学习器
    // ========================================
    class AdvancedPersonalizer {
        constructor() {
            this.patternKey = 'advanced_user_patterns';
            this.maxPatterns = 30;
            this.similarityThreshold = 0.7;
        }
        
        async getRecommendation(userInput, context) {
            const patterns = this.getStoredPatterns();
            const contextSignature = this.createContextSignature(context);
            
            // 寻找相似情境
            const similarPatterns = patterns.filter(pattern => 
                this.calculateSimilarity(pattern.contextSignature, contextSignature) > this.similarityThreshold
            );
            
            if (similarPatterns.length > 0) {
                const bestPattern = this.selectBestPattern(similarPatterns);
                return {
                    suggestion: bestPattern.action,
                    reason: `基于您类似情境下的偏好推荐`,
                    confidence: bestPattern.confidence,
                    feature: bestPattern.feature,
                    source: 'personalized'
                };
            }
            
            // 没有匹配模式时的基础推荐
            return this.getRuleBasedRecommendation(context);
        }
        
        learnFromFeedback(interactionRecord) {
            if (!interactionRecord.userFeedback) return;
            
            const newPattern = {
                contextSignature: this.createContextSignature(interactionRecord.context),
                action: interactionRecord.recommendation.suggestion,
                feature: interactionRecord.recommendation.feature,
                feedback: interactionRecord.userFeedback,
                confidence: interactionRecord.recommendation.confidence,
                timestamp: Date.now()
            };
            
            const patterns = this.getStoredPatterns();
            patterns.push(newPattern);
            
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
                context.timeSlot || 'unknown',
                context.weekDay || 'unknown',
                context.season || 'unknown',
                context.topic || 'general',
                context.productivityLevel || 50,
                context.userEnergy || 50
            ].join('|');
        }
        
        calculateSimilarity(sig1, sig2) {
            if (sig1 === sig2) return 1;
            
            const parts1 = sig1.split('|');
            const parts2 = sig2.split('|');
            
            let matches = 0;
            const minLength = Math.min(parts1.length, parts2.length);
            
            for (let i = 0; i < minLength; i++) {
                if (parts1[i] === parts2[i]) matches++;
            }
            
            return matches / Math.max(parts1.length, parts2.length);
        }
        
        selectBestPattern(patterns) {
            const feedbackWeights = { positive: 1.0, neutral: 0.5, negative: 0.1 };
            
            return patterns.reduce((best, current) => {
                const currentScore = (current.confidence || 0.5) * 
                                   (feedbackWeights[current.feedback] || 0.5);
                const bestScore = (best.confidence || 0.5) * 
                                (feedbackWeights[best.feedback] || 0.5);
                
                return currentScore > bestScore ? current : best;
            });
        }
        
        getRuleBasedRecommendation(context) {
            const rules = [
                {
                    condition: ctx => ctx.timeSlot === 'morning' && ctx.topic === 'coding',
                    action: 'morning_coding_setup',
                    feature: 'productivity',
                    reason: '早上编程时间，为您优化开发环境'
                },
                {
                    condition: ctx => ctx.timeSlot === 'evening' && ctx.stressIndicators?.length > 0,
                    action: 'relaxation_mode',
                    feature: 'wellbeing',
                    reason: '检测到晚间压力信号，建议放松模式'
                },
                {
                    condition: ctx => ctx.productivityLevel < 40,
                    action: 'focus_boost',
                    feature: 'productivity',
                    reason: '检测到低效状态，提供专注力提升建议'
                }
            ];
            
            for (const rule of rules) {
                if (rule.condition(context)) {
                    return {
                        suggestion: rule.action,
                        reason: rule.reason,
                        confidence: 0.8,
                        feature: rule.feature,
                        source: 'rule_based'
                    };
                }
            }
            
            return {
                suggestion: 'general_assistance',
                reason: '提供通用帮助',
                confidence: 0.5,
                feature: 'general',
                source: 'default'
            };
        }
    }
    
    // ========================================
    // 智能推荐引擎
    // ========================================
    class RecommendationEngine {
        constructor() {
            this.confidenceWeights = {
                personalized: 0.7,
                contextual: 0.3
            };
        }
        
        async makeDecision(userInput, context, personalizedRec) {
            // 获取基于规则的推荐
            const ruleBasedRec = this.getRuleBasedRecommendation(context);
            
            // 融合决策
            if (personalizedRec.source === 'personalized' && personalizedRec.confidence > 0.6) {
                return personalizedRec;
            }
            
            if (ruleBasedRec.confidence > personalizedRec.confidence) {
                return ruleBasedRec;
            }
            
            return personalizedRec;
        }
        
        getRuleBasedRecommendation(context) {
            const recommendations = {
                morning: {
                    coding: { suggestion: 'morning_coding_routine', confidence: 0.9 },
                    general: { suggestion: 'daily_planning', confidence: 0.7 }
                },
                afternoon: {
                    general: { suggestion: 'productivity_check', confidence: 0.8 }
                },
                evening: {
                    stressed: { suggestion: 'relaxation_activities', confidence: 0.85 },
                    general: { suggestion: 'day_review', confidence: 0.7 }
                }
            };
            
            const timeRecs = recommendations[context.timeSlot] || {};
            const specificRec = timeRecs[context.topic] || timeRecs.general || 
                              { suggestion: 'default_suggestion', confidence: 0.5 };
            
            return {
                ...specificRec,
                reason: this.getRecommendationReason(context, specificRec.suggestion),
                feature: this.categorizeFeature(specificRec.suggestion),
                source: 'rule_based_fusion'
            };
        }
        
        getRecommendationReason(context, suggestion) {
            const reasons = {
                'morning_coding_routine': '根据您的晨间编程习惯推荐',
                'daily_planning': '帮助您规划一天的工作',
                'productivity_check': '午后效率检查',
                'relaxation_activities': '缓解晚间工作压力',
                'day_review': '总结今日收获',
                'default_suggestion': '基于当前情境的通用建议'
            };
            
            return reasons[suggestion] || '智能情境推荐';
        }
        
        categorizeFeature(suggestion) {
            const categories = {
                'morning_coding_routine': 'productivity',
                'daily_planning': 'organization',
                'productivity_check': 'analytics',
                'relaxation_activities': 'wellbeing',
                'day_review': 'reflection'
            };
            
            return categories[suggestion] || 'general';
        }
    }
    
    // ========================================
    // 用户界面管理器
    // ========================================
    class UIManager {
        constructor() {
            this.ensureStylesLoaded();
        }
        
        displayRecommendation(recommendation, interactionId) {
            // 创建建议卡片
            const card = this.createRecommendationCard(recommendation, interactionId);
            
            // 找到合适的插入位置
            const targetContainer = this.findInsertionPoint();
            if (targetContainer) {
                targetContainer.prepend(card);
                
                // 自动消失
                setTimeout(() => {
                    if (card.parentElement) {
                        card.remove();
                    }
                }, 10000);
            }
        }
        
        createRecommendationCard(recommendation, interactionId) {
            const card = document.createElement('div');
            card.className = 'integrated-smart-assistant-card';
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-icon">🤖</span>
                    <span class="card-title">智能建议</span>
                    <button class="card-close" onclick="this.closest('.integrated-smart-assistant-card').remove()">×</button>
                </div>
                <div class="card-content">
                    <p><strong>推荐:</strong> ${recommendation.suggestion}</p>
                    <p><small>${recommendation.reason}</small></p>
                    <div class="confidence-meter">
                        <span>置信度: ${(recommendation.confidence * 100).toFixed(0)}%</span>
                        <div class="meter-bar">
                            <div class="meter-fill" style="width: ${(recommendation.confidence * 100)}%"></div>
                        </div>
                    </div>
                    <div class="card-actions">
                        <button class="btn-primary" onclick="IntegratedAssistant.applyRecommendation('${recommendation.suggestion}')">
                            应用建议
                        </button>
                        <button class="btn-secondary" onclick="this.closest('.integrated-smart-assistant-card').remove()">
                            忽略
                        </button>
                    </div>
                    <div class="feedback-section">
                        <small>这个建议有用吗？</small>
                        <div class="feedback-buttons">
                            <button class="feedback-btn positive" onclick="IntegratedAssistant.recordFeedback('${interactionId}', 'positive')">
                                👍 有帮助
                            </button>
                            <button class="feedback-btn neutral" onclick="IntegratedAssistant.recordFeedback('${interactionId}', 'neutral')">
                                😐 一般
                            </button>
                            <button class="feedback-btn negative" onclick="IntegratedAssistant.recordFeedback('${interactionId}', 'negative')">
                                👎 不合适
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            return card;
        }
        
        findInsertionPoint() {
            // 优先在聊天输入区域显示
            return document.querySelector('.chat-input-area') || 
                   document.querySelector('.main-content') ||
                   document.body;
        }
        
        ensureStylesLoaded() {
            if (document.getElementById('integrated-assistant-styles')) return;
            
            const style = document.createElement('style');
            style.id = 'integrated-assistant-styles';
            style.textContent = `
                .integrated-smart-assistant-card {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 12px;
                    margin: 15px 0;
                    padding: 20px;
                    box-shadow: 0 6px 20px rgba(0,0,0,0.2);
                    animation: slideInFromTop 0.4s ease-out;
                    max-width: 500px;
                }
                
                @keyframes slideInFromTop {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .card-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid rgba(255,255,255,0.3);
                }
                
                .card-icon {
                    font-size: 20px;
                }
                
                .card-title {
                    font-weight: bold;
                    font-size: 16px;
                    flex-grow: 1;
                    margin-left: 10px;
                }
                
                .card-close {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 24px;
                    cursor: pointer;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 50%;
                }
                
                .card-close:hover {
                    background: rgba(255,255,255,0.2);
                }
                
                .card-content p {
                    margin: 10px 0;
                    line-height: 1.5;
                }
                
                .confidence-meter {
                    margin: 15px 0;
                }
                
                .meter-bar {
                    height: 6px;
                    background: rgba(255,255,255,0.3);
                    border-radius: 3px;
                    margin-top: 5px;
                    overflow: hidden;
                }
                
                .meter-fill {
                    height: 100%;
                    background: white;
                    border-radius: 3px;
                    transition: width 0.5s ease;
                }
                
                .card-actions {
                    display: flex;
                    gap: 10px;
                    margin: 15px 0;
                }
                
                .btn-primary, .btn-secondary {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                }
                
                .btn-primary {
                    background: white;
                    color: #667eea;
                }
                
                .btn-secondary {
                    background: rgba(255,255,255,0.2);
                    color: white;
                    border: 1px solid rgba(255,255,255,0.3);
                }
                
                .feedback-section {
                    margin-top: 20px;
                    padding-top: 15px;
                    border-top: 1px solid rgba(255,255,255,0.2);
                }
                
                .feedback-buttons {
                    display: flex;
                    gap: 8px;
                    margin-top: 10px;
                }
                
                .feedback-btn {
                    padding: 6px 12px;
                    border: none;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 12px;
                    transition: all 0.2s;
                }
                
                .feedback-btn.positive { background: #4CAF50; color: white; }
                .feedback-btn.neutral { background: #FF9800; color: white; }
                .feedback-btn.negative { background: #F44336; color: white; }
                
                .feedback-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 3px 8px rgba(0,0,0,0.2);
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    // ========================================
    // 系统监控组件
    // ========================================
    class SystemActivityMonitor {
        async getMetrics() {
            return {
                cpuUsage: this.estimateCPUUsage(),
                memoryPressure: this.estimateMemoryPressure(),
                networkActivity: this.estimateNetworkActivity(),
                batteryLevel: await this.getBatteryLevel(),
                performanceScore: await this.assessPerformance()
            };
        }
        
        estimateCPUUsage() {
            const activeElements = document.querySelectorAll(':focus, .active, :hover');
            return Math.min(100, 20 + (activeElements.length * 3));
        }
        
        estimateMemoryPressure() {
            const domNodes = document.querySelectorAll('*');
            return Math.min(100, domNodes.length / 15);
        }
        
        estimateNetworkActivity() {
            return document.querySelectorAll('[data-loading]').length > 0 ? 75 : 25;
        }
        
        async getBatteryLevel() {
            if (navigator.getBattery) {
                try {
                    const battery = await navigator.getBattery();
                    return Math.round(battery.level * 100);
                } catch {
                    return 80;
                }
            }
            return 80;
        }
        
        async assessPerformance() {
            const start = performance.now();
            let test = 0;
            for (let i = 0; i < 50000; i++) {
                test += Math.sqrt(i);
            }
            const end = performance.now();
            
            const executionTime = end - start;
            return Math.max(0, Math.min(100, 100 - (executionTime / 3)));
        }
    }
    
    class UserBehaviorAnalyzer {
        async getPatterns() {
            return {
                usageFrequency: await this.analyzeUsageFrequency(),
                preferencePatterns: await this.analyzePreferences(),
                interactionStyle: await this.analyzeInteractionStyle()
            };
        }
        
        async analyzeUsageFrequency() {
            const sessions = this.getUserSessions();
            return {
                dailyAverage: sessions.length / 7,
                peakHours: this.identifyPeakHours(sessions),
                consistency: this.measureUsageConsistency(sessions)
            };
        }
        
        async analyzePreferences() {
            const interactions = this.getUserInteractions();
            const featureCounts = this.countFeatureUsage(interactions);
            
            return {
                favoriteFeatures: Object.keys(featureCounts).sort((a,b) => featureCounts[b] - featureCounts[a]).slice(0,3),
                usageDiversity: Object.keys(featureCounts).length,
                preferenceStability: this.measurePreferenceStability(interactions)
            };
        }
        
        async analyzeInteractionStyle() {
            const recentActions = this.getRecentActions(50);
            return {
                interactionSpeed: this.calculateAverageInterval(recentActions) < 3000 ? 'fast' : 'moderate',
                exploration: recentActions.length > 20 ? 'high' : 'moderate',
                consistency: recentActions.length > 30 ? 'consistent' : 'variable'
            };
        }
        
        // 辅助方法
        getUserSessions() {
            try {
                return JSON.parse(localStorage.getItem('user_sessions') || '[]');
            } catch {
                return [];
            }
        }
        
        getUserInteractions() {
            try {
                return JSON.parse(localStorage.getItem('user_interactions') || '[]');
            } catch {
                return [];
            }
        }
        
        getRecentActions(count) {
            const interactions = this.getUserInteractions();
            return interactions.slice(-count);
        }
        
        identifyPeakHours(sessions) {
            const hourCounts = new Array(24).fill(0);
            sessions.forEach(session => {
                const hour = new Date(session.timestamp).getHours();
                hourCounts[hour]++;
            });
            
            const maxCount = Math.max(...hourCounts);
            return hourCounts.map((count, hour) => ({ hour, count }))
                           .filter(item => item.count > maxCount * 0.6)
                           .map(item => item.hour);
        }
        
        measureUsageConsistency(sessions) {
            if (sessions.length < 7) return 'insufficient';
            
            const dailyCounts = new Array(7).fill(0);
            sessions.forEach(session => {
                const day = new Date(session.timestamp).getDay();
                dailyCounts[day]++;
            });
            
            const avg = dailyCounts.reduce((a,b) => a+b, 0) / 7;
            const variance = dailyCounts.reduce((sum, count) => sum + Math.pow(count - avg, 2), 0) / 7;
            
            return variance < 2 ? 'high' : variance < 5 ? 'moderate' : 'low';
        }
        
        countFeatureUsage(interactions) {
            const counts = {};
            interactions.forEach(interaction => {
                const feature = interaction.feature || 'unknown';
                counts[feature] = (counts[feature] || 0) + 1;
            });
            return counts;
        }
        
        measurePreferenceStability(interactions) {
            if (interactions.length < 10) return 'developing';
            
            const firstHalf = interactions.slice(0, Math.floor(interactions.length / 2));
            const secondHalf = interactions.slice(Math.floor(interactions.length / 2));
            
            const firstPrefs = this.getTopPreferences(firstHalf);
            const secondPrefs = this.getTopPreferences(secondHalf);
            
            const overlap = firstPrefs.filter(pref => secondPrefs.includes(pref)).length;
            return overlap >= 2 ? 'stable' : 'evolving';
        }
        
        getTopPreferences(interactions) {
            const featureCounts = this.countFeatureUsage(interactions);
            return Object.keys(featureCounts)
                        .sort((a,b) => featureCounts[b] - featureCounts[a])
                        .slice(0, 3);
        }
        
        calculateAverageInterval(actions) {
            if (actions.length < 2) return 5000;
            
            const intervals = [];
            for (let i = 1; i < actions.length; i++) {
                intervals.push(actions[i].timestamp - actions[i-1].timestamp);
            }
            
            return intervals.reduce((a,b) => a+b, 0) / intervals.length;
        }
    }
    
    class EnvironmentalContextMonitor {
        async getFactors() {
            return {
                timeContext: this.getTimeContext(),
                deviceContext: this.getDeviceContext(),
                locationInference: this.inferLocation(),
                socialContext: this.assessSocialEnvironment()
            };
        }
        
        getTimeContext() {
            const now = new Date();
            return {
                hour: now.getHours(),
                dayOfWeek: now.getDay(),
                isWeekend: [0, 6].includes(now.getDay()),
                season: this.getSeason(now.getMonth())
            };
        }
        
        getDeviceContext() {
            const ua = navigator.userAgent.toLowerCase();
            return {
                isMobile: /mobile|android|iphone/.test(ua),
                isTablet: /tablet|ipad/.test(ua),
                isDesktop: !/mobile|tablet/.test(ua),
                screenSize: this.categorizeScreenSize(),
                connection: navigator.connection?.effectiveType || 'unknown'
            };
        }
        
        inferLocation() {
            // 简化的位置推断
            const referrer = document.referrer;
            const isWorkRelated = /office|work|company|enterprise/.test(referrer);
            const isEducation = /edu|school|university|learn/.test(referrer);
            
            return {
                likelyLocation: isWorkRelated ? 'workplace' : isEducation ? 'educational' : 'home',
                environmentType: this.inferEnvironmentType()
            };
        }
        
        assessSocialEnvironment() {
            const socialIndicators = {
                hasSocialMedia: /facebook|twitter|instagram|wechat|qq/.test(document.referrer),
                collaborativeElements: document.querySelectorAll('[data-collaborative]').length > 0,
                sharingFeatures: document.querySelectorAll('[data-share]').length > 0
            };
            
            return {
                socialMediaActive: socialIndicators.hasSocialMedia,
                collaborationLevel: socialIndicators.collaborativeElements ? 'high' : 'low',
                sharingTendency: socialIndicators.sharingFeatures ? 'active' : 'passive'
            };
        }
        
        getSeason(month) {
            if (month >= 11 || month <= 1) return 'winter';
            if (month >= 2 && month <= 4) return 'spring';
            if (month >= 5 && month <= 7) return 'summer';
            return 'autumn';
        }
        
        categorizeScreenSize() {
            const width = window.innerWidth;
            if (width < 768) return 'small';
            if (width < 1024) return 'medium';
            return 'large';
        }
        
        inferEnvironmentType() {
            const width = window.innerWidth;
            const height = window.innerHeight;
            
            if (width > 1920 && height > 1080) return 'professional_desk';
            if (width < 800) return 'mobile_personal';
            if (width > 1200) return 'home_office';
            return 'generic_environment';
        }
    }
    
    class EmotionalStateDetector {
        async detectState() {
            return {
                valence: await this.assessValence(),
                arousal: await this.assessArousal(),
                stressIndicators: await this.detectStressMarkers(),
                engagementLevel: await this.measureEngagement()
            };
        }
        
        async assessValence() {
            const recentContent = this.getRecentUserInputs();
            const sentimentScore = this.simpleSentimentAnalysis(recentContent);
            
            if (sentimentScore > 0.2) return 'positive';
            if (sentimentScore < -0.2) return 'negative';
            return 'neutral';
        }
        
        async assessArousal() {
            const interactionSpeed = this.measureInteractionPace();
            const contentComplexity = this.assessContentComplexity();
            
            if (interactionSpeed > 80 || contentComplexity > 0.8) return 'high';
            if (interactionSpeed < 30 && contentComplexity < 0.4) return 'low';
            return 'moderate';
        }
        
        async detectStressMarkers() {
            const markers = [];
            
            const typingPattern = await this.analyzeTypingBehavior();
            if (typingPattern.irregularity > 0.6) markers.push('irregular_typing');
            if (typingPattern.speed > 100) markers.push('rapid_typing');
            
            const actionPattern = await this.analyzeActionPattern();
            if (actionPattern.frequentUndo) markers.push('correction_behavior');
            if (actionPattern.rapidSwitching) markers.push('task_switching_stress');
            
            return markers;
        }
        
        async measureEngagement() {
            const focusMetrics = await this.getFocusIndicators();
            const engagementScore = this.calculateEngagementScore(focusMetrics);
            
            if (engagementScore > 75) return 'high';
            if (engagementScore > 50) return 'moderate';
            return 'low';
        }
        
        // 辅助方法
        getRecentUserInputs() {
            const inputs = document.querySelectorAll('input[type="text"], textarea');
            return Array.from(inputs).map(input => input.value).join(' ').toLowerCase();
        }
        
        simpleSentimentAnalysis(text) {
            const positiveWords = ['好', '棒', '喜欢', '满意', '优秀', 'great', 'good', 'excellent', 'awesome'];
            const negativeWords = ['差', '糟糕', '讨厌', '不满', '困难', 'bad', 'terrible', 'difficult', 'awful'];
            
            let score = 0;
            const words = text.split(/\s+/);
            const totalWords = words.length;
            
            positiveWords.forEach(word => {
                const count = (text.match(new RegExp(word, 'g')) || []).length;
                score += count;
            });
            
            negativeWords.forEach(word => {
                const count = (text.match(new RegExp(word, 'g')) || []).length;
                score -= count;
            });
            
            return totalWords > 0 ? score / totalWords : 0;
        }
        
        measureInteractionPace() {
            const recentActions = this.getRecentActions(30);
            if (recentActions.length < 2) return 50;
            
            const intervals = [];
            for (let i = 1; i < recentActions.length; i++) {
                intervals.push(recentActions[i].timestamp - recentActions[i-1].timestamp);
            }
            
            const avgInterval = intervals.reduce((a,b) => a+b, 0) / intervals.length;
            return Math.round(60000 / Math.max(1, avgInterval));
        }
        
        assessContentComplexity() {
            const content = this.getRecentUserInputs();
            const sentences = content.split(/[.!?。！？]+/);
            const avgLength = content.length / Math.max(1, sentences.length);
            return Math.min(1, avgLength / 100);
        }
        
        async analyzeTypingBehavior() {
            // 简化实现
            return { irregularity: 0.4, speed: 65 };
        }
        
        async analyzeActionPattern() {
            // 简化实现
            return { frequentUndo: false, rapidSwitching: false };
        }
        
        async getFocusIndicators() {
            // 简化实现
            return { focusDuration: 300, distractions: 2, taskSwitches: 3 };
        }
        
        calculateEngagementScore(metrics) {
            let score = 50;
            if (metrics.focusDuration > 600) score += 25;
            if (metrics.distractions < 2) score += 15;
            if (metrics.taskSwitches < 4) score += 10;
            return Math.min(100, score);
        }
        
        getRecentActions(count) {
            try {
                const actions = JSON.parse(localStorage.getItem('user_action_log') || '[]');
                return actions.slice(-count);
            } catch {
                return [];
            }
        }
    }
    
    // ========================================
    // 全局API接口
    // ========================================
    
    // 创建全局实例
    const IntegratedAssistant = new IntegratedSmartAssistant();
    window.IntegratedAssistant = IntegratedAssistant;
    
    // 便捷的全局方法
    window.getIntegratedSmartSuggestion = async function(userInput, context = {}) {
        return await IntegratedAssistant.provideSmartAssistance(userInput, context);
    };
    
    window.recordIntegratedFeedback = function(interactionId, feedback, comments = '') {
        IntegratedAssistant.recordUserFeedback(interactionId, feedback, comments);
    };
    
    window.getIntegratedAssistantStats = function() {
        return IntegratedAssistant.getLearningStats();
    };
    
    // 应用建议的全局方法
    IntegratedAssistant.applyRecommendation = function(suggestion) {
        const actions = {
            'morning_coding_routine': () => this.setupMorningCoding(),
            'daily_planning': () => this.showDailyPlanner(),
            'productivity_check': () => this.runProductivityCheck(),
            'relaxation_activities': () => this.suggestRelaxation(),
            'day_review': () => this.showDayReview(),
            'focus_boost': () => this.enableFocusMode()
        };
        
        const action = actions[suggestion];
        if (action) {
            action.call(this);
            this.showToast(`已应用建议: ${suggestion}`, 'success');
        } else {
            this.showToast(`建议 "${suggestion}" 已记录`, 'info');
        }
    };
    
    // 反馈记录的全局方法
    IntegratedAssistant.recordFeedback = function(interactionId, feedback) {
        this.recordUserFeedback(interactionId, feedback);
        this.showToast(`感谢您的反馈！`, 'success');
        
        // 自动隐藏卡片
        const card = document.querySelector(`[data-interaction-id="${interactionId}"]`);
        if (card) {
            setTimeout(() => card.remove(), 1000);
        }
    };
    
    // 实用工具方法
    IntegratedAssistant.setupMorningCoding = function() {
        console.log('设置晨间编程环境...');
        // 这里可以添加具体的环境设置逻辑
    };
    
    IntegratedAssistant.showDailyPlanner = function() {
        console.log('显示每日计划...');
        // 显示计划界面
    };
    
    IntegratedAssistant.runProductivityCheck = function() {
        console.log('运行生产力检查...');
        // 执行生产力分析
    };
    
    IntegratedAssistant.suggestRelaxation = function() {
        console.log('推荐放松活动...');
        // 推荐放松方式
    };
    
    IntegratedAssistant.showDayReview = function() {
        console.log('显示日回顾...');
        // 显示当日总结
    };
    
    IntegratedAssistant.enableFocusMode = function() {
        console.log('启用专注模式...');
        // 启用专注功能
    };
    
    IntegratedAssistant.showToast = function(message, type = 'info') {
        // 简单的toast提示
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#F44336' : '#2196F3'};
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideInUp 0.3s ease;
        `;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };
    
    // 添加CSS动画
    if (!document.getElementById('assistant-animations')) {
        const animStyle = document.createElement('style');
        animStyle.id = 'assistant-animations';
        animStyle.textContent = `
            @keyframes slideInUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            @keyframes fadeOut {
                from { opacity: 1; transform: translateY(0); }
                to { opacity: 0; transform: translateY(20px); }
            }
        `;
        document.head.appendChild(animStyle);
    }
    
    console.log('✅ 智能情境学习助手整合版已就绪');
    console.log('使用方法:');
    console.log('- await getIntegratedSmartSuggestion("您的需求")');
    console.log('- recordIntegratedFeedback(interactionId, "positive/neutral/negative")');
    console.log('- getIntegratedAssistantStats() 查看统计');
    
})();