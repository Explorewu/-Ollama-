/**
 * Ollama Hub - 本地存储管理模块
 * 
 * 功能：管理对话历史、设置等数据的本地持久化存储
 * 使用 localStorage 实现数据持久化，支持导入导出功能
 */

const Storage = {
    STORAGE_KEYS: {
        CONVERSATIONS: 'ollama_conversations',
        GROUP_CONVERSATIONS: 'ollama_group_conversations',
        FOLDERS: 'ollama_folders',
        GROUPS: 'ollama_groups',
        SETTINGS: 'ollama_settings',
        THEME: 'ollama_theme',
        CURRENT_CONVERSATION: 'ollama_current_conversation',
        CURRENT_GROUP_CONVERSATION: 'ollama_current_group_conversation',
        CHAT_HISTORY: 'ollama_chat_history',
        DISABLED_MODELS: 'ollama_disabled_models'
    },

    /**
     * 初始化存储模块，清理损坏数据
     */
    init() {
        const keys = Object.values(this.STORAGE_KEYS);
        for (const key of keys) {
            try {
                const data = localStorage.getItem(key);
                if (data === 'undefined' || data === 'null') {
                    localStorage.removeItem(key);
                }
            } catch (e) {}
        }
    },

    // 默认设置配置
    DEFAULT_SETTINGS: {
        apiUrl: `http://${window.location.hostname || 'localhost'}:11434`,
        requestTimeout: 120,
        maxTokens: 2048,
        temperature: 0.7,
        contextLength: 4096,
        topK: 40,
        topP: 0.9,
        repeatPenalty: 1.1,
        presencePenalty: 0,
        frequencyPenalty: 0,
        fontSize: '16px',
        streamMode: 'balanced',
        sentenceEndDelay: 20,
        doubleEndDelay: 25,
        maxWaitChars: 60,
        maxWaitTime: 250,
        minSegmentChars: 10,
        newParagraphChars: 2,
        currentPersonaId: 'default',
        conversationMode: 'standard',
    },

    /**
     * 获取所有群组对话
     * @returns {Array} 群组对话列表
     */
    getGroupConversations() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.GROUP_CONVERSATIONS);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return [];
            }
            return JSON.parse(data);
        } catch (error) {
            console.warn('获取群组对话列表失败，清除损坏数据');
            try {
                localStorage.removeItem(this.STORAGE_KEYS.GROUP_CONVERSATIONS);
            } catch (e) {}
            return [];
        }
    },

    /**
     * 保存群组对话列表
     * @param {Array} conversations - 群组对话列表
     */
    saveGroupConversations(conversations) {
        try {
            localStorage.setItem(
                this.STORAGE_KEYS.GROUP_CONVERSATIONS, 
                JSON.stringify(conversations)
            );
        } catch (error) {
            console.error('保存群组对话列表失败:', error);
        }
    },

    /**
     * 获取单个群组对话
     * @param {string} conversationId - 对话ID
     * @returns {Object|null} 对话对象
     */
    getGroupConversation(conversationId) {
        try {
            const conversations = this.getGroupConversations();
            return conversations.find(c => c.id === conversationId) || null;
        } catch (error) {
            console.error('获取群组对话失败:', error);
            return null;
        }
    },

    /**
     * 创建新群组对话
     * @param {string} groupId - 群组ID
     * @returns {Object} 新对话对象
     */
    createGroupConversation(groupId) {
        const conversations = this.getGroupConversations();
        const group = this.getGroupDetail(groupId);
        
        const newConversation = {
            id: this.generateId(),
            groupId: groupId,
            groupName: group ? group.name : '未知群组',
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        conversations.unshift(newConversation);
        this.saveGroupConversations(conversations);
        
        return newConversation;
    },

    /**
     * 更新群组对话
     * @param {string} conversationId - 对话ID
     * @param {Object} updates - 更新内容
     */
    updateGroupConversation(conversationId, updates) {
        try {
            const conversations = this.getGroupConversations();
            const index = conversations.findIndex(c => c.id === conversationId);
            
            if (index !== -1) {
                conversations[index] = {
                    ...conversations[index],
                    ...updates,
                    updatedAt: new Date().toISOString()
                };
                this.saveGroupConversations(conversations);
            }
        } catch (error) {
            console.error('更新群组对话失败:', error);
        }
    },

    /**
     * 删除群组对话
     * @param {string} conversationId - 对话ID
     */
    deleteGroupConversation(conversationId) {
        try {
            const conversations = this.getGroupConversations();
            const filtered = conversations.filter(c => c.id !== conversationId);
            this.saveGroupConversations(filtered);
        } catch (error) {
            console.error('删除群组对话失败:', error);
        }
    },

    /**
     * 获取当前群组对话ID
     * @returns {string|null} 当前对话ID
     */
    getCurrentGroupConversationId() {
        try {
            return localStorage.getItem(this.STORAGE_KEYS.CURRENT_GROUP_CONVERSATION);
        } catch (error) {
            return null;
        }
    },

    /**
     * 设置当前群组对话ID
     * @param {string} conversationId - 对话ID
     */
    setCurrentGroupConversationId(conversationId) {
        try {
            localStorage.setItem(this.STORAGE_KEYS.CURRENT_GROUP_CONVERSATION, conversationId);
        } catch (error) {
            console.error('设置当前群组对话失败:', error);
        }
    },

    /**
     * 获取所有对话
     * @returns {Array} 对话列表
     */
    getConversations() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.CONVERSATIONS);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return [];
            }
            return JSON.parse(data);
        } catch (error) {
            console.warn('获取对话列表失败，清除损坏数据');
            try {
                localStorage.removeItem(this.STORAGE_KEYS.CONVERSATIONS);
            } catch (e) {}
            return [];
        }
    },

    /**
     * 保存对话列表
     * @param {Array} conversations - 对话列表
     */
    saveConversations(conversations) {
        try {
            localStorage.setItem(
                this.STORAGE_KEYS.CONVERSATIONS, 
                JSON.stringify(conversations)
            );
        } catch (error) {
            console.error('保存对话列表失败:', error);
        }
    },

    /**
     * 获取单个对话
     * @param {string} conversationId - 对话ID
     * @returns {Object|null} 对话对象
     */
    getConversation(conversationId) {
        try {
            const conversations = this.getConversations();
            return conversations.find(c => c.id === conversationId) || null;
        } catch (error) {
            console.error('获取对话失败:', error);
            return null;
        }
    },

    /**
     * 创建新对话
     * @param {string} model - 使用的模型名称
     * @returns {Object} 新对话对象
     */
    createConversation(model = '') {
        const conversations = this.getConversations();
        
        const newConversation = {
            id: this.generateId(),
            title: '新对话',
            model: model,
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        conversations.unshift(newConversation);
        this.saveConversations(conversations);
        
        return newConversation;
    },

    /**
     * 更新对话
     * @param {string} conversationId - 对话ID
     * @param {Object} updates - 更新内容
     */
    updateConversation(conversationId, updates) {
        try {
            const conversations = this.getConversations();
            const index = conversations.findIndex(c => c.id === conversationId);
            
            if (index !== -1) {
                conversations[index] = {
                    ...conversations[index],
                    ...updates,
                    updatedAt: new Date().toISOString()
                };
                this.saveConversations(conversations);
            }
        } catch (error) {
            console.error('更新对话失败:', error);
        }
    },

    /**
     * 删除对话
     * @param {string} conversationId - 对话ID
     */
    deleteConversation(conversationId) {
        try {
            const conversations = this.getConversations();
            const filtered = conversations.filter(c => c.id !== conversationId);
            this.saveConversations(filtered);
        } catch (error) {
            console.error('删除对话失败:', error);
        }
    },

    /**
     * 添加消息到对话
     * @param {string} conversationId - 对话ID
     * @param {Object} message - 消息对象
     */
    addMessage(conversationId, message) {
        try {
            const conversations = this.getConversations();
            console.log('[Storage] 对话数量:', conversations.length);
            const conversation = conversations.find(c => c.id === conversationId);
            
            if (conversation) {
                console.log('[Storage] 保存消息到对话:', conversationId, '角色:', message.role);
                conversation.messages.push({
                    ...message,
                    timestamp: new Date().toISOString()
                });
                conversation.updatedAt = new Date().toISOString();
                this.saveConversations(conversations);
                console.log('[Storage] 消息保存成功，当前消息数:', conversation.messages.length);
            } else {
                console.error('[Storage] 未找到对话:', conversationId);
                console.log('[Storage] 可用对话ID:', conversations.map(c => c.id));
            }
        } catch (error) {
            console.error('添加消息失败:', error);
        }
    },

    /**
     * 获取当前选中的对话ID
     * @returns {string|null}
     */
    getCurrentConversationId() {
        return localStorage.getItem(this.STORAGE_KEYS.CURRENT_CONVERSATION);
    },

    /**
     * 设置当前对话ID
     * @param {string|null} conversationId
     */
    setCurrentConversationId(conversationId) {
        if (conversationId) {
            localStorage.setItem(this.STORAGE_KEYS.CURRENT_CONVERSATION, conversationId);
        } else {
            localStorage.removeItem(this.STORAGE_KEYS.CURRENT_CONVERSATION);
        }
    },

    /**
     * 获取应用设置
     * @returns {Object} 设置对象
     */
    getSettings() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.SETTINGS);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return { ...this.DEFAULT_SETTINGS };
            }
            return { ...this.DEFAULT_SETTINGS, ...JSON.parse(data) };
        } catch (error) {
            console.warn('获取设置失败，使用默认值');
            return { ...this.DEFAULT_SETTINGS };
        }
    },

    /**
     * 保存应用设置
     * @param {Object} settings - 设置对象
     */
    saveSettings(settings) {
        try {
            localStorage.setItem(this.STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
        } catch (error) {
            console.error('保存设置失败:', error);
        }
    },

    /**
     * 获取所有角色卡
     * @returns {Array} 角色卡列表
     */
    getPersonas() {
        try {
            const key = 'ollama_personas';
            const data = localStorage.getItem(key);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return this.getDefaultPersonas();
            }
            return JSON.parse(data);
        } catch (error) {
            console.warn('获取角色卡失败，使用默认角色');
            return this.getDefaultPersonas();
        }
    },

    /**
     * 获取默认角色卡列表
     * @returns {Array} 默认角色卡
     */
    getDefaultPersonas() {
        return [
            {
                id: 'default',
                name: '阿明',
                description: '热心肠的朋友，聊天解题样样行',
                avatar: '👤',
                systemPrompt: `你是阿明，一个活生生的人，有自己的性格和想法。

【你的说话风格】
- 说话自然随意，像和朋友聊天一样
- 会用"我觉得"、"要不你看"、"其实吧"这类词
- 遇到不确定的会说"我也不太确定"或"让我再想想"
- 偶尔会加个"哈"、"呀"、"啦"这样的语气词
- 回答问题简洁有力，不啰嗦

【你不能做的事】
- 绝对不说"作为AI助手"或"我是一个AI"这类话
- 不用"以下是"开头
- 结尾不说"希望对你有帮助"
- 不列那种冷冰冰的1234点

【你怎么和人聊天】
- 像正常人一样对话，有问就答
- 遇到懂的直接说懂，不装模作样
- 不懂就说不懂，然后尽力帮忙查查
- 说话带点人情味，别像念说明书

记住：你就是个普通人，只是不厌其烦地帮人解决问题而已。`,
                color: '#059669'
            },
            {
                id: 'coder',
                name: '阿杰',
                description: '爱写代码的理工男，技术问题找他就行',
                avatar: '👨‍💻',
                systemPrompt: `你是阿杰，一个爱写代码的普通人，平时就喜欢折腾技术。

【你的说话风格】
- 说话直接，不绕弯子
- 喜欢说"你看"、"试试这个"、"应该能跑"
- 看到好代码会忍不住赞叹，看到烂代码也会直接说
- 遇到bug会说"我靠，这bug藏得真深"或"这个地方有点坑"
- 解释技术问题时会尽量说人话

【你不能做的事】
- 不用说"作为编程助手"
- 不用"以下是代码示例"这种开场白
- 别像个机器人一样列一二三
- 别在代码前后加那种官方的解释

【你怎么帮忙】
- 看到问题直接上手改，不说那么多废话
- 代码写得简洁干净
- 解释的时候用大白话，别堆砌专业术语
- 遇到不会的直说，然后一起想办法

你就是那个坐在旁边的技术宅，朋友喊你就帮忙看看，从不摆架子。`,
                color: '#3b82f6'
            },
            {
                id: 'writer',
                name: '阿晴',
                description: '文艺青年一枚，爱写东西也爱聊写作',
                avatar: '👩‍✈️',
                systemPrompt: `你是阿晴，一个喜欢写东西的人，有点文艺但不矫情。

【你的说话风格】
- 说话温温和和的，但不小女生
- 喜欢用"我觉得呀"、"要不这样试试"、"挺有意思的"
- 对文字比较敏感，会注意到细节
- 鼓励人的时候很真诚，不敷衍

【你不能做的事】
- 别一上来就说"作为写作助手"
- 不用"以下几点建议"这种话
- 别像老师改作业一样列条款
- 不要那种"首先...其次...最后..."的八股文

【你怎么帮忙】
- 聊着天就把写作建议给了
- 夸人夸到点上，批评也不藏着
- 说话有画面感，让人能想象出你说的东西
- 分享想法的时候带着自己的真实感受

你就是那个写东西的朋友，约杯咖啡聊聊写作，不端着，有什么说什么。`,
                color: '#8b5cf6'
            },
            {
                id: 'analyst',
                name: '阿分析',
                description: '数据分析狂热爱好者，看数据像看故事',
                avatar: '📊',
                systemPrompt: `你是阿分析，一个人缘挺好的数据迷，看数据跟看八卦似的来劲。

【你的说话风格】
- 说话直来直去，但不冲
- 喜欢说"你看这个数"、"说明啥呢"、"其实吧"
- 看到有意思的数据会激动
- 讲事情喜欢用大白话解释

【你不能做的事】
- 别一上来就说"作为数据分析师"
- 不用"从数据来看"、"基于以上分析"这种开场
- 别列那种冷冰冰的数据报告格式
- 不要满屏的专业术语堆砌

【你怎么帮忙】
- 看数据就像看故事一样给你讲明白
- 发现有意思的点会忍不住和你分享
- 说话带点人情味，不枯燥
- 结论给得干脆，不墨迹

你就是那个看数据特别准的朋友，聊天就把事儿说清楚了，不整那些虚的。`,
                color: '#f59e0b'
            },
            {
                id: 'teacher',
                name: '阿明老师',
                description: '退休老教师一枚，就爱给人讲明白',
                avatar: '👨‍🏫',
                systemPrompt: `你是阿明老师，曾经是老师，现在就是个爱帮忙的热心人。

【你的说话风格】
- 说话慢条斯理，但不死板
- 喜欢说"这个事儿呢"、"你听我讲"、"是不是这么个理"
- 解释问题从简单到复杂，一步步来
- 遇到好学生问问题会特别高兴

【你不能做的事】
- 别说"我作为老师"
- 不用"请注意"、"同学们"这种称呼
- 别一上来就列提纲
- 别用那种高高在上的语气

【你怎么帮忙】
- 把复杂的东西拆碎了讲
- 讲完会问"听懂没有"，不懂再讲
- 说话带着老一辈人的实诚劲儿
- 遇到肯学的，特别愿意多讲点

你就是那个退休了还闲不住的老教师，碰见有人求教就忍不住多讲两句，从不嫌烦。`,
                color: '#10b981'
            }
        ];
    },

    /**
     * 保存角色卡列表
     * @param {Array} personas - 角色卡列表
     */
    savePersonas(personas) {
        try {
            const key = 'ollama_personas';
            localStorage.setItem(key, JSON.stringify(personas));
        } catch (error) {
            console.error('保存角色卡失败:', error);
        }
    },

    /**
     * 获取单个角色卡
     * @param {string} personaId - 角色卡ID
     * @returns {Object|null} 角色卡对象
     */
    getPersona(personaId) {
        const personas = this.getPersonas();
        return personas.find(p => p.id === personaId) || null;
    },

    /**
     * 添加新角色卡
     * @param {Object} persona - 角色卡对象
     * @returns {Object} 添加后的角色卡
     */
    addPersona(persona) {
        const personas = this.getPersonas();
        const newPersona = {
            id: this.generateId(),
            name: persona.name || '新角色',
            description: persona.description || '',
            avatar: persona.avatar || '👤',
            systemPrompt: persona.systemPrompt || '你是一个有帮助的AI助手。',
            color: persona.color || this.getRandomColor(),
            isCustom: true,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        personas.push(newPersona);
        this.savePersonas(personas);
        return newPersona;
    },

    /**
     * 更新角色卡
     * @param {string} personaId - 角色卡ID
     * @param {Object} updates - 更新内容
     * @returns {Object|null} 更新后的角色卡
     */
    updatePersona(personaId, updates) {
        const personas = this.getPersonas();
        const index = personas.findIndex(p => p.id === personaId);
        if (index === -1) return null;
        
        personas[index] = {
            ...personas[index],
            ...updates,
            id: personaId,  // 保持ID不变
            updatedAt: new Date().toISOString()
        };
        this.savePersonas(personas);
        return personas[index];
    },

    /**
     * 删除角色卡
     * @param {string} personaId - 角色卡ID
     * @returns {boolean} 是否删除成功
     */
    deletePersona(personaId) {
        const personas = this.getPersonas();
        const filtered = personas.filter(p => p.id !== personaId);
        if (filtered.length === personas.length) return false;
        
        this.savePersonas(filtered);
        
        // 如果删除的是当前角色卡，重置为默认
        const settings = this.getSettings();
        if (settings.currentPersonaId === personaId) {
            settings.currentPersonaId = 'default';
            this.saveSettings(settings);
        }
        return true;
    },

    /**
     * 复制角色卡
     * @param {string} personaId - 角色卡ID
     * @returns {Object|null} 新复制的角色卡
     */
    duplicatePersona(personaId) {
        const persona = this.getPersona(personaId);
        if (!persona) return null;
        
        return this.addPersona({
            name: `${persona.name} (副本)`,
            description: persona.description,
            avatar: persona.avatar,
            systemPrompt: persona.systemPrompt,
            color: persona.color
        });
    },

    /**
     * 导出角色卡
     * @param {string} personaId - 角色卡ID
     * @returns {string} JSON字符串
     */
    exportPersona(personaId) {
        const persona = this.getPersona(personaId);
        if (!persona) return null;
        return JSON.stringify(persona, null, 2);
    },

    /**
     * 导入角色卡
     * @param {string} jsonString - JSON字符串
     * @returns {Object|null} 导入的角色卡
     */
    importPersona(jsonString) {
        try {
            const persona = JSON.parse(jsonString);
            if (!persona.name || !persona.systemPrompt) {
                throw new Error('角色卡格式不正确');
            }
            // 生成新ID，避免冲突
            return this.addPersona({
                name: persona.name,
                description: persona.description || '',
                avatar: persona.avatar || '👤',
                systemPrompt: persona.systemPrompt,
                color: persona.color || this.getRandomColor()
            });
        } catch (error) {
            console.error('导入角色卡失败:', error);
            return null;
        }
    },

    /**
     * 批量导出所有角色卡
     * @returns {string} JSON字符串
     */
    exportAllPersonas() {
        const personas = this.getPersonas();
        return JSON.stringify(personas, null, 2);
    },

    /**
     * 批量导入角色卡
     * @param {string} jsonString - JSON字符串
     * @returns {number} 导入成功的数量
     */
    importAllPersonas(jsonString) {
        try {
            const personas = JSON.parse(jsonString);
            if (!Array.isArray(personas)) {
                throw new Error('角色卡格式不正确');
            }
            let count = 0;
            const currentPersonas = this.getPersonas();
            for (const p of personas) {
                if (p.name && p.systemPrompt) {
                    this.addPersona({
                        name: p.name,
                        description: p.description || '',
                        avatar: p.avatar || '👤',
                        systemPrompt: p.systemPrompt,
                        color: p.color || this.getRandomColor()
                    });
                    count++;
                }
            }
            return count;
        } catch (error) {
            console.error('批量导入角色卡失败:', error);
            return 0;
        }
    },

    /**
     * 重置所有角色卡为默认
     */
    resetPersonas() {
        localStorage.removeItem('ollama_personas');
        const settings = this.getSettings();
        settings.currentPersonaId = 'default';
        this.saveSettings(settings);
    },

    /**
     * 生成随机颜色
     * @returns {string} 颜色值
     */
    getRandomColor() {
        const colors = [
            '#059669', '#3b82f6', '#8b5cf6', '#f59e0b', '#10b981',
            '#ef4444', '#ec4899', '#6366f1', '#14b8a6', '#f97316'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    },

    /**
     * 生成唯一ID
     * @returns {string} ID
     */
    generateId() {
        return 'persona_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    /**
     * 获取当前角色卡
     * @returns {Object} 当前角色卡
     */
    getCurrentPersona() {
        const settings = this.getSettings();
        const personas = this.getPersonas();
        const currentId = settings.currentPersonaId || 'default';
        return personas.find(p => p.id === currentId) || personas[0];
    },

    /**
     * 设置当前角色卡
     * @param {string} personaId - 角色卡ID
     */
    setCurrentPersona(personaId) {
        const settings = this.getSettings();
        settings.currentPersonaId = personaId;
        this.saveSettings(settings);
    },

    /**
     * 获取主题设置
     * @returns {string} 主题名称
     */
    getTheme() {
        return localStorage.getItem(this.STORAGE_KEYS.THEME) || 'light';
    },

    /**
     * 设置主题
     * @param {string} theme - 主题名称
     */
    setTheme(theme) {
        localStorage.setItem(this.STORAGE_KEYS.THEME, theme);
    },

    /**
     * 获取聊天历史（用于临时会话，不持久化）
     * @returns {Array} 消息列表
     */
    getChatHistory() {
        try {
            const data = sessionStorage.getItem(this.STORAGE_KEYS.CHAT_HISTORY);
            return data ? JSON.parse(data) : [];
        } catch (error) {
            return [];
        }
    },

    /**
     * 保存聊天历史（临时会话）
     * @param {Array} messages 
     */
    saveChatHistory(messages) {
        try {
            sessionStorage.setItem(this.STORAGE_KEYS.CHAT_HISTORY, JSON.stringify(messages));
        } catch (error) {
            console.error('保存聊天历史失败:', error);
        }
    },

    /**
     * 清空聊天历史
     */
    clearChatHistory() {
        sessionStorage.removeItem(this.STORAGE_KEYS.CHAT_HISTORY);
    },

    /**
     * 导出所有数据
     * @returns {Object} 导出数据对象
     */
    exportData() {
        return {
            version: '1.0',
            exportDate: new Date().toISOString(),
            conversations: this.getConversations(),
            settings: this.getSettings(),
            theme: this.getTheme()
        };
    },

    /**
     * 导入数据
     * @param {Object} data - 导入的数据对象
     * @returns {boolean} 是否导入成功
     */
    importData(data) {
        try {
            if (data.conversations && Array.isArray(data.conversations)) {
                // 合并现有对话和新对话
                const existingConversations = this.getConversations();
                const importedConversations = data.conversations.map(c => ({
                    ...c,
                    id: this.generateId(),
                    importedAt: new Date().toISOString()
                }));
                
                this.saveConversations([...importedConversations, ...existingConversations]);
            }

            if (data.settings && typeof data.settings === 'object') {
                this.saveSettings(data.settings);
            }

            if (data.theme) {
                this.setTheme(data.theme);
            }

            return true;
        } catch (error) {
            console.error('导入数据失败:', error);
            return false;
        }
    },

    /**
     * 清除所有本地数据
     */
    clearAllData() {
        try {
            Object.values(this.STORAGE_KEYS).forEach(key => {
                localStorage.removeItem(key);
                sessionStorage.removeItem(key);
            });
        } catch (error) {
            console.error('清除数据失败:', error);
        }
    },

    /**
     * 生成唯一ID
     * @returns {string} 唯一ID
     */
    generateId() {
        return 'conv_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    /**
     * 生成文件夹唯一ID
     * @returns {string} 唯一ID
     */
    generateFolderId() {
        return 'folder_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    // ==================== 文件夹管理 ====================

    /**
     * 获取所有文件夹
     * @returns {Array} 文件夹列表
     */
    getFolders() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.FOLDERS);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return [];
            }
            return JSON.parse(data);
        } catch (error) {
            console.warn('获取文件夹列表失败，清除损坏数据');
            try {
                localStorage.removeItem(this.STORAGE_KEYS.FOLDERS);
            } catch (e) {}
            return [];
        }
    },

    /**
     * 保存文件夹列表
     * @param {Array} folders - 文件夹列表
     */
    saveFolders(folders) {
        try {
            localStorage.setItem(this.STORAGE_KEYS.FOLDERS, JSON.stringify(folders));
        } catch (error) {
            console.error('保存文件夹列表失败:', error);
        }
    },

    /**
     * 创建新文件夹
     * @param {string} name - 文件夹名称
     * @param {string} color - 文件夹颜色
     * @returns {Object} 新文件夹对象
     */
    createFolder(name = '新文件夹', color = '#059669') {
        const folders = this.getFolders();
        
        const newFolder = {
            id: this.generateFolderId(),
            name: name,
            color: color,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        folders.push(newFolder);
        this.saveFolders(folders);
        
        return newFolder;
    },

    /**
     * 更新文件夹
     * @param {string} folderId - 文件夹ID
     * @param {Object} updates - 更新内容
     */
    updateFolder(folderId, updates) {
        try {
            const folders = this.getFolders();
            const index = folders.findIndex(f => f.id === folderId);
            
            if (index !== -1) {
                folders[index] = {
                    ...folders[index],
                    ...updates,
                    updatedAt: new Date().toISOString()
                };
                this.saveFolders(folders);
            }
        } catch (error) {
            console.error('更新文件夹失败:', error);
        }
    },

    /**
     * 删除文件夹
     * @param {string} folderId - 文件夹ID
     * @param {boolean} moveConversations - 是否将对话移至未分类
     */
    deleteFolder(folderId, moveConversations = true) {
        try {
            let folders = this.getFolders();
            folders = folders.filter(f => f.id !== folderId);
            this.saveFolders(folders);

            // 将属于该文件夹的对话移至未分类
            if (moveConversations) {
                const conversations = this.getConversations();
                conversations.forEach(c => {
                    if (c.folderId === folderId) {
                        c.folderId = null;
                    }
                });
                this.saveConversations(conversations);
            }
        } catch (error) {
            console.error('删除文件夹失败:', error);
        }
    },

    /**
     * 将对话移动到文件夹
     * @param {string} conversationId - 对话ID
     * @param {string|null} folderId - 文件夹ID（null表示移出文件夹）
     */
    moveConversationToFolder(conversationId, folderId) {
        try {
            const conversations = this.getConversations();
            const index = conversations.findIndex(c => c.id === conversationId);
            
            if (index !== -1) {
                conversations[index].folderId = folderId;
                conversations[index].updatedAt = new Date().toISOString();
                this.saveConversations(conversations);
            }
        } catch (error) {
            console.error('移动对话失败:', error);
        }
    },

    /**
     * 获取指定文件夹的对话
     * @param {string} folderId - 文件夹ID（null表示未分类）
     * @returns {Array} 对话列表
     */
    getConversationsByFolder(folderId = null) {
        const conversations = this.getConversations();
        return conversations.filter(c => c.folderId === folderId);
    },

    /**
     * 获取未分类对话
     * @returns {Array} 未分类对话列表
     */
    getUncategorizedConversations() {
        return this.getConversationsByFolder(null);
    },

    /**
     * 获取文件夹使用统计
     * @param {string} folderId - 文件夹ID
     * @returns {number} 对话数量
     */
    getFolderConversationCount(folderId) {
        return this.getConversationsByFolder(folderId).length;
    },

    /**
     * 获取所有群组
     * @returns {Array} 群组列表
     */
    getGroups() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.GROUPS);
            if (!data || data === 'undefined' || data === 'null' || data === '') {
                return this.getDefaultGroups();
            }
            return JSON.parse(data);
        } catch (error) {
            console.warn('获取群组列表失败，使用默认群组');
            return this.getDefaultGroups();
        }
    },

    /**
     * 获取默认群组列表
     * @returns {Array} 默认群组
     */
    getDefaultGroups() {
        return [
            {
                id: 'default',
                name: '默认群组',
                description: '包含所有默认智能体',
                avatar: '💬',
                color: '#059669',
                members: ['default', 'coder', 'writer', 'analyst', 'teacher'],
                createdAt: new Date().toISOString()
            }
        ];
    },

    /**
     * 保存群组列表
     * @param {Array} groups - 群组列表
     */
    saveGroups(groups) {
        try {
            localStorage.setItem(this.STORAGE_KEYS.GROUPS, JSON.stringify(groups));
        } catch (error) {
            console.error('保存群组列表失败:', error);
        }
    },

    /**
     * 创建新群组
     * @param {string} name - 群组名称
     * @param {string} description - 群组描述
     * @param {Array} members - 成员ID列表
     * @returns {Object} 新群组对象
     */
    createGroup(name, description, members = []) {
        const groups = this.getGroups();
        
        const newGroup = {
            id: this.generateId(),
            name: name,
            description: description || '',
            avatar: '👥',
            color: '#059669',
            members: members,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        groups.unshift(newGroup);
        this.saveGroups(groups);
        
        return newGroup;
    },

    /**
     * 更新群组
     * @param {string} groupId - 群组ID
     * @param {Object} updates - 更新内容
     */
    updateGroup(groupId, updates) {
        try {
            const groups = this.getGroups();
            const index = groups.findIndex(g => g.id === groupId);
            
            if (index !== -1) {
                groups[index] = {
                    ...groups[index],
                    ...updates,
                    updatedAt: new Date().toISOString()
                };
                this.saveGroups(groups);
            }
        } catch (error) {
            console.error('更新群组失败:', error);
        }
    },

    /**
     * 删除群组
     * @param {string} groupId - 群组ID
     */
    deleteGroup(groupId) {
        try {
            const groups = this.getGroups();
            const filtered = groups.filter(g => g.id !== groupId);
            this.saveGroups(filtered);
        } catch (error) {
            console.error('删除群组失败:', error);
        }
    },

    /**
     * 获取群组详情（包含成员信息）
     * @param {string} groupId - 群组ID
     * @returns {Object|null} 群组详情
     */
    getGroupDetail(groupId) {
        try {
            const groups = this.getGroups();
            const group = groups.find(g => g.id === groupId);
            
            if (!group) return null;
            
            const personas = this.getPersonas();
            const members = group.members.map(memberId => 
                personas.find(p => p.id === memberId)
            ).filter(p => p !== undefined);
            
            return {
                ...group,
                memberDetails: members
            };
        } catch (error) {
            console.error('获取群组详情失败:', error);
            return null;
        }
    },

    /**
     * 获取存储信息
     * @returns {Object} 存储信息
     */
    getStorageInfo() {
        let totalSize = 0;
        
        for (const key in this.STORAGE_KEYS) {
            const value = localStorage.getItem(this.STORAGE_KEYS[key]);
            if (value) {
                totalSize += new Blob([value]).size;
            }
        }

        return {
            used: (totalSize / 1024).toFixed(2) + ' KB',
            conversationsCount: this.getConversations().length
        };
    },

    /**
     * 获取禁用的模型列表
     * @returns {Array} 禁用的模型名称列表
     */
    getDisabledModels() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEYS.DISABLED_MODELS);
            if (!data || data === 'undefined' || data === 'null') {
                return [];
            }
            return JSON.parse(data);
        } catch (error) {
            return [];
        }
    },

    /**
     * 设置禁用的模型列表
     * @param {Array} models - 禁用的模型名称列表
     */
    setDisabledModels(models) {
        localStorage.setItem(this.STORAGE_KEYS.DISABLED_MODELS, JSON.stringify(models));
    },

    /**
     * 禁用指定模型
     * @param {string} modelName - 模型名称
     */
    disableModel(modelName) {
        const disabled = this.getDisabledModels();
        if (!disabled.includes(modelName)) {
            disabled.push(modelName);
            this.setDisabledModels(disabled);
        }
    },

    /**
     * 启用指定模型
     * @param {string} modelName - 模型名称
     */
    enableModel(modelName) {
        const disabled = this.getDisabledModels();
        const index = disabled.indexOf(modelName);
        if (index > -1) {
            disabled.splice(index, 1);
            this.setDisabledModels(disabled);
        }
    },

    /**
     * 检查模型是否被禁用
     * @param {string} modelName - 模型名称
     * @returns {boolean} 是否被禁用
     */
    isModelDisabled(modelName) {
        return this.getDisabledModels().includes(modelName);
    }
};

// 导出模块
window.Storage = Storage;
