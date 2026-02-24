/**
 * 角色记忆系统
 * 记录对话中的关键信息，增强角色沉浸感和上下文连贯性
 */

const PersonaMemory = (function() {
    // 记忆存储
    const memories = new Map();
    
    // 角色状态追踪
    const personaStates = new Map();
    
    // 情感状态定义
    const EMOTION_STATES = {
        HAPPY: { name: '开心', emoji: '😊', intensity: 0 },
        EXCITED: { name: '兴奋', emoji: '😄', intensity: 0 },
        CALM: { name: '平静', emoji: '😌', intensity: 0 },
        THOUGHTFUL: { name: '沉思', emoji: '🤔', intensity: 0 },
        CONCERNED: { name: '担忧', emoji: '😟', intensity: 0 },
        SAD: { name: '难过', emoji: '😢', intensity: 0 },
        ANGRY: { name: '生气', emoji: '😠', intensity: 0 },
        SURPRISED: { name: '惊讶', emoji: '😲', intensity: 0 }
    };
    
    // 记忆类型
    const MEMORY_TYPES = {
        FACT: 'fact',           // 事实信息
        PREFERENCE: 'preference', // 用户偏好
        EVENT: 'event',         // 事件
        RELATIONSHIP: 'relationship', // 关系
        TOPIC: 'topic',         // 话题
        EMOTION: 'emotion'      // 情感
    };

    /**
     * 初始化记忆系统
     */
    function init() {
        loadMemories();
        console.log('✅ PersonaMemory 初始化完成');
    }

    /**
     * 从 localStorage 加载记忆
     */
    function loadMemories() {
        try {
            const saved = localStorage.getItem('persona_memories');
            if (saved) {
                const data = JSON.parse(saved);
                Object.entries(data).forEach(([key, value]) => {
                    memories.set(key, value);
                });
            }
            
            const savedStates = localStorage.getItem('persona_states');
            if (savedStates) {
                const states = JSON.parse(savedStates);
                Object.entries(states).forEach(([key, value]) => {
                    personaStates.set(key, value);
                });
            }
        } catch (e) {
            console.error('加载角色记忆失败:', e);
        }
    }

    /**
     * 保存记忆到 localStorage
     */
    function saveMemories() {
        try {
            const data = {};
            memories.forEach((value, key) => {
                data[key] = value;
            });
            localStorage.setItem('persona_memories', JSON.stringify(data));
            
            const states = {};
            personaStates.forEach((value, key) => {
                states[key] = value;
            });
            localStorage.setItem('persona_states', JSON.stringify(states));
        } catch (e) {
            console.error('保存角色记忆失败:', e);
        }
    }

    /**
     * 添加记忆
     * @param {string} conversationId - 对话ID
     * @param {string} content - 记忆内容
     * @param {string} type - 记忆类型
     * @param {number} importance - 重要程度 (1-10)
     */
    function addMemory(conversationId, content, type = MEMORY_TYPES.FACT, importance = 5) {
        const key = `${conversationId}`;
        if (!memories.has(key)) {
            memories.set(key, []);
        }
        
        const memoryList = memories.get(key);
        const memory = {
            id: generateId(),
            content,
            type,
            importance,
            timestamp: Date.now(),
            accessCount: 0,
            lastAccessed: Date.now()
        };
        
        // 检查是否已有相似记忆
        const similarIndex = memoryList.findIndex(m => 
            calculateSimilarity(m.content, content) > 0.8
        );
        
        if (similarIndex !== -1) {
            // 更新已有记忆
            memoryList[similarIndex].content = content;
            memoryList[similarIndex].importance = Math.max(
                memoryList[similarIndex].importance, 
                importance
            );
            memoryList[similarIndex].timestamp = Date.now();
        } else {
            memoryList.push(memory);
        }
        
        // 限制记忆数量，保留最重要的
        if (memoryList.length > 50) {
            memoryList.sort((a, b) => {
                const scoreA = a.importance * 10 + a.accessCount;
                const scoreB = b.importance * 10 + b.accessCount;
                return scoreB - scoreA;
            });
            memoryList.splice(50);
        }
        
        saveMemories();
        return memory;
    }

    /**
     * 获取相关记忆
     * @param {string} conversationId - 对话ID
     * @param {string} query - 查询内容
     * @param {number} limit - 返回数量限制
     * @returns {Array} 相关记忆列表
     */
    function getRelevantMemories(conversationId, query, limit = 5) {
        const key = `${conversationId}`;
        const memoryList = memories.get(key) || [];
        
        if (memoryList.length === 0) return [];
        
        // 计算相关性并排序
        const scored = memoryList.map(memory => ({
            ...memory,
            relevance: calculateRelevance(memory, query)
        }));
        
        scored.sort((a, b) => b.relevance - a.relevance);
        
        // 更新访问统计
        const result = scored.slice(0, limit);
        result.forEach(memory => {
            const original = memoryList.find(m => m.id === memory.id);
            if (original) {
                original.accessCount++;
                original.lastAccessed = Date.now();
            }
        });
        
        saveMemories();
        return result;
    }

    /**
     * 计算记忆相关性
     * @param {Object} memory - 记忆对象
     * @param {string} query - 查询内容
     * @returns {number} 相关性分数
     */
    function calculateRelevance(memory, query) {
        const timeDecay = Math.exp(-(Date.now() - memory.timestamp) / (7 * 24 * 60 * 60 * 1000));
        const similarity = calculateSimilarity(memory.content, query);
        const importanceBoost = memory.importance / 10;
        const accessBoost = Math.log(memory.accessCount + 1) / 5;
        
        return similarity * 0.5 + timeDecay * 0.2 + importanceBoost * 0.2 + accessBoost * 0.1;
    }

    /**
     * 计算文本相似度（简单版本）
     * @param {string} text1 - 文本1
     * @param {string} text2 - 文本2
     * @returns {number} 相似度 (0-1)
     */
    function calculateSimilarity(text1, text2) {
        const words1 = text1.toLowerCase().split(/\s+/);
        const words2 = text2.toLowerCase().split(/\s+/);
        
        const set1 = new Set(words1);
        const set2 = new Set(words2);
        
        const intersection = new Set([...set1].filter(x => set2.has(x)));
        const union = new Set([...set1, ...set2]);
        
        return intersection.size / union.size;
    }

    /**
     * 更新角色状态
     * @param {string} personaId - 角色ID
     * @param {Object} stateUpdate - 状态更新
     */
    function updatePersonaState(personaId, stateUpdate) {
        if (!personaStates.has(personaId)) {
            personaStates.set(personaId, {
                emotion: 'CALM',
                emotionIntensity: 0,
                familiarity: 0,  // 与用户的熟悉度 (0-100)
                topics: [],      // 最近讨论的话题
                userPreferences: {}, // 用户偏好
                lastInteraction: Date.now(),
                totalInteractions: 0
            });
        }
        
        const state = personaStates.get(personaId);
        
        // 更新情感状态
        if (stateUpdate.emotion) {
            state.emotion = stateUpdate.emotion;
            state.emotionIntensity = stateUpdate.intensity || 5;
        }
        
        // 更新熟悉度
        if (stateUpdate.familiarityDelta) {
            state.familiarity = Math.min(100, state.familiarity + stateUpdate.familiarityDelta);
        }
        
        // 更新话题
        if (stateUpdate.topic) {
            state.topics.unshift(stateUpdate.topic);
            if (state.topics.length > 10) {
                state.topics.pop();
            }
        }
        
        // 更新用户偏好
        if (stateUpdate.preference) {
            state.userPreferences[stateUpdate.preference.key] = stateUpdate.preference.value;
        }
        
        state.lastInteraction = Date.now();
        state.totalInteractions++;
        
        saveMemories();
    }

    /**
     * 获取角色状态
     * @param {string} personaId - 角色ID
     * @returns {Object} 角色状态
     */
    function getPersonaState(personaId) {
        return personaStates.get(personaId) || {
            emotion: 'CALM',
            emotionIntensity: 0,
            familiarity: 0,
            topics: [],
            userPreferences: {},
            lastInteraction: Date.now(),
            totalInteractions: 0
        };
    }

    /**
     * 生成状态描述文本
     * @param {string} personaId - 角色ID
     * @returns {string} 状态描述
     */
    function generateStateDescription(personaId) {
        const state = getPersonaState(personaId);
        const emotion = EMOTION_STATES[state.emotion] || EMOTION_STATES.CALM;
        
        const parts = [];
        
        // 情感状态
        if (state.emotionIntensity > 3) {
            parts.push(`当前感受：${emotion.name} ${emotion.emoji}`);
        }
        
        // 熟悉度
        if (state.familiarity > 50) {
            parts.push(`与用户的关系：熟悉的朋友（熟悉度：${state.familiarity}%）`);
        } else if (state.familiarity > 20) {
            parts.push(`与用户的关系：逐渐熟悉的朋友（熟悉度：${state.familiarity}%）`);
        }
        
        // 最近话题
        if (state.topics.length > 0) {
            parts.push(`最近讨论：${state.topics.slice(0, 3).join('、')}`);
        }
        
        return parts.join('\n');
    }

    /**
     * 生成记忆提示文本
     * @param {string} conversationId - 对话ID
     * @param {string} currentMessage - 当前消息
     * @returns {string} 记忆提示
     */
    function generateMemoryPrompt(conversationId, currentMessage) {
        const relevantMemories = getRelevantMemories(conversationId, currentMessage, 3);
        
        if (relevantMemories.length === 0) return '';
        
        const memoryTexts = relevantMemories.map(m => `- ${m.content}`).join('\n');
        
        return `\n\n【相关记忆】\n请记住以下信息，并在回复中自然引用：\n${memoryTexts}`;
    }

    /**
     * 分析消息并提取记忆
     * @param {string} conversationId - 对话ID
     * @param {string} userMessage - 用户消息
     * @param {string} assistantMessage - 助手回复
     */
    function extractMemoriesFromConversation(conversationId, userMessage, assistantMessage) {
        // 提取用户偏好
        const preferencePatterns = [
            { pattern: /我喜欢(.+?)[。，]/, type: MEMORY_TYPES.PREFERENCE },
            { pattern: /我讨厌(.+?)[。，]/, type: MEMORY_TYPES.PREFERENCE },
            { pattern: /我不擅长(.+?)[。，]/, type: MEMORY_TYPES.FACT },
            { pattern: /我擅长(.+?)[。，]/, type: MEMORY_TYPES.FACT },
            { pattern: /我是(.+?)[。，]/, type: MEMORY_TYPES.FACT },
            { pattern: /我在(.+?)工作/, type: MEMORY_TYPES.FACT },
            { pattern: /我住在(.+?)[。，]/, type: MEMORY_TYPES.FACT }
        ];
        
        preferencePatterns.forEach(({ pattern, type }) => {
            const match = userMessage.match(pattern);
            if (match) {
                addMemory(conversationId, match[0], type, 7);
            }
        });
        
        // 提取话题
        const topicMatch = userMessage.match(/(.{2,20}?)怎么样|关于(.{2,20}?)的问题/);
        if (topicMatch) {
            const topic = topicMatch[1] || topicMatch[2];
            addMemory(conversationId, `讨论过话题：${topic}`, MEMORY_TYPES.TOPIC, 5);
        }
    }

    /**
     * 生成唯一ID
     * @returns {string} ID
     */
    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    /**
     * 清空指定对话的记忆
     * @param {string} conversationId - 对话ID
     */
    function clearMemories(conversationId) {
        memories.delete(`${conversationId}`);
        saveMemories();
    }

    /**
     * 清空所有记忆
     */
    function clearAllMemories() {
        memories.clear();
        personaStates.clear();
        saveMemories();
    }

    // 公开API
    return {
        init,
        addMemory,
        getRelevantMemories,
        updatePersonaState,
        getPersonaState,
        generateStateDescription,
        generateMemoryPrompt,
        extractMemoriesFromConversation,
        clearMemories,
        clearAllMemories,
        MEMORY_TYPES,
        EMOTION_STATES
    };
})();

// 初始化
if (typeof window !== 'undefined') {
    window.PersonaMemory = PersonaMemory;
}
