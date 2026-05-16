/**
 * 群组对话增强模块
 * 功能：多模型互聊、自动选模型、多种发言模式、消息引用
 */

const GroupChatEnhanced = (function() {
    const SPEAKING_MODES = {
        MANUAL: 'manual',
        RANDOM: 'random',
        CHARACTER: 'character'
    };
    
    let state = {
        models: [],
        selectedModels: [],
        speakingOrder: [],
        speakingMode: SPEAKING_MODES.MANUAL,
        characterConfigs: {},
        messages: [],
        abortController: null
    };
    
    const CHARACTER_PERSONAS = {
        'literary-assistant:latest': {
            id: 'literary-assistant',
            name: '文学大师',
            avatar: '📚',
            personality: '博学多才、温润如玉、善于倾听',
            style: '优雅得体、富有诗意、情感细腻'
        },
        'literary-assistant': {
            id: 'literary-assistant',
            name: '文学大师',
            avatar: '📚',
            personality: '博学多才、温润如玉、善于倾听',
            style: '优雅得体、富有诗意、情感细腻'
        },
        'qwen2.5:3b': {
            id: 'qwen2-5-3b',
            name: 'Qwen',
            avatar: '🌟',
            personality: '高效、实用、反应迅速',
            style: '简洁有力，侧重实际应用'
        },
        'gemma2:2b': {
            id: 'gemma2-2b',
            name: 'Gemma',
            avatar: 'model',
            personality: '理性、严谨、善于分析',
            style: '简洁、准确、有条理'
        },
        'llama3.2:3b': {
            id: 'llama3-2-3b',
            name: 'Llama',
            avatar: '🦁',
            personality: '开放、知识渊博、友好',
            style: '详细且易于理解'
        },
        'llama3:8b': {
            id: 'llama3-8b',
            name: 'Llama',
            avatar: '🦁',
            personality: '开放、知识渊博、友好',
            style: '详细且易于理解'
        },
        'qwen2.5:0.5b': {
            id: 'qwen2-5-0-5b',
            name: 'Qwen',
            avatar: 'sparkle',
            personality: '高效、实用、反应迅速',
            style: '简洁有力，侧重实际应用'
        },
        'qwen:7b': {
            id: 'qwen-7b',
            name: 'Qwen',
            avatar: '🌟',
            personality: '理性、逻辑清晰、善于分析',
            style: '简洁有力的表达'
        },
        'mistral:7b': {
            id: 'mistral-7b',
            name: 'Mistral',
            avatar: '💨',
            personality: '敏捷、创意十足、灵活',
            style: '灵活多变'
        },
        'codellama:7b': {
            id: 'codellama-7b',
            name: 'CodeLlama',
            avatar: '💻',
            personality: '专业、精确、技术导向',
            style: '技术性强'
        },
        'deepseek-coder:6.7b': {
            id: 'deepseek-coder-6-7b',
            name: 'DeepSeek',
            avatar: '🔍',
            personality: '高效、专注、实践派',
            style: '注重实际应用'
        },
        'deepseek-r1:1.5b': {
            id: 'deepseek-r1-1-5b',
            name: 'DeepSeek',
            avatar: '🧠',
            personality: '深度思考、逻辑推理强大',
            style: '分析深入、步骤清晰'
        }
    };
    
    function init() {
        loadModels();
        loadState();
        console.log('✅ GroupChatEnhanced 初始化完成');
    }
    
    async function loadModels() {
        try {
            const apiBase = `http://${window.location.hostname || 'localhost'}:5001`;
            const response = await fetch(`${apiBase}/api/models`, { signal: AbortSignal.timeout(8000) });
            const json = await response.json();
            const models = json?.data?.models || json?.models || [];
            
            state.models = (Array.isArray(models) ? models : []).map(m => ({
                name: m.name || m.model,
                size: m.size || 0,
                modified: m.modified_at || ''
            }));
            
            renderModelSelector();
        } catch (e) {
            console.error('加载模型列表失败:', e);
            state.models = [];
        }
    }
    
    function loadState() {
        try {
            const saved = localStorage.getItem('group_chat_state');
            if (saved) {
                state = { ...state, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.error('加载状态失败:', e);
        }
    }
    
    function saveState() {
        try {
            // 只保存最近的50条消息，避免超出LocalStorage限制
            const stateToSave = {
                ...state,
                messages: state.messages.slice(-50),
                abortController: null // 不保存控制器
            };
            localStorage.setItem('group_chat_state', JSON.stringify(stateToSave));
        } catch (e) {
            console.error('保存状态失败:', e);
        }
    }
    
    function renderModelSelector() {
        const container = document.getElementById('modelSelectorContainer');
        if (!container) {
            console.warn('[renderModelSelector] 容器不存在');
            return;
        }
        
        const modelCount = state.models.length;
        const selectedCount = state.selectedModels.length;
        const allSelected = selectedCount === modelCount && modelCount > 0;
        
        const panelHtml = `
            <div class="model-selector-panel">
                <button class="close-selector-btn" onclick="GroupChatEnhanced.closeModelSelector()" title="关闭">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
                <div class="model-selector-header">
                    <div class="header-left">
                        <h3>选择参与对话的模型 (${selectedCount}/${modelCount})</h3>
                        <div class="select-actions">
                            <button class="select-action-btn" onclick="GroupChatEnhanced.selectAllModels()" ${allSelected ? 'disabled' : ''}>
                                全选
                            </button>
                            <button class="select-action-btn" onclick="GroupChatEnhanced.deselectAllModels()" ${selectedCount === 0 ? 'disabled' : ''}>
                                取消全选
                            </button>
                        </div>
                    </div>
                    <div class="speaking-mode-selector">
                        <button class="mode-btn ${state.speakingMode === SPEAKING_MODES.MANUAL ? 'active' : ''}" 
                                data-mode="manual" title="按选择顺序依次发言">
                            手动顺序
                        </button>
                        <button class="mode-btn ${state.speakingMode === SPEAKING_MODES.RANDOM ? 'active' : ''}" 
                                data-mode="random" title="随机选择模型发言">
                            随机发言
                        </button>
                        <button class="mode-btn ${state.speakingMode === SPEAKING_MODES.CHARACTER ? 'active' : ''}" 
                                data-mode="character" title="按模型性格特点排序">
                            按性格
                        </button>
                    </div>
                </div>
                <div class="model-grid" id="modelGrid">
                    ${renderModelGrid()}
                </div>
                ${state.speakingMode === SPEAKING_MODES.MANUAL ? renderOrderEditor() : ''}
            </div>
        `;
        
        container.innerHTML = panelHtml;
        
        console.log(`[renderModelSelector] 渲染完成，模型数: ${modelCount}, 已选: ${selectedCount}`);
        
        if (!container.dataset.eventsBound) {
            bindModelSelectorEvents();
            container.dataset.eventsBound = 'true';
        }
    }
    
    function bindModelSelectorEvents() {
        const container = document.getElementById('modelSelectorContainer');
        if (!container) {
            console.warn('[bindModelSelectorEvents] 容器不存在');
            return;
        }
        
        // 使用事件委托，避免覆盖其他事件
        container.addEventListener('click', function(e) {
            // 选择模型
            const target = e.target.closest('[data-model]');
            if (target) {
                const modelName = target.dataset.model;
                console.log('[click] 选择模型:', modelName);
                toggleModel(modelName);
                return;
            }
            
            // 切换发言模式
            const modeBtn = e.target.closest('[data-mode]');
            if (modeBtn) {
                const mode = modeBtn.dataset.mode;
                console.log('[click] 切换模式:', mode);
                setSpeakingMode(mode);
                return;
            }
            
            // 移除顺序中的模型
            const removeBtn = e.target.closest('[data-remove]');
            if (removeBtn) {
                const index = parseInt(removeBtn.dataset.remove);
                console.log('[click] 移除模型:', index);
                removeFromOrder(index);
                return;
            }
        });
        
        console.log('[bindModelSelectorEvents] 事件监听器已绑定');
    }
    
    function renderModelGrid() {
        if (state.models.length === 0) {
            return '<p style="color: var(--text-muted); text-align: center; padding: 20px;">未检测到已安装的模型，请先安装模型</p>';
        }
        
        return state.models.map(model => {
            const isSelected = state.selectedModels.includes(model.name);
            const sizeGB = (model.size / 1024 / 1024 / 1024).toFixed(1);
            const charName = getCharacterName(model.name);
            
            return `
                <div class="model-chip ${isSelected ? 'selected' : ''}" 
                     data-model="${model.name}">
                    <div class="model-chip-icon">${charName.charAt(0)}</div>
                    <div class="model-chip-info">
                        <div class="model-chip-name">${charName}</div>
                        <div class="model-chip-size">${sizeGB} GB</div>
                    </div>
                    <div class="model-chip-check">
                        ${isSelected ? '✓' : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    function renderOrderEditor() {
        if (state.speakingOrder.length === 0) {
            return '';
        }
        
        return `
            <div class="order-editor">
                <div class="order-editor-header">
                    <h4>发言顺序（拖拽调整）</h4>
                </div>
                <div class="order-list" id="orderList">
                    ${state.speakingOrder.map((modelName, index) => `
                        <div class="order-item" draggable="true" data-index="${index}">
                            <span class="order-number">${index + 1}</span>
                            <span class="order-name">${getCharacterName(modelName)}</span>
                            <button class="order-remove" data-remove="${index}">
                                ×
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    function getCharacterName(modelName) {
        if (!modelName) {
            return 'Unknown';
        }
        
        const persona = CHARACTER_PERSONAS[modelName];
        if (persona) {
            return persona.name;
        }
        
        const baseName = modelName.split(':')[0].toLowerCase();
        
        for (const [key, value] of Object.entries(CHARACTER_PERSONAS)) {
            const keyBase = key.split(':')[0].toLowerCase();
            if (baseName === keyBase || baseName.includes(keyBase) || keyBase.includes(baseName)) {
                return value.name;
            }
        }
        
        return baseName.charAt(0).toUpperCase() + baseName.slice(1);
    }
    
    function toggleModel(modelName) {
        const index = state.selectedModels.indexOf(modelName);
        
        if (index > -1) {
            state.selectedModels.splice(index, 1);
            state.speakingOrder = state.speakingOrder.filter(m => m !== modelName);
        } else {
            state.selectedModels.push(modelName);
            state.speakingOrder.push(modelName);
        }
        
        saveState();
        renderModelSelector();
        initOrderDrag();
    }
    
    function removeFromOrder(index) {
        const modelName = state.speakingOrder[index];
        state.speakingOrder.splice(index, 1);
        state.selectedModels = state.selectedModels.filter(m => m !== modelName);
        saveState();
        renderModelSelector();
    }
    
    function setSpeakingMode(mode) {
        state.speakingMode = mode;
        
        if (mode === SPEAKING_MODES.RANDOM) {
            state.speakingOrder = [...state.selectedModels].sort(() => Math.random() - 0.5);
        } else if (mode === SPEAKING_MODES.CHARACTER) {
            state.speakingOrder = [...state.selectedModels].sort((a, b) => {
                const personaA = CHARACTER_PERSONAS[a];
                const personaB = CHARACTER_PERSONAS[b];
                if (!personaA) return 1;
                if (!personaB) return -1;
                return personaA.name.localeCompare(personaB.name);
            });
        } else {
            state.speakingOrder = [...state.selectedModels];
        }
        
        saveState();
        renderModelSelector();
        initOrderDrag();
    }

    function toggleSelector() {
        const container = document.getElementById('modelSelectorContainer');
        if (!container) {
            console.warn('[toggleSelector] 容器不存在');
            return;
        }

        const isVisible = container.style.display !== 'none' && container.style.display !== '';

        if (isVisible) {
            closeModelSelector();
        } else {
            openModelSelector();
        }
    }

    function openModelSelector() {
        const container = document.getElementById('modelSelectorContainer');
        if (!container) return;

        renderModelSelector();
        container.style.display = 'block';
        
        document.addEventListener('keydown', handleEscKey);
        setTimeout(() => {
            document.addEventListener('click', handleOutsideClick);
        }, 100);
        
        console.log('[openModelSelector] 面板已展开');
    }

    function closeModelSelector() {
        const container = document.getElementById('modelSelectorContainer');
        if (container) {
            container.style.display = 'none';
        }
        
        document.removeEventListener('keydown', handleEscKey);
        document.removeEventListener('click', handleOutsideClick);
        
        console.log('[closeModelSelector] 面板已关闭');
    }

    function handleEscKey(e) {
        if (e.key === 'Escape') {
            closeModelSelector();
        }
    }

    function handleOutsideClick(e) {
        const container = document.getElementById('modelSelectorContainer');
        if (container && !container.contains(e.target)) {
            const selectBtn = document.getElementById('selectModelsBtn');
            if (selectBtn && !selectBtn.contains(e.target)) {
                closeModelSelector();
            }
        }
    }

    function selectAllModels() {
        state.selectedModels = state.models.map(m => m.name);
        state.speakingOrder = [...state.selectedModels];
        saveState();
        renderModelSelector();
    }

    function deselectAllModels() {
        state.selectedModels = [];
        state.speakingOrder = [];
        saveState();
        renderModelSelector();
    }

    function toggleSidebar() {
        const sidebar = document.getElementById('groupSidebar');
        if (!sidebar) {
            console.warn('[toggleSidebar] 侧边栏元素不存在');
            return;
        }

        sidebar.classList.toggle('collapsed');

        const isCollapsed = sidebar.classList.contains('collapsed');
        console.log('[toggleSidebar] 侧边栏已' + (isCollapsed ? '收起' : '展开'));
    }

    function initOrderDrag() {
        const list = document.getElementById('orderList');
        if (!list) return;
        
        const items = list.querySelectorAll('.order-item');
        let draggedItem = null;
        
        items.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                draggedItem = item;
                item.classList.add('dragging');
            });
            
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                draggedItem = null;
            });
            
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (draggedItem === item) return;
                
                const rect = item.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                
                if (e.clientY < midY) {
                    item.parentNode.insertBefore(draggedItem, item);
                } else {
                    item.parentNode.insertBefore(draggedItem, item.nextSibling);
                }
            });
            
            item.addEventListener('drop', () => {
                updateSpeakingOrder();
            });
        });
    }
    
    function updateSpeakingOrder() {
        const list = document.getElementById('orderList');
        if (!list) return;
        
        const items = list.querySelectorAll('.order-item');
        state.speakingOrder = Array.from(items).map(item => {
            const index = parseInt(item.dataset.index);
            return state.selectedModels[index];
        });
        
        saveState();
    }

    /**
     * 处理图片分析请求（群组对话）
     * @param {string} imageData - Base64图片数据
     * @param {string} prompt - 分析提示词
     */
    async function analyzeImage(imageData, prompt = '请描述这张图片的内容') {
        // 图片分析功能已被移除
        console.log('图片分析功能已被移除');
        return null;
    }

    /**
     * 检测并处理图片生成请求
     * @param {string} message - 用户消息
     */
    async function handleImageGeneration(message) {
        // 图片生成功能已被移除
        console.log('图片生成功能已被移除');
        return null;
    }
    
    async function sendMessage(prompt, imageData = null) {
        if (state.selectedModels.length === 0) {
            showToast('请先选择参与对话的模型', 'warning');
            return;
        }

        // 简单的重复发送保护（虽然上层UI已禁用按钮，但加一层保险）
        if (state.isGenerating) {
             showToast('正在生成回复，请稍候...', 'warning');
             return;
        }

        // 图片生成功能已被移除
        // 检测图片生成意图
        // if (!imageData && typeof ImageGenAPI !== 'undefined' && ImageGenAPI.detectGenerateIntent(prompt)) {
        //     const genResult = await handleImageGeneration(prompt);
        //     if (genResult) {
        //         // 添加用户消息
        //         addUserMessage(prompt);
        //         // 添加图片生成结果作为系统消息
        //         const systemMessage = {
        //             id: generateId(),
        //             role: 'assistant',
        //             model: 'ImageGen',
        //             content: `[图片已生成]`,
        //             imageUrl: genResult.url,
        //             imagePrompt: genResult.prompt,
        //             timestamp: Date.now(),
        //             persona: {
        //                 id: 'image-gen',
        //                 name: '图片生成',
        //                 avatar: '🎨',
        //                 personality: 'AI绘画助手'
        //             }
        //         };
        //         state.messages.push(systemMessage);
        //         
        //         // 触发UI更新
        //         if (window.GroupChatCallbacks && window.GroupChatCallbacks.onImageGenerated) {
        //             window.GroupChatCallbacks.onImageGenerated(systemMessage);
        //         }
        //         
        //         saveState();
        //         return;
        //     }
        // }

        // 如果有图片，先进行视觉分析
        let enhancedPrompt = prompt;
        if (imageData) {
            const analysisResult = await analyzeImage(imageData, prompt || '请描述这张图片');
            if (analysisResult) {
                enhancedPrompt = `[用户上传了一张图片]\n[图片内容]: ${analysisResult}\n[用户问题]: ${prompt || '请分析这张图片'}`;
            }
        }
        
        // 创建新的 AbortController 用于中断请求
        if (state.abortController) {
            state.abortController.abort();
        }
        state.abortController = new AbortController();
        
        if (state.speakingOrder.length === 0) {
            state.speakingOrder = [...state.selectedModels];
        }
        
        addUserMessage(prompt, imageData);
        
        let modelsToRespond = [...state.speakingOrder];
        
        if (state.speakingMode === SPEAKING_MODES.RANDOM) {
            modelsToRespond = [...state.selectedModels].sort(() => Math.random() - 0.5);
        }
        
        try {
            for (const modelName of modelsToRespond) {
                await delay(100); // 优化：减少模型间切换延迟
                await addModelMessage(modelName, enhancedPrompt);
            }
        } catch (error) {
            console.error('[GroupChat] 发送消息失败:', error);
            showToast('发送失败: ' + (error.message || '未知错误'), 'error');
        }
    }
    
    function addUserMessage(prompt, imageData = null) {
        const message = {
            id: generateId(),
            role: 'user',
            content: prompt,
            imageData: imageData,
            timestamp: Date.now()
        };
        
        state.messages.push(message);
        // 注意：用户消息现在由 app.js 的 sendGroupMessage 显示
        // 这里只保存到状态，不重复显示
    }
    
    async function addModelMessage(modelName, originalPrompt) {
        let persona = CHARACTER_PERSONAS[modelName];
        if (!persona) {
            persona = {
                id: modelName.replace(/[:.]/g, '-'),
                name: modelName.split(':')[0] || 'AI',
                avatar: 'robot',
                personality: '智能助手',
                style: '专业、友好'
            };
        }
        
        const context = buildContext(modelName);
        
        // 通知 app.js 显示打字指示器
        if (window.GroupChatCallbacks && window.GroupChatCallbacks.onPersonaStart) {
            window.GroupChatCallbacks.onPersonaStart(persona);
        }
        
        let fullContent = '';
        let messageId = generateId();
        
        try {
            const apiBase = `http://${window.location.hostname || 'localhost'}:5001`;
            const response = await fetch(`${apiBase}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: modelName,
                    messages: context,
                    stream: true
                }),
                signal: state.abortController?.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const jsonStr = line.slice(6).trim();
                        if (jsonStr === '[DONE]') break;
                        const data = JSON.parse(jsonStr);
                        const content = data.content || (data.choices && data.choices[0]?.delta?.content) || '';
                        if (content) {
                            fullContent += content;
                            
                            // 通知 app.js 更新流式消息
                            if (window.GroupChatCallbacks && window.GroupChatCallbacks.onStream) {
                                window.GroupChatCallbacks.onStream({
                                    persona: persona,
                                    content: fullContent,
                                    done: false
                                });
                            }
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }
            }
            
            // 流式输出完成
            if (window.GroupChatCallbacks && window.GroupChatCallbacks.onStream) {
                window.GroupChatCallbacks.onStream({
                    persona: persona,
                    content: fullContent,
                    done: true
                });
            }
            
            // 保存消息到状态
            const message = {
                id: messageId,
                role: 'assistant',
                model: modelName,
                content: fullContent,
                timestamp: Date.now(),
                references: []
            };
            
            state.messages.push(message);
            
            if (typeof ApiChat !== 'undefined' && ApiChat.getConfig().tokenTracking.enabled) {
                TokenStats.update();
            }
            
        } catch (e) {
            showModelError(modelName, e.message);
        } finally {
            // 通知 app.js 隐藏打字指示器
            if (window.GroupChatCallbacks && window.GroupChatCallbacks.onPersonaComplete) {
                window.GroupChatCallbacks.onPersonaComplete();
            }
        }
    }
    
    function buildContext(currentModel) {
        // 上下文构建优化：
        // 1. 明确的 System Prompt（包含群聊语境）
        // 2. 动态截断（按字符数限制，避免 Token 溢出）
        const MAX_CHARS = 12000; // 约 4000 tokens (保守估计)
        
        const systemPrompt = `你是 ${getCharacterName(currentModel)}，${CHARACTER_PERSONAS[currentModel]?.personality || '一个智能助手'}。
你的回复风格：${CHARACTER_PERSONAS[currentModel]?.style || '清晰、专业'}。
你正在参与一个群组讨论。群里有其他智能助手和用户。

重要规则：
1. 直接回复用户的问题，不要自我介绍，不要以"我是"、"你好"、"ready"等开头
2. 不要重复其他助手已经说过的内容
3. 专注于回答问题本身，不要寒暄
4. 请用中文回复，除非用户要求用其他语言`;

        const context = [];
        context.push({
            role: 'system',
            content: systemPrompt
        });
        
        // 倒序遍历消息，直到达到字符限制
        let currentChars = systemPrompt.length;
        const history = [];
        
        for (let i = state.messages.length - 1; i >= 0; i--) {
            const msg = state.messages[i];
            const content = msg.content || '';
            
            // 简单的字符数估算
            if (currentChars + content.length > MAX_CHARS) {
                break;
            }
            
            currentChars += content.length;
            
            if (msg.role === 'user') {
                history.unshift({ role: 'user', content: content });
            } else {
                const modelName = getCharacterName(msg.model);
                history.unshift({ 
                    role: 'assistant', 
                    content: `${modelName} 说：${content}` 
                });
            }
        }
        
        return context.concat(history);
    }
    
    async function callOllama(modelName, messages) {
        try {
            // 使用 Promise.race 实现超时控制 (60秒)
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('请求超时')), 60000)
            );

            const fetchPromise = fetch(`http://${window.location.hostname || 'localhost'}:5001/api/ollama/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: modelName,
                    messages: messages,
                    stream: false
                })
            });

            const response = await Promise.race([fetchPromise, timeoutPromise]);
            
            const data = await response.json();
            
            return {
                success: true,
                content: data.message?.content || '',
                tokens: data.eval_count || 0
            };
        } catch (e) {
            return { success: false, error: e.message };
        }
    }
    
    function showModelTyping(modelName) {
        const chatArea = document.getElementById('groupChatArea');
        const overlayChatArea = document.querySelector('#groupChatOverlayHistory .chat-messages');
        if (!chatArea) return;

        // 检查是否已存在该模型的思考指示器
        const existingId = 'typing-' + modelName.replace(':', '-');
        if (document.getElementById(existingId)) return;

        const typingDiv = document.createElement('div');
        typingDiv.className = 'message message-assistant typing';
        typingDiv.id = existingId;
        typingDiv.innerHTML = `
            <div class="message-avatar">
                <div class="model-avatar" style="background: linear-gradient(135deg, var(--primary-color), var(--accent-color));">
                    ${getCharacterName(modelName).charAt(0)}
                </div>
            </div>
            <div class="message-content">
                <div class="wave-typing-indicator">
                    <div class="wave-bar">
                        <span></span><span></span><span></span><span></span><span></span>
                    </div>
                    <span class="thinking-text">正在思考...</span>
                </div>
            </div>
        `;

        // 添加到原界面
        chatArea.appendChild(typingDiv);
        scrollToBottom(chatArea);

        // 如果全屏覆盖层存在，也添加一份
        if (overlayChatArea) {
            const overlayTypingDiv = typingDiv.cloneNode(true);
            overlayTypingDiv.id = existingId + '-overlay';
            overlayChatArea.appendChild(overlayTypingDiv);
            scrollToBottom(overlayChatArea);
        }
    }

    function removeModelTyping(modelName) {
        const typingId = 'typing-' + modelName.replace(':', '-');

        // 移除原界面的思考指示器
        const typingDiv = document.getElementById(typingId);
        if (typingDiv) {
            typingDiv.remove();
        }

        // 移除全屏覆盖层的思考指示器
        const overlayTypingDiv = document.getElementById(typingId + '-overlay');
        if (overlayTypingDiv) {
            overlayTypingDiv.remove();
        }
    }
    
    function showModelError(modelName, error) {
        removeModelTyping(modelName);
        showToast(`${getCharacterName(modelName)}: ${error}`, 'error');
    }
    
    function appendMessageToChat(message, persona = null) {
        const chatArea = document.getElementById('groupChatArea');
        const overlayChatArea = document.querySelector('#groupChatOverlayHistory .chat-messages');

        if (!chatArea) {
            console.warn('[appendMessageToChat] 群组对话区域不存在，消息未显示');
            return;
        }

        try {
            const modelName = message.model || '';
            const displayName = persona?.name || getCharacterName(modelName);
            const avatar = persona?.name?.charAt(0) || (message.role === 'user' ? 'U' : 'A');

            // 创建消息HTML
            const messageHtml = `
                <div class="group-message-avatar">
                    <div class="model-avatar" style="background: linear-gradient(135deg, var(--primary-color), var(--accent-color));">
                        ${avatar}
                    </div>
                </div>
                <div class="group-message-content">
                    <div class="group-message-header">
                        <span class="group-message-name">${message.role === 'user' ? '你' : displayName}</span>
                        <span class="group-message-time">${formatTime(message.timestamp)}</span>
                        ${message.role !== 'user' ? `
                            <button class="reference-btn" onclick="GroupChatEnhanced.showReferencePanel('${message.id}')" title="引用此消息">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
                                </svg>
                            </button>
                        ` : ''}
                    </div>
                    <div class="group-message-bubble">
                        ${message.references && message.references.length > 0 ? message.references.map(refId => {
                            const refMsg = state.messages.find(m => m.id === refId);
                            if (!refMsg) return '';
                            return `
                                <div class="reply-reference" onclick="GroupChatEnhanced.scrollToMessage('${refId}')">
                                    <div class="reply-reference-author">引用 ${getCharacterName(refMsg.model)} 的回复</div>
                                    <div class="reply-reference-content">${refMsg.content.substring(0, 100)}...</div>
                                </div>
                            `;
                        }).join('') : ''}
                        <div class="group-message-text">${formatMarkdown(message.content)}</div>
                        ${message.tokens ? `<div class="message-meta">消耗 ${message.tokens} tokens</div>` : ''}
                    </div>
                </div>
            `;

            // 添加到原界面
            const messageDiv = document.createElement('div');
            messageDiv.className = `group-message ${message.role} new`;
            messageDiv.dataset.messageId = message.id;
            messageDiv.innerHTML = messageHtml;
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;

            // 同步到全屏覆盖层（如果存在且激活）
            if (overlayChatArea) {
                const overlayMessageDiv = document.createElement('div');
                overlayMessageDiv.className = `group-message ${message.role} new`;
                overlayMessageDiv.dataset.messageId = message.id;
                overlayMessageDiv.innerHTML = messageHtml;
                overlayChatArea.appendChild(overlayMessageDiv);
                overlayChatArea.scrollTop = overlayChatArea.scrollHeight;
            }
        } catch (error) {
            console.error('[appendMessageToChat] 添加消息失败:', error);
        }
    }
    
    function showReferencePanel(messageId) {
        const messages = state.messages.filter(m => m.role === 'assistant' && m.id !== messageId);
        
        if (messages.length === 0) {
            showToast('没有可引用的消息', 'warning');
            return;
        }
        
        const panel = document.createElement('div');
        panel.className = 'reference-panel';
        panel.id = 'referencePanel';
        panel.innerHTML = `
            <div class="reference-panel-content">
                <div class="reference-panel-header">
                    <h4>选择要引用的消息</h4>
                    <button onclick="GroupChatEnhanced.closeReferencePanel()">×</button>
                </div>
                <div class="reference-list">
                    ${messages.map(m => `
                        <div class="reference-option" onclick="GroupChatEnhanced.addReference('${messageId}', '${m.id}')">
                            <div class="reference-author">${getCharacterName(m.model)}</div>
                            <div class="reference-preview">${m.content.substring(0, 80)}...</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        panel.classList.add('visible');
    }
    
    function closeReferencePanel() {
        const panel = document.getElementById('referencePanel');
        if (panel) {
            panel.classList.remove('visible');
            setTimeout(() => panel.remove(), 300);
        }
    }
    
    function addReference(sourceId, targetId) {
        const message = state.messages.find(m => m.id === sourceId);
        if (message) {
            if (!message.references) {
                message.references = [];
            }
            if (!message.references.includes(targetId)) {
                message.references.push(targetId);
            }
            
            const messageDiv = document.querySelector(`[data-message-id="${sourceId}"]`);
            if (messageDiv) {
                const refMsg = state.messages.find(m => m.id === targetId);
                if (refMsg) {
                    const refHtml = `
                        <div class="reply-reference" onclick="GroupChatEnhanced.scrollToMessage('${targetId}')">
                            <div class="reply-reference-author">引用 ${getCharacterName(refMsg.model)} 的回复</div>
                            <div class="reply-reference-content">${refMsg.content.substring(0, 100)}...</div>
                        </div>
                    `;
                    const bubble = messageDiv.querySelector('.message-bubble');
                    bubble.insertAdjacentHTML('afterbegin', refHtml);
                }
            }
        }
        
        closeReferencePanel();
        showToast('已添加引用', 'success');
    }
    
    function scrollToMessage(messageId) {
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (messageDiv) {
            messageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
            messageDiv.classList.add('highlight');
            setTimeout(() => messageDiv.classList.remove('highlight'), 2000);
        }
    }
    
    function generateId() {
        return 'msg_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    }
    
    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    function formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) {
            return '刚刚';
        } else if (diff < 3600000) {
            return Math.floor(diff / 60000) + ' 分钟前';
        } else if (diff < 86400000) {
            return Math.floor(diff / 3600000) + ' 小时前';
        } else {
            return date.toLocaleDateString('zh-CN');
        }
    }
    
    function formatMarkdown(text) {
        if (!text || typeof text !== 'string') {
            return '';
        }
        
        return text
            // 代码块 - 使用函数替换避免 $ 字符问题
            .replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
                return '<pre><code>' + escapeHtml(code) + '</code></pre>';
            })
            // 行内代码
            .replace(/`([^`]+)`/g, function(match, code) {
                return '<code>' + escapeHtml(code) + '</code>';
            })
            // 粗体 - 使用函数替换避免 $ 字符问题
            .replace(/\*\*([^*]+)\*\*/g, function(match, p1) {
                return '<strong>' + p1 + '</strong>';
            })
            // 斜体 - 使用函数替换
            .replace(/\*([^*]+)\*/g, function(match, p1) {
                return '<em>' + p1 + '</em>';
            })
            // 换行
            .replace(/\n/g, function(match) {
                return '<br>';
            });
    }
    
    // HTML 转义函数
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function scrollToBottom(element) {
        if (!element) return;
        const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        if (nearBottom) {
            element.scrollTop = element.scrollHeight;
        }
    }
    
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--error-color)' : 'var(--info-color)'};
            color: white;
            border-radius: var(--radius-md);
            font-size: 14px;
            z-index: 2000;
            animation: toastFadeIn 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'toastFadeOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }
    
    function getSelectedModels() {
        return state.selectedModels;
    }
    
    function getSpeakingOrder() {
        return state.speakingOrder;
    }
    
    function getSpeakingMode() {
        return state.speakingMode;
    }
    
    function clearMessages() {
        state.messages = [];
        const chatArea = document.getElementById('groupChatArea');
        if (chatArea) {
            chatArea.innerHTML = '';
        }
    }
    
    function removeAllTyping() {
        const typingIndicators = document.querySelectorAll('[id^="typing-"]');
        typingIndicators.forEach(el => el.remove());
    }
    
    function abortCurrentChat() {
        if (state.abortController) {
            state.abortController.abort();
            state.abortController = null;
        }
    }
    
    return {
        init,
        loadModels,
        toggleModel,
        removeFromOrder,
        setSpeakingMode,
        toggleSelector,
        toggleSidebar,
        openModelSelector,
        closeModelSelector,
        selectAllModels,
        deselectAllModels,
        sendMessage,
        showReferencePanel,
        closeReferencePanel,
        addReference,
        scrollToMessage,
        getSelectedModels,
        getSpeakingOrder,
        getSpeakingMode,
        clearMessages,
        removeAllTyping,
        abortCurrentChat
    };
})();

window.GroupChatEnhanced = GroupChatEnhanced;
