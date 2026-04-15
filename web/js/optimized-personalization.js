/**
 * 优化的个性化学习算法
 * 基于深度用户行为分析和自适应推荐系统
 */

class OptimizedPersonalizationEngine {
    constructor() {
        this.userProfile = this.loadUserProfile();
        this.interactionHistory = this.loadInteractionHistory();
        this.preferenceModel = new PreferenceLearningModel();
        this.adaptationEngine = new AdaptiveRecommendationEngine();
        this.feedbackAnalyzer = new FeedbackAnalysisSystem();
        
        // 配置参数
        this.config = {
            maxHistoryLength: 100,
            similarityThreshold: 0.75,
            adaptationRate: 0.3,
            confidenceDecay: 0.95,
            minConfidence: 0.3
        };
    }
    
    // 主要推荐入口
    async getPersonalizedRecommendation(userInput, context) {
        try {
            // 1. 更新用户画像
            this.updateUserProfile(userInput, context);
            
            // 2. 分析当前情境
            const contextAnalysis = await this.analyzeContext(context);
            
            // 3. 生成候选推荐
            const candidates = await this.generateRecommendationCandidates(contextAnalysis);
            
            // 4. 个性化排序
            const rankedRecommendations = await this.rankByPersonalization(candidates);
            
            // 5. 自适应调整
            const finalRecommendation = await this.adaptiveAdjustment(
                rankedRecommendations[0], contextAnalysis
            );
            
            // 6. 记录交互
            const interactionId = this.recordInteraction(
                userInput, context, finalRecommendation
            );
            
            return {
                ...finalRecommendation,
                interactionId: interactionId,
                personalizationScore: this.calculatePersonalizationScore(finalRecommendation)
            };
            
        } catch (error) {
            console.error('个性化推荐出错:', error);
            return this.getDefaultRecommendation(context);
        }
    }
    
    // 更新用户画像
    updateUserProfile(userInput, context) {
        const profileUpdate = {
            timestamp: Date.now(),
            inputCharacteristics: this.analyzeInputCharacteristics(userInput),
            contextPatterns: this.extractContextPatterns(context),
            behavioralMetrics: this.calculateBehavioralMetrics()
        };
        
        this.userProfile.history.push(profileUpdate);
        
        // 保持历史长度限制
        if (this.userProfile.history.length > this.config.maxHistoryLength) {
            this.userProfile.history.shift();
        }
        
        // 更新核心特征
        this.userProfile.coreTraits = this.extractCoreTraits();
        this.userProfile.preferredStyles = this.identifyPreferredStyles();
        this.userProfile.skillLevel = this.assessSkillLevel();
        
        this.saveUserProfile();
    }
    
    // 深度情境分析
    async analyzeContext(context) {
        return {
            temporalFactors: this.analyzeTemporalContext(context),
            behavioralPatterns: await this.identifyBehavioralPatterns(context),
            emotionalIndicators: await this.detectEmotionalState(context),
            cognitiveLoad: this.assessCognitiveLoad(context),
            socialContext: this.analyzeSocialFactors(context),
            environmentalFactors: this.analyzeEnvironmentalContext(context)
        };
    }
    
    // 生成推荐候选项
    async generateRecommendationCandidates(contextAnalysis) {
        const candidates = [];
        
        // 基于历史成功模式
        const historicalSuccesses = this.findHistoricalSuccesses();
        candidates.push(...historicalSuccesses.map(success => ({
            type: 'historical_success',
            content: success.recommendation,
            confidence: success.confidence * 0.9,
            source: 'past_performance'
        })));
        
        // 基于情境匹配
        const contextualMatches = await this.findContextualMatches(contextAnalysis);
        candidates.push(...contextualMatches.map(match => ({
            type: 'contextual_match',
            content: match.recommendation,
            confidence: match.similarityScore,
            source: 'context_similarity'
        })));
        
        // 基于协同过滤
        const collaborativeSuggestions = await this.getCollaborativeSuggestions();
        candidates.push(...collaborativeSuggestions.map(suggestion => ({
            type: 'collaborative_filtering',
            content: suggestion.recommendation,
            confidence: suggestion.confidence,
            source: 'user_similarity'
        })));
        
        // 基于强化学习
        const rlRecommendations = await this.getReinforcementLearningSuggestions(contextAnalysis);
        candidates.push(...rlRecommendations.map(rec => ({
            type: 'reinforcement_learning',
            content: rec.action,
            confidence: rec.qValue,
            source: 'optimal_policy'
        })));
        
        return candidates;
    }
    
    // 个性化排序算法
    async rankByPersonalization(candidates) {
        const ranked = candidates.map(candidate => {
            const personalizationScore = this.calculateCandidateScore(candidate);
            return {
                ...candidate,
                personalizationScore: personalizationScore,
                finalConfidence: candidate.confidence * personalizationScore
            };
        });
        
        return ranked.sort((a, b) => b.finalConfidence - a.finalConfidence);
    }
    
    // 自适应调整
    async adaptiveAdjustment(recommendation, contextAnalysis) {
        // 动态信心衰减
        const decayedConfidence = recommendation.confidence * this.config.confidenceDecay;
        
        // 上下文适配调整
        const contextAdjusted = await this.adjustForContext(
            recommendation, contextAnalysis
        );
        
        // 个性风格匹配
        const styleMatched = this.matchUserStyle(contextAdjusted);
        
        return {
            ...styleMatched,
            confidence: Math.max(decayedConfidence, this.config.minConfidence),
            adaptationTimestamp: Date.now()
        };
    }
    
    // 反馈学习系统
    learnFromFeedback(interactionRecord) {
        if (!interactionRecord.userFeedback) return;
        
        // 更新偏好模型
        this.preferenceModel.update(
            interactionRecord.context,
            interactionRecord.recommendation,
            interactionRecord.userFeedback
        );
        
        // 分析反馈模式
        const feedbackInsights = this.feedbackAnalyzer.analyze(
            interactionRecord.userFeedback,
            interactionRecord.feedbackComments
        );
        
        // 调整推荐策略
        this.adaptationEngine.updateStrategy(feedbackInsights);
        
        // 更新用户画像
        this.updateProfileFromFeedback(interactionRecord);
        
        this.saveUserProfile();
    }
    
    // 私有辅助方法
    loadUserProfile() {
        try {
            const saved = localStorage.getItem('optimized_user_profile');
            return saved ? JSON.parse(saved) : this.createDefaultProfile();
        } catch (error) {
            console.warn('加载用户画像失败:', error);
            return this.createDefaultProfile();
        }
    }
    
    createDefaultProfile() {
        return {
            userId: this.generateUserId(),
            createdAt: Date.now(),
            history: [],
            coreTraits: {},
            preferredStyles: {},
            skillLevel: 'beginner',
            adaptationPreferences: {
                conservative: 0.5,
                exploratory: 0.5
            }
        };
    }
    
    saveUserProfile() {
        try {
            localStorage.setItem('optimized_user_profile', JSON.stringify(this.userProfile));
        } catch (error) {
            console.warn('保存用户画像失败:', error);
        }
    }
    
    loadInteractionHistory() {
        try {
            const saved = localStorage.getItem('interaction_history_optimized');
            return saved ? JSON.parse(saved) : [];
        } catch (error) {
            return [];
        }
    }
    
    analyzeInputCharacteristics(input) {
        return {
            length: input.length,
            complexity: this.calculateTextComplexity(input),
            sentiment: this.analyzeSentiment(input),
            keywords: this.extractKeywords(input),
            questionType: this.classifyQuestionType(input)
        };
    }
    
    calculateTextComplexity(text) {
        const sentences = text.split(/[.!?。！？]+/).filter(s => s.trim());
        const words = text.split(/\s+/).filter(w => w.length > 0);
        
        if (words.length === 0) return 0;
        
        const avgSentenceLength = words.length / Math.max(1, sentences.length);
        const avgWordLength = words.reduce((sum, word) => sum + word.length, 0) / words.length;
        
        // 复杂度评分 (0-1)
        return Math.min(1, (avgSentenceLength / 20 + avgWordLength / 10) / 2);
    }
    
    analyzeSentiment(text) {
        const positiveWords = ['好', '棒', '喜欢', '满意', '优秀', 'great', 'good', 'excellent'];
        const negativeWords = ['差', '糟糕', '讨厌', '不满', '困难', 'bad', 'terrible', 'difficult'];
        
        let score = 0;
        const lowerText = text.toLowerCase();
        
        positiveWords.forEach(word => {
            if (lowerText.includes(word)) score += 1;
        });
        
        negativeWords.forEach(word => {
            if (lowerText.includes(word)) score -= 1;
        });
        
        if (score > 0) return 'positive';
        if (score < 0) return 'negative';
        return 'neutral';
    }
    
    extractKeywords(text) {
        // 简化的关键词提取
        const commonWords = ['的', '了', '在', '是', '我', '有', '和', '就', 'the', 'and', 'or', 'but'];
        const words = text.toLowerCase()
                         .replace(/[^\w\s\u4e00-\u9fff]/g, ' ')
                         .split(/\s+/)
                         .filter(word => word.length > 1 && !commonWords.includes(word));
        
        // 统计词频
        const wordCount = {};
        words.forEach(word => {
            wordCount[word] = (wordCount[word] || 0) + 1;
        });
        
        // 返回前5个高频词
        return Object.entries(wordCount)
                    .sort(([,a], [,b]) => b - a)
                    .slice(0, 5)
                    .map(([word]) => word);
    }
    
    classifyQuestionType(text) {
        const classifications = {
            'how-to': ['如何', '怎么', '怎样', 'how to', 'how do'],
            'troubleshooting': ['问题', '错误', 'bug', 'error', '解决', 'fix'],
            'learning': ['学习', '教程', '指南', 'learn', 'tutorial', 'guide'],
            'comparison': ['比较', '对比', '区别', 'compare', 'vs', 'difference'],
            'optimization': ['优化', '提升', '改善', 'optimize', 'improve', 'better']
        };
        
        const lowerText = text.toLowerCase();
        for (const [type, keywords] of Object.entries(classifications)) {
            if (keywords.some(keyword => lowerText.includes(keyword))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    extractContextPatterns(context) {
        return {
            timePattern: context.timeSlot || 'unknown',
            activityPattern: this.identifyActivityPattern(context),
            focusArea: context.primaryContext || 'general',
            environmentalSetup: context.environmentalFactors || {}
        };
    }
    
    identifyActivityPattern(context) {
        const activeDetectors = context.activeDetectors || [];
        if (activeDetectors.includes('programming') && activeDetectors.includes('debugging')) {
            return 'development_debugging';
        }
        if (activeDetectors.includes('learning') && activeDetectors.includes('research')) {
            return 'study_research';
        }
        if (activeDetectors.includes('creative') && activeDetectors.includes('writing')) {
            return 'creative_content';
        }
        return 'general';
    }
    
    calculateBehavioralMetrics() {
        const recentHistory = this.interactionHistory.slice(-20);
        return {
            interactionFrequency: recentHistory.length / 7, // 每周交互次数
            feedbackPositivity: this.calculateFeedbackPositivity(recentHistory),
            explorationRate: this.calculateExplorationRate(recentHistory),
            consistency: this.calculateConsistency(recentHistory)
        };
    }
    
    calculateFeedbackPositivity(history) {
        const feedbackEntries = history.filter(h => h.userFeedback);
        if (feedbackEntries.length === 0) return 0.5;
        
        const positiveCount = feedbackEntries.filter(h => h.userFeedback === 'positive').length;
        return positiveCount / feedbackEntries.length;
    }
    
    calculateExplorationRate(history) {
        if (history.length < 2) return 0;
        
        const uniqueRecommendations = new Set(history.map(h => h.recommendation?.type));
        return uniqueRecommendations.size / history.length;
    }
    
    calculateConsistency(history) {
        if (history.length < 5) return 0.5;
        
        const preferredTypes = this.getPreferredRecommendationTypes(history);
        const matches = history.filter(h => 
            preferredTypes.includes(h.recommendation?.type)
        ).length;
        
        return matches / history.length;
    }
    
    getPreferredRecommendationTypes(history) {
        const typeCount = {};
        history.forEach(h => {
            const type = h.recommendation?.type;
            if (type) {
                typeCount[type] = (typeCount[type] || 0) + 1;
            }
        });
        
        return Object.entries(typeCount)
                    .sort(([,a], [,b]) => b - a)
                    .slice(0, 3)
                    .map(([type]) => type);
    }
    
    extractCoreTraits() {
        const traits = {};
        const history = this.userProfile.history;
        
        // 分析学习偏好
        const learningInteractions = history.filter(h => 
            h.contextPatterns?.focusArea === 'learning'
        );
        traits.learningStyle = this.determineLearningStyle(learningInteractions);
        
        // 分析技术偏好
        const techInteractions = history.filter(h => 
            h.contextPatterns?.activityPattern?.includes('programming')
        );
        traits.techPreferences = this.determineTechPreferences(techInteractions);
        
        // 分析交互风格
        traits.interactionStyle = this.determineInteractionStyle(history);
        
        return traits;
    }
    
    determineLearningStyle(interactions) {
        const tutorialCount = interactions.filter(h => 
            h.inputCharacteristics?.questionType === 'learning'
        ).length;
        
        const handsOnCount = interactions.filter(h => 
            h.contextPatterns?.activityPattern === 'development_debugging'
        ).length;
        
        if (tutorialCount > handsOnCount) return 'theoretical';
        if (handsOnCount > tutorialCount) return 'practical';
        return 'balanced';
    }
    
    determineTechPreferences(interactions) {
        const languageUsage = {};
        interactions.forEach(h => {
            const lang = h.contextPatterns?.environmentalSetup?.language;
            if (lang) {
                languageUsage[lang] = (languageUsage[lang] || 0) + 1;
            }
        });
        
        const preferredLanguages = Object.entries(languageUsage)
                                        .sort(([,a], [,b]) => b - a)
                                        .slice(0, 3)
                                        .map(([lang]) => lang);
        
        return {
            languages: preferredLanguages,
            complexityPreference: this.determineComplexityPreference(interactions)
        };
    }
    
    determineComplexityPreference(interactions) {
        const complexities = interactions.map(h => h.inputCharacteristics?.complexity || 0);
        const avgComplexity = complexities.reduce((a,b) => a+b, 0) / Math.max(1, complexities.length);
        
        if (avgComplexity > 0.7) return 'advanced';
        if (avgComplexity > 0.4) return 'intermediate';
        return 'beginner';
    }
    
    determineInteractionStyle(history) {
        const responseTimes = [];
        for (let i = 1; i < history.length; i++) {
            responseTimes.push(history[i].timestamp - history[i-1].timestamp);
        }
        
        const avgResponseTime = responseTimes.reduce((a,b) => a+b, 0) / Math.max(1, responseTimes.length);
        
        if (avgResponseTime < 300000) return 'active'; // 5分钟内
        if (avgResponseTime < 1800000) return 'regular'; // 30分钟内
        return 'casual';
    }
    
    identifyPreferredStyles() {
        const styles = {};
        const recentHistory = this.interactionHistory.slice(-30);
        
        // 语言风格偏好
        styles.communicationStyle = this.determineCommunicationStyle(recentHistory);
        
        // 详细程度偏好
        styles.detailLevel = this.determineDetailPreference(recentHistory);
        
        // 互动方式偏好
        styles.interactionMode = this.determineInteractionMode(recentHistory);
        
        return styles;
    }
    
    determineCommunicationStyle(history) {
        const formalIndicators = ['正式', '专业', 'technical', 'formal'];
        const casualIndicators = ['轻松', '简单', 'easy', 'casual'];
        
        let formalCount = 0;
        let casualCount = 0;
        
        history.forEach(h => {
            const text = h.userInput || '';
            formalIndicators.forEach(indicator => {
                if (text.includes(indicator)) formalCount++;
            });
            casualIndicators.forEach(indicator => {
                if (text.includes(indicator)) casualCount++;
            });
        });
        
        return formalCount > casualCount ? 'formal' : 'casual';
    }
    
    determineDetailPreference(history) {
        const inputLengths = history.map(h => h.userInput?.length || 0);
        const avgLength = inputLengths.reduce((a,b) => a+b, 0) / Math.max(1, inputLengths.length);
        
        if (avgLength > 200) return 'detailed';
        if (avgLength > 50) return 'moderate';
        return 'brief';
    }
    
    determineInteractionMode(history) {
        const questionTypes = history.map(h => h.inputCharacteristics?.questionType || 'general');
        const questionCount = questionTypes.filter(type => type !== 'general').length;
        
        const directiveCount = history.filter(h => 
            (h.userInput || '').includes('帮我') || (h.userInput || '').includes('please')
        ).length;
        
        if (questionCount > history.length * 0.7) return 'inquiring';
        if (directiveCount > history.length * 0.5) return 'directive';
        return 'collaborative';
    }
    
    assessSkillLevel() {
        const recentHistory = this.interactionHistory.slice(-20);
        const complexInteractions = recentHistory.filter(h => 
            h.inputCharacteristics?.complexity > 0.6
        );
        
        const successRate = this.calculateSuccessRate(recentHistory);
        
        if (complexInteractions.length > 10 && successRate > 0.7) return 'advanced';
        if (complexInteractions.length > 5 && successRate > 0.5) return 'intermediate';
        return 'beginner';
    }
    
    calculateSuccessRate(history) {
        const feedbackEntries = history.filter(h => h.userFeedback);
        if (feedbackEntries.length === 0) return 0.5;
        
        const positiveFeedback = feedbackEntries.filter(h => h.userFeedback === 'positive').length;
        return positiveFeedback / feedbackEntries.length;
    }
    
    findHistoricalSuccesses() {
        return this.interactionHistory
            .filter(h => h.userFeedback === 'positive')
            .sort((a, b) => b.timestamp - a.timestamp)
            .slice(0, 10);
    }
    
    async findContextualMatches(contextAnalysis) {
        const matches = [];
        const recentHistory = this.interactionHistory.slice(-50);
        
        recentHistory.forEach(historyItem => {
            const similarity = this.calculateContextSimilarity(
                contextAnalysis, 
                historyItem.contextAnalysis
            );
            
            if (similarity > this.config.similarityThreshold) {
                matches.push({
                    recommendation: historyItem.recommendation,
                    similarityScore: similarity,
                    historicalContext: historyItem.context
                });
            }
        });
        
        return matches;
    }
    
    calculateContextSimilarity(current, historical) {
        if (!historical) return 0;
        
        let similarity = 0;
        let totalFactors = 0;
        
        // 时间因素相似度
        if (current.temporalFactors && historical.temporalFactors) {
            similarity += this.compareTemporalFactors(
                current.temporalFactors, 
                historical.temporalFactors
            );
            totalFactors++;
        }
        
        // 行为模式相似度
        if (current.behavioralPatterns && historical.behavioralPatterns) {
            similarity += this.compareBehavioralPatterns(
                current.behavioralPatterns, 
                historical.behavioralPatterns
            );
            totalFactors++;
        }
        
        // 认知负荷相似度
        if (current.cognitiveLoad && historical.cognitiveLoad) {
            similarity += 1 - Math.abs(
                current.cognitiveLoad - historical.cognitiveLoad
            );
            totalFactors++;
        }
        
        return totalFactors > 0 ? similarity / totalFactors : 0;
    }
    
    compareTemporalFactors(current, historical) {
        const factors = ['timeOfDay', 'dayOfWeek', 'season'];
        let matches = 0;
        
        factors.forEach(factor => {
            if (current[factor] === historical[factor]) {
                matches++;
            }
        });
        
        return matches / factors.length;
    }
    
    compareBehavioralPatterns(current, historical) {
        const patternKeys = Object.keys(current);
        let similarity = 0;
        
        patternKeys.forEach(key => {
            if (current[key] === historical[key]) {
                similarity += 1;
            }
        });
        
        return patternKeys.length > 0 ? similarity / patternKeys.length : 0;
    }
    
    async getCollaborativeSuggestions() {
        // 简化的协同过滤实现
        const similarUsers = this.findSimilarUsers();
        const suggestions = [];
        
        similarUsers.forEach(user => {
            const userSuccesses = user.history.filter(h => h.feedback === 'positive');
            userSuccesses.forEach(success => {
                suggestions.push({
                    recommendation: success.recommendation,
                    confidence: success.confidence * 0.8,
                    similarity: user.similarityScore
                });
            });
        });
        
        return suggestions;
    }
    
    findSimilarUsers() {
        // 简化实现 - 在实际应用中这里会有更复杂的用户相似度计算
        return [{
            userId: 'similar_user_1',
            similarityScore: 0.75,
            history: this.interactionHistory.slice(-10).map(h => ({
                ...h,
                feedback: 'positive'
            }))
        }];
    }
    
    async getReinforcementLearningSuggestions(contextAnalysis) {
        // 简化的强化学习实现
        const state = this.encodeState(contextAnalysis);
        const actions = this.getPossibleActions();
        
        const qValues = actions.map(action => ({
            action: action,
            qValue: this.calculateQValue(state, action)
        }));
        
        return qValues.sort((a, b) => b.qValue - a.qValue).slice(0, 3);
    }
    
    encodeState(contextAnalysis) {
        // 将情境分析编码为状态向量
        return JSON.stringify(contextAnalysis);
    }
    
    getPossibleActions() {
        return [
            'provide_tutorial',
            'offer_debugging_help',
            'suggest_optimization',
            'recommend_resources',
            'propose_collaboration'
        ];
    }
    
    calculateQValue(state, action) {
        // 简化的Q值计算
        const baseValue = 0.5;
        const contextBonus = this.getContextActionBonus(state, action);
        const historicalBonus = this.getHistoricalSuccessBonus(action);
        
        return Math.min(1, baseValue + contextBonus + historicalBonus);
    }
    
    getContextActionBonus(state, action) {
        // 基于情境的动作奖励
        const bonuses = {
            'provide_tutorial': state.includes('learning') ? 0.3 : 0,
            'offer_debugging_help': state.includes('debugging') ? 0.4 : 0,
            'suggest_optimization': state.includes('performance') ? 0.3 : 0
        };
        
        return bonuses[action] || 0;
    }
    
    getHistoricalSuccessBonus(action) {
        const successes = this.interactionHistory.filter(h => 
            h.userFeedback === 'positive' && h.recommendation?.type === action
        );
        
        return Math.min(0.2, successes.length * 0.05);
    }
    
    calculateCandidateScore(candidate) {
        let score = 0.5; // 基础分数
        
        // 用户画像匹配度
        score += this.calculateProfileMatch(candidate) * 0.3;
        
        // 历史成功率
        score += this.calculateHistoricalSuccessRate(candidate) * 0.2;
        
        // 时效性权重
        score += this.calculateRecencyWeight(candidate) * 0.1;
        
        return Math.min(1, Math.max(0, score));
    }
    
    calculateProfileMatch(candidate) {
        const traits = this.userProfile.coreTraits;
        const matches = {
            'technical_depth': traits.skillLevel === 'advanced' ? 0.8 : 0.4,
            'learning_oriented': traits.learningStyle === 'theoretical' ? 0.7 : 0.5,
            'practical_focus': traits.learningStyle === 'practical' ? 0.8 : 0.4
        };
        
        return matches[candidate.type] || 0.5;
    }
    
    calculateHistoricalSuccessRate(candidate) {
        const similarRecommendations = this.interactionHistory.filter(h => 
            h.recommendation?.type === candidate.type
        );
        
        if (similarRecommendations.length === 0) return 0.5;
        
        const successes = similarRecommendations.filter(h => h.userFeedback === 'positive').length;
        return successes / similarRecommendations.length;
    }
    
    calculateRecencyWeight(candidate) {
        // 假设候选推荐有时间戳
        const age = Date.now() - (candidate.timestamp || Date.now());
        const daysOld = age / (1000 * 60 * 60 * 24);
        
        // 较新的推荐获得更高权重
        return Math.max(0, 1 - daysOld / 30);
    }
    
    async adjustForContext(recommendation, contextAnalysis) {
        const adjustments = {
            'high_cognitive_load': { detailLevel: 'reduced', complexity: 'simplified' },
            'low_energy': { tone: 'encouraging', length: 'shorter' },
            'high_stress': { approach: 'step_by_step', reassurance: 'included' }
        };
        
        let adjusted = { ...recommendation };
        
        // 根据认知负荷调整
        if (contextAnalysis.cognitiveLoad > 0.7) {
            adjusted = this.applyAdjustments(adjusted, adjustments['high_cognitive_load']);
        }
        
        // 根据情绪状态调整
        if (contextAnalysis.emotionalIndicators?.stressLevel > 0.6) {
            adjusted = this.applyAdjustments(adjusted, adjustments['high_stress']);
        }
        
        return adjusted;
    }
    
    applyAdjustments(recommendation, adjustments) {
        return {
            ...recommendation,
            adjustments: { ...recommendation.adjustments, ...adjustments }
        };
    }
    
    matchUserStyle(recommendation) {
        const styles = this.userProfile.preferredStyles;
        
        // 调整沟通风格
        if (styles.communicationStyle === 'formal' && recommendation.tone !== 'formal') {
            recommendation.tone = 'formal';
        }
        
        // 调整详细程度
        if (styles.detailLevel === 'brief' && recommendation.detailLevel !== 'concise') {
            recommendation.detailLevel = 'concise';
        }
        
        return recommendation;
    }
    
    calculatePersonalizationScore(recommendation) {
        const factors = [
            recommendation.personalizationScore || 0.5,
            this.userProfile.adaptationPreferences.conservative,
            this.calculateContextRelevance(recommendation)
        ];
        
        return factors.reduce((a, b) => a + b, 0) / factors.length;
    }
    
    calculateContextRelevance(recommendation) {
        // 基于推荐类型和当前情境的相关性
        const contextWeights = {
            'programming': ['technical', 'debugging', 'optimization'],
            'learning': ['tutorial', 'educational', 'guidance'],
            'creative': ['inspirational', 'design', 'innovative']
        };
        
        const currentContext = this.getCurrentContextType();
        const relevantTypes = contextWeights[currentContext] || [];
        
        return relevantTypes.includes(recommendation.type) ? 0.8 : 0.3;
    }
    
    getCurrentContextType() {
        // 简化实现
        return 'general';
    }
    
    recordInteraction(userInput, context, recommendation) {
        const interaction = {
            id: this.generateInteractionId(),
            timestamp: Date.now(),
            userInput: userInput,
            context: context,
            recommendation: recommendation,
            userFeedback: null,
            feedbackComments: '',
            feedbackTimestamp: null
        };
        
        this.interactionHistory.push(interaction);
        
        if (this.interactionHistory.length > this.config.maxHistoryLength) {
            this.interactionHistory.shift();
        }
        
        this.saveInteractionHistory();
        
        return interaction.id;
    }
    
    saveInteractionHistory() {
        try {
            localStorage.setItem('interaction_history_optimized', 
                              JSON.stringify(this.interactionHistory));
        } catch (error) {
            console.warn('保存交互历史失败:', error);
        }
    }
    
    getDefaultRecommendation(context) {
        return {
            type: 'general_assistance',
            content: '您好！我可以帮助您解决各种问题，请告诉我您需要什么帮助。',
            confidence: 0.3,
            source: 'default',
            personalizationScore: 0.1
        };
    }
    
    generateUserId() {
        return 'user_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    generateInteractionId() {
        return 'int_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    // 分析时间情境
    analyzeTemporalContext(context) {
        const now = new Date();
        return {
            timeOfDay: this.getTimeOfDay(now),
            dayOfWeek: now.getDay(),
            isWeekend: [0, 6].includes(now.getDay()),
            season: this.getSeason(now.getMonth()),
            workHours: this.isWorkHours(now)
        };
    }
    
    getTimeOfDay(date) {
        const hour = date.getHours();
        if (hour >= 6 && hour < 12) return 'morning';
        if (hour >= 12 && hour < 18) return 'afternoon';
        if (hour >= 18 && hour < 22) return 'evening';
        return 'night';
    }
    
    getSeason(month) {
        if (month >= 11 || month <= 1) return 'winter';
        if (month >= 2 && month <= 4) return 'spring';
        if (month >= 5 && month <= 7) return 'summer';
        return 'autumn';
    }
    
    isWorkHours(date) {
        const hour = date.getHours();
        return hour >= 9 && hour <= 18;
    }
    
    // 识别行为模式
    async identifyBehavioralPatterns(context) {
        return {
            interactionFrequency: await this.measureInteractionFrequency(),
            attentionSpan: await this.estimateAttentionSpan(),
            taskSwitching: await this.detectTaskSwitching(),
            learningPace: await this.assessLearningPace()
        };
    }
    
    async measureInteractionFrequency() {
        const recentInteractions = this.interactionHistory.slice(-10);
        if (recentInteractions.length < 2) return 'moderate';
        
        const intervals = [];
        for (let i = 1; i < recentInteractions.length; i++) {
            intervals.push(
                recentInteractions[i].timestamp - recentInteractions[i-1].timestamp
            );
        }
        
        const avgInterval = intervals.reduce((a,b) => a+b, 0) / intervals.length;
        const minutes = avgInterval / (1000 * 60);
        
        if (minutes < 5) return 'high';
        if (minutes < 30) return 'moderate';
        return 'low';
    }
    
    async estimateAttentionSpan() {
        const recentLongSessions = this.interactionHistory
            .filter(h => h.sessionDuration > 300000) // 5分钟以上
            .slice(-5);
            
        return recentLongSessions.length > 2 ? 'long' : 'short';
    }
    
    async detectTaskSwitching() {
        const recentContexts = this.interactionHistory
            .slice(-10)
            .map(h => h.context?.primaryContext || 'general');
            
        const uniqueContexts = new Set(recentContexts);
        return uniqueContexts.size > 3 ? 'frequent' : 'infrequent';
    }
    
    async assessLearningPace() {
        const learningInteractions = this.interactionHistory
            .filter(h => h.context?.primaryContext === 'learning')
            .slice(-20);
            
        if (learningInteractions.length < 5) return 'unknown';
        
        const complexityProgression = learningInteractions.map(h => 
            h.inputCharacteristics?.complexity || 0
        );
        
        const trend = this.calculateTrend(complexityProgression);
        if (trend > 0.1) return 'fast';
        if (trend < -0.1) return 'slow';
        return 'steady';
    }
    
    calculateTrend(values) {
        if (values.length < 2) return 0;
        
        const n = values.length;
        const sumX = (n * (n - 1)) / 2;
        const sumY = values.reduce((a, b) => a + b, 0);
        const sumXY = values.reduce((sum, y, i) => sum + y * i, 0);
        const sumXX = values.reduce((sum, _, i) => sum + i * i, 0);
        
        return (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    }
    
    // 检测情绪状态
    async detectEmotionalState(context) {
        return {
            stressLevel: await this.assessStressLevel(context),
            frustration: await this.detectFrustration(context),
            engagement: await this.measureEngagement(context),
            satisfaction: await this.estimateSatisfaction()
        };
    }
    
    async assessStressLevel(context) {
        // 基于打字速度、错误率等指标
        const typingSpeed = this.estimateTypingSpeed();
        const errorRate = this.calculateErrorRate();
        
        let stressScore = 0;
        if (typingSpeed > 100) stressScore += 0.3; // 快速打字可能表示紧张
        if (errorRate > 0.1) stressScore += 0.4;   // 高错误率表示压力
        
        return Math.min(1, stressScore);
    }
    
    estimateTypingSpeed() {
        // 简化实现
        return 60; // 每分钟字符数
    }
    
    calculateErrorRate() {
        // 简化实现
        return 0.05; // 5%的错误率
    }
    
    async detectFrustration(context) {
        const recentFeedback = this.interactionHistory
            .slice(-5)
            .filter(h => h.userFeedback);
            
        const negativeFeedback = recentFeedback.filter(h => h.userFeedback === 'negative').length;
        return recentFeedback.length > 0 ? negativeFeedback / recentFeedback.length : 0;
    }
    
    async measureEngagement(context) {
        const activeTime = this.calculateActiveTime();
        const interactionDepth = this.assessInteractionDepth();
        
        return (activeTime + interactionDepth) / 2;
    }
    
    calculateActiveTime() {
        const recentSession = this.interactionHistory.slice(-1)[0];
        if (!recentSession) return 0.5;
        
        const duration = Date.now() - recentSession.timestamp;
        const minutes = duration / (1000 * 60);
        
        return Math.min(1, minutes / 30); // 30分钟内线性增长
    }
    
    assessInteractionDepth() {
        const recentInputs = this.interactionHistory
            .slice(-5)
            .map(h => h.userInput?.length || 0);
            
        const avgLength = recentInputs.reduce((a,b) => a+b, 0) / Math.max(1, recentInputs.length);
        return Math.min(1, avgLength / 200); // 200字符为满分
    }
    
    async estimateSatisfaction() {
        const recentPositiveFeedback = this.interactionHistory
            .slice(-10)
            .filter(h => h.userFeedback === 'positive').length;
            
        return recentPositiveFeedback / 10;
    }
    
    // 评估认知负荷
    assessCognitiveLoad(context) {
        const factors = {
            taskComplexity: this.assessTaskComplexity(context),
            multitasking: this.detectMultitasking(context),
            timePressure: this.assessTimePressure(context),
            familiarity: this.assessFamiliarity(context)
        };
        
        return (factors.taskComplexity + factors.multitasking + 
                factors.timePressure - factors.familiarity) / 4;
    }
    
    assessTaskComplexity(context) {
        const complexityIndicators = [
            context.activeDetectors?.length || 0,
            context.detectedContexts?.programming?.complexity === 'high' ? 1 : 0,
            context.detectedContexts?.analytics?.dataType ? 0.5 : 0
        ];
        
        return Math.min(1, complexityIndicators.reduce((a,b) => a+b, 0) / 2);
    }
    
    detectMultitasking(context) {
        const activeContexts = context.activeDetectors || [];
        return activeContexts.length > 2 ? 0.8 : 
               activeContexts.length > 1 ? 0.5 : 0;
    }
    
    assessTimePressure(context) {
        // 基于时间情境判断
        const temporal = this.analyzeTemporalContext(context);
        return temporal.workHours ? 0.6 : 0.3;
    }
    
    assessFamiliarity(context) {
        const familiarContexts = this.interactionHistory
            .filter(h => h.context?.primaryContext === context.primaryContext)
            .length;
            
        return Math.min(1, familiarContexts / 20);
    }
    
    // 分析社会因素
    analyzeSocialFactors(context) {
        return {
            collaborationLevel: context.detectedContexts?.collaboration ? 'high' : 'low',
            socialMediaActivity: this.detectSocialMediaPresence(),
            communicationNeeds: this.assessCommunicationNeeds(context)
        };
    }
    
    detectSocialMediaPresence() {
        // 检测页面中是否有社交媒体相关内容
        const socialKeywords = ['facebook', 'twitter', 'wechat', 'qq', 'social'];
        const pageText = document.body.textContent.toLowerCase();
        
        return socialKeywords.some(keyword => pageText.includes(keyword)) ? 'active' : 'inactive';
    }
    
    assessCommunicationNeeds(context) {
        const collaborativeContexts = ['collaboration', 'team', 'shared'];
        const isCollaborative = collaborativeContexts.some(ctx => 
            context.activeDetectors?.includes(ctx)
        );
        
        return isCollaborative ? 'high' : 'low';
    }
    
    // 分析环境因素
    analyzeEnvironmentalContext(context) {
        return {
            deviceType: this.detectDeviceType(),
            networkQuality: this.assessNetworkQuality(),
            physicalEnvironment: this.inferPhysicalEnvironment(context)
        };
    }
    
    detectDeviceType() {
        const ua = navigator.userAgent.toLowerCase();
        if (/mobile|android|iphone/.test(ua)) return 'mobile';
        if (/tablet|ipad/.test(ua)) return 'tablet';
        return 'desktop';
    }
    
    assessNetworkQuality() {
        // 简化实现
        return navigator.connection?.effectiveType || 'unknown';
    }
    
    inferPhysicalEnvironment(context) {
        // 基于时间和设备推断物理环境
        const temporal = this.analyzeTemporalContext(context);
        const device = this.detectDeviceType();
        
        if (temporal.workHours && device === 'desktop') return 'office';
        if (!temporal.workHours && device === 'mobile') return 'home';
        return 'unknown';
    }
    
    updateProfileFromFeedback(interactionRecord) {
        // 根据反馈更新用户画像
        if (interactionRecord.userFeedback === 'negative') {
            // 减少类似推荐的权重
            this.decreaseRecommendationWeight(interactionRecord.recommendation.type);
        } else if (interactionRecord.userFeedback === 'positive') {
            // 增加类似推荐的权重
            this.increaseRecommendationWeight(interactionRecord.recommendation.type);
        }
    }
    
    decreaseRecommendationWeight(type) {
        // 实现权重衰减逻辑
        console.log(`降低 ${type} 类型推荐的权重`);
    }
    
    increaseRecommendationWeight(type) {
        // 实现权重增强逻辑
        console.log(`提高 ${type} 类型推荐的权重`);
    }
}

// 偏好学习模型
class PreferenceLearningModel {
    update(context, recommendation, feedback) {
        // 实现偏好学习算法
        console.log('更新偏好模型:', { context, recommendation, feedback });
    }
}

// 自适应推荐引擎
class AdaptiveRecommendationEngine {
    updateStrategy(feedbackInsights) {
        // 根据反馈洞察调整推荐策略
        console.log('调整推荐策略:', feedbackInsights);
    }
}

// 反馈分析系统
class FeedbackAnalysisSystem {
    analyze(feedback, comments) {
        return {
            feedbackType: feedback,
            sentiment: this.analyzeCommentSentiment(comments),
            keyThemes: this.extractKeyThemes(comments)
        };
    }
    
    analyzeCommentSentiment(comments) {
        if (!comments) return 'neutral';
        const lowerComments = comments.toLowerCase();
        if (lowerComments.includes('很好') || lowerComments.includes('great')) return 'positive';
        if (lowerComments.includes('不好') || lowerComments.includes('bad')) return 'negative';
        return 'neutral';
    }
    
    extractKeyThemes(comments) {
        if (!comments) return [];
        // 简化的主题提取
        return comments.split(/[，。！？,.\n]/).filter(t => t.length > 5);
    }
}

// 全局实例
const OptimizedPersonalizer = new OptimizedPersonalizationEngine();

// 便捷的全局方法
window.getOptimizedRecommendation = async function(userInput, context = {}) {
    return await OptimizedPersonalizer.getPersonalizedRecommendation(userInput, context);
};

window.recordOptimizedFeedback = function(interactionId, feedback, comments = '') {
    const interaction = OptimizedPersonalizer.interactionHistory.find(h => h.id === interactionId);
    if (interaction) {
        interaction.userFeedback = feedback;
        interaction.feedbackComments = comments;
        interaction.feedbackTimestamp = Date.now();
        OptimizedPersonalizer.learnFromFeedback(interaction);
        OptimizedPersonalizer.saveInteractionHistory();
    }
};

window.getPersonalizationStats = function() {
    return {
        userProfile: OptimizedPersonalizer.userProfile,
        interactionHistory: OptimizedPersonalizer.interactionHistory.length,
        preferenceModel: OptimizedPersonalizer.preferenceModel,
        adaptationEngine: OptimizedPersonalizer.adaptationEngine
    };
};

console.log('🚀 优化个性化算法引擎已启动');
console.log('使用方法:');
console.log('- await getOptimizedRecommendation("您的需求", context)');
console.log('- recordOptimizedFeedback(interactionId, "positive/negative/neutral", "评论")');
console.log('- getPersonalizationStats() 查看统计信息');