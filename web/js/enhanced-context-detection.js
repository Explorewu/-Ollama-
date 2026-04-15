/**
 * 增强情境识别系统
 * 提供多维度的情境检测能力
 */

class EnhancedContextDetectionSystem {
    constructor() {
        this.detectors = this.initializeDetectors();
        this.currentContext = {};
        this.history = [];
        this.maxHistory = 50;
    }
    
    initializeDetectors() {
        return {
            // 编程相关检测
            programming: new ProgrammingContextDetector(),
            
            // 学习相关检测
            learning: new LearningContextDetector(),
            
            // 创意工作检测
            creative: new CreativeContextDetector(),
            
            // 协作相关检测
            collaboration: new CollaborationContextDetector(),
            
            // 数据分析检测
            analytics: new AnalyticsContextDetector(),
            
            // 调试相关检测
            debugging: new DebuggingContextDetector(),
            
            // 写作相关检测
            writing: new WritingContextDetector(),
            
            // 研究相关检测
            research: new ResearchContextDetector()
        };
    }
    
    async getCurrentContext() {
        const context = {
            timestamp: Date.now(),
            activeDetectors: [],
            detectedContexts: {}
        };
        
        // 并行执行所有检测器
        const detectionPromises = Object.entries(this.detectors).map(async ([name, detector]) => {
            try {
                const result = await detector.detect();
                if (result.isActive) {
                    context.activeDetectors.push(name);
                    context.detectedContexts[name] = result;
                }
                return { name, result };
            } catch (error) {
                console.warn(`检测器 ${name} 执行失败:`, error);
                return { name, result: { isActive: false, error: error.message } };
            }
        });
        
        await Promise.all(detectionPromises);
        
        // 分析上下文关系
        context.relationships = this.analyzeContextRelationships(context.detectedContexts);
        
        // 评估主要情境
        context.primaryContext = this.determinePrimaryContext(context);
        
        // 更新历史记录
        this.updateHistory(context);
        
        this.currentContext = context;
        return context;
    }
    
    analyzeContextRelationships(detectedContexts) {
        const relationships = {};
        
        // 检测编程与调试的关系
        if (detectedContexts.programming?.isActive && detectedContexts.debugging?.isActive) {
            relationships.programming_debugging = 'combined';
        }
        
        // 检测学习与研究的关系
        if (detectedContexts.learning?.isActive && detectedContexts.research?.isActive) {
            relationships.learning_research = 'synergistic';
        }
        
        // 检测创意与写作的关系
        if (detectedContexts.creative?.isActive && detectedContexts.writing?.isActive) {
            relationships.creative_writing = 'complementary';
        }
        
        return relationships;
    }
    
    determinePrimaryContext(context) {
        const weights = {
            programming: 1.0,
            debugging: 0.9,
            learning: 0.8,
            creative: 0.7,
            collaboration: 0.6,
            analytics: 0.5,
            writing: 0.4,
            research: 0.3
        };
        
        let primaryContext = 'general';
        let highestWeight = 0;
        
        context.activeDetectors.forEach(detectorName => {
            const weight = weights[detectorName] || 0;
            if (weight > highestWeight) {
                highestWeight = weight;
                primaryContext = detectorName;
            }
        });
        
        return primaryContext;
    }
    
    updateHistory(context) {
        this.history.push({
            ...context,
            id: this.generateId()
        });
        
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
        
        // 保存到localStorage
        try {
            localStorage.setItem('context_detection_history', JSON.stringify(this.history));
        } catch (error) {
            console.warn('保存情境历史失败:', error);
        }
    }
    
    generateId() {
        return 'ctx_' + Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    getContextHistory(filter = {}) {
        let filteredHistory = [...this.history];
        
        if (filter.detector) {
            filteredHistory = filteredHistory.filter(record => 
                record.activeDetectors.includes(filter.detector)
            );
        }
        
        if (filter.timeRange) {
            const cutoffTime = Date.now() - filter.timeRange;
            filteredHistory = filteredHistory.filter(record => 
                record.timestamp > cutoffTime
            );
        }
        
        return filteredHistory;
    }
    
    getPatternAnalysis() {
        const analysis = {
            frequency: {},
            sequences: [],
            correlations: {}
        };
        
        // 统计频率
        this.history.forEach(record => {
            record.activeDetectors.forEach(detector => {
                analysis.frequency[detector] = (analysis.frequency[detector] || 0) + 1;
            });
        });
        
        // 分析序列模式
        for (let i = 1; i < this.history.length; i++) {
            const prev = this.history[i-1].activeDetectors;
            const current = this.history[i].activeDetectors;
            
            const sequence = `${prev.sort().join(',')}>${current.sort().join(',')}`;
            analysis.sequences[sequence] = (analysis.sequences[sequence] || 0) + 1;
        }
        
        return analysis;
    }
}

// 编程情境检测器
class ProgrammingContextDetector {
    async detect() {
        const result = {
            isActive: false,
            language: null,
            frameworks: [],
            complexity: 'unknown',
            editorType: 'unknown'
        };
        
        const activeElement = document.activeElement;
        
        // 检测代码编辑器
        const editorSelectors = [
            '.code-editor', '.editor', '.monaco-editor', '.ace_editor',
            '[data-language]', '[class*="code"]', 'textarea[data-editor]'
        ];
        
        const isCodeEditor = editorSelectors.some(selector => 
            activeElement?.matches(selector) || activeElement?.closest(selector)
        );
        
        if (isCodeEditor) {
            result.isActive = true;
            result.language = this.detectLanguage(activeElement);
            result.frameworks = this.detectFrameworks();
            result.complexity = this.assessComplexity();
            result.editorType = this.detectEditorType();
        }
        
        return result;
    }
    
    detectLanguage(element) {
        // 从元素属性或内容推断语言
        const langAttr = element.getAttribute('data-language') || 
                        element.className.match(/lang-(\w+)/)?.[1];
        
        if (langAttr) return langAttr;
        
        // 从文件扩展名推断
        const fileName = element.id || '';
        const extMatch = fileName.match(/\.(\w+)$/);
        if (extMatch) {
            const extensions = {
                'js': 'javascript', 'ts': 'typescript', 'py': 'python',
                'java': 'java', 'cpp': 'cpp', 'html': 'html', 'css': 'css'
            };
            return extensions[extMatch[1]] || extMatch[1];
        }
        
        return 'unknown';
    }
    
    detectFrameworks() {
        const frameworks = [];
        const frameworkIndicators = {
            'react': ['.jsx', '.tsx', 'React.', 'useState', 'useEffect'],
            'vue': ['Vue.', 'v-', '@click', 'vue'],
            'angular': ['ng-', 'Angular.', '@Component'],
            'node': ['require(', 'import ', 'express', 'npm']
        };
        
        const pageContent = document.body.textContent.toLowerCase();
        Object.entries(frameworkIndicators).forEach(([framework, indicators]) => {
            if (indicators.some(indicator => pageContent.includes(indicator))) {
                frameworks.push(framework);
            }
        });
        
        return frameworks;
    }
    
    assessComplexity() {
        const codeElements = document.querySelectorAll('pre, code, .code-block');
        const totalLines = Array.from(codeElements).reduce((total, el) => {
            return total + (el.textContent.match(/\n/g) || []).length + 1;
        }, 0);
        
        if (totalLines > 1000) return 'high';
        if (totalLines > 100) return 'medium';
        if (totalLines > 10) return 'low';
        return 'minimal';
    }
    
    detectEditorType() {
        if (document.querySelector('.monaco-editor')) return 'vscode';
        if (document.querySelector('.ace_editor')) return 'ace';
        if (document.querySelector('[data-editor="codemirror"]')) return 'codemirror';
        return 'basic';
    }
}

// 学习情境检测器
class LearningContextDetector {
    async detect() {
        const result = {
            isActive: false,
            learningType: 'unknown',
            subject: 'unknown',
            difficulty: 'unknown',
            resources: []
        };
        
        const learningIndicators = [
            '.tutorial', '.course', '.lesson', '.documentation', 
            '.guide', '.manual', '[class*="learn"]', '[class*="study"]'
        ];
        
        const hasLearningContent = learningIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasLearningContent) {
            result.isActive = true;
            result.learningType = this.detectLearningType();
            result.subject = this.detectSubject();
            result.difficulty = this.assessDifficulty();
            result.resources = this.findLearningResources();
        }
        
        return result;
    }
    
    detectLearningType() {
        const content = document.body.textContent.toLowerCase();
        const typeIndicators = {
            'tutorial': ['step by step', 'how to', 'guide', 'walkthrough'],
            'course': ['module', 'lesson', 'chapter', 'curriculum'],
            'documentation': ['api', 'reference', 'docs', 'manual'],
            'practice': ['exercise', 'quiz', 'challenge', 'hands-on']
        };
        
        for (const [type, indicators] of Object.entries(typeIndicators)) {
            if (indicators.some(indicator => content.includes(indicator))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    detectSubject() {
        const title = document.title.toLowerCase();
        const subjects = ['javascript', 'python', 'react', 'vue', 'database', 'algorithm'];
        return subjects.find(subject => title.includes(subject)) || 'unknown';
    }
    
    assessDifficulty() {
        const content = document.body.textContent.toLowerCase();
        const advancedTerms = ['advanced', 'complex', 'expert', 'senior'];
        const beginnerTerms = ['beginner', 'basic', 'intro', 'fundamental'];
        
        const advancedCount = advancedTerms.filter(term => content.includes(term)).length;
        const beginnerCount = beginnerTerms.filter(term => content.includes(term)).length;
        
        if (advancedCount > beginnerCount) return 'advanced';
        if (beginnerCount > advancedCount) return 'beginner';
        return 'intermediate';
    }
    
    findLearningResources() {
        const resources = [];
        const resourceTypes = {
            'video': 'video',
            'pdf': 'document',
            'github': 'repository',
            'demo': 'interactive'
        };
        
        Object.entries(resourceTypes).forEach(([keyword, type]) => {
            if (document.body.textContent.toLowerCase().includes(keyword)) {
                resources.push(type);
            }
        });
        
        return resources;
    }
}

// 创意工作检测器
class CreativeContextDetector {
    async detect() {
        const result = {
            isActive: false,
            creativeType: 'unknown',
            tools: [],
            inspirationSources: []
        };
        
        const creativeIndicators = [
            '.design-tool', '.canvas', '.drawing', '.writing-area',
            '[class*="creative"]', '[class*="design"]', '[class*="art"]'
        ];
        
        const hasCreativeElements = creativeIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasCreativeElements) {
            result.isActive = true;
            result.creativeType = this.detectCreativeType();
            result.tools = this.detectCreativeTools();
            result.inspirationSources = this.findInspirationSources();
        }
        
        return result;
    }
    
    detectCreativeType() {
        const content = document.body.textContent.toLowerCase();
        const typeIndicators = {
            'design': ['layout', 'color', 'typography', 'ui', 'ux'],
            'writing': ['story', 'article', 'blog', 'copy', 'content'],
            'visual': ['image', 'photo', 'graphic', 'illustration'],
            'music': ['audio', 'sound', 'composition', 'melody']
        };
        
        for (const [type, indicators] of Object.entries(typeIndicators)) {
            if (indicators.some(indicator => content.includes(indicator))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    detectCreativeTools() {
        const tools = [];
        const toolIndicators = {
            'figma': 'design',
            'photoshop': 'image-editing',
            'canva': 'graphic-design',
            'notion': 'content-creation'
        };
        
        Object.entries(toolIndicators).forEach(([tool, category]) => {
            if (document.body.textContent.toLowerCase().includes(tool)) {
                tools.push({ name: tool, category });
            }
        });
        
        return tools;
    }
    
    findInspirationSources() {
        const sources = [];
        const inspirationTypes = ['gallery', 'portfolio', 'inspiration', 'examples'];
        
        inspirationTypes.forEach(type => {
            if (document.body.textContent.toLowerCase().includes(type)) {
                sources.push(type);
            }
        });
        
        return sources;
    }
}

// 协作情境检测器
class CollaborationContextDetector {
    async detect() {
        const result = {
            isActive: false,
            collaborationType: 'unknown',
            teamSize: 'unknown',
            communicationChannels: []
        };
        
        const collabIndicators = [
            '.collaboration', '.team', '.shared', '.comments',
            '[class*="collab"]', '[class*="team"]', '[data-shared]'
        ];
        
        const hasCollaboration = collabIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasCollaboration) {
            result.isActive = true;
            result.collaborationType = this.detectCollaborationType();
            result.teamSize = this.estimateTeamSize();
            result.communicationChannels = this.detectCommunicationChannels();
        }
        
        return result;
    }
    
    detectCollaborationType() {
        const content = document.body.textContent.toLowerCase();
        const typeIndicators = {
            'pair-programming': ['pair', 'buddy', 'driver', 'navigator'],
            'team-project': ['team', 'group', 'project', 'sprint'],
            'review': ['review', 'feedback', 'comment', 'suggest'],
            'brainstorming': ['brainstorm', 'idea', 'discussion', 'meeting']
        };
        
        for (const [type, indicators] of Object.entries(typeIndicators)) {
            if (indicators.some(indicator => content.includes(indicator))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    estimateTeamSize() {
        const userAvatars = document.querySelectorAll('[class*="avatar"], [class*="user"]');
        const avatarCount = userAvatars.length;
        
        if (avatarCount > 10) return 'large';
        if (avatarCount > 3) return 'medium';
        if (avatarCount > 1) return 'small';
        return 'individual';
    }
    
    detectCommunicationChannels() {
        const channels = [];
        const channelTypes = {
            'chat': ['chat', 'message', 'slack', 'discord'],
            'video': ['video', 'call', 'meet', 'zoom'],
            'document': ['document', 'file', 'share', 'drive']
        };
        
        Object.entries(channelTypes).forEach(([channel, keywords]) => {
            const hasChannel = keywords.some(keyword => 
                document.body.textContent.toLowerCase().includes(keyword)
            );
            if (hasChannel) {
                channels.push(channel);
            }
        });
        
        return channels;
    }
}

// 数据分析检测器
class AnalyticsContextDetector {
    async detect() {
        const result = {
            isActive: false,
            dataType: 'unknown',
            visualizationType: 'unknown',
            analysisGoals: []
        };
        
        const analyticsIndicators = [
            '.chart', '.graph', '.dashboard', '.data-table',
            '[class*="chart"]', '[class*="graph"]', '[class*="data"]'
        ];
        
        const hasAnalytics = analyticsIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasAnalytics) {
            result.isActive = true;
            result.dataType = this.detectDataType();
            result.visualizationType = this.detectVisualizationType();
            result.analysisGoals = this.identifyAnalysisGoals();
        }
        
        return result;
    }
    
    detectDataType() {
        const content = document.body.textContent.toLowerCase();
        const dataTypes = {
            'financial': ['revenue', 'profit', 'budget', 'sales'],
            'user-behavior': ['user', 'visitor', 'session', 'conversion'],
            'performance': ['performance', 'speed', 'load', 'response'],
            'marketing': ['campaign', 'ad', 'click', 'impression']
        };
        
        for (const [type, keywords] of Object.entries(dataTypes)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    detectVisualizationType() {
        const chartElements = document.querySelectorAll('.chart, .graph, canvas, svg');
        if (chartElements.length === 0) return 'none';
        
        const chartTypes = {
            'line': chartElements.length > 5 ? 'dashboard' : 'single-metric',
            'bar': 'comparison',
            'pie': 'distribution'
        };
        
        return chartTypes.line; // 默认返回第一个
    }
    
    identifyAnalysisGoals() {
        const goals = [];
        const goalKeywords = {
            'trend-analysis': ['trend', 'growth', 'pattern', 'change-over-time'],
            'comparison': ['compare', 'versus', 'benchmark', 'contrast'],
            'prediction': ['forecast', 'predict', 'future', 'projection']
        };
        
        Object.entries(goalKeywords).forEach(([goal, keywords]) => {
            const hasGoal = keywords.some(keyword => 
                document.body.textContent.toLowerCase().includes(keyword)
            );
            if (hasGoal) {
                goals.push(goal);
            }
        });
        
        return goals;
    }
}

// 调试情境检测器
class DebuggingContextDetector {
    async detect() {
        const result = {
            isActive: false,
            debugType: 'unknown',
            errorSeverity: 'unknown',
            debuggingTools: []
        };
        
        const debugIndicators = [
            '.debugger', '.console', '.terminal', '.error-log',
            '[class*="debug"]', '[class*="error"]', '[data-debug]'
        ];
        
        const hasDebugElements = debugIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasDebugElements) {
            result.isActive = true;
            result.debugType = this.detectDebugType();
            result.errorSeverity = this.assessErrorSeverity();
            result.debuggingTools = this.detectDebuggingTools();
        }
        
        return result;
    }
    
    detectDebugType() {
        const content = document.body.textContent.toLowerCase();
        const debugTypes = {
            'frontend': ['javascript', 'css', 'html', 'dom', 'browser'],
            'backend': ['server', 'database', 'api', 'request', 'response'],
            'mobile': ['ios', 'android', 'app', 'device', 'simulator'],
            'performance': ['memory', 'cpu', 'slow', 'lag', 'freeze']
        };
        
        for (const [type, keywords] of Object.entries(debugTypes)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    assessErrorSeverity() {
        const errorMessages = document.querySelectorAll('.error, .warning, .alert');
        const errorCount = errorMessages.length;
        
        if (errorCount > 10) return 'critical';
        if (errorCount > 3) return 'high';
        if (errorCount > 0) return 'medium';
        return 'low';
    }
    
    detectDebuggingTools() {
        const tools = [];
        const toolIndicators = {
            'devtools': 'browser-devtools',
            'console': 'developer-console',
            'profiler': 'performance-profiler',
            'network-tab': 'network-inspector'
        };
        
        Object.entries(toolIndicators).forEach(([indicator, tool]) => {
            if (document.body.textContent.toLowerCase().includes(indicator)) {
                tools.push(tool);
            }
        });
        
        return tools;
    }
}

// 写作情境检测器
class WritingContextDetector {
    async detect() {
        const result = {
            isActive: false,
            writingType: 'unknown',
            audience: 'unknown',
            tone: 'unknown'
        };
        
        const writingAreas = document.querySelectorAll('textarea, .writing-area, .content-editor, [contenteditable]');
        const hasWritingArea = writingAreas.length > 0;
        
        if (hasWritingArea) {
            result.isActive = true;
            result.writingType = this.detectWritingType();
            result.audience = this.identifyAudience();
            result.tone = this.assessTone();
        }
        
        return result;
    }
    
    detectWritingType() {
        const content = document.body.textContent.toLowerCase();
        const writingTypes = {
            'technical': ['technical', 'documentation', 'manual', 'specification'],
            'creative': ['story', 'fiction', 'narrative', 'creative-writing'],
            'business': ['proposal', 'report', 'presentation', 'business-plan'],
            'academic': ['research', 'thesis', 'paper', 'study']
        };
        
        for (const [type, keywords] of Object.entries(writingTypes)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    identifyAudience() {
        const content = document.body.textContent.toLowerCase();
        const audiences = {
            'developers': ['developer', 'programmer', 'coder', 'engineer'],
            'managers': ['manager', 'executive', 'leader', 'supervisor'],
            'customers': ['customer', 'client', 'user', 'audience'],
            'students': ['student', 'learner', 'education', 'academic']
        };
        
        for (const [audience, keywords] of Object.entries(audiences)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return audience;
            }
        }
        
        return 'general';
    }
    
    assessTone() {
        const formalIndicators = ['formal', 'official', 'professional', 'corporate'];
        const casualIndicators = ['casual', 'friendly', 'informal', 'conversational'];
        
        const content = document.body.textContent.toLowerCase();
        const formalCount = formalIndicators.filter(word => content.includes(word)).length;
        const casualCount = casualIndicators.filter(word => content.includes(word)).length;
        
        if (formalCount > casualCount) return 'formal';
        if (casualCount > formalCount) return 'casual';
        return 'neutral';
    }
}

// 研究情境检测器
class ResearchContextDetector {
    async detect() {
        const result = {
            isActive: false,
            researchType: 'unknown',
            methodology: 'unknown',
            sources: []
        };
        
        const researchIndicators = [
            '.research-paper', '.literature-review', '.study', '.experiment',
            '[class*="research"]', '[class*="study"]', '[data-research]'
        ];
        
        const hasResearchContent = researchIndicators.some(selector => 
            document.querySelector(selector)
        );
        
        if (hasResearchContent) {
            result.isActive = true;
            result.researchType = this.detectResearchType();
            result.methodology = this.identifyMethodology();
            result.sources = this.findResearchSources();
        }
        
        return result;
    }
    
    detectResearchType() {
        const content = document.body.textContent.toLowerCase();
        const researchTypes = {
            'literature-review': ['literature', 'review', 'survey', 'existing-work'],
            'experimental': ['experiment', 'study', 'trial', 'observation'],
            'theoretical': ['theory', 'conceptual', 'framework', 'model'],
            'empirical': ['data', 'empirical', 'quantitative', 'qualitative']
        };
        
        for (const [type, keywords] of Object.entries(researchTypes)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return type;
            }
        }
        
        return 'general';
    }
    
    identifyMethodology() {
        const methodologies = {
            'qualitative': ['interview', 'focus-group', 'ethnographic', 'case-study'],
            'quantitative': ['survey', 'statistical', 'measurement', 'numerical'],
            'mixed-methods': ['mixed', 'combination', 'triangulation', 'multiple-methods']
        };
        
        const content = document.body.textContent.toLowerCase();
        for (const [method, keywords] of Object.entries(methodologies)) {
            if (keywords.some(keyword => content.includes(keyword))) {
                return method;
            }
        }
        
        return 'unknown';
    }
    
    findResearchSources() {
        const sources = [];
        const sourceTypes = {
            'academic-journals': ['journal', 'publication', 'peer-reviewed'],
            'books': ['book', 'textbook', 'monograph', 'edited-volume'],
            'online-databases': ['database', 'repository', 'archive', 'digital-library'],
            'primary-data': ['survey', 'interview', 'experiment', 'observation']
        };
        
        const content = document.body.textContent.toLowerCase();
        Object.entries(sourceTypes).forEach(([source, keywords]) => {
            if (keywords.some(keyword => content.includes(keyword))) {
                sources.push(source);
            }
        });
        
        return sources;
    }
}

// 全局实例和API
const EnhancedContextSystem = new EnhancedContextDetectionSystem();

// 便捷的全局方法
window.getEnhancedContext = async function() {
    return await EnhancedContextSystem.getCurrentContext();
};

window.getContextHistory = function(filter = {}) {
    return EnhancedContextSystem.getContextHistory(filter);
};

window.getContextPatterns = function() {
    return EnhancedContextSystem.getPatternAnalysis();
};

console.log('🚀 增强情境识别系统已加载');
console.log('使用方法:');
console.log('- await getEnhancedContext() // 获取当前情境');
console.log('- getContextHistory({detector: "programming"}) // 获取历史记录');
console.log('- getContextPatterns() // 获取模式分析');