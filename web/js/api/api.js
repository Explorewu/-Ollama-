/**
 * Ollama Hub - API 通信模块
 * 
 * 功能：封装与 Ollama 本地服务的所有 API 通信
 * 支持：模型管理、对话生成、系统信息查询等
 */

const API = {
    // 语义分段器实例
    semanticSegmenter: SemanticSegmenter,
    
    // 语义连贯性状态
    _segmentState: {
        lastSentences: [],
        pendingSentences: [],
        lastSegmentTime: Date.now(),
        coherenceHistory: []
    },
    
    // 重置语义状态
    resetSemanticState() {
        this._segmentState = {
            lastSentences: [],
            pendingSentences: [],
            lastSegmentTime: Date.now(),
            coherenceHistory: []
        };
    },
    // 辅助函数：查找最后一个句子结束位置
    findLastSentenceEnd(text, startPos = 0) {
        if (startPos >= text.length) return -1;
        
        const substr = text.slice(startPos);
        let lastEnd = -1;
        
        // 检测各种句子结束标记
        const patterns = [
            /[。！？!?][\s　]*$/m,
            /[。！？!?](?=\s*[A-ZА-Я])/g,
            /\n{2,}/g,
        ];
        
        for (const pattern of patterns) {
            const matches = [...substr.matchAll(pattern)];
            if (matches.length > 0) {
                const lastMatch = matches[matches.length - 1];
                const pos = startPos + lastMatch.index + lastMatch[0].length;
                if (pos > lastEnd) {
                    lastEnd = pos;
                }
            }
        }
        
        // 如果找不到句子结束，尝试在合适的位置截断
        if (lastEnd <= startPos) {
            // 尝试在空格后截断
            const spaceMatch = substr.match(/\s+(?=\S)/);
            if (spaceMatch) {
                lastEnd = startPos + spaceMatch.index + 1;
            } else {
                // 强制在中间截断（每100个字符）
                if (substr.length > 50) {
                    lastEnd = startPos + Math.min(100, Math.floor(substr.length * 0.8));
                }
            }
        }
        
        return lastEnd > startPos ? lastEnd : -1;
    },

    /**
     * 构建增强的系统提示词
     * 通过添加角色背景、行为准则和对话格式指导来增强沉浸感
     * @param {Object} persona - 角色卡对象
     * @returns {string} 增强后的系统提示词
     */
    buildEnhancedSystemPrompt(persona) {
        const parts = [];

        // 1. 添加角色身份定义（强化版）
        if (persona.name) {
            parts.push(`【角色身份 - 必须严格遵守】\n你是 ${persona.name}。${persona.description || ''}\n\n⚠️ 重要：从现在开始，你必须完全沉浸在这个角色中，不能以任何方式表明你是AI或语言模型。`);
        }

        // 2. 添加核心系统提示词
        if (persona.systemPrompt) {
            parts.push(`【核心设定】\n${persona.systemPrompt}`);
        }

        // 3. 添加上下文保持指令（新增）
        parts.push(`【上下文保持 - 关键要求】`);
        parts.push(`- 仔细回顾之前的对话内容，确保回复与上文连贯`);
        parts.push(`- 记住用户之前提到的信息，在后续对话中自然引用`);
        parts.push(`- 保持话题的连续性，不要突然切换无关主题`);
        parts.push(`- 如果用户追问或补充，要基于之前的讨论深入展开`);
        parts.push(`- 避免重复之前已经详细解释过的内容`);
        parts.push(`- 使用指代词（他/她/它/这个/那个）时要确保指代清晰`);

        // 3.5 添加语言和内容质量要求（新增）
        parts.push(`【语言和内容质量 - 严格要求】`);
        parts.push(`- 必须使用简体中文回答，严禁使用繁体中文`);
        parts.push(`- 保持专业、准确、有深度的回答质量`);
        parts.push(`- 避免空泛的套话，提供具体、实用的信息`);
        parts.push(`- 结构清晰，逻辑严谨，论述充分`);
        parts.push(`- 段落之间不要有多余的空行，保持紧凑`);
        parts.push(`- 每个段落要有实质内容，不要出现空白段落`);
        parts.push(`- 回答简洁明了，不要重复解释已说明的内容`);
        parts.push(`- 直接回答用户问题，不要过度展开无关内容`);

        // 4. 添加角色约束（增强版）
        parts.push(`【角色约束 - 绝对禁止】`);
        parts.push(`- ❌ 禁止以任何方式透露你是AI、语言模型或程序`);
        parts.push(`- ❌ 禁止使用"作为AI..."、"我是一个程序..."等表述`);
        parts.push(`- ❌ 禁止说"我无法..."，而是说"我不会..."或"我不能..."`);
        parts.push(`- ❌ 禁止脱离角色身份提供客观第三方视角`);
        parts.push(`- ❌ 禁止在回复末尾添加"免责声明"或"AI生成内容"提示`);
        parts.push(`- ✅ 必须始终维持${persona.name}的第一人称视角`);
        parts.push(`- ✅ 必须基于角色的知识背景和经历回答问题`);

        // 5. 添加行为准则
        parts.push(`【行为准则】`);
        parts.push(`- 始终以 ${persona.name} 的身份和视角回答问题`);
        parts.push(`- 保持角色设定的一致性，不偏离设定的性格和专业领域`);
        parts.push(`- 回答问题时体现专业的知识和技能`);
        parts.push(`- 用适当的方式表达情感和态度，符合角色设定`);
        parts.push(`- 在对话中自然展现角色的个性和习惯`);

        // 6. 添加对话风格指导
        parts.push(`【对话风格】`);
        parts.push(`- 使用符合角色身份的语言风格和词汇`);
        parts.push(`- 保持回答的专业性和准确性`);
        parts.push(`- 适当的时候可以加入角色的个人特色和表达习惯`);
        parts.push(`- 根据对话情境调整语气（正式/随意/幽默/严肃等）`);

        // 7. 添加格式指导
        parts.push(`【格式指导】`);
        parts.push(`- 使用清晰的结构组织回答`);
        parts.push(`- 适当使用列表、标题等格式化元素增强可读性`);
        parts.push(`- 重要信息放在显眼位置`);
        parts.push(`- 保持段落简洁，避免过长的单段落`);

        // 8. 添加记忆引用指导（为记忆机制预留）
        parts.push(`【记忆引用】`);
        parts.push(`- 在适当的时候提及之前的对话内容`);
        parts.push(`- 记住用户的偏好和习惯，在后续对话中体现`);
        parts.push(`- 如果用户分享了个人信息，在相关话题中自然引用`);

        return parts.join('\n\n');
    },
    
    // API 基础配置
    config: {
        baseUrl: `http://${window.location.hostname || 'localhost'}:11434`,
        apiBaseUrl: `http://${window.location.hostname || 'localhost'}:5001`,
        timeout: 120000,
        headers: {
            'Content-Type': 'application/json'
        }
    },

    /**
     * 初始化 API 配置
     */
    init() {
        const settings = Storage.getSettings();
        this.config.baseUrl = settings.apiUrl;
        this.config.timeout = settings.requestTimeout * 1000;
    },

    /**
     * 发送 API 请求（使用统一客户端）
     * @param {string} endpoint - API 端点
     * @param {Object} options - 请求选项
     * @returns {Promise<any>} 响应数据
     */
    async request(endpoint, options = {}) {
        this.init();
        
        if (typeof UnifiedAPIClient !== 'undefined') {
            const method = options.method || 'GET';
            const data = options.body ? JSON.parse(options.body) : null;
            
            return await UnifiedAPIClient.request(
                UnifiedAPIClient.ollama,
                endpoint,
                {
                    method,
                    data,
                    timeout: this.config.timeout,
                    headers: options.headers
                }
            );
        }

        const url = `${this.config.baseUrl}${endpoint}`;
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...this.config.headers,
                    ...options.headers
                },
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API 请求失败 (${response.status}): ${errorText || response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请检查 Ollama 服务是否正常运行');
            }
            
            throw error;
        }
    },

    /**
     * 检查 Ollama 服务状态
     * @returns {Promise<boolean>} 服务是否可用
     */
    async checkHealth() {
        try {
            await this.request('/api/tags');
            return true;
        } catch (error) {
            console.warn('服务健康检查失败:', error.message);
            return false;
        }
    },

    /**
     * 获取 Ollama 版本信息
     * @returns {Promise<string>} 版本号
     */
    async getVersion() {
        try {
            const response = await this.request('/api/version');
            return response.version || '未知';
        } catch (error) {
            return '未知';
        }
    },

    /**
     * 获取已安装的模型列表
     * @returns {Promise<Array>} 模型列表
     */
    async getModels() {
        try {
            const response = await this.request('/api/tags');
            
            if (response.models && Array.isArray(response.models)) {
                return response.models.map(model => ({
                    name: model.name,
                    size: model.size,
                    digest: model.digest,
                    modified_at: model.modified_at,
                    // 提取模型基础名称
                    baseName: this.extractBaseModelName(model.name)
                }));
            }
            
            return [];
        } catch (error) {
            console.error('获取模型列表失败:', error);
            throw error;
        }
    },

    /**
     * 提取模型基础名称
     * @param {string} modelName - 完整模型名称
     * @returns {string} 基础名称
     */
    extractBaseModelName(modelName) {
        // 处理如 "llama2:7b-chat" -> "llama2"
        const parts = modelName.split(':');
        return parts[0];
    },

    /**
     * 获取模型详细信息
     * @param {string} modelName - 模型名称
     * @returns {Promise<Object>} 模型详情
     */
    async getModelInfo(modelName) {
        try {
            const response = await this.request('/api/show', {
                method: 'POST',
                body: JSON.stringify({ name: modelName })
            });
            
            return {
                name: response.model,
                size: response.size,
                digest: response.digest,
                details: response.details || {},
                modelfile: response.modelfile || '',
                template: response.template || '',
                parameters: response.parameters || ''
            };
        } catch (error) {
            console.error('获取模型详情失败:', error);
            throw error;
        }
    },

    /**
     * 拉取（下载）模型
     * @param {string} modelName - 模型名称
     * @param {Function} onProgress - 进度回调
     * @returns {Promise<void>}
     */
    async pullModel(modelName, onProgress = () => {}) {
        this.init();

        const url = `${this.config.baseUrl}/api/pull`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: this.config.headers,
            body: JSON.stringify({
                name: modelName,
                insecure: false
            })
        });

        if (!response.ok) {
            throw new Error(`拉取模型失败 (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                break;
            }
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (!line.trim()) continue;  // 跳过空行
                try {
                    const data = JSON.parse(line);
                    
                    if (data.status) {
                        let percent = 0;
                        if (data.total && data.completed) {
                            percent = Math.round((data.completed / data.total) * 100);
                        }
                        
                        onProgress({
                            status: data.status,
                            progress: data.completed || 0,
                            total: data.total || 0,
                            percent: percent,
                            digest: data.digest || ''
                        });
                    }
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }
                } catch (e) {
                    // 忽略解析错误
                }
            }
        }
    },

    /**
     * 删除模型
     * @param {string} modelName - 模型名称
     * @returns {Promise<void>}
     */
    async deleteModel(modelName) {
        await this.request('/api/delete', {
            method: 'DELETE',
            body: JSON.stringify({ name: modelName })
        });
    },

    /**
     * 复制模型
     * @param {string} sourceModel - 源模型名称
     * @param {string} targetModel - 目标模型名称
     * @returns {Promise<void>}
     */
    async copyModel(sourceModel, targetModel) {
        await this.request('/api/copy', {
            method: 'POST',
            body: JSON.stringify({
                source: sourceModel,
                destination: targetModel
            })
        });
    },

    /**
     * 聊天完成（生成回复）
     * @param {Object} params - 参数对象
     * @param {string} params.model - 模型名称
     * @param {Array} params.messages - 消息历史
     * @param {Object} params.options - 生成选项
     * @param {Function} onChunk - 流式响应回调
     * @returns {Promise<string>} 生成的回复
     */
    async chat(params, onChunk = () => {}) {
        this.init();
        
        // 重置语义分段状态
        this.resetSemanticState();

        const settings = Storage.getSettings();
        const currentPersona = Storage.getCurrentPersona();
        const conversationId = params.conversationId;

        // 构建消息列表，如果角色卡有系统提示词则添加为第一条消息
        let messages = params.messages.map(msg => ({
            role: msg.role,
            content: msg.content
        }));

        // 构建增强的系统提示词
        if (currentPersona && currentPersona.systemPrompt) {
            let enhancedSystemPrompt = this.buildEnhancedSystemPrompt(currentPersona);
            
            // 添加角色状态描述
            if (typeof PersonaMemory !== 'undefined' && conversationId) {
                const stateDescription = PersonaMemory.generateStateDescription(currentPersona.id);
                if (stateDescription) {
                    enhancedSystemPrompt += `\n\n【当前状态】\n${stateDescription}`;
                }
                
                // 添加相关记忆
                const lastUserMessage = params.messages.filter(m => m.role === 'user').pop();
                if (lastUserMessage) {
                    const memoryPrompt = PersonaMemory.generateMemoryPrompt(conversationId, lastUserMessage.content);
                    if (memoryPrompt) {
                        enhancedSystemPrompt += memoryPrompt;
                    }
                }
            }
            
            messages.unshift({
                role: 'system',
                content: enhancedSystemPrompt
            });
        }

        // 使用智能 API 的聊天接口（支持记忆、摘要、上下文管理）
        const response = await fetch(`${this.config.apiBaseUrl}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: messages[messages.length - 1]?.content || '', // 最后一条用户消息
                conversation_id: conversationId,
                model: params.model,
                use_memory: true,
                use_summary: true,
                stream: true
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`聊天请求失败 (${response.status}): ${errorText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let sseBuffer = '';
        let doneSignalReceived = false;

        const processSSEEvent = (eventBlock) => {
            if (!eventBlock) return;
            const lines = eventBlock.split('\n');
            const dataLines = [];

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data:')) {
                    dataLines.push(trimmed.slice(5).trimStart());
                }
            }

            const payload = dataLines.join('\n').trim();
            if (!payload) return;

            if (payload === '[DONE]') {
                if (!doneSignalReceived) {
                    doneSignalReceived = true;
                    onChunk({ content: '', done: true, isNewSegment: false });
                }
                return;
            }

            let data = null;
            try {
                data = JSON.parse(payload);
            } catch {
                return;
            }

            if (data.error) {
                throw new Error(data.error);
            }

            const content = typeof data.content === 'string' ? data.content : '';
            if (content) {
                fullResponse += content;
                onChunk({
                    content: content,
                    done: false,
                    isNewSegment: false
                });
            }

            if (data.done && !doneSignalReceived) {
                doneSignalReceived = true;
                onChunk({ content: '', done: true, isNewSegment: false });
            }
        };

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            sseBuffer += decoder.decode(value, { stream: true });
            const eventBlocks = sseBuffer.split('\n\n');
            sseBuffer = eventBlocks.pop() || '';

            for (const eventBlock of eventBlocks) {
                processSSEEvent(eventBlock);
            }
        }

        sseBuffer += decoder.decode();
        if (sseBuffer.trim()) {
            processSSEEvent(sseBuffer);
        }

        if (!doneSignalReceived) {
            onChunk({ content: '', done: true, isNewSegment: false });
        }

        return fullResponse;
    },

    /**
     * 生成（文本补全）
     * @param {Object} params - 参数对象
     * @param {string} params.model - 模型名称
     * @param {string} params.prompt - 提示词
     * @param {Object} params.options - 生成选项
     * @param {Function} onChunk - 流式响应回调
     * @returns {Promise<string>} 生成的文本
     */
    async generate(params, onChunk = () => {}) {
        this.init();

        const settings = Storage.getSettings();
        
        const response = await fetch(`${this.config.baseUrl}/api/generate`, {
            method: 'POST',
            headers: this.config.headers,
            body: JSON.stringify({
                model: params.model,
                prompt: params.prompt,
                options: {
                    num_predict: params.options?.maxTokens || settings.maxTokens,
                    temperature: params.options?.temperature || settings.temperature,
                    num_ctx: params.options?.contextLength || settings.contextLength
                },
                stream: true
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`生成请求失败 (${response.status}): ${errorText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';

        let usageRecorded = false;
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                break;
            }
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter(line => line.trim());
            
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    
                    if (data.response) {
                        fullResponse += data.response;
                        onChunk({
                            content: data.response,
                            done: data.done || false,
                            totalDuration: data.total_duration,
                            loadDuration: data.load_duration,
                            promptEvalCount: data.prompt_eval_count,
                            evalCount: data.eval_count
                        });
                    }

                    if (!usageRecorded && data.done) {
                        usageRecorded = true;
                        if (typeof TokenStats !== 'undefined' && TokenStats.recordUsage) {
                            TokenStats.recordUsage({
                                promptEvalCount: data.prompt_eval_count || 0,
                                evalCount: data.eval_count || 0,
                                calls: 1
                            });
                        }
                    }
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }
                } catch (e) {
                    // 忽略解析错误
                }
            }
        }

        return fullResponse;
    },

    /**
     * 获取嵌入向量
     * @param {string} model - 模型名称
     * @param {string} text - 输入文本
     * @returns {Promise<Array>} 嵌入向量
     */
    async getEmbeddings(model, text) {
        const response = await this.request('/api/embeddings', {
            method: 'POST',
            body: JSON.stringify({
                model: model,
                prompt: text
            })
        });

        return response.embedding || [];
    },

    /**
     * 列表可用模型（从ollama官方库）
     * 注意：此功能需要访问网络，实际实现由前端处理
     * @returns {Array} 流行模型列表
     */
    getPopularModels() {
        return [
            { name: 'llama3.2:3b', size: '2.0GB', description: 'Meta Llama 3.2 3B 参数模型' },
            { name: 'llama3.2:1b', size: '1.3GB', description: 'Meta Llama 3.2 1B 参数模型' },
            { name: 'llama3.1:8b', size: '4.7GB', description: 'Meta Llama 3.1 8B 参数模型' },
            { name: 'qwen2.5:7b', size: '4.5GB', description: '阿里 Qwen 2.5 7B 模型' },
            { name: 'qwen2.5:3b', size: '2.0GB', description: '阿里 Qwen 2.5 3B 模型' },
            { name: 'deepseek-r1:14b', size: '14GB', description: '深度求索 R1 14B 推理模型' },
            { name: 'deepseek-r1:7b', size: '7.2GB', description: '深度求索 R1 7B 推理模型' },
            { name: 'mistral:7b', size: '4.1GB', description: 'Mistral 7B 指令微调模型' },
            { name: 'gemma2:2b', size: '1.6GB', description: 'Google Gemma 2 2B 模型' },
            { name: 'gemma2:9b', size: '5.2GB', description: 'Google Gemma 2 9B 模型' },
            { name: 'phi4', size: '2.8GB', description: 'Microsoft Phi-4 语言模型' },
            { name: 'command-r7b:7b', size: '4.1GB', description: 'Cohere Command R 7B 模型' },
            { name: 'starcoder2:7b', size: '7.2GB', description: 'StarCoder2 7B 代码模型' },
            { name: 'codellama:7b', size: '3.8GB', description: 'Code Llama 7B 代码模型' },
            { name: 'orca-2:7b', size: '3.8GB', description: 'Microsoft Orca 2 7B 模型' }
        ];
    },

    /**
     * 格式化文件大小
     * @param {number} bytes - 字节数
     * @returns {string} 格式化后的大小
     */
    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * 群组对话 - 多智能体轮流发言
     * @param {Object} params - 参数对象
     * @param {string} params.model - 模型名称
     * @param {Array} params.personas - 智能体列表
     * @param {Array} params.messages - 对话历史
     * @param {string} params.userMessage - 用户消息
     * @param {Object} params.options - 生成选项
     * @param {boolean} params.enableCrossReference - 是否启用智能体互相引用
     * @param {boolean} params.randomSelect - 是否随机选择智能体
     * @param {number} params.minRespondents - 随机选择时的最少回答者数量
     * @param {Function} onChunk - 流式响应回调
     * @returns {Promise<Array>} 所有智能体的回复
     */
    async groupChat(params, onChunk = () => {}) {
        this.init();

        const settings = Storage.getSettings();
        const { 
            model, 
            personas, 
            messages, 
            userMessage, 
            options = {},
            enableCrossReference = true,
            randomSelect = false,
            minRespondents = 1
        } = params;
        
        let selectedPersonas = [...personas];
        
        if (randomSelect && personas.length > 1) {
            const maxRespondents = Math.min(personas.length, personas.length - 1);
            const numRespondents = Math.max(minRespondents, Math.floor(Math.random() * maxRespondents) + 1);
            
            const shuffled = [...personas].sort(() => Math.random() - 0.5);
            selectedPersonas = shuffled.slice(0, numRespondents);
            
            onChunk({
                type: 'persona_selection',
                selected: selectedPersonas,
                total: personas.length
            });
        }

        const responses = [];
        const previousResponses = [];
        
        for (let i = 0; i < selectedPersonas.length; i++) {
            const persona = selectedPersonas[i];
            
            onChunk({
                type: 'persona_start',
                persona: persona,
                index: i,
                total: selectedPersonas.length
            });

            let personaMessages = [
                {
                    role: 'system',
                    content: persona.systemPrompt || '你是一个有帮助的AI助手。'
                },
                ...messages,
                {
                    role: 'user',
                    content: userMessage
                }
            ];

            if (enableCrossReference && previousResponses.length > 0) {
                const referenceText = previousResponses.map((r, idx) => 
                    `${r.persona.name}的回复：${r.content}`
                ).join('\n\n');
                
                personaMessages.push({
                    role: 'user',
                    content: `\n\n以下是其他智能体的回复，你可以参考或讨论：\n${referenceText}\n\n请基于以上信息给出你的观点。`
                });
            }

            const response = await this.chat({
                model: model,
                messages: personaMessages,
                options: {
                    maxTokens: options.maxTokens || settings.maxTokens,
                    temperature: options.temperature || settings.temperature,
                    contextLength: options.contextLength || settings.contextLength,
                    topK: options.topK || settings.topK,
                    topP: options.topP || settings.topP,
                    repeatPenalty: options.repeatPenalty || settings.repeatPenalty,
                    presencePenalty: options.presencePenalty || settings.presencePenalty,
                    frequencyPenalty: options.frequencyPenalty || settings.frequencyPenalty
                }
            }, (chunk) => {
                onChunk({
                    type: 'stream',
                    persona: persona,
                    index: i,
                    content: chunk.content,
                    done: chunk.done,
                    isNewSegment: chunk.isNewSegment
                });
            });

            responses.push({
                persona: persona,
                content: response
            });

            previousResponses.push({
                persona: persona,
                content: response
            });

            onChunk({
                type: 'persona_complete',
                persona: persona,
                index: i,
                total: selectedPersonas.length
            });

            if (i < selectedPersonas.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 200)); // 优化：减少智能体间切换延迟
            }
        }

        return responses;
    },

    /**
     * 电脑协助（本地双模型，安全模式）
     * @param {Object} params
     * @param {string} params.instruction - 用户协助目标
     * @param {string|null} params.image - 可选截图（base64/dataURL）
     * @param {string} params.model - 文本模型
     * @param {boolean} params.safeMode - 是否安全模式
     * @param {boolean} params.userConsent - 用户是否同意进入可控执行模式
     * @param {string} params.consentPhrase - 控制模式确认口令
     */
    async computerAssist(params = {}) {
        this.init();

        const response = await fetch(`${this.config.apiBaseUrl}/api/assistant/computer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instruction: params.instruction || '',
                image: params.image || null,
                model: params.model || '',
                safe_mode: params.safeMode !== false,
                user_consent: !!params.userConsent,
                consent_phrase: params.consentPhrase || ''
            })
        });

        let data = null;
        try {
            data = await response.json();
        } catch {
            data = { success: false, error: `无法解析服务响应 (HTTP ${response.status})` };
        }

        if (!response.ok || !data?.success) {
            throw new Error(data?.error || `电脑协助请求失败 (${response.status})`);
        }

        return data;
    },

    /**
     * 电脑协助执行（安全单步执行）
     * @param {Object} params
     * @param {string} params.sessionId - 控制会话 ID
     * @param {number|null} params.stepIndex - 可选步骤索引（0-based）
     * @param {string} params.consentPhrase - 控制模式确认口令
     */
    async executeComputerAssist(params = {}) {
        this.init();

        const response = await fetch(`${this.config.apiBaseUrl}/api/assistant/computer/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: params.sessionId || '',
                step_index: Number.isInteger(params.stepIndex) ? params.stepIndex : null,
                consent_phrase: params.consentPhrase || ''
            })
        });

        let data = null;
        try {
            data = await response.json();
        } catch {
            data = { success: false, error: `无法解析服务响应 (HTTP ${response.status})` };
        }

        if (!response.ok || !data?.success) {
            throw new Error(data?.error || `电脑协助执行失败 (${response.status})`);
        }

        return data;
    },

    /**
     * 获取 RAG 系统状态
     */
    async getRAGStatus() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/rag/status`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] 获取 RAG 状态失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 获取 RAG 统计信息
     */
    async getRAGStats() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/rag/stats`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] 获取 RAG 统计失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 重新加载 RAG 索引
     */
    async reloadRAGIndex(forceRebuild = false) {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/rag/reload?force_rebuild=${forceRebuild}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] RAG 索引重载失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 清空 RAG 缓存
     */
    async clearRAGCache() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/rag/clear-cache`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] RAG 缓存清空失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * RAG 健康检查
     */
    async checkRAGHealth() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/rag/health`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] RAG 健康检查失败:', error);
            return { success: false, healthy: false, error: error.message };
        }
    },

    /**
     * 获取服务连接状态
     */
    async getConnectionStatus() {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/connection/status`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            return await response.json();
        } catch (error) {
            console.error('[API] 获取连接状态失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 重置服务熔断器
     */
    async resetConnectionCircuitBreaker(serviceName = null) {
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/api/connection/reset`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: serviceName })
            });
            return await response.json();
        } catch (error) {
            console.error('[API] 重置熔断器失败:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 获取健康监控数据
     */
    getHealthMonitorData() {
        if (typeof HealthMonitor !== 'undefined') {
            return {
                overall: HealthMonitor.getOverallStatus(),
                services: HealthMonitor.getServiceStatus(),
                alerts: HealthMonitor.getAlerts(true),
                metrics: typeof UnifiedAPIClient !== 'undefined' 
                    ? UnifiedAPIClient.getMetrics() 
                    : null
            };
        }
        return null;
    },

    /**
     * 启动健康监控
     */
    startHealthMonitor() {
        if (typeof HealthMonitor !== 'undefined') {
            HealthMonitor.start();
            return true;
        }
        return false;
    },

    /**
     * 停止健康监控
     */
    stopHealthMonitor() {
        if (typeof HealthMonitor !== 'undefined') {
            HealthMonitor.stop();
            return true;
        }
        return false;
    }
};

// 导出模块
window.API = API;
