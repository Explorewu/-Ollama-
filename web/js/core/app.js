/**
 * Ollama Hub - 主应用逻辑
 * 
 * 功能：协调所有模块，提供完整的用户交互体验
 * 包括：标签页导航、模型管理、智能对话、系统监控等
 */

/**
 * 滚动状态管理器
 * 用于安全地管理 document.body.style.overflow 状态
 * 支持嵌套锁定，避免覆盖其他组件设置的滚动状态
 */
const ScrollStateManager = {
    _lockCount: 0,
    _originalOverflow: '',

    acquire() {
        if (this._lockCount === 0) {
            this._originalOverflow = document.body.style.overflow || '';
            document.body.style.overflow = 'hidden';
        }
        this._lockCount++;
    },

    release() {
        this._lockCount--;
        if (this._lockCount < 0) {
            this._lockCount = 0;
        }
        if (this._lockCount === 0) {
            document.body.style.overflow = this._originalOverflow;
        }
    },

    reset() {
        this._lockCount = 0;
        document.body.style.overflow = this._originalOverflow;
    },

    getLockCount() {
        return this._lockCount;
    }
};

const App = {
    // 当前状态
    state: {
        currentPage: 'chat',
        currentConversation: null,
        currentGroupConversation: null,
        currentGroup: null,
        isGenerating: false,
        installedModels: [],
        selectedModel: '',
        systemInfo: {},
        virtualizationEnabled: true,
        virtMaxRendered: 200,
        virtChunkSize: 150,
        virtOverscan: 30,
        searchActive: false,
        searchQuery: '',
        searchMatches: [],
        searchIndex: -1,
        chatImage: null,
        chatImageBase64: null,
        computerAssistControlEnabled: false,
        computerAssistControlSession: null,
        computerAssistOperationTicket: []
    },
    _streamFlushHandle: null,
    _pendingStreamUpdates: {},

    /**
     * 初始化应用
     */
    async init() {
        console.log('🚀 Ollama Hub 初始化中...');

        // 初始化存储模块（清理损坏数据）
        Storage.init();

        // 初始化主题
        ThemeManager.init();

        // ===== 初始化拆分模块 =====
        // 聊天模块
        if (window.AppChat) {
            AppChat.init(this);
        }

        // 绑定事件监听器（使用事件模块）
        if (window.AppEvents) {
            AppEvents.bindAll(this);
        } else {
            this.bindEvents();
        }

        // 群组模块
        if (window.AppGroup) {
            AppGroup.init(this);
        }

        // 搜索模块
        if (window.AppSearch) {
            AppSearch.init(this);
        } else {
            // 备用搜索UI
            this.initSearchUI();
        }

        // 初始化电脑协助可控执行模式（默认关闭，可持久化）
        this.initComputerAssistControlMode();

        // 初始化拖拽上传
        this.initDragUpload();

        // 加载设置到UI
        this.loadSettingsToUI();

        // ===== 并行初始化 =====
        // 这些任务互不依赖，可以并行执行
        const [_, __] = await Promise.all([
            // 初始化系统信息和加载模型（可并行）
            Promise.all([
                this.initSystemInfo(),
                this.loadModels()
            ]),
            // 加载对话和群组历史（可并行）
            Promise.all([
                this.loadConversations(),
                this.loadGroups()
            ])
        ]);

        // 设置默认对话
        this.setupDefaultConversation();

        // 开始系统监控（延迟启动，等页面稳定后再运行）
        setTimeout(() => this.startSystemMonitoring(), 2000);

        // ===== 按需加载（非阻塞）=====
        // 这些服务不需要立即加载，延迟初始化
        setTimeout(() => {
            this.initMarkdownWorker();
            this.initVirtualization();
        }, 500);

        // ===== 可选模块（延迟加载）=====
        // 这些模块只在需要时加载
        this.lazyLoadOptionalModules();

        // 初始化智能对话全屏覆盖层
        this.initChatOverlay();

        // 初始化群组对话全屏覆盖层
        this.initGroupChatOverlay();

        console.log('✅ Ollama Hub 初始化完成');
    },

    /**
     * 按需加载可选模块（延迟初始化）
     */
    lazyLoadOptionalModules() {
        // 延迟加载可选模块，不阻塞主线程
        setTimeout(() => {
            // 初始化 API 配置模块
            if (typeof ApiChat !== 'undefined') {
                ApiChat.init();
            }

            // 初始化 TOKEN 统计
            if (typeof TokenStats !== 'undefined') {
                TokenStats.init();
            }

            // 初始化群组对话增强模块
            if (typeof GroupChatEnhanced !== 'undefined') {
                GroupChatEnhanced.init();

                // 注册群组对话回调函数
                window.GroupChatCallbacks = {
                    onPersonaStart: (persona) => {
                        this.showGroupTypingIndicator(persona);
                        this.appendGroupMessageToOverlay('assistant', '', persona);
                        const overlayMessages = document.querySelector('#groupChatOverlayHistory .chat-messages');
                        if (overlayMessages) {
                            overlayMessages.scrollTop = overlayMessages.scrollHeight;
                        }
                    },
                    onStream: (chunk) => {
                        this.updateGroupStreamingMessage(chunk.persona, chunk.content, chunk.done);
                        this.updateGroupOverlayStreamingMessage(chunk.persona, chunk.content, chunk.done);
                    },
                    onPersonaComplete: () => {
                        this.hideGroupTypingIndicator();
                    }
                };
            }

            // 初始化角色记忆系统
            if (typeof PersonaMemory !== 'undefined') {
                PersonaMemory.init();
            }

            // 初始化 API Key 管理模块
            if (typeof APIKeyManager !== 'undefined') {
                APIKeyManager.init();
            }

            // 初始化函数调用管理模块
            if (typeof FunctionManager !== 'undefined') {
                FunctionManager.init();
            }


        }, 1000);
    },





    /**
     * 绑定所有事件监听器
     */
    bindEvents() {
        // 主题切换按钮
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => ThemeManager.toggleTheme());
        }

        // 主题选项
        document.querySelectorAll('.theme-option').forEach(option => {
            option.addEventListener('click', () => {
                ThemeManager.applyTheme(option.dataset.theme);
            });
        });

        // 侧边栏导航
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => this.switchPage(item.dataset.page));
        });

        // 快速操作按钮
        document.getElementById('pullModelBtn')?.addEventListener('click', () => this.openPullModal());
        document.getElementById('pullModelBtn2')?.addEventListener('click', () => this.openPullModal());
        document.getElementById('newChatBtn')?.addEventListener('click', () => this.startNewChat());
        document.getElementById('newChatBtn2')?.addEventListener('click', () => this.startNewChat());
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.refreshAll());

        // 模型搜索
        const modelSearch = document.getElementById('modelSearch');
        if (modelSearch) {
            modelSearch.addEventListener('input', (e) => this.filterModels(e.target.value));
        }

        // 筛选按钮
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.filterModels(document.getElementById('modelSearch')?.value || '', btn.dataset.filter);
            });
        });

        // 聊天输入框
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.addEventListener('input', () => this.handleChatInput());
            chatInput.addEventListener('keydown', (e) => this.handleChatKeydown(e));

            // 自动调整高度
            const adjustHeight = () => {
                chatInput.style.height = 'auto';
                chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
            };

            chatInput.addEventListener('input', adjustHeight);

            // 初始化时调整高度
            setTimeout(adjustHeight, 0);
        }

        // 发送按钮
        document.getElementById('sendBtn')?.addEventListener('click', () => this.sendMessage());
        document.getElementById('computerAssistBtn')?.addEventListener('click', () => {
            this.handleComputerAssistRequest({
                forced: true,
                allowControl: !!this.state.computerAssistControlEnabled
            });
        });
        document.getElementById('computerAssistControlToggleBtn')?.addEventListener('click', () => {
            this.toggleComputerAssistControlMode();
        });
        document.getElementById('computerAssistRunBtn')?.addEventListener('click', () => {
            this.handleComputerAssistExecution({});
        });

        // 图片上传按钮
        document.getElementById('imageUploadBtn')?.addEventListener('click', () => {
            document.getElementById('chatImageInput')?.click();
        });
        
        document.getElementById('chatImageInput')?.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleChatImageUpload(e.target.files[0]);
            }
        });
        
        document.getElementById('removeChatImageBtn')?.addEventListener('click', () => {
            this.clearChatImage();
        });

        // 清空对话按钮
        document.getElementById('clearChatBtn')?.addEventListener('click', () => this.clearCurrentChat());

        // 世界观相关事件
        this.bindWorldviewEvents();

        // 模型选择器
        const modelSelect = document.getElementById('modelSelect');
        if (modelSelect) {
            modelSelect.addEventListener('change', (e) => {
                this.state.selectedModel = e.target.value;
                this.updateConversationModel(e.target.value);
            });
        }

        // 新建对话按钮（侧边栏）
        document.getElementById('newConversationBtn')?.addEventListener('click', () => this.startNewChat());

        // 建议按钮 - 点击后填充输入框，等待用户确认发送
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                document.getElementById('chatInput').value = prompt;
                this.handleChatInput();
                this.showToast('已填入输入框，请按 Enter 发送或点击发送按钮', 'info');
            });
        });

        // 群组对话相关
        document.getElementById('newGroupBtn')?.addEventListener('click', () => this.showGroupModal('create'));

        // 侧边栏折叠/展开功能
        const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
        const sidebarExpandBtn = document.getElementById('sidebarExpandBtn');
        const groupSidebar = document.getElementById('groupSidebar');
        const mainSidebar = document.getElementById('mainSidebar');

        // 主侧边栏折叠
        const mainSidebarExpandBtn = document.getElementById('mainSidebarExpandBtn');
        if (sidebarCollapseBtn && mainSidebar) {
            sidebarCollapseBtn.addEventListener('click', () => {
                mainSidebar.classList.add('collapsed');
                localStorage.setItem('mainSidebarCollapsed', 'true');
            });
        }

        // 主侧边栏展开
        if (mainSidebarExpandBtn && mainSidebar) {
            mainSidebarExpandBtn.addEventListener('click', () => {
                mainSidebar.classList.remove('collapsed');
                localStorage.setItem('mainSidebarCollapsed', 'false');
            });
        }

        // 群组侧边栏折叠
        if (sidebarCollapseBtn && groupSidebar) {
            sidebarCollapseBtn.addEventListener('click', () => {
                groupSidebar.classList.add('collapsed');
                if (sidebarExpandBtn) {
                    sidebarExpandBtn.classList.add('visible');
                }
                localStorage.setItem('sidebarCollapsed', 'true');
            });
        }

        if (sidebarExpandBtn && groupSidebar) {
            sidebarExpandBtn.addEventListener('click', () => {
                groupSidebar.classList.remove('collapsed');
                sidebarExpandBtn.classList.remove('visible');
                localStorage.setItem('sidebarCollapsed', 'false');
            });
        }

        // 恢复主侧边栏状态
        const isMainCollapsed = localStorage.getItem('mainSidebarCollapsed') === 'true';
        if (isMainCollapsed && mainSidebar) {
            mainSidebar.classList.add('collapsed');
        }

        // 恢复群组侧边栏状态
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed && groupSidebar) {
            groupSidebar.classList.add('collapsed');
            if (sidebarExpandBtn) {
                sidebarExpandBtn.classList.add('visible');
            }
        }

        document.getElementById('groupChatInput')?.addEventListener('input', () => this.handleGroupChatInput());
        document.getElementById('groupChatInput')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendGroupMessage();
            }
        });
        document.getElementById('groupSendBtn')?.addEventListener('click', () => this.sendGroupMessage());
        document.getElementById('pauseGroupChatBtn')?.addEventListener('click', () => this.pauseGroupChat());

        document.getElementById('groupModalClose')?.addEventListener('click', () => this.hideGroupModal());
        document.getElementById('groupModalCancel')?.addEventListener('click', () => this.hideGroupModal());
        document.getElementById('groupForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveGroup();
        });
        document.getElementById('deleteConfirmCancel')?.addEventListener('click', () => this.hideDeleteConfirm());
        document.getElementById('deleteConfirmConfirm')?.addEventListener('click', () => this.confirmDeleteGroup());

        document.getElementById('groupModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'groupModal') this.hideGroupModal();
        });
        document.getElementById('deleteConfirmModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'deleteConfirmModal') this.hideDeleteConfirm();
        });

        // 群组聊天输入框自动调整高度
        const groupChatInput = document.getElementById('groupChatInput');
        if (groupChatInput) {
            const adjustGroupHeight = () => {
                groupChatInput.style.height = 'auto';
                groupChatInput.style.height = Math.min(groupChatInput.scrollHeight, 200) + 'px';
            };

            groupChatInput.addEventListener('input', adjustGroupHeight);
            setTimeout(adjustGroupHeight, 0);
        }
        document.getElementById('clearGroupChatBtn')?.addEventListener('click', () => this.clearGroupChat());

        // 设置表单
        this.bindSettingsEvents();

        // 下载模型模态框
        this.bindPullModalEvents();

        // 通用模态框
        this.bindModalEvents();

        // 参数说明模态框
        this.bindParamGuideEvents();

        // 窗口大小变化
        window.addEventListener('resize', () => this.handleResize());
    },

    /**
     * 绑定世界观相关事件
     */
    bindWorldviewEvents() {
        const worldviewInput = document.getElementById('overlayWorldviewInput');
        const templateBtn = document.getElementById('worldviewTemplateBtn');
        const modal = document.getElementById('worldviewModal');
        const modalClose = document.getElementById('worldviewModalClose');
        const addBtn = document.getElementById('addWorldviewBtn');

        // 世界观输入框 - 保存到当前对话
        if (worldviewInput) {
            worldviewInput.addEventListener('change', () => {
                this.saveWorldviewToConversation();
            });
        }

        // 模板按钮 - 打开弹窗
        if (templateBtn) {
            templateBtn.addEventListener('click', () => {
                this.showWorldviewModal();
            });
        }

        // 关闭弹窗
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                const modalOverlay = document.getElementById('worldviewModalOverlay');
                if (modalOverlay) {
                    modalOverlay.classList.remove('active');
                }
            });
        }

        // 点击弹窗外部关闭
        const modalOverlay = document.getElementById('worldviewModalOverlay');
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    modalOverlay.classList.remove('active');
                }
            });
        }

        // 添加新世界观
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                const nameInput = document.getElementById('newWorldviewName');
                const contentInput = document.getElementById('newWorldviewContent');
                if (nameInput.value.trim() && contentInput.value.trim()) {
                    WorldviewManager.add({
                        name: nameInput.value.trim(),
                        content: contentInput.value.trim()
                    });
                    nameInput.value = '';
                    contentInput.value = '';
                    this.renderWorldviewList();
                    this.showToast('世界观已添加', 'success');
                }
            });
        }
    },

    /**
     * 保存世界观到当前对话
     */
    saveWorldviewToConversation() {
        const worldviewInput = document.getElementById('overlayWorldviewInput');
        if (!worldviewInput || !this.state.currentConversation) return;

        const worldview = worldviewInput.value.trim();
        Storage.updateConversation(this.state.currentConversation.id, {
            worldview: worldview
        });
    },

    /**
     * 加载当前对话的世界观
     */
    loadWorldviewToInput() {
        const worldviewInput = document.getElementById('overlayWorldviewInput');
        if (!worldviewInput || !this.state.currentConversation) return;

        const conversation = Storage.getConversation(this.state.currentConversation.id);
        if (conversation && conversation.worldview) {
            worldviewInput.value = conversation.worldview;
        } else {
            worldviewInput.value = '';
        }
    },

    /**
     * 显示世界观选择弹窗
     */
    showWorldviewModal() {
        const modalOverlay = document.getElementById('worldviewModalOverlay');
        if (modalOverlay) {
            this.renderWorldviewList();
            modalOverlay.classList.add('active');
        }
    },

    /**
     * 渲染世界观列表
     */
    renderWorldviewList() {
        const list = document.getElementById('worldviewList');
        if (!list) return;

        const worldviews = WorldviewManager.getAll();
        list.innerHTML = worldviews.map(w => `
            <div class="worldview-item" data-id="${w.id}" data-content="${this.escapeHtml(w.content)}">
                <div class="worldview-name">${w.name}</div>
                <div class="worldview-preview">${w.content}</div>
            </div>
        `).join('');

        // 点击选择世界观
        list.querySelectorAll('.worldview-item').forEach(item => {
            item.addEventListener('click', () => {
                const content = item.dataset.content;
                const worldviewInput = document.getElementById('overlayWorldviewInput');
                if (worldviewInput) {
                    worldviewInput.value = content;
                    this.saveWorldviewToConversation();
                }
                const modalOverlay = document.getElementById('worldviewModalOverlay');
                if (modalOverlay) {
                    modalOverlay.classList.remove('active');
                }
            });
        });
    },

    /**
     * 绑定设置相关事件
     */
    bindSettingsEvents() {
        // 自动保存设置
        const saveSettings = () => {
            const settings = {
                apiUrl: document.getElementById('apiUrl')?.value || `http://${window.location.hostname || 'localhost'}:11434`,
                requestTimeout: parseInt(document.getElementById('requestTimeout')?.value) || 120,
                maxTokens: parseInt(document.getElementById('maxTokens')?.value) || 2048,
                temperature: parseFloat(document.getElementById('temperature')?.value) || 0.7,
                contextLength: parseInt(document.getElementById('contextLength')?.value) || 4096,
                topK: parseInt(document.getElementById('topK')?.value) || 40,
                topP: parseFloat(document.getElementById('topP')?.value) || 0.9,
                repeatPenalty: parseFloat(document.getElementById('repeatPenalty')?.value) || 1.1,
                presencePenalty: parseFloat(document.getElementById('presencePenalty')?.value) || 0,
                frequencyPenalty: parseFloat(document.getElementById('frequencyPenalty')?.value) || 0,
                fontSize: document.getElementById('fontSize')?.value || '16px',
                streamMode: document.getElementById('streamMode')?.value || 'balanced',
                sentenceEndDelay: parseInt(document.getElementById('sentenceEndDelay')?.value) || 20,
                doubleEndDelay: parseInt(document.getElementById('sentenceEndDelay')?.value) || 20,
                maxWaitChars: parseInt(document.getElementById('maxWaitChars')?.value) || 60,
                maxWaitTime: parseInt(document.getElementById('maxWaitTime')?.value) || 250,
                minSegmentChars: 10,
                newParagraphChars: 2,
                conversationMode: document.getElementById('conversationMode')?.value || 'standard',
            };
            Storage.saveSettings(settings);
            
            // 更新字体大小
            document.documentElement.style.setProperty('--font-size-base', settings.fontSize);
            
            // 显示Toast提示
            App.showToast('设置已保存', 'success');
        };

        // 绑定输入事件
        ['apiUrl', 'requestTimeout', 'maxTokens', 'temperature', 'contextLength', 
         'topK', 'topP', 'repeatPenalty', 'presencePenalty', 'frequencyPenalty', 'fontSize',
         'sentenceEndDelay', 'maxWaitChars', 'maxWaitTime'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', saveSettings);
                element.addEventListener('input', saveSettings);
            }
        });

        // 对话模式选择事件
        const conversationModeSelect = document.getElementById('conversationMode');
        if (conversationModeSelect) {
            conversationModeSelect.addEventListener('change', () => {
                saveSettings();
                App.showToast(`已切换至${conversationModeSelect.value === 'adult' ? '成人' : '标准'}模式`, 'info');
            });
        }

        // 绑定所有滑块的值显示更新
        const sliderMappings = [
            { slider: 'temperature', value: 'temperatureValue' },
            { slider: 'topK', value: 'topKValue' },
            { slider: 'topP', value: 'topPValue' },
            { slider: 'repeatPenalty', value: 'repeatPenaltyValue' },
            { slider: 'presencePenalty', value: 'presencePenaltyValue' },
            { slider: 'frequencyPenalty', value: 'frequencyPenaltyValue' }
        ];

        sliderMappings.forEach(({ slider, value }) => {
            const sliderEl = document.getElementById(slider);
            const valueEl = document.getElementById(value);
            if (sliderEl && valueEl) {
                sliderEl.addEventListener('input', () => {
                    valueEl.textContent = sliderEl.value;
                });
            }
        });

        // TOKEN 统计开关事件
        const tokenStatsEnabled = document.getElementById('tokenStatsEnabled');
        if (tokenStatsEnabled) {
            tokenStatsEnabled.addEventListener('change', () => {
                if (typeof ApiChat !== 'undefined') {
                    const config = ApiChat.getConfig();
                    config.tokenTracking.enabled = tokenStatsEnabled.checked;
                    ApiChat.saveConfig();
                    TokenStats.update();
                    App.showToast(tokenStatsEnabled.checked ? 'TOKEN 统计已开启' : 'TOKEN 统计已关闭', 'success');
                }
            });
        }

        // 流式模式选择器事件
        const streamModeBtns = document.querySelectorAll('.stream-mode-btn');
        const streamModeInput = document.getElementById('streamMode');
        const streamModeHint = document.getElementById('streamModeHint');
        const streamModeHints = {
            fast: '快速模式：响应最快，可能在句子中间分段',
            balanced: '平衡模式：兼顾响应速度与阅读体验',
            complete: '完整模式：等待完整句子，响应较慢',
            manual: '手动模式：点击按钮继续显示下一段'
        };

        streamModeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                streamModeBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const mode = btn.dataset.mode;
                streamModeInput.value = mode;
                if (streamModeHint) {
                    streamModeHint.textContent = streamModeHints[mode];
                }
                saveSettings();
            });
        });

        // 流式设置滑块事件
        const streamSliderMappings = [
            { slider: 'sentenceEndDelay', value: 'sentenceEndDelayValue', suffix: 'ms' },
            { slider: 'maxWaitChars', value: 'maxWaitCharsValue', suffix: '' },
            { slider: 'maxWaitTime', value: 'maxWaitTimeValue', suffix: 'ms' }
        ];

        streamSliderMappings.forEach(({ slider, value, suffix }) => {
            const sliderEl = document.getElementById(slider);
            const valueEl = document.getElementById(value);
            if (sliderEl && valueEl) {
                sliderEl.addEventListener('input', () => {
                    valueEl.textContent = sliderEl.value + (suffix || '');
                });
            }
        });

        // 数据导出
        document.getElementById('exportDataBtn')?.addEventListener('click', () => this.exportData());

        // 数据导入
        document.getElementById('importDataBtn')?.addEventListener('click', () => this.importData());

        // 清除所有数据
        document.getElementById('clearAllDataBtn')?.addEventListener('click', () => this.clearAllData());

        // 创建新角色卡
        document.getElementById('createPersonaBtn')?.addEventListener('click', () => {
            this.openPersonaEditor(null);
        });

        // 导出当前角色
        document.getElementById('exportCurrentPersonaBtn')?.addEventListener('click', () => {
            this.exportCurrentPersona();
        });

        // 导出全部角色
        document.getElementById('exportAllPersonasBtn')?.addEventListener('click', () => {
            this.exportAllPersonas();
        });

        // 导入单个角色
        document.getElementById('importPersonaBtn')?.addEventListener('click', () => {
            this.openPersonaImportDialog();
        });

        // 批量导入角色
        document.getElementById('batchImportPersonaBtn')?.addEventListener('click', () => {
            this.openPersonaBatchImport();
        });

        // 重置所有角色卡
        document.getElementById('resetPersonasBtn')?.addEventListener('click', () => {
            this.resetAllPersonas();
        });

        // 角色卡导入/导出下拉菜单切换
        const importExportBtn = document.getElementById('personaImportExportBtn');
        const importExportMenu = document.getElementById('personaImportExportMenu');
        if (importExportBtn && importExportMenu) {
            importExportBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                importExportMenu.classList.toggle('active');
            });
            document.addEventListener('click', () => {
                importExportMenu.classList.remove('active');
            });
            importExportMenu.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }

        // 绑定设置页面二级菜单导航
        const navItems = document.querySelectorAll('.settings-nav .nav-item, .sidebar-footer .nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const section = item.dataset.section;
                if (!section) return;

                // 更新导航项状态
                navItems.forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');

                // 显示对应内容区域
                document.querySelectorAll('.settings-section').forEach(sec => {
                    sec.classList.remove('active');
                });
                const targetSection = document.getElementById(`section-${section}`);
                if (targetSection) {
                    targetSection.classList.add('active');
                }
            });
        });
    },

    /**
     * 绑定下载模态框事件
     */
    bindPullModalEvents() {
        const modal = document.getElementById('pullModalOverlay');
        const closeBtn = document.getElementById('pullModalClose');
        const cancelBtn = document.getElementById('pullCancelBtn');
        const confirmBtn = document.getElementById('pullConfirmBtn');
        const modelInput = document.getElementById('modelNameInput');

        // 关闭模态框
        const closeModal = () => {
            modal.classList.remove('active');
            modelInput.value = '';
            document.getElementById('downloadProgress').style.display = 'none';
        };

        closeBtn?.addEventListener('click', closeModal);
        cancelBtn?.addEventListener('click', closeModal);
        modal?.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        // 确认下载
        confirmBtn?.addEventListener('click', async () => {
            const modelName = modelInput.value.trim();
            if (!modelName) {
                this.showToast('请输入模型名称', 'warning');
                return;
            }
            await this.pullModel(modelName);
        });

        // 热门模型快捷选择
        document.querySelectorAll('.model-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                modelInput.value = chip.dataset.model;
            });
            
            // 鼠标悬浮显示提示框
            chip.addEventListener('mouseenter', (e) => {
                this.showModelTooltip(e, chip);
            });
            
            // 鼠标离开隐藏提示框
            chip.addEventListener('mouseleave', () => {
                this.hideModelTooltip();
            });
        });
    },

    /**
     * 显示模型悬浮提示框
     */
    showModelTooltip(event, chip) {
        const tooltip = document.getElementById('modelTooltip');
        if (!tooltip) return;
        
        // 获取模型数据
        const modelName = chip.dataset.model || chip.textContent.trim();
        const modelSize = chip.dataset.size || '未知';
        const modelEffect = chip.dataset.effect || '暂无描述';
        const modelUsage = chip.dataset.usage || '暂无描述';
        const downloadTime = chip.dataset.downloadTime || '未知';
        const releaseTime = chip.dataset.release || '未知';
        const reasoning = chip.dataset.reasoning || '支持';
        
        // 更新提示框内容
        document.getElementById('tooltipTitle').textContent = modelName;
        document.getElementById('tooltipSize').textContent = modelSize + ' GB';
        document.getElementById('tooltipEffect').textContent = modelEffect;
        document.getElementById('tooltipUsage').textContent = modelUsage;
        document.getElementById('tooltipTime').textContent = downloadTime;
        document.getElementById('tooltipRelease').textContent = releaseTime;
        const reasoningElement = document.getElementById('tooltipReasoning');
        reasoningElement.textContent = reasoning;
        reasoningElement.setAttribute('data-value', reasoning);
        
        // 计算提示框位置（使用鼠标事件位置）
        const tooltipHeight = tooltip.offsetHeight || 200;
        const tooltipWidth = tooltip.offsetWidth || 360;
        
        // 获取鼠标位置（优先使用事件位置，否则使用芯片位置）
        let mouseX, mouseY;
        if (event && event.clientX !== undefined) {
            mouseX = event.clientX;
            mouseY = event.clientY;
        } else {
            const chipRect = chip.getBoundingClientRect();
            mouseX = chipRect.left + (chipRect.width / 2);
            mouseY = chipRect.bottom;
        }
        
        // 计算悬浮卡片位置（以鼠标位置为中心）
        let left = mouseX - (tooltipWidth / 2);
        let top = mouseY + 12;
        
        // 检测边界，防止超出视口
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const padding = 20;
        
        // 检查右侧边界
        if (left + tooltipWidth > viewportWidth - padding) {
            left = viewportWidth - padding - tooltipWidth;
        }
        
        // 检查左侧边界
        if (left < padding) {
            left = padding;
        }
        
        // 检查底部边界
        if (top + tooltipHeight > viewportHeight - padding) {
            // 如果下方空间不足，显示在上方
            top = mouseY - tooltipHeight - 12;
        }
        
        // 设置提示框位置（fixed 定位，不使用 transform）
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.transform = 'none';
        
        // 显示提示框
        tooltip.style.display = 'block';
    },

    /**
     * 隐藏模型悬浮提示框
     */
    hideModelTooltip() {
        const tooltip = document.getElementById('modelTooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    },

    /**
     * 绑定通用模态框事件
     */
    bindModalEvents() {
        const overlay = document.getElementById('modalOverlay');
        const closeBtn = document.getElementById('modalClose');

        closeBtn?.addEventListener('click', () => {
            overlay.classList.remove('active');
        });

        overlay?.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    },

    /**
     * 绑定参数说明模态框事件
     */
    bindParamGuideEvents() {
        const guideBtn = document.getElementById('paramGuideBtn');
        const overlay = document.getElementById('paramGuideOverlay');
        const closeBtn = document.getElementById('paramGuideClose');

        guideBtn?.addEventListener('click', () => {
            overlay.classList.add('active');
        });

        closeBtn?.addEventListener('click', () => {
            overlay.classList.remove('active');
        });

        overlay?.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    },

    /**
     * 切换页面
     * @param {string} pageName - 页面名称
     */
    switchPage(pageName) {
        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });

        // 更新内容显示
        document.querySelectorAll('.page-content').forEach(content => {
            content.classList.toggle('active', content.id === `${pageName}-page`);
        });

        this.state.currentPage = pageName;

        // 页面特定初始化
        if (pageName === 'models') {
            this.loadModels();
        } else if (pageName === 'chat') {
            this.loadConversations();
        } else if (pageName === 'group-chat') {
            this.loadGroups();
            // 自动加载上次选择的群组
            this.loadLastSelectedGroup();
        } else if (pageName === 'dashboard') {
            this.updateSystemResources();
            this.updateDashboardStats();
        }
    },

    updateDashboardStats() {
        this.updateModelCount();
        this.checkServicesStatus();
    },

    async updateModelCount() {
        const modelCountEl = document.getElementById('modelCount');
        if (!modelCountEl) return;
        
        try {
            const models = await API.getModels();
            if (models && models.length) {
                modelCountEl.textContent = models.length;
            }
        } catch (e) {
            modelCountEl.textContent = '--';
        }
    },

    async checkServicesStatus() {
        const serviceStatus = document.getElementById('serviceStatus');
        const ragStatus = document.getElementById('ragStatus');
        const ragDocCount = document.getElementById('ragDocCount');
        
        // 检查 Ollama 服务状态
        try {
            const ollama = await fetch(`http://${window.location.hostname || 'localhost'}:11434/api/tags`);
            if (serviceStatus) {
                serviceStatus.textContent = ollama.ok ? '运行中' : '异常';
                serviceStatus.style.color = ollama.ok ? '#22c55e' : '#ef4444';
            }
        } catch (e) {
            if (serviceStatus) {
                serviceStatus.textContent = '未连接';
                serviceStatus.style.color = '#ef4444';
            }
        }
        
        // 检查后端 API 服务状态
        try {
            const api = await fetch(`http://${window.location.hostname || 'localhost'}:5001/api/health`);
            if (ragStatus) {
                ragStatus.textContent = api.ok ? '运行中' : '异常';
                ragStatus.style.color = api.ok ? '#22c55e' : '#ef4444';
            }
        } catch (e) {
            if (ragStatus) {
                ragStatus.textContent = '未连接';
                ragStatus.style.color = '#ef4444';
            }
        }
    },

    /**
     * 加载上次选择的群组
     */
    loadLastSelectedGroup() {
        const lastGroupId = localStorage.getItem('lastSelectedGroupId');
        const groups = Storage.getGroups();
        
        if (lastGroupId && groups.some(g => g.id === lastGroupId)) {
            // 有上次选择的群组且仍然存在
            this.selectGroup(lastGroupId);
        } else if (groups.length > 0) {
            // 没有上次选择或已删除，选择第一个
            this.selectGroup(groups[0].id);
        }
        // 如果没有群组，显示空状态（由UI自动处理）
    },

    /**
     * 打开下载模型模态框
     */
    openPullModal() {
        document.getElementById('pullModalOverlay').classList.add('active');
    },

    /**
     * 下载模型
     * @param {string} modelName - 模型名称
     */
    async pullModel(modelName) {
        const progressContainer = document.getElementById('downloadProgress');
        const progressBar = document.getElementById('progressBarFill');
        const progressStatus = document.getElementById('progressStatus');
        const progressPercent = document.getElementById('progressPercent');
        const confirmBtn = document.getElementById('pullConfirmBtn');

        progressContainer.style.display = 'block';
        confirmBtn.disabled = true;

        try {
            await API.pullModel(modelName, (progress) => {
                progressStatus.textContent = progress.status;
                progressPercent.textContent = progress.progress + '%';
                progressBar.style.width = progress.progress + '%';
            });

            this.showToast(`模型 ${modelName} 下载完成！`, 'success');
            await this.loadModels();
            
            setTimeout(() => {
                document.getElementById('pullModalOverlay').classList.remove('active');
                progressContainer.style.display = 'none';
                progressBar.style.width = '0%';
                confirmBtn.disabled = false;
            }, 1500);

        } catch (error) {
            this.showToast(`下载失败: ${error.message}`, 'error');
            progressStatus.textContent = '下载失败';
            confirmBtn.disabled = false;
        }
    },

    /**
     * 加载模型列表
     */
    async loadModels() {
        const grid = document.getElementById('modelsGrid');

        try {
            const models = await API.getModels();
            this.state.installedModels = models;

            // 更新设置页面的模型选择下拉框
            const settingsModelSelect = document.getElementById('modelSelectNew');
            if (settingsModelSelect) {
                this.updateSettingsModelSelect(models);
            }

            // 渲染模型卡片
            this.renderModelCards(models);

            // 更新服务状态为正常
            this.updateServiceStatus(true);

        } catch (error) {
            console.warn('⚠️ Ollama 服务未启动（这是正常的，可以稍后启动）:', error.message);
            
            // 优雅降级：服务未启动时显示友好提示，不阻止使用
            this.state.installedModels = [];
            
            // 更新服务状态为离线
            this.updateServiceStatus(false);
            
            // 如果当前在模型管理页面，显示友好提示
            if (grid && document.querySelector('.page-content.active')?.id === 'models-page') {
                grid.innerHTML = `
                    <div class="empty-state" style="padding: 40px; text-align: center;">
                        <div class="empty-state-icon" style="font-size: 48px; margin-bottom: 20px;">🔌</div>
                        <h3 style="color: var(--text-primary); margin-bottom: 10px;">Ollama 服务未启动</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 20px;">
                            可以继续使用，但对话功能需要先启动 Ollama
                        </p>
                        <div class="empty-state-actions">
                            <button class="btn btn-primary" onclick="App.autoStartService()">
                                启动 Ollama 服务
                            </button>
                            <button class="btn btn-secondary" onclick="App.loadModels()">
                                重新加载
                            </button>
                        </div>
                    </div>
                `;
            }
        }
    },

    /**
     * 更新模型选择下拉框
     * @param {Array} models - 模型列表
     */
    updateSettingsModelSelect(models) {
        const select = document.getElementById('modelSelectNew');
        if (!select) return;

        const currentValue = select.value;

        // 过滤掉禁用的模型
        const disabledModels = Storage.getDisabledModels();
        const enabledModels = models.filter(model => !disabledModels.includes(model.name));

        select.innerHTML = '<option value="">选择模型...</option>';

        enabledModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            option.textContent = model.name;
            select.appendChild(option);
        });

        // 恢复选中的模型（如果它没有被禁用）
        if (currentValue && enabledModels.find(m => m.name === currentValue)) {
            select.value = currentValue;
            this.state.selectedModel = currentValue;
        } else if (enabledModels.length > 0) {
            // 如果当前选中的模型被禁用了，选择第一个可用模型
            select.value = enabledModels[0].name;
            this.state.selectedModel = enabledModels[0].name;
        }

        // 更新模型计数（显示启用的模型数/总数）
        const modelCountEl = document.getElementById('modelCount');
        if (modelCountEl) {
            modelCountEl.textContent = `${enabledModels.length}/${models.length}`;
        }
    },

    /**
     * 渲染模型卡片
     * @param {Array} models - 模型列表
     */
    renderModelCards(models) {
        const grid = document.getElementById('modelsGrid');

        // 过滤掉禁用的模型
        const disabledModels = Storage.getDisabledModels();
        const enabledModels = models.filter(model => !disabledModels.includes(model.name));

        if (enabledModels.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📦</div>
                    <h3>暂无已启用的模型</h3>
                    <p>所有模型已被禁用，请在设置中启用模型</p>
                    <button class="btn btn-primary" onclick="App.switchPage('settings')">
                        前往设置
                    </button>
                </div>
            `;
            return;
        }

        // 对模型排序，literary-super 优先显示
        const sortedModels = [...enabledModels].sort((a, b) => {
            if (a.name.includes('literary-super')) return -1;
            if (b.name.includes('literary-super')) return 1;
            if (a.name.includes('literary-assistant')) return -1;
            if (b.name.includes('literary-assistant')) return 1;
            return 0;
        });
        
        grid.innerHTML = sortedModels.map(model => {
            const icon = '🤖';
            const description = '点击使用此模型进行对话，或删除模型以释放空间。';
            
            return `
            <div class="model-card" data-model="${model.name}">
                <div class="model-card-header">
                    <div class="model-icon-large">${icon}</div>
                    <div class="model-info">
                        <div class="model-name">${model.name}</div>
                        <div class="model-size">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                            </svg>
                            ${API.formatSize(model.size)}
                        </div>
                    </div>
                </div>
                <div class="model-description">
                    ${description}
                </div>
                <div class="model-actions">
                    <button class="btn btn-primary" onclick="App.useModel('${model.name}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                        </svg>
                        开始对话
                    </button>
                    <button class="btn btn-secondary" onclick="App.deleteModel('${model.name}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        删除
                    </button>
                </div>
            </div>
        `}).join('');
    },

    /**
     * 过滤模型
     * @param {string} query - 搜索关键词
     * @param {string} filter - 筛选类型
     */
    filterModels(query = '', filter = 'all') {
        const cards = document.querySelectorAll('.model-card');
        const lowercaseQuery = query.toLowerCase();

        cards.forEach(card => {
            const modelName = card.dataset.model.toLowerCase();
            const matchesQuery = modelName.includes(lowercaseQuery);
            
            // 目前所有模型都是已下载的，所以筛选逻辑可以根据需要扩展
            const matchesFilter = filter === 'all' || filter === 'downloaded';
            
            card.style.display = matchesQuery && matchesFilter ? '' : 'none';
        });
    },

    /**
     * 使用指定模型
     * @param {string} modelName - 模型名称
     */
    useModel(modelName) {
        this.switchPage('chat');
        const modelSelect = document.getElementById('modelSelect');
        if (modelSelect) {
            modelSelect.value = modelName;
        }
        this.state.selectedModel = modelName;
        this.updateConversationModel(modelName);
        this.showToast(`已选择模型: ${modelName}`, 'success');
    },

    /**
     * 删除模型
     * @param {string} modelName - 模型名称
     */
    async deleteModel(modelName) {
        if (!confirm(`确定要删除模型 "${modelName}" 吗？此操作不可恢复。`)) {
            return;
        }

        try {
            await API.deleteModel(modelName);
            this.showToast(`模型 ${modelName} 已删除`, 'success');
            await this.loadModels();
        } catch (error) {
            this.showToast(`删除失败: ${error.message}`, 'error');
        }
    },

    /**
     * 初始化系统信息
     */
    async initSystemInfo() {
        const osInfo = document.getElementById('osInfo');
        const ollamaVersion = document.getElementById('ollamaVersion');
        const apiAddress = document.getElementById('apiAddress');

        // 获取操作系统信息
        const platform = navigator.platform;
        osInfo.textContent = platform;

        // 获取 Ollama 版本
        const version = await API.getVersion();
        ollamaVersion.textContent = version;

        // 显示 API 地址
        const settings = Storage.getSettings();
        apiAddress.textContent = settings.apiUrl;

        // 检查服务状态
        await this.checkServiceStatus();
        
        // 检查 RAG 状态
        await this.checkRAGStatus();
    },

    /**
     * 检查服务状态
     */
    async checkServiceStatus() {
        const statusElement = document.getElementById('serviceStatus');
        const statusIcon = document.querySelector('.status-icon');

        statusElement.textContent = '检查中...';

        const isHealthy = await API.checkHealth();
        this.updateServiceStatus(isHealthy);
    },

    /**
     * 更新服务状态显示
     * @param {boolean} isRunning - 服务是否运行
     */
    updateServiceStatus(isRunning) {
        const statusElement = document.getElementById('serviceStatus');
        const statusIcon = document.querySelector('.status-icon');

        if (isRunning) {
            statusElement.textContent = '运行中';
            statusElement.style.color = 'var(--success-color)';
            statusIcon.style.background = 'var(--primary-subtle)';
            statusIcon.style.color = 'var(--primary-color)';
        } else {
            statusElement.textContent = '未运行';
            statusElement.style.color = 'var(--error-color)';
            statusIcon.style.background = '#fef2f2';
            statusIcon.style.color = '#ef4444';
        }
    },

    /**
     * 检查 RAG 系统状态
     */
    async checkRAGStatus() {
        const ragStatus = document.getElementById('ragStatus');
        const ragDocCount = document.getElementById('ragDocCount');
        const ragIcon = document.querySelector('.rag-icon');
        
        if (!ragStatus) return;
        
        ragStatus.textContent = '检查中...';
        
        try {
            const health = await API.checkRAGHealth();
            
            if (health.success && health.healthy) {
                ragStatus.textContent = '正常';
                ragStatus.style.color = 'var(--success-color)';
                if (ragIcon) {
                    ragIcon.style.background = 'var(--primary-subtle)';
                    ragIcon.style.color = 'var(--primary-color)';
                }
                
                // 获取文档数量
                const stats = await API.getRAGStats();
                if (stats.success && stats.data && stats.data.stats) {
                    const indexStats = stats.data.stats.index || {};
                    const numDocs = indexStats.num_documents || 0;
                    const numChunks = indexStats.num_chunks || 0;
                    if (ragDocCount) {
                        ragDocCount.textContent = `${numDocs} 文档 / ${numChunks} 分块`;
                    }
                }
            } else {
                ragStatus.textContent = '未初始化';
                ragStatus.style.color = 'var(--warning-color)';
                if (ragIcon) {
                    ragIcon.style.background = '#fef3c7';
                    ragIcon.style.color = '#d97706';
                }
                if (ragDocCount) {
                    ragDocCount.textContent = '请先构建索引';
                }
            }
        } catch (error) {
            console.error('[App] 检查 RAG 状态失败:', error);
            ragStatus.textContent = '异常';
            ragStatus.style.color = 'var(--error-color)';
            if (ragDocCount) {
                ragDocCount.textContent = '连接失败';
            }
        }
    },

    /**
     * 开始系统资源监控
     */
    startSystemMonitoring() {
        this.updateSystemResources();
        
        // 保存定时器引用以便后续清理
        if (this._systemMonitorInterval) {
            clearInterval(this._systemMonitorInterval);
        }
        
        // 每5秒更新一次
        this._systemMonitorInterval = setInterval(() => {
            if (this.state.currentTab === 'dashboard') {
                this.updateSystemResources();
            }
        }, 5000);
    },

    /**
     * 更新系统资源显示
     */
    updateSystemResources() {
        // 模拟CPU使用率（实际应用中需要从系统获取）
        const cpuUsage = Math.floor(Math.random() * 30) + 10;
        const cpuBar = document.getElementById('cpuBar');
        const cpuElement = document.getElementById('cpuUsage');

        if (cpuElement) {
            cpuElement.textContent = cpuUsage + '%';
        }
        if (cpuBar) {
            cpuBar.style.width = cpuUsage + '%';
        }

        // 获取内存使用情况
        if (navigator.memory) {
            const memoryInfo = navigator.memory;
            const usedMemory = memoryInfo.usedJSHeapSize;
            const totalMemory = memoryInfo.jsHeapSizeLimit;
            const memoryUsage = Math.round((usedMemory / totalMemory) * 100);
            
            const memoryElement = document.getElementById('memoryUsage');
            const memoryBar = document.getElementById('memoryBar');

            if (memoryElement) {
                memoryElement.textContent = API.formatSize(usedMemory);
            }
            if (memoryBar) {
                memoryBar.style.width = memoryUsage + '%';
            }
        }
    },

    /**
     * 处理聊天输入
     */
    handleChatInput() {
        const input = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        const charCount = document.getElementById('charCount');

        const length = input.value.length;
        const hasContent = input.value.trim() || this.state.chatImageBase64;
        sendBtn.disabled = !hasContent || !this.state.selectedModel || this.state.isGenerating;
        
        if (charCount) {
            charCount.textContent = `${length} / 4000`;
        }
    },

    /**
     * 处理聊天键盘事件
     * @param {KeyboardEvent} e
     */
    handleChatKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    },

    /**
     * 处理聊天图片上传
     * @param {File} file - 上传的图片文件
     */
    async handleChatImageUpload(file) {
        if (!file.type.startsWith('image/')) {
            this.showToast('请上传图片文件', 'error');
            return;
        }

        // 检查文件大小，如果大于500KB则压缩
        const maxSize = 500 * 1024; // 500KB
        let finalFile = file;

        if (file.size > maxSize) {
            try {
                finalFile = await this.compressImage(file, maxSize);
                this.showToast(`图片已压缩: ${(file.size / 1024).toFixed(1)}KB → ${(finalFile.size / 1024).toFixed(1)}KB`, 'info');
            } catch (error) {
                console.error('图片压缩失败:', error);
                this.showToast('图片压缩失败，使用原图', 'warning');
            }
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.chatImage = e.target.result;
            this.state.chatImageBase64 = e.target.result.split(',')[1];

            const preview = document.getElementById('chatImagePreview');
            const previewImg = document.getElementById('chatPreviewImg');
            if (preview && previewImg) {
                previewImg.src = e.target.result;
                preview.style.display = 'block';
            }

            this.handleChatInput();
        };
        reader.readAsDataURL(finalFile);
    },

    /**
     * 压缩图片
     * @param {File} file - 原始图片文件
     * @param {number} maxSize - 目标最大文件大小（字节）
     * @returns {Promise<File>} 压缩后的图片文件
     */
    compressImage(file, maxSize) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    // 计算压缩质量
                    let quality = 0.9;
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');

                    // 限制最大尺寸
                    const maxWidth = 1920;
                    const maxHeight = 1920;
                    let width = img.width;
                    let height = img.height;

                    if (width > maxWidth) {
                        height = (maxWidth / width) * height;
                        width = maxWidth;
                    }
                    if (height > maxHeight) {
                        width = (maxHeight / height) * width;
                        height = maxHeight;
                    }

                    canvas.width = width;
                    canvas.height = height;
                    ctx.drawImage(img, 0, 0, width, height);

                    // 逐步降低质量直到文件大小合适
                    const compress = () => {
                        const dataUrl = canvas.toDataURL('image/jpeg', quality);
                        const base64 = dataUrl.split(',')[1];
                        const fileSize = (base64.length * 3) / 4; // 估算

                        if (fileSize > maxSize && quality > 0.3) {
                            quality -= 0.1;
                            compress();
                        } else {
                            // 转换为 Blob
                            fetch(dataUrl)
                                .then(res => res.blob())
                                .then(blob => {
                                    const compressedFile = new File([blob], file.name, {
                                        type: 'image/jpeg',
                                        lastModified: Date.now()
                                    });
                                    resolve(compressedFile);
                                })
                                .catch(reject);
                        }
                    };
                    compress();
                };
                img.onerror = reject;
                img.src = e.target.result;
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    },

    /**
     * 初始化拖拽上传
     */
    initDragUpload() {
        const chatInputContainer = document.querySelector('.chat-input-container');
        if (!chatInputContainer) return;

        // 防止默认行为
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            chatInputContainer.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // 拖拽进入时添加视觉反馈
        chatInputContainer.addEventListener('dragenter', () => {
            chatInputContainer.classList.add('drag-over');
            // 延迟添加脉冲动画，让入场动画先完成
            setTimeout(() => {
                chatInputContainer.classList.add('drag-active');
            }, 400);
        });

        chatInputContainer.addEventListener('dragover', () => {
            chatInputContainer.classList.add('drag-over');
        });

        chatInputContainer.addEventListener('dragleave', (e) => {
            // 只有离开容器时才移除样式
            if (!chatInputContainer.contains(e.relatedTarget)) {
                chatInputContainer.classList.remove('drag-over', 'drag-active');
            }
        });

        // 拖拽放下时处理文件
        chatInputContainer.addEventListener('drop', (e) => {
            chatInputContainer.classList.remove('drag-over', 'drag-active');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const imageFile = Array.from(files).find(f => f.type.startsWith('image/'));
                if (imageFile) {
                    this.handleChatImageUpload(imageFile);
                    this.showToast('图片已添加', 'success');
                } else {
                    this.showToast('请拖拽图片文件', 'error');
                }
            }
        });
    },
    
    /**
     * 清除聊天图片
     */
    clearChatImage() {
        this.state.chatImage = null;
        this.state.chatImageBase64 = null;
        
        const preview = document.getElementById('chatImagePreview');
        const input = document.getElementById('chatImageInput');
        if (preview) preview.style.display = 'none';
        if (input) input.value = '';
        
        this.handleChatInput();
    },

    /**
     * 处理图片生成请求
     * @param {string} message - 用户消息
     */
    // 图片生成功能已被移除
    async handleImageGenerationRequest(message) {
        console.log('图片生成功能已被移除');
        return null;
    },

    /**
     * 下载图片
     */
    downloadImage(url, filename) {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || 'generated-image.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    },

    /**
     * 重新生成图片
     */
    async regenerateImage(prompt) {
        const input = document.getElementById('overlayChatInput') || document.getElementById('chatInput');
        if (input) {
            input.value = `画 ${prompt}`;
            if (document.getElementById('chatOverlay')?.classList.contains('active')) {
                this.sendMessageFromOverlay();
            } else {
                this.sendMessage();
            }
        }
    },

    /**
     * 打开图片预览
     */
    openImagePreview(url) {
        const overlay = document.createElement('div');
        overlay.className = 'image-preview-overlay';
        overlay.innerHTML = `
            <div class="image-preview-container">
                <img src="${url}" alt="预览图片">
                <button class="close-preview-btn" onclick="this.parentElement.parentElement.remove()">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
        document.body.appendChild(overlay);
    },

    initComputerAssistControlMode() {
        let enabled = false;
        try {
            enabled = localStorage.getItem('computerAssistControlEnabled') === 'true';
        } catch {
            enabled = false;
        }
        this.state.computerAssistControlEnabled = enabled;
        this.updateComputerAssistControlToggleUI();
    },

    updateComputerAssistControlToggleUI() {
        const btn = document.getElementById('computerAssistControlToggleBtn');
        if (!btn) return;

        const enabled = !!this.state.computerAssistControlEnabled;
        btn.classList.toggle('active', enabled);
        btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        btn.title = enabled
            ? '可控执行模式已开启：电脑协助会优先生成可执行操作单（仍需逐步确认）'
            : '可控执行模式已关闭：电脑协助仅提供建议';
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="10" rx="2"/>
                <circle cx="${enabled ? '16' : '8'}" cy="16" r="2"/>
                <path d="M8 11V7a4 4 0 0 1 8 0"/>
            </svg>
            ${enabled ? '可控执行: 开' : '可控执行: 关'}
        `;
    },

    toggleComputerAssistControlMode(forceValue = null) {
        const nextValue = typeof forceValue === 'boolean'
            ? forceValue
            : !this.state.computerAssistControlEnabled;
        this.state.computerAssistControlEnabled = nextValue;
        try {
            localStorage.setItem('computerAssistControlEnabled', nextValue ? 'true' : 'false');
        } catch {
            // ignore localStorage errors
        }
        this.updateComputerAssistControlToggleUI();
        this.showToast(
            nextValue
                ? '已开启可控执行模式：之后点“电脑协助”会直接生成可执行操作单'
                : '已关闭可控执行模式：之后点“电脑协助”仅给出建议',
            'info'
        );
    },

    parseComputerAssistRequest(message) {
        const raw = (message || '').trim();
        if (!raw) {
            return { isAssist: false, allowControl: false, instruction: '' };
        }

        const controlPatterns = [
            /^\/assist-control\b[:：]?\s*/i,
            /^\/computer-control\b[:：]?\s*/i,
            /^\/电脑协助执行\b[:：]?\s*/,
            /^\/同意控电脑\b[:：]?\s*/
        ];
        for (const pattern of controlPatterns) {
            if (pattern.test(raw)) {
                return {
                    isAssist: true,
                    allowControl: true,
                    instruction: raw.replace(pattern, '').trim()
                };
            }
        }

        const assistPatterns = [
            /^\/assist(?!-run\b|-control\b)\b[:：]?\s*/i,
            /^\/computer-assist\b[:：]?\s*/i,
            /^\/电脑协助\b[:：]?\s*/
        ];
        for (const pattern of assistPatterns) {
            if (pattern.test(raw)) {
                return {
                    isAssist: true,
                    allowControl: false,
                    instruction: raw.replace(pattern, '').trim()
                };
            }
        }

        // 自然语言控制意图（无命令）
        const controlIntentPatterns = [
            /(帮我|请|麻烦)?(直接|自动|代我|替我)?(操作|控制|点|点击|执行)(一下)?(电脑|界面|窗口|页面|桌面)/,
            /(你来|你帮我|AI帮我).*(操作|点击|控制)/,
            /(可控执行|代操作|自动点一下|帮我完成这个操作)/,
            /(继续帮我操作|下一步你来执行)/
        ];
        if (controlIntentPatterns.some(pattern => pattern.test(raw))) {
            return { isAssist: true, allowControl: true, instruction: raw };
        }

        // 自然语言协助意图（无命令）
        const assistIntentPatterns = [
            /(帮我|请|麻烦).*(看看|分析|判断).*(界面|页面|窗口|截图)/,
            /(怎么|如何).*(操作|点击|处理|设置)/,
            /(下一步).*(怎么|如何|该怎么).*(做|点|操作)/,
            /(协助我|指导我).*(操作|点击|处理)/,
            /(我该怎么点|我该怎么操作|该点哪里)/
        ];
        if (assistIntentPatterns.some(pattern => pattern.test(raw))) {
            return { isAssist: true, allowControl: false, instruction: raw };
        }

        return { isAssist: false, allowControl: false, instruction: raw };
    },

    isComputerAssistIntent(message) {
        return this.parseComputerAssistRequest(message).isAssist;
    },

    isComputerAssistControlIntent(message) {
        return this.parseComputerAssistRequest(message).allowControl;
    },

    normalizeComputerAssistInstruction(message) {
        return this.parseComputerAssistRequest(message).instruction;
    },

    parseComputerAssistRunRequest(message) {
        const raw = (message || '').trim();
        if (!raw) {
            return { isRun: false, stepIndex: null };
        }

        const quickRunMatch = raw.match(/^(执行一步|继续执行|继续|下一步)$/);
        if (quickRunMatch) {
            return { isRun: true, stepIndex: null };
        }

        const match = raw.match(/^\/assist-run\b(?:[:：]?\s*(\d+))?/i)
            || raw.match(/^\/computer-run\b(?:[:：]?\s*(\d+))?/i)
            || raw.match(/^\/电脑执行\b(?:[:：]?\s*(\d+))?/)
            || raw.match(/^执行第?\s*(\d+)\s*步$/);

        if (!match) {
            return { isRun: false, stepIndex: null };
        }

        let stepIndex = null;
        if (match[1]) {
            const oneBased = parseInt(match[1], 10);
            if (Number.isFinite(oneBased) && oneBased > 0) {
                stepIndex = oneBased - 1;
            }
        }

        return { isRun: true, stepIndex };
    },

    formatComputerAssistResult(payload) {
        const data = payload || {};
        const analysis = data.analysis || {};
        const steps = Array.isArray(analysis.step_by_step) ? analysis.step_by_step : [];
        const checks = Array.isArray(analysis.risk_checks) ? analysis.risk_checks : [];
        const operationTicket = Array.isArray(data.operation_ticket) ? data.operation_ticket : [];
        const controlSession = data.control_session || null;
        const modeText = data.mode === 'guided_control_plan'
            ? '可控执行（单步确认）'
            : '仅协助，不自动控制电脑';

        const lines = [];
        lines.push('### 电脑协助（安全模式）');
        lines.push('');
        lines.push(`- 模式：${modeText}`);
        lines.push(`- 文本模型：${data.model || this.state.selectedModel || '未知'}`);
        lines.push(`- 视觉模型：${data.vision_used ? '已启用' : '未启用'}`);
        lines.push(`- 自动控制：${data?.safety?.auto_control_enabled ? '已启用' : '禁用（仅白名单单步执行）'}`);
        lines.push('');

        if (analysis.intent_summary) {
            lines.push(`**任务理解**：${analysis.intent_summary}`);
            lines.push('');
        }

        if (data.vision_summary) {
            lines.push('**视觉观察**：');
            lines.push(data.vision_summary);
            lines.push('');
        }

        if (analysis.refuse_reason) {
            lines.push(`**安全提示**：${analysis.refuse_reason}`);
            lines.push('');
        }

        if (steps.length > 0) {
            lines.push('**建议步骤（你手动执行）**：');
            steps.forEach((step, index) => {
                lines.push(`${index + 1}. ${step}`);
            });
            lines.push('');
        }

        if (checks.length > 0) {
            lines.push('**安全核对清单（额外功能）**：');
            checks.forEach(item => {
                lines.push(`- [ ] ${item}`);
            });
            lines.push('');
        }

        if (operationTicket.length > 0) {
            lines.push('**智能操作单（可执行步骤）**：');
            operationTicket.forEach((step, index) => {
                const action = step.action || 'verify';
                const target = step.target || '未指定目标';
                const coord = Number.isFinite(step.x) && Number.isFinite(step.y)
                    ? ` @(${step.x}, ${step.y})`
                    : '';
                const keys = Array.isArray(step.keys) && step.keys.length
                    ? ` keys=${step.keys.join('+')}`
                    : '';
                const value = step.value ? ` value=${step.value}` : '';
                lines.push(`${index + 1}. [${action}] ${target}${coord}${keys}${value}`);
            });
            lines.push('');
        }

        if (controlSession?.session_id) {
            const nextIndex = Number.isInteger(controlSession.next_index) ? controlSession.next_index : 0;
            const totalSteps = Number.isInteger(controlSession.total_steps)
                ? controlSession.total_steps
                : (operationTicket.length || 0);
            const displayIndex = totalSteps > 0 ? Math.min(nextIndex + 1, totalSteps) : 0;
            lines.push('**控制会话**：');
            lines.push(`- 会话ID：${controlSession.session_id}`);
            lines.push(`- 下一步索引：${displayIndex}/${totalSteps}`);
            lines.push('- 执行方式：点击“执行一步”按钮');
            lines.push(`- 高级方式：\`/assist-run\`（可加序号，如 \`/assist-run 2\`）`);
            lines.push('');
        }

        lines.push('_提示：系统不会执行脚本或命令行，仅在白名单动作内按“单步确认”执行。_');
        return lines.join('\n');
    },

    formatComputerExecutionResult(payload) {
        const data = payload || {};
        const action = data.action || {};
        const result = data.result || {};
        const controlSession = data.control_session || null;
        const lines = [];

        lines.push('### 电脑执行结果（安全单步）');
        lines.push('');
        lines.push(`- 执行状态：${data.executed ? '成功' : '失败'}`);
        lines.push(`- 动作：${action.action || '未知'}`);
        lines.push(`- 目标：${action.target || '未指定'}`);

        if (Number.isFinite(action.x) && Number.isFinite(action.y)) {
            lines.push(`- 坐标：(${action.x}, ${action.y})`);
        }
        if (Array.isArray(action.keys) && action.keys.length > 0) {
            lines.push(`- 快捷键：${action.keys.join('+')}`);
        }
        if (action.value) {
            lines.push(`- 参数：${action.value}`);
        }
        if (result.message) {
            lines.push(`- 回执：${result.message}`);
        }
        lines.push('');

        if (controlSession?.session_id) {
            const nextIndex = Number.isInteger(controlSession.next_index) ? controlSession.next_index : 0;
            const totalSteps = Number.isInteger(controlSession.total_steps) ? controlSession.total_steps : 0;
            const displayIndex = totalSteps > 0 ? Math.min(nextIndex + 1, totalSteps) : 0;
            lines.push(`- 会话进度：${displayIndex}/${totalSteps}`);
            if (nextIndex < totalSteps) {
                lines.push('- 继续执行：点击“执行一步”按钮（或输入 `/assist-run`）');
            } else {
                lines.push('- 操作单已执行完成');
            }
            lines.push('');
        }

        lines.push('_提示：每一步都需要你显式触发和确认。_');
        return lines.join('\n');
    },

    setChatGeneratingState(isGenerating) {
        this.state.isGenerating = !!isGenerating;
        this.handleChatInput();
        this.handleOverlayInput();
    },

    /**
     * 发送消息
     */
    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        const hasImage = this.state.chatImageBase64;
        const runRequest = this.parseComputerAssistRunRequest(message);

        if (this.state.isGenerating || (!message && !hasImage)) {
            return;
        }

        if (runRequest.isRun) {
            input.value = '';
            this.handleChatInput();
            input.style.height = 'auto';
            input.style.height = '24px';
            await this.handleComputerAssistExecution({
                fromOverlay: false,
                rawMessage: message,
                stepIndex: runRequest.stepIndex
            });
            return;
        }

        if (!this.state.selectedModel) {
            return;
        }

        const assistRequest = this.parseComputerAssistRequest(message);
        if (assistRequest.isAssist) {
            input.value = '';
            this.handleChatInput();
            input.style.height = 'auto';
            input.style.height = '24px';
            await this.handleComputerAssistRequest({
                forced: false,
                fromOverlay: false,
                rawMessage: message,
                allowControl: assistRequest.allowControl || this.state.computerAssistControlEnabled
            });
            return;
        }

        // 检测图片生成意图
        if (!hasImage && typeof ImageGenAPI !== 'undefined' && ImageGenAPI.detectGenerateIntent(message)) {
            await this.handleImageGenerationRequest(message);
            return;
        }

        // 确保有当前对话
        if (!this.state.currentConversation) {
            this.startNewChat(this.state.selectedModel);
            if (!this.state.currentConversation) {
                this.showToast('创建对话失败，请重试', 'error');
                return;
            }
        }

        // 清空输入框
        input.value = '';
        this.handleChatInput();
        
        // 重置文本框高度
        input.style.height = 'auto';
        input.style.height = '24px';

        // 根据设置决定是否自动进入全屏
        const settings = Storage.getSettings();
        if (settings.autoEnterFullscreen) {
            this.enterChatOverlay();
        }

        // 构建消息内容
        let finalMessage = message;
        let imageData = this.state.chatImage;
        
        // 如果有图片，先进行视觉分析
        if (hasImage) {
            const visionPrompt = message || '请描述这张图片的内容';
            
            // 添加用户消息（带图片）
            this.appendMessage('user', message || '请分析这张图片', imageData);
            
            // 显示加载状态
            this.showLoadingState();
            
            try {
                // 调用视觉理解API
                const visionResult = await VisionAPI.analyze(this.state.chatImage, visionPrompt);
                
                if (visionResult.error) {
                    throw new Error(visionResult.error);
                }
                
                // 构建包含图片分析的完整消息
                finalMessage = `[用户上传了一张图片，问题是: ${visionPrompt}]\n\n[图片分析结果]: ${visionResult.result}\n\n[用户]: ${message || ''}`;
                
            } catch (error) {
                this.showToast(`图片分析失败: ${error.message}`, 'error');
                this.appendMessage('assistant', `抱歉，图片分析失败: ${error.message}`);
                this.hideLoadingState();
                this.clearChatImage();
                return;
            }
            
            // 清除图片
            this.clearChatImage();
        } else {
            // 添加用户消息到UI
            this.appendMessage('user', message);
        }
        
        // 保存到存储
        Storage.addMessage(this.state.currentConversation.id, {
            role: 'user',
            content: finalMessage,
            hasImage: hasImage
        });

        // 验证对话是否存在
        let conversation = Storage.getConversation(this.state.currentConversation?.id);
        if (!conversation) {
            console.warn('对话不存在，重新创建对话');
            const newConversation = Storage.createConversation(this.state.selectedModel);
            this.state.currentConversation = newConversation;
            Storage.setCurrentConversationId(newConversation.id);
            
            Storage.addMessage(newConversation.id, {
                role: 'user',
                content: finalMessage,
                hasImage: hasImage
            });
            
            const chatHistory = document.getElementById('chatHistory');
            const lastMessage = chatHistory?.querySelector('.chat-messages .message:last-child');
            if (lastMessage) {
                lastMessage.dataset.conversationId = newConversation.id;
            }
            
            conversation = newConversation;
        }

        // 显示加载状态（如果没有图片则在这里显示）
        if (!hasImage) {
            this.showLoadingState();
        }

        try {
            const messages = conversation.messages.map(m => ({
                role: m.role,
                content: m.content
            }));

            // 发送请求
            const response = await API.chat({
                model: this.state.selectedModel,
                messages: messages,
                conversationId: this.state.currentConversation.id
            }, (chunk) => {
                this.updateStreamingResponse(chunk);
            });

            // 更新对话标题
            if (this.state.currentConversation.title === '新对话') {
                const title = message.slice(0, 20) + (message.length > 20 ? '...' : '');
                Storage.updateConversation(this.state.currentConversation.id, { title });
                this.loadConversations();
            }

        } catch (error) {
            this.showToast(`生成回复失败: ${error.message}`, 'error');
            this.appendMessage('assistant', `抱歉，发生了错误: ${error.message}`);
        } finally {
            this.hideLoadingState();
        }
    },

    async handleComputerAssistRequest(options = {}) {
        const { forced = false, fromOverlay = false, rawMessage = null, allowControl = false } = options;
        const overlay = document.getElementById('chatOverlay');
        const overlayActive = fromOverlay || !!(overlay && overlay.classList.contains('active'));
        const inputEl = overlayActive
            ? document.getElementById('overlayChatInput')
            : document.getElementById('chatInput');

        const inputMessage = typeof rawMessage === 'string'
            ? rawMessage.trim()
            : (inputEl?.value || '').trim();
        const runRequest = this.parseComputerAssistRunRequest(inputMessage);
        if (runRequest.isRun) {
            await this.handleComputerAssistExecution({ stepIndex: runRequest.stepIndex });
            return;
        }
        const parsedRequest = this.parseComputerAssistRequest(inputMessage);
        const controlRequested = !!(allowControl || parsedRequest.allowControl);
        const instruction = forced
            ? (parsedRequest.isAssist ? parsedRequest.instruction : inputMessage)
            : parsedRequest.instruction;
        const hasImage = !!this.state.chatImage;

        if ((!instruction && !hasImage) || !this.state.selectedModel || this.state.isGenerating) {
            if (!instruction && !hasImage) {
                this.showToast('请输入协助目标，或上传截图后再发起电脑协助', 'warning');
            }
            return;
        }

        if (controlRequested) {
            const confirmed = window.confirm(
                '你已请求“可控执行模式”。系统只会生成白名单动作并按单步确认执行，不会运行脚本或命令。是否继续？'
            );
            if (!confirmed) {
                this.showToast('已取消可控执行模式', 'info');
                return;
            }
        }

        if (!this.state.currentConversation) {
            this.startNewChat(this.state.selectedModel);
            if (!this.state.currentConversation) {
                this.showToast('创建对话失败，请重试', 'error');
                return;
            }
        }

        if (inputEl && typeof rawMessage !== 'string') {
            inputEl.value = '';
            if (overlayActive) {
                this.handleOverlayInput();
                inputEl.style.height = 'auto';
                inputEl.style.height = '24px';
            } else {
                this.handleChatInput();
                inputEl.style.height = 'auto';
                inputEl.style.height = '24px';
            }
        }

        const imageData = this.state.chatImage;
        const finalInstruction = instruction || '请基于截图提供下一步安全操作建议';
        const userMessage = controlRequested
            ? `【电脑协助-可控执行】${finalInstruction}`
            : `【电脑协助】${finalInstruction}`;

        this.appendMessage('user', userMessage, imageData);
        Storage.addMessage(this.state.currentConversation.id, {
            role: 'user',
            content: userMessage,
            hasImage: !!imageData
        });

        if (imageData) {
            this.clearChatImage();
        }

        this.setChatGeneratingState(true);
        this.showToast(
            controlRequested
                ? '电脑协助分析中（生成安全操作单）...'
                : '电脑协助分析中（本地双模型，安全模式）...',
            'info'
        );

        try {
            const response = await API.computerAssist({
                instruction: finalInstruction,
                image: imageData,
                model: this.state.selectedModel,
                safeMode: true,
                userConsent: controlRequested,
                consentPhrase: controlRequested ? 'ALLOW_LOCAL_ASSISTED_CONTROL' : ''
            });

            const payload = response.data || {};
            const assistantMessage = this.formatComputerAssistResult(payload);
            this.appendMessage('assistant', assistantMessage);

            if (payload.control_session?.session_id) {
                this.state.computerAssistControlSession = payload.control_session;
                if (Array.isArray(payload.operation_ticket)) {
                    this.state.computerAssistControlSession.operation_ticket = payload.operation_ticket;
                }
                this.showToast('已创建控制会话，点击“执行一步”开始单步执行', 'success');
            } else if (controlRequested) {
                this.state.computerAssistControlSession = null;
            }

            if (Array.isArray(payload.operation_ticket)) {
                this.state.computerAssistOperationTicket = payload.operation_ticket;
            }

            if (this.state.currentConversation?.id && assistantMessage.trim()) {
                Storage.addMessage(this.state.currentConversation.id, {
                    role: 'assistant',
                    content: assistantMessage
                });
            }

            if (this.state.currentConversation?.title === '新对话') {
                const title = finalInstruction.slice(0, 20) + (finalInstruction.length > 20 ? '...' : '');
                Storage.updateConversation(this.state.currentConversation.id, { title });
                this.loadConversations();
            }
        } catch (error) {
            const errorMessage = `电脑协助失败: ${error.message}`;
            this.appendMessage('assistant', errorMessage);
            this.showToast(errorMessage, 'error');
        } finally {
            this.setChatGeneratingState(false);
        }
    },

    async handleComputerAssistExecution(options = {}) {
        const { stepIndex = null } = options;
        if (this.state.isGenerating) {
            return;
        }

        const session = this.state.computerAssistControlSession;
        if (!session?.session_id) {
            const message = '暂无可执行控制会话。请先点“电脑协助”生成智能操作单。';
            this.appendMessage('assistant', message);
            this.showToast(message, 'warning');
            return;
        }

        const ticket = (Array.isArray(session.operation_ticket) && session.operation_ticket.length > 0)
            ? session.operation_ticket
            : (Array.isArray(this.state.computerAssistOperationTicket) ? this.state.computerAssistOperationTicket : []);

        if (!ticket.length) {
            const message = '当前操作单为空，无法执行。请重新生成协助操作单。';
            this.appendMessage('assistant', message);
            this.showToast(message, 'warning');
            return;
        }

        const nextIndex = Number.isInteger(stepIndex)
            ? stepIndex
            : (Number.isInteger(session.next_index) ? session.next_index : 0);

        if (nextIndex < 0 || nextIndex >= ticket.length) {
            const message = `步骤索引超出范围（1-${ticket.length}）。`;
            this.appendMessage('assistant', message);
            this.showToast(message, 'warning');
            return;
        }

        const step = ticket[nextIndex] || {};
        const stepTitle = `[${step.action || 'verify'}] ${step.target || '未指定目标'}`;
        const confirmed = window.confirm(
            `即将执行第 ${nextIndex + 1} 步：${stepTitle}\n\n系统只会执行白名单动作，是否继续？`
        );
        if (!confirmed) {
            this.showToast('已取消执行', 'info');
            return;
        }

        if (!this.state.currentConversation) {
            if (!this.state.selectedModel) {
                this.showToast('请先选择模型并生成控制会话', 'warning');
                return;
            }
            this.startNewChat(this.state.selectedModel);
            if (!this.state.currentConversation) {
                this.showToast('创建对话失败，请重试', 'error');
                return;
            }
        }

        const userMessage = `【电脑执行】第 ${nextIndex + 1} 步：${stepTitle}`;
        this.appendMessage('user', userMessage);
        Storage.addMessage(this.state.currentConversation.id, {
            role: 'user',
            content: userMessage
        });

        this.setChatGeneratingState(true);
        this.showToast(`执行第 ${nextIndex + 1} 步中...`, 'info');

        try {
            const response = await API.executeComputerAssist({
                sessionId: session.session_id,
                stepIndex: nextIndex,
                consentPhrase: 'ALLOW_LOCAL_ASSISTED_CONTROL'
            });

            const payload = response.data || {};
            if (payload.control_session?.session_id) {
                const mergedSession = payload.control_session;
                if (!Array.isArray(mergedSession.operation_ticket) || mergedSession.operation_ticket.length === 0) {
                    mergedSession.operation_ticket = ticket;
                }
                this.state.computerAssistControlSession = mergedSession;
                this.state.computerAssistOperationTicket = mergedSession.operation_ticket;
            }

            const assistantMessage = this.formatComputerExecutionResult(payload);
            this.appendMessage('assistant', assistantMessage);
            if (assistantMessage.trim()) {
                Storage.addMessage(this.state.currentConversation.id, {
                    role: 'assistant',
                    content: assistantMessage
                });
            }
        } catch (error) {
            const errorMessage = `电脑执行失败: ${error.message}`;
            this.appendMessage('assistant', errorMessage);
            this.showToast(errorMessage, 'error');
        } finally {
            this.setChatGeneratingState(false);
        }
    },

    /**
     * 初始化智能对话全屏覆盖层 v2.0
     * 特性：ESC退出、背景切换、快捷键提示
     */
    initChatOverlay() {
        const overlay = document.getElementById('chatOverlay');
        const exitBtn = document.getElementById('exitChatOverlayBtn');
        const overlayInput = document.getElementById('overlayChatInput');
        const overlaySendBtn = document.getElementById('overlaySendBtn');
        const overlayClearBtn = document.getElementById('overlayClearChatBtn');

        if (!overlay || this._chatOverlayInitialized) return;

        // ESC键退出全屏 - 保存引用以便清理，防止内存泄漏
        const self = this;
        this._chatOverlayEscHandler = function(e) {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                self.exitChatOverlay();
            }
        };
        document.addEventListener('keydown', this._chatOverlayEscHandler);

        // 点击背景区域退出（全屏模式下）- 保存引用
        this._chatOverlayClickHandler = function(e) {
            if (e.target === overlay) {
                self.exitChatOverlay();
            }
        };
        overlay.addEventListener('click', this._chatOverlayClickHandler);

        // 退出全屏按钮
        if (exitBtn) {
            exitBtn.addEventListener('click', () => this.exitChatOverlay());
        }

        // 覆盖层输入框事件
        if (overlayInput) {
            overlayInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessageFromOverlay();
                }
            });

            overlayInput.addEventListener('input', () => {
                this.handleOverlayInput();
            });
        }

        // 覆盖层发送按钮
        if (overlaySendBtn) {
            overlaySendBtn.addEventListener('click', () => this.sendMessageFromOverlay());
        }

        // 覆盖层清空按钮
        if (overlayClearBtn) {
            overlayClearBtn.addEventListener('click', () => {
                const history = document.getElementById('chatOverlayHistory');
                if (history) {
                    const messages = history.querySelector('.chat-messages') || history;
                    messages.innerHTML = '';
                }
                this.showToast('对话已清空', 'success');
            });
        }

        // 快捷键提示 - 3秒后自动隐藏
        const shortcutHint = document.getElementById('shortcutHint');
        if (shortcutHint) {
            setTimeout(() => {
                shortcutHint.classList.add('visible');
                setTimeout(() => {
                    shortcutHint.classList.remove('visible');
                }, 3000);
            }, 1000);
        }

        this._chatOverlayInitialized = true;
    },

    /**
     * 进入全屏聊天模式 v2.0
     * 特性：平滑动画、快捷键提示
     */
    enterChatOverlay() {
        const overlay = document.getElementById('chatOverlay');
        const history = document.getElementById('chatOverlayHistory');
        const originalHistory = document.getElementById('chatHistory');
        const modelBadge = document.getElementById('overlayModelBadge');
        const shortcutHint = document.getElementById('shortcutHint');

        if (!overlay || !originalHistory) return;

        // 同步聊天记录
        if (history && originalHistory) {
            history.innerHTML = originalHistory.innerHTML;
            // 添加时间戳到现有消息
            this.addTimestampsToMessages(history);
        }

        // 同步模型名称
        if (modelBadge && this.state.selectedModel) {
            modelBadge.textContent = this.state.selectedModel;
        }

        // 显示覆盖层
        overlay.classList.add('active');

        // 聚焦输入框
        const overlayInput = document.getElementById('overlayChatInput');
        if (overlayInput) {
            overlayInput.focus();
        }

        // 滚动到底部
        if (history) {
            history.scrollTop = history.scrollHeight;
        }

        // 显示快捷键提示
        if (shortcutHint) {
            shortcutHint.classList.add('visible');
            setTimeout(() => {
                shortcutHint.classList.remove('visible');
            }, 4000);
        }

        // 禁用页面滚动（使用状态管理器避免冲突）
        ScrollStateManager.acquire();
    },

    /**
     * 为消息添加时间戳
     */
    addTimestampsToMessages(container) {
        if (!container) return;

        const messages = container.querySelectorAll('.message');
        messages.forEach(msg => {
            if (!msg.querySelector('.message-meta')) {
                const time = new Date().toLocaleTimeString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
                const metaDiv = document.createElement('div');
                metaDiv.className = 'message-meta';
                metaDiv.innerHTML = `
                    <span class="message-time">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                        ${time}
                    </span>
                `;
                msg.appendChild(metaDiv);
            }
        });
    },

    /**
     * 优化的消息同步方法
     * 使用DocumentFragment减少DOM重绘，保留必要的事件监听器
     */
    syncMessages(sourceId, targetId, options = {}) {
        const { targetUseMessagesContainer = false } = options;
        const source = document.getElementById(sourceId);
        const target = document.getElementById(targetId);

        if (!source || !target) return false;

        const sourceContainer = source.querySelector('.chat-messages') || source;
        const nodes = sourceContainer.querySelectorAll('.date-separator, .message');

        // 使用DocumentFragment批量操作，减少DOM重绘
        const fragment = document.createDocumentFragment();

        nodes.forEach(node => {
            const clonedNode = node.cloneNode(true);

            // 重新绑定dataset属性（如果存在）
            if (node.dataset?.content) {
                clonedNode.dataset.content = node.dataset.content;
            }

            // 清除可能导致样式冲突的内联样式（全屏模式下的右对齐等）
            if (clonedNode.style) {
                clonedNode.style.marginLeft = '';
                clonedNode.style.marginRight = '';
                clonedNode.style.alignSelf = '';
            }

            fragment.appendChild(clonedNode);
        });

        let targetContainer = target;
        if (targetUseMessagesContainer) {
            targetContainer = target.querySelector('.chat-messages');
            if (!targetContainer) {
                target.innerHTML = '<div class="chat-messages" data-last-date="" data-start-index=""></div>';
                targetContainer = target.querySelector('.chat-messages');
            }
        }

        targetContainer.innerHTML = '';
        targetContainer.appendChild(fragment);

        return true;
    },

    /**
     * 退出全屏聊天模式 v2.0
     * 特性：平滑动画、基于动画事件的精确同步
     */
    exitChatOverlay() {
        const overlay = document.getElementById('chatOverlay');

        if (!overlay) return;

        // 防止重复触发退出动画
        if (overlay.dataset.exiting === 'true') {
            return;
        }
        overlay.dataset.exiting = 'true';

        // 退出动画
        overlay.style.animation = 'overlayExit 0.3s ease forwards';

        // 清理 ESC 和点击背景的事件监听器，防止内存泄漏
        if (this._chatOverlayEscHandler) {
            document.removeEventListener('keydown', this._chatOverlayEscHandler);
        }
        if (this._chatOverlayClickHandler) {
            overlay.removeEventListener('click', this._chatOverlayClickHandler);
        }

        // 基于动画事件的精确同步
        const handleAnimationEnd = () => {
            // 隐藏覆盖层（先隐藏，提升响应速度）
            overlay.classList.remove('active');
            overlay.style.animation = '';

            // 恢复页面滚动（强制重置确保可滚动）
            ScrollStateManager.reset();

            // 清理事件监听器
            overlay.removeEventListener('animationend', handleAnimationEnd);
            delete overlay.dataset.exiting;

            // 延迟同步聊天记录（后台执行，不阻塞UI）
            this.flushPendingStreamingUpdates();
            const syncTask = () => {
                this.syncMessages('chatOverlayHistory', 'chatHistory', {
                    targetUseMessagesContainer: true
                });
            };
            if (typeof window.requestIdleCallback === 'function') {
                window.requestIdleCallback(syncTask, { timeout: 1000 });
            } else {
                setTimeout(syncTask, 0);
            }
        };

        // 监听动画结束事件
        overlay.addEventListener('animationend', handleAnimationEnd);

        // 备用机制：动画结束后强制清理
        setTimeout(() => {
            if (overlay.dataset.exiting === 'true') {
                handleAnimationEnd();
            }
        }, 350);
    },

    /**
     * 从覆盖层发送消息
     */
    async sendMessageFromOverlay() {
        const overlayInput = document.getElementById('overlayChatInput');
        const message = overlayInput?.value.trim();
        const runRequest = this.parseComputerAssistRunRequest(message);

        if (!message || this.state.isGenerating) {
            return;
        }

        if (runRequest.isRun) {
            overlayInput.value = '';
            this.handleOverlayInput();
            overlayInput.style.height = 'auto';
            overlayInput.style.height = '24px';
            await this.handleComputerAssistExecution({
                fromOverlay: true,
                rawMessage: message,
                stepIndex: runRequest.stepIndex
            });
            return;
        }

        if (!this.state.selectedModel) {
            return;
        }

        const assistRequest = this.parseComputerAssistRequest(message);
        if (assistRequest.isAssist) {
            overlayInput.value = '';
            this.handleOverlayInput();
            overlayInput.style.height = 'auto';
            overlayInput.style.height = '24px';
            await this.handleComputerAssistRequest({
                forced: false,
                fromOverlay: true,
                rawMessage: message,
                allowControl: assistRequest.allowControl || this.state.computerAssistControlEnabled
            });
            return;
        }

        // 确保有当前对话
        if (!this.state.currentConversation) {
            this.startNewChat(this.state.selectedModel);
            if (!this.state.currentConversation) {
                this.showToast('创建对话失败，请重试', 'error');
                return;
            }
        }

        // 清空输入框
        overlayInput.value = '';
        this.handleOverlayInput();

        // 调整输入框高度
        overlayInput.style.height = 'auto';
        overlayInput.style.height = '24px';

        // 添加用户消息（主界面与全屏会自动同步）
        this.appendMessage('user', message);

        // 保存到存储
        Storage.addMessage(this.state.currentConversation.id, {
            role: 'user',
            content: message
        });

        // 隐藏欢迎消息（如果在原界面）
        const welcomeMessage = document.querySelector('#chatHistory .welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        // 调用API生成回复
        await this.generateOverlayResponse();
    },

    /**
     * 生成覆盖层AI回复
     */
    async generateOverlayResponse() {
        if (!this.state.currentConversation) {
            this.showToast('对话不存在', 'error');
            return;
        }

        this.setChatGeneratingState(true);

        try {
            const conversation = Storage.getConversation(this.state.currentConversation.id);
            if (!conversation) {
                throw new Error('对话不存在');
            }

            let messages = conversation.messages.map(m => ({
                role: m.role,
                content: m.content
            }));

            // 如果有世界观设定，添加到系统消息
            if (conversation.worldview && conversation.worldview.trim()) {
                const systemMsg = {
                    role: 'system',
                    content: conversation.worldview.trim()
                };
                messages = [systemMsg, ...messages];
            }

            // 发送请求
            await API.chat({
                model: this.state.selectedModel,
                messages: messages,
                conversationId: this.state.currentConversation.id
            }, (chunk) => {
                this.updateStreamingResponse(chunk);
            });

            // 更新对话标题
            if (this.state.currentConversation.title === '新对话' && conversation.messages.length > 0) {
                const firstUserMessage = conversation.messages.find(m => m.role === 'user');
                if (firstUserMessage) {
                    const title = firstUserMessage.content.slice(0, 20) + (firstUserMessage.content.length > 20 ? '...' : '');
                    Storage.updateConversation(this.state.currentConversation.id, { title });
                    this.loadConversations();
                }
            }

        } catch (error) {
            this.showToast(`生成回复失败: ${error.message}`, 'error');
            this.appendMessage('assistant', `抱歉，发生了错误: ${error.message}`);
        } finally {
            this.setChatGeneratingState(false);
        }
    },

    /**
     * 处理覆盖层输入框输入事件
     */
    handleOverlayInput() {
        const overlayInput = document.getElementById('overlayChatInput');
        const overlaySendBtn = document.getElementById('overlaySendBtn');

        if (overlayInput && overlaySendBtn) {
            overlaySendBtn.disabled = !overlayInput.value.trim() || this.state.isGenerating;
        }
    },

    /**
     * 添加消息到覆盖层
     * @param {string} role - 角色: user 或 assistant
     * @param {string} content - 消息内容
     */
    appendMessageToOverlay(role, content) {
        const messagesContainer = document.querySelector('#chatOverlayHistory .chat-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        messageDiv.dataset.role = role;
        messageDiv.dataset.content = content;

        const avatar = role === 'user' 
            ? '<div class="user-avatar">我</div>'
            : `<div class="ai-avatar">${this.state.selectedModel?.charAt(0).toUpperCase() || 'A'}</div>`;

        const isLoading = role === 'assistant' && !content;
        
        messageDiv.innerHTML = `
            ${avatar}
            <div class="message-content">
                <div class="message-bubble ${role === 'user' ? 'user-bubble' : 'ai-bubble'} ${isLoading ? 'loading-bubble' : ''}">
                    ${role === 'user' ? this.escapeHtml(content) : (isLoading ? `
                        <div class="stream-loading">
                            <div class="stream-line"></div>
                            <span class="stream-text">AI 正在思考</span>
                        </div>
                    ` : '<div class="typing-indicator"><span></span><span></span><span></span></div>')}
                </div>
                <div class="message-actions">
                    <button class="message-action-btn" title="复制" onclick="App.copyMessage(this)">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2"/>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                    </button>
                    ${role === 'assistant' ? `<button class="message-action-btn" title="重新生成" onclick="App.regenerateMessage(this)">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M23 4v6h-6M1 20v-6h6"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    </button>` : ''}
                    ${role === 'user' ? `<button class="message-action-btn" title="编辑" onclick="App.editMessage(this)">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>` : ''}
                    <button class="message-action-btn" title="删除" onclick="App.deleteMessage(this)">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        
        // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
        messageDiv.addEventListener('animationend', function handler() {
            messageDiv.classList.add('visible');
            messageDiv.removeEventListener('animationend', handler);
        }, { once: true });
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    },

    /**
     * 复制消息内容
     * @param {HTMLElement} btn - 点击的按钮元素
     */
    copyMessage(btn) {
        const messageEl = btn.closest('.message');
        if (!messageEl) return;

        const bubble = messageEl.querySelector('.message-bubble');
        if (!bubble) return;

        const text = bubble.innerText || bubble.textContent;
        if (text) {
            navigator.clipboard.writeText(text).then(() => {
                this.showToast('已复制到剪贴板', 'success');
            }).catch(() => {
                this.showToast('复制失败', 'error');
            });
        }
    },

    /**
     * 删除群组消息
     * @param {HTMLElement} btn - 点击的按钮元素
     */
    deleteGroupMessage(btn) {
        const messageEl = btn.closest('.message');
        if (messageEl) {
            messageEl.remove();
            this.showToast('消息已删除', 'success');
        }
    },

    /**
     * 编辑消息
     * @param {HTMLElement} btn - 编辑按钮元素
     */
    editMessage(btn) {
        const messageDiv = btn.closest('.message');
        const originalContent = messageDiv.dataset.content;
        const input = document.getElementById('chatInput');
        
        // 将内容填入输入框
        input.value = originalContent;
        input.focus();
        
        // 调整输入框高度
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
        
        this.handleChatInput();
        
        // 删除原消息
        const conversationId = this.state.currentConversation?.id;
        if (conversationId) {
            // 找到这条消息在对话中的索引
            const conversation = Storage.getConversation(conversationId);
            if (conversation && conversation.messages) {
                const messages = conversation.messages;
                
                // 找到当前消息在数组中的索引
                const messageIndex = messages.findIndex(m => m.content === originalContent && m.role === 'user');
                
                if (messageIndex !== -1) {
                    // 删除该用户消息及之后的所有消息
                    messages.splice(messageIndex);
                    Storage.saveConversations();
                }
            }
            
            // 从UI中删除该消息及之后的AI回复（无论对话是否在storage中）
            let nextSibling = messageDiv.nextElementSibling;
            while (nextSibling) {
                const toRemove = nextSibling;
                nextSibling = nextSibling.nextElementSibling;
                toRemove.remove();
            }
            messageDiv.remove();
            
            this.showToast('消息已填入输入框，请编辑后发送', 'info');
        }
    },

    /**
     * 重新发送消息 - 填入输入框
     * @param {HTMLElement} btn - 重新发送按钮元素
     */
    resendMessage(btn) {
        const messageDiv = btn.closest('.message');
        const originalContent = messageDiv.dataset.content;
        
        // 填入输入框
        const input = document.getElementById('chatInput');
        input.value = originalContent;
        input.focus();
        
        // 调整输入框高度
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
        
        // 更新发送按钮状态
        this.handleChatInput();
        
        // 删除原消息及之后的AI回复
        const conversationId = this.state.currentConversation?.id;
        if (conversationId) {
            const conversation = Storage.getConversation(conversationId);
            if (conversation && conversation.messages) {
                const messages = conversation.messages;
                
                // 找到当前消息在数组中的索引
                const messageIndex = messages.findIndex(m => m.content === originalContent && m.role === 'user');
                
                if (messageIndex !== -1) {
                    // 删除该用户消息及之后的所有消息
                    messages.splice(messageIndex);
                    Storage.saveConversations();
                }
            }
            
            // 从UI中删除该消息及之后的AI回复（无论对话是否在storage中）
            let nextSibling = messageDiv.nextElementSibling;
            while (nextSibling) {
                const toRemove = nextSibling;
                nextSibling = nextSibling.nextElementSibling;
                toRemove.remove();
            }
            messageDiv.remove();
        }
        
        // 提示用户可以编辑后发送
        this.showToast('消息已填入输入框，请确认后发送', 'info');
    },

    /**
     * 重新生成AI回复
     * @param {HTMLElement} btn - 重新生成按钮元素
     */
    regenerateMessage(btn) {
        const assistantMessageDiv = btn.closest('.message');
        const userMessageDiv = assistantMessageDiv.previousElementSibling;
        
        if (!userMessageDiv || userMessageDiv.classList.contains('message-actions')) {
            userMessageDiv = assistantMessageDiv.previousElementSibling;
        }
        
        if (!userMessageDiv || userMessageDiv.dataset.role !== 'user') {
            this.showToast('找不到对应的用户消息', 'error');
            return;
        }
        
        const userContent = userMessageDiv.dataset.content;
        
        // 标记为重新生成
        const conversationId = this.state.currentConversation?.id;
        if (conversationId) {
            const conversation = Storage.getConversation(conversationId);
            if (conversation && conversation.messages) {
                const messages = conversation.messages;
                const userMsgIndex = messages.findIndex(m => m.content === userContent && m.role === 'user');
                const assistantMsgIndex = messages.findIndex(m => m.role === 'assistant' && m.content !== assistantMessageDiv.dataset.content);
                
                // 删除当前AI回复
                if (assistantMsgIndex !== -1) {
                    messages.splice(assistantMsgIndex, 1);
                }
            }
        }
        
        // 删除当前AI回复的DOM
        assistantMessageDiv.remove();
        
        // 发送用户消息获取新回复
        const input = document.getElementById('chatInput');
        input.value = userContent;
        input.focus();
        
        // 重新发送
        this.sendMessage();
        
        this.showToast('正在重新生成...', 'info');
    },

    /**
     * 添加消息到聊天界面
     * @param {string} role - 消息角色
     * @param {string} content - 消息内容
     */
    appendMessage(role, content, imageData = null) {
        const chatHistory = document.getElementById('chatHistory');
        const overlayMessages = document.querySelector('#chatOverlayHistory .chat-messages');
        const welcomeMessage = chatHistory.querySelector('.welcome-message');
        
        // 移除欢迎消息
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        // 检查是否需要创建消息容器
        let messagesContainer = chatHistory.querySelector('.chat-messages');
        if (!messagesContainer) {
            messagesContainer = document.createElement('div');
            messagesContainer.className = 'chat-messages';
            messagesContainer.dataset.lastDate = '';
            chatHistory.insertBefore(messagesContainer, chatHistory.firstChild);
        }

        // 创建消息HTML
        let avatarHtml;
        if (role === 'assistant') {
            avatarHtml = `
                <div class="tech-avatar">
                    <div class="tech-avatar-stars"></div>
                    <div class="tech-avatar-ring"></div>
                </div>
            `;
        } else {
            avatarHtml = `
                <div class="tech-avatar user-avatar">
                    <div class="tech-avatar-ring"></div>
                </div>
            `;
        }
        
        let actionsHtml = '';
        if (role === 'user') {
            actionsHtml = `
                <div class="message-actions">
                    <button class="message-action-btn" title="编辑后重新发送" onclick="App.editMessage(this)">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="message-action-btn" title="重新发送" onclick="App.resendMessage(this)">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    </button>
                </div>
            `;
        }
        
        // 图片HTML
        let imageHtml = '';
        if (imageData && role === 'user') {
            imageHtml = `<img src="${imageData}" class="chat-message-image" alt="用户上传的图片" onclick="window.open(this.src, '_blank')">`;
        }
        
        const ts = new Date();
        this.ensureDateSeparator(messagesContainer, ts);
        const timeHtml = `
            <div class="message-meta">
                <span class="message-time">${this.formatTime(ts)}</span>
            </div>
        `;
        const messageHtml = `
            <div class="message-avatar">${avatarHtml}</div>
            <div class="message-content">${imageHtml}${this.escapeHtml(content)}</div>
            ${timeHtml}
            ${actionsHtml}
        `;
        
        // 添加到原界面
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role} new`;
        messageDiv.dataset.content = content;
        messageDiv.innerHTML = messageHtml;
        messagesContainer.appendChild(messageDiv);
        
        // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
        messageDiv.addEventListener('animationend', function handler() {
            messageDiv.classList.add('visible');
            messageDiv.removeEventListener('animationend', handler);
        }, { once: true });
        
        this.renderMarkdownAsync(content).then(html => {
            const bubble = messageDiv.querySelector('.message-content');
            if (bubble) {
                bubble.innerHTML = html;
                this.applyCollapseIfNeeded(messageDiv);
            }
        });
        if (this.state.virtualizationEnabled) {
            this.trimMessagesTop(messagesContainer);
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // 同步到全屏覆盖层（如果存在）
        if (overlayMessages) {
            this.ensureDateSeparator(overlayMessages, ts);
            const overlayMessageDiv = document.createElement('div');
            overlayMessageDiv.className = `message ${role}`;
            overlayMessageDiv.dataset.content = content;
            overlayMessageDiv.innerHTML = messageHtml;
            overlayMessages.appendChild(overlayMessageDiv);
            
            // 动画结束后添加 visible 类
            overlayMessageDiv.addEventListener('animationend', function handler() {
                overlayMessageDiv.classList.add('visible');
                overlayMessageDiv.removeEventListener('animationend', handler);
            }, { once: true });
            
            this.renderMarkdownAsync(content).then(html => {
                const bubble = overlayMessageDiv.querySelector('.message-content');
                if (bubble) {
                    bubble.innerHTML = html;
                    this.applyCollapseIfNeeded(overlayMessageDiv);
                }
            });
            overlayMessages.scrollTop = overlayMessages.scrollHeight;
        }
    },

    /**
     * 格式化消息内容
     * @param {string} content - 原始内容
     * @returns {string} 格式化后的HTML
     */
    formatMessageContent(content) {
        if (!content) return '';
        
        // 检查 MarkdownRenderer 是否已加载
        if (typeof MarkdownRenderer !== 'undefined' && MarkdownRenderer.render) {
            try {
                return MarkdownRenderer.render(content);
            } catch (error) {
                console.error('Markdown rendering error:', error);
                return this.escapeHtml(content);
            }
        } else {
            // 如果 MarkdownRenderer 未加载，返回转义的纯文本
            console.warn('MarkdownRenderer not loaded yet');
            return this.escapeHtml(content);
        }
    },

    /**
     * HTML转义（安全处理用户输入）
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 显示加载状态 - 灵动水滴头像
     */
    showLoadingState() {
        this.state.isGenerating = true;
        
        const chatHistory = document.getElementById('chatHistory');
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant loading';
        loadingDiv.id = 'loadingMessage';
        loadingDiv.innerHTML = `
            <div class="loading-left">
                <div class="wave-typing-indicator">
                    <div class="wave-bar">
                        <span></span><span></span><span></span><span></span><span></span>
                    </div>
                </div>
            </div>
            <div class="loading-right">
                <div class="loading-text">AI 正在思考</div>
            </div>
        `;
        
        chatHistory.appendChild(loadingDiv);
        
        // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
        loadingDiv.addEventListener('animationend', function handler() {
            loadingDiv.classList.add('visible');
            loadingDiv.removeEventListener('animationend', handler);
        }, { once: true });
        
        chatHistory.scrollTop = chatHistory.scrollHeight;

        this.handleChatInput();
    },

    /**
     * 隐藏加载状态
     */
    hideLoadingState() {
        this.state.isGenerating = false;
        
        const loadingMessage = document.getElementById('loadingMessage');
        if (loadingMessage) {
            loadingMessage.remove();
        }

        this.handleChatInput();
    },

    /**
     * 清理流式内容
     * 移除空白段落，合并多余换行符
     * @param {string} content - 原始内容
     * @returns {Object} 清理后的内容和是否应该忽略
     */
    cleanStreamingContent(content) {
        if (!content) return { cleaned: '', ignore: true };

        // 只移除开头和结尾的换行符，保留内部空白
        let cleaned = content.replace(/^\n+/, '').replace(/\n+$/, '');

        // 如果清理后为空，完全忽略
        if (!cleaned) return { cleaned: '', ignore: true };

        // 合并多个连续换行符为两个（段落分隔），但最多合并3个以上
        cleaned = cleaned.replace(/\n{4,}/g, '\n\n');
        // 处理每行，保留代码块的缩进
        const lines = cleaned.split('\n');
        const processedLines = lines.map(line => {
            // 如果是代码块内容，保留原始行
            if (line.trim().startsWith('```') || line.trim().endsWith('```')) {
                return line;
            }
            // 普通文本移除行首尾空白，但保留一个空格用于分隔
            return line.trim();
        });

        cleaned = processedLines.join('\n');

        // 如果全部是空白字符，忽略
        if (!cleaned.replace(/\n/g, '').trim()) {
            return { cleaned: '', ignore: true };
        }

        return { cleaned, ignore: false };
    },

    scheduleStreamingFlush() {
        if (this._streamFlushHandle !== null) return;
        this._streamFlushHandle = requestAnimationFrame(() => {
            this._streamFlushHandle = null;
            this.flushPendingStreamingUpdates();
        });
    },

    flushPendingStreamingUpdates() {
        if (this._streamFlushHandle !== null) {
            cancelAnimationFrame(this._streamFlushHandle);
            this._streamFlushHandle = null;
        }

        const updates = this._pendingStreamUpdates || {};
        this._pendingStreamUpdates = {};

        Object.keys(updates).forEach(containerId => {
            const update = updates[containerId];
            if (!update) return;
            const { content = '', done = false, isNewSegment = false } = update;
            if (!content && !done && !isNewSegment) return;
            this.updateMessageElement(containerId, content, done, isNewSegment);
        });
    },

    queueStreamingUpdate(containerId, content, done, isNewSegment) {
        if (!containerId) return;

        if (!this._pendingStreamUpdates[containerId]) {
            this._pendingStreamUpdates[containerId] = {
                content: '',
                done: false,
                isNewSegment: false
            };
        }

        const queue = this._pendingStreamUpdates[containerId];

        // 避免把段落切分和普通追加混在同一批次里
        if (isNewSegment && queue.content) {
            this.flushPendingStreamingUpdates();
            this._pendingStreamUpdates[containerId] = {
                content: '',
                done: false,
                isNewSegment: false
            };
        }

        const currentQueue = this._pendingStreamUpdates[containerId];
        if (content) currentQueue.content += content;
        if (done) currentQueue.done = true;
        if (isNewSegment) currentQueue.isNewSegment = true;

        this.scheduleStreamingFlush();
    },

    /**
     * 更新流式响应
     * @param {Object} data - 流式数据对象
     */
    updateStreamingResponse(data) {
        const { content: rawContent, done, isNewSegment } = data || {};
        
        if (!rawContent && !done) return;

        // 清理内容
        const { cleaned, ignore } = this.cleanStreamingContent(rawContent);
        if (ignore && !done) return;
        
        const content = ignore ? '' : cleaned;
        
        // 判断当前应该更新哪个界面
        const overlay = document.getElementById('chatOverlay');
        const isOverlayActive = overlay && overlay.classList.contains('active');
        const containerId = isOverlayActive ? 'chatOverlayHistory' : 'chatHistory';
        
        this.queueStreamingUpdate(containerId, content, !!done, !!isNewSegment);
    },
    
    /**
     * 更新消息元素（通用函数）
     * @param {string} containerId - 容器ID
     * @param {string} content - 内容
     * @param {boolean} done - 是否完成
     * @param {boolean} isNewSegment - 是否新段落
     */
    updateMessageElement(containerId, content, done, isNewSegment) {
        const chatHistory = document.getElementById(containerId);
        if (!chatHistory) return;
        
        let messagesContainer = chatHistory.querySelector('.chat-messages');
        
        if (!messagesContainer) {
            messagesContainer = document.createElement('div');
            messagesContainer.className = 'chat-messages';
            chatHistory.insertBefore(messagesContainer, chatHistory.firstChild);
        }

        // 移除loadingMessage
        const loadingMessage = document.getElementById('loadingMessage');
        if (loadingMessage) loadingMessage.remove();

        // 检查是否有正在流式完成的消息
        const oldStreamingMsg = messagesContainer.querySelector('.message.assistant[data-streaming="true"]');

        if (done && !content && !oldStreamingMsg) {
            return;
        }
        
        // 如果是新段落，将旧消息标记为已完成
        if (isNewSegment && oldStreamingMsg) {
            oldStreamingMsg.dataset.streaming = 'false';
            oldStreamingMsg.classList.remove('streaming');
            const oldContentDiv = oldStreamingMsg.querySelector('.message-content');
            if (oldContentDiv) oldContentDiv.removeAttribute('data-streaming');
        }

        // 如果是新段落或没有正在流式的消息，创建新消息
        if (isNewSegment || !oldStreamingMsg) {
            const newMessage = document.createElement('div');
            newMessage.className = 'message assistant new';
            newMessage.dataset.streaming = 'true';
            
            // 根据容器选择不同的头像
            const isOverlay = containerId === 'chatOverlayHistory';
            const avatar = isOverlay 
                ? `<div class="ai-avatar">${this.state.selectedModel?.charAt(0).toUpperCase() || 'A'}</div>`
                : `<div class="tech-avatar">
                        <div class="tech-avatar-stars"></div>
                        <div class="tech-avatar-ring"></div>
                    </div>`;
            
            newMessage.innerHTML = `
                <div class="message-avatar">
                    ${avatar}
                </div>
                <div class="message-content" data-streaming="true">${this.escapeHtml(content)}</div>
            `;
            
            messagesContainer.appendChild(newMessage);
            
            // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
            newMessage.addEventListener('animationend', function handler() {
                newMessage.classList.add('visible');
                newMessage.removeEventListener('animationend', handler);
            }, { once: true });
        } else {
            // 流式输出时直接追加纯文本
            const contentDiv = oldStreamingMsg.querySelector('.message-content');
            if (contentDiv) {
                contentDiv.textContent += content;
            }
        }

        // 滚动到底部
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // 完成时隐藏加载状态并渲染最终 Markdown
        if (done) {
            const streamingMsg = messagesContainer.querySelector('.message.assistant[data-streaming="true"]');
            if (streamingMsg) {
                streamingMsg.dataset.streaming = 'false';
                streamingMsg.classList.remove('streaming');
                const contentDiv = streamingMsg.querySelector('.message-content');
                if (contentDiv) {
                    contentDiv.removeAttribute('data-streaming');
                    const finalText = contentDiv.textContent || contentDiv.innerText;
                    contentDiv.innerHTML = this.escapeHtml(finalText);
                    streamingMsg.dataset.content = finalText;
                    this.renderMarkdownAsync(finalText).then(html => {
                        contentDiv.innerHTML = html;
                        this.applyCollapseIfNeeded(streamingMsg);
                    });
                    // 时间戳与日期分组
                    const ts = new Date();
                    this.ensureDateSeparator(messagesContainer, ts);
                    if (!streamingMsg.querySelector('.message-meta')) {
                        const metaDiv = document.createElement('div');
                        metaDiv.className = 'message-meta';
                        metaDiv.innerHTML = `<span class="message-time">${this.formatTime(ts)}</span>`;
                        streamingMsg.appendChild(metaDiv);
                    }
                    
                    // 保存AI回复到存储
                    if (this.state.currentConversation?.id && finalText.trim()) {
                        console.log('保存AI回复到对话:', this.state.currentConversation.id, finalText.slice(0, 50));
                        Storage.addMessage(this.state.currentConversation.id, {
                            role: 'assistant',
                            content: finalText
                        });
                    } else {
                        console.warn('无法保存AI回复:', {
                            conversationId: this.state.currentConversation?.id,
                            hasContent: !!finalText.trim(),
                            content: finalText ? finalText.slice(0, 50) : 'empty'
                        });
                    }
                }
            }
        }
    },

    /**
     * HTML 转义（用于流式输出时安全追加文本）
     * @param {string} text - 原始文本
     * @returns {string} 转义后的 HTML
     */
    escapeHtml(text) {
        if (!text) return '';
        const htmlEscapes = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        };
        return text.replace(/[&<>"']/g, char => htmlEscapes[char]);
    },

    initMarkdownWorker() {
        // 如果已存在，先终止旧的 Worker
        this.terminateMarkdownWorker();
        
        const workerCode = String(function() {
            const esc = function(s) {
                return s.replace(/[&<>"']/g, function(c) {
                    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]);
                });
            };
            const md = function(t) {
                let s = t.replace(/\r\n/g,'\n').replace(/\r/g,'\n');
                s = s.replace(/```([\s\S]*?)```/g, function(m, p1) {
                    return '<pre><code>'+esc(p1)+'</code></pre>';
                });
                s = s.replace(/^######\s?(.*)$/gm, '<h6>$1</h6>');
                s = s.replace(/^#####\s?(.*)$/gm, '<h5>$1</h5>');
                s = s.replace(/^####\s?(.*)$/gm, '<h4>$1</h4>');
                s = s.replace(/^###\s?(.*)$/gm, '<h3>$1</h3>');
                s = s.replace(/^##\s?(.*)$/gm, '<h2>$1</h2>');
                s = s.replace(/^#\s?(.*)$/gm, '<h1>$1</h1>');
                s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                s = s.replace(/\*(.*?)\*/g, '<em>$1</em>');
                s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
                s = s.replace(/\[(.*?)\]\((https?:[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
                s = s.replace(/^(?:- |\* )(.*)$/gm, '<li>$1</li>');
                s = s.replace(/(<li>[^<]+<\/li>\n?)+/g, function(m) {
                    return '<ul>'+m.replace(/\n/g,'')+'</ul>';
                });
                s = s.split(/\n{2,}/).map(function(p) {
                    if (/^\s*<(h\d|ul|pre)/.test(p)) return p;
                    return '<p>' + p.replace(/\n/g,'<br/>') + '</p>';
                }).join('');
                return s;
            };
            onmessage = function(e) {
                const t = e.data;
                try {
                    const html = md(t);
                    postMessage({ ok: true, html: html });
                } catch (err) {
                    postMessage({ ok: false, html: esc(t) });
                }
            };
        });
        const code = workerCode.substring(workerCode.indexOf('{') + 1, workerCode.lastIndexOf('}'));
        const blob = new Blob([code], { type: 'application/javascript' });
        this._mdWorker = new Worker(URL.createObjectURL(blob));
        this._mdCache = new Map();
        this._mdCacheMax = 500;
    },
    
    /**
     * 终止 Markdown Worker，释放资源
     */
    terminateMarkdownWorker() {
        if (this._mdWorker) {
            this._mdWorker.terminate();
            this._mdWorker = null;
        }
        if (this._mdCache) {
            this._mdCache.clear();
            this._mdCache = null;
        }
    },
    mdCacheGet(key) {
        if (!this._mdCache) return null;
        const v = this._mdCache.get(key);
        if (v !== undefined) {
            this._mdCache.delete(key);
            this._mdCache.set(key, v);
            return v;
        }
        return null;
    },
    mdCacheSet(key, val) {
        if (!this._mdCache) return;
        if (this._mdCache.has(key)) this._mdCache.delete(key);
        this._mdCache.set(key, val);
        if (this._mdCache.size > this._mdCacheMax) {
            const firstKey = this._mdCache.keys().next().value;
            this._mdCache.delete(firstKey);
        }
    },
    renderMarkdownAsync(text) {
        const key = text.length + ':' + (text.charCodeAt(0) || 0) + ':' + (text.charCodeAt(text.length-1) || 0);
        const cached = this.mdCacheGet(key);
        if (cached) return Promise.resolve(cached);
        return new Promise((resolve) => {
            if (!this._mdWorker) {
                resolve(this.escapeHtml(text));
                return;
            }
            const handle = (e) => {
                const html = e.data && e.data.html ? e.data.html : this.escapeHtml(text);
                this._mdWorker.removeEventListener('message', handle);
                this.mdCacheSet(key, html);
                resolve(html);
            };
            this._mdWorker.addEventListener('message', handle);
            this._mdWorker.postMessage(text);
        });
    },
    initVirtualization() {
        this.state.virtualizationEnabled = true;
    },
    renderMessagesWindow(conversation, container) {
        const total = conversation.messages.length;
        const start = Math.max(0, total - this.state.virtMaxRendered);
        container.dataset.startIndex = String(start);
        const hasEarlier = start > 0;
        if (hasEarlier) {
            const sentinel = document.createElement('button');
            sentinel.className = 'suggestion-btn';
            sentinel.id = 'loadEarlierBtn';
            sentinel.textContent = '加载更早消息';
            sentinel.addEventListener('click', () => this.loadEarlierChunk(conversation, container));
            container.appendChild(sentinel);
        }
        for (let i = start; i < total; i++) {
            const msg = conversation.messages[i];
            const ts = msg.timestamp ? new Date(msg.timestamp) : new Date();
            this.ensureDateSeparator(container, ts);
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${msg.role}`;
            let avatarHtml;
            if (msg.role === 'assistant') {
                avatarHtml = `
                    <div class="tech-avatar">
                        <div class="tech-avatar-stars"></div>
                        <div class="tech-avatar-ring"></div>
                    </div>
                `;
            } else {
                avatarHtml = `
                    <div class="tech-avatar user-avatar">
                        <div class="tech-avatar-ring"></div>
                    </div>
                `;
            }
            const timeHtml = `
                <div class="message-meta">
                    <span class="message-time">
                        ${this.formatTime(ts)}
                    </span>
                </div>
            `;
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatarHtml}</div>
                <div class="message-content">${this.escapeHtml(msg.content)}</div>
                ${timeHtml}
            `;
            container.appendChild(messageDiv);
            
            // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
            messageDiv.classList.add('visible');
            
            this.renderMarkdownAsync(msg.content).then(html => {
                const bubble = messageDiv.querySelector('.message-content');
                if (bubble) bubble.innerHTML = html;
            });
        }
    },
    loadEarlierChunk(conversation, container) {
        const start = parseInt(container.dataset.startIndex || '0', 10);
        if (start <= 0) return;
        const nextStart = Math.max(0, start - this.state.virtChunkSize);
        container.dataset.startIndex = String(nextStart);
        const beforeSentinel = container.querySelector('#loadEarlierBtn');
        const fragment = document.createDocumentFragment();
        for (let i = nextStart; i < start; i++) {
            const msg = conversation.messages[i];
            const ts = msg.timestamp ? new Date(msg.timestamp) : new Date();
            this.ensureDateSeparator(container, ts);
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${msg.role}`;
            let avatarHtml;
            if (msg.role === 'assistant') {
                avatarHtml = `
                    <div class="tech-avatar">
                        <div class="tech-avatar-stars"></div>
                        <div class="tech-avatar-ring"></div>
                    </div>
                `;
            } else {
                avatarHtml = `
                    <div class="tech-avatar user-avatar">
                        <div class="tech-avatar-ring"></div>
                    </div>
                `;
            }
            const timeHtml = `
                <div class="message-meta">
                    <span class="message-time">
                        ${this.formatTime(ts)}
                    </span>
                </div>
            `;
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatarHtml}</div>
                <div class="message-content">${this.escapeHtml(msg.content)}</div>
                ${timeHtml}
            `;
            messageDiv.classList.add('visible');
            fragment.appendChild(messageDiv);
            this.renderMarkdownAsync(msg.content).then(html => {
                const bubble = messageDiv.querySelector('.message-content');
                if (bubble) bubble.innerHTML = html;
            });
        }
        if (beforeSentinel) {
            container.insertBefore(fragment, beforeSentinel.nextSibling);
        } else {
            container.appendChild(fragment);
        }
        if (nextStart === 0) {
            const btn = container.querySelector('#loadEarlierBtn');
            if (btn) btn.remove();
        }
    },
    trimMessagesTop(container) {
        const msgs = Array.from(container.querySelectorAll('.message'));
        const limit = this.state.virtMaxRendered + this.state.virtOverscan;
        if (msgs.length <= limit) return;
        const removeCount = msgs.length - limit;
        for (let i = 0; i < removeCount; i++) {
            const el = msgs[i];
            if (el && el.parentNode === container) {
                el.remove();
            }
        }
    },
    applyCollapseIfNeeded(messageEl) {
        const bubble = messageEl.querySelector('.message-content');
        if (!bubble) return;
        requestAnimationFrame(() => {
            const contentText = bubble.textContent || '';
            const tooLong = contentText.length > 1200 || bubble.scrollHeight > 600;
            if (tooLong && !bubble.classList.contains('collapsed')) {
                bubble.classList.add('collapsed');
                let toggle = messageEl.querySelector('.collapse-toggle');
                if (!toggle) {
                    toggle = document.createElement('button');
                    toggle.className = 'collapse-toggle';
                    toggle.textContent = '展开更多';
                    toggle.addEventListener('click', () => {
                        const isCollapsed = bubble.classList.contains('collapsed');
                        if (isCollapsed) {
                            bubble.classList.remove('collapsed');
                            toggle.textContent = '收起';
                        } else {
                            bubble.classList.add('collapsed');
                            toggle.textContent = '展开更多';
                        }
                    });
                    messageEl.appendChild(toggle);
                }
            }
        });
    },
    initSearchUI() {
        // 防止重复初始化
        if (this._searchUIInitialized) return;
        this._searchUIInitialized = true;
        
        const actions = document.querySelector('#chat-page .chat-actions');
        if (actions) {
            const btn = document.createElement('button');
            btn.className = 'action-link';
            btn.id = 'searchMsgBtn';
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> 搜索消息';
            btn.addEventListener('click', () => this.openSearchBar());
            actions.appendChild(btn);
        }
    },
    openSearchBar() {
        if (this.state.searchActive) return;
        this.state.searchActive = true;
        const actions = document.querySelector('#chat-page .chat-actions');
        if (!actions) return;
        const bar = document.createElement('div');
        bar.id = 'chatSearchBar';
        bar.style.display = 'flex';
        bar.style.alignItems = 'center';
        bar.style.gap = '8px';
        bar.style.marginTop = '8px';
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = '输入关键词，回车搜索';
        input.style.flex = '1';
        const count = document.createElement('span');
        count.id = 'searchCount';
        const prev = document.createElement('button');
        prev.textContent = '上一条';
        const next = document.createElement('button');
        next.textContent = '下一条';
        const close = document.createElement('button');
        close.textContent = '关闭';
        actions.appendChild(bar);
        bar.appendChild(input);
        bar.appendChild(count);
        bar.appendChild(prev);
        bar.appendChild(next);
        bar.appendChild(close);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.state.searchQuery = input.value.trim();
                this.runSearch();
            }
        });
        prev.addEventListener('click', () => this.navigateSearch(-1));
        next.addEventListener('click', () => this.navigateSearch(1));
        close.addEventListener('click', () => this.closeSearchBar());
    },
    closeSearchBar() {
        this.state.searchActive = false;
        this.state.searchQuery = '';
        this.state.searchMatches = [];
        this.state.searchIndex = -1;
        const bar = document.getElementById('chatSearchBar');
        if (bar) bar.remove();
        this.clearSearchHighlights();
    },
    runSearch() {
        const q = this.state.searchQuery;
        this.clearSearchHighlights();
        this.state.searchMatches = [];
        this.state.searchIndex = -1;
        if (!q) {
            const count = document.getElementById('searchCount');
            if (count) count.textContent = '';
            return;
        }
        const container = document.querySelector('#chatHistory .chat-messages');
        if (!container) return;
        const messages = Array.from(container.querySelectorAll('.message'));
        const lower = q.toLowerCase();
        const hits = [];
        messages.forEach(msg => {
            const bubble = msg.querySelector('.message-content');
            if (!bubble) return;
            this.highlightInElement(bubble, lower, hits, msg);
        });
        this.state.searchMatches = hits;
        const count = document.getElementById('searchCount');
        if (count) count.textContent = `${hits.length} 条结果`;
        if (hits.length > 0) {
            this.state.searchIndex = 0;
            this.scrollToSearchCurrent();
        }
    },
    clearSearchHighlights() {
        document.querySelectorAll('.search-hit').forEach(el => {
            const parent = el.parentNode;
            if (!parent) return;
            const text = document.createTextNode(el.textContent || '');
            parent.replaceChild(text, el);
            parent.normalize();
        });
        document.querySelectorAll('.search-current').forEach(el => {
            el.classList.remove('search-current');
        });
    },
    highlightInElement(bubble, lowerQuery, hits, msgEl) {
        const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT, null);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(node => {
            const text = node.nodeValue || '';
            let ltext = text.toLowerCase();
            let idx = 0;
            while (true) {
                idx = ltext.indexOf(lowerQuery, idx);
                if (idx === -1) break;
                const before = document.createTextNode(text.slice(0, idx));
                const mark = document.createElement('mark');
                mark.className = 'search-hit';
                mark.textContent = text.slice(idx, idx + lowerQuery.length);
                const after = document.createTextNode(text.slice(idx + lowerQuery.length));
                const parent = node.parentNode;
                if (parent) {
                    parent.insertBefore(before, node);
                    parent.insertBefore(mark, node);
                    parent.insertBefore(after, node);
                    parent.removeChild(node);
                }
                hits.push({ el: mark, msg: msgEl });
                idx += lowerQuery.length;
                node = after;
                text = node.nodeValue || '';
                ltext = text.toLowerCase();
            }
        });
    },
    navigateSearch(step) {
        if (!this.state.searchMatches.length) return;
        this.state.searchIndex = (this.state.searchIndex + step + this.state.searchMatches.length) % this.state.searchMatches.length;
        this.scrollToSearchCurrent();
    },
    scrollToSearchCurrent() {
        this.clearCurrentMark();
        const hit = this.state.searchMatches[this.state.searchIndex];
        if (!hit) return;
        const bubble = hit.el.closest('.message-content');
        if (bubble && bubble.classList.contains('collapsed')) {
            bubble.classList.remove('collapsed');
            const toggle = hit.msg.querySelector('.collapse-toggle');
            if (toggle) toggle.textContent = '收起';
        }
        hit.el.classList.add('search-current');
        hit.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    },
    clearCurrentMark() {
        document.querySelectorAll('.search-current').forEach(el => el.classList.remove('search-current'));
    },

    /**
     * 日期分组与时间格式化
     */
    formatTime(dateObj) {
        try {
            return dateObj.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            const h = String(dateObj.getHours()).padStart(2, '0');
            const m = String(dateObj.getMinutes()).padStart(2, '0');
            return `${h}:${m}`;
        }
    },
    formatDateKey(dateObj) {
        const y = dateObj.getFullYear();
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    },
    ensureDateSeparator(container, dateObj) {
        if (!container) return;
        const key = this.formatDateKey(dateObj);
        const last = container.dataset.lastDate || '';
        if (last !== key) {
            const sep = document.createElement('div');
            sep.className = 'date-separator';
            sep.innerHTML = `<span>${key}</span>`;
            container.appendChild(sep);
            container.dataset.lastDate = key;
        }
    },

    /**
     * 开始新对话
     * @param {string} model - 可选，指定模型
     */
    startNewChat(model = '') {
        const selectedModel = model || this.state.selectedModel;
        
        if (!selectedModel) {
            this.showToast('请先选择一个模型', 'warning');
            this.switchPage('models');
            return;
        }

        // 创建新对话
        const conversation = Storage.createConversation(selectedModel);
        this.state.currentConversation = conversation;
        Storage.setCurrentConversationId(conversation.id);

        // 更新模型选择
        const modelSelect = document.getElementById('modelSelect');
        if (modelSelect) {
            modelSelect.value = selectedModel;
        }
        this.state.selectedModel = selectedModel;

        // 清空聊天界面
        this.clearChatUI();

        // 加载对话历史
        this.loadConversations();

        this.switchPage('chat');
        this.showToast('已创建新对话', 'success');
    },

    /**
     * 清空聊天界面
     */
    clearChatUI() {
        const chatHistory = document.getElementById('chatHistory');
        chatHistory.innerHTML = `
            <div class="welcome-message">
                <h3>欢迎使用智能对话</h3>
                <p>选择一个模型开始与本地大模型进行对话</p>
                <div class="suggestions">
                    <p class="suggestions-title">✨ 试试这样问</p>
                    <div class="suggestion-chips">
                        <button class="suggestion-btn" data-prompt="你好，请介绍一下你自己">
                            <span class="suggestion-text">自我介绍</span>
                        </button>
                        <button class="suggestion-btn" data-prompt="帮我写一段Python代码，实现一个简单的计算器">
                            <span class="suggestion-text">Python代码</span>
                        </button>
                        <button class="suggestion-btn" data-prompt="用简单的话解释一下什么是机器学习">
                            <span class="suggestion-text">机器学习</span>
                        </button>
                        <button class="suggestion-btn" data-prompt="帮我写一封工作邮件，主题是请假申请">
                            <span class="suggestion-text">写邮件</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // 重新绑定建议按钮事件 - 点击后填充输入框，等待用户确认发送
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                document.getElementById('chatInput').value = prompt;
                this.handleChatInput();
                this.showToast('已填入输入框，请按 Enter 发送或点击发送按钮', 'info');
            });
        });
    },

    /**
     * 清空当前对话
     */
    clearCurrentChat() {
        if (!confirm('确定要清空当前对话吗？此操作不可恢复。')) {
            return;
        }

        if (this.state.currentConversation) {
            Storage.updateConversation(this.state.currentConversation.id, {
                messages: []
            });
        }

        this.clearChatUI();
        this.showToast('对话已清空', 'success');
    },

    /**
     * 加载对话历史列表
     */
    loadConversations() {
        console.log('[DEBUG] loadConversations called');
        const conversations = Storage.getConversations();
        console.log('[DEBUG] conversations:', conversations);
        const folders = Storage.getFolders();
        const list = document.getElementById('conversationsList');
        console.log('[DEBUG] list element:', list);
        
        if (!list) {
            console.error('[DEBUG] conversationsList element not found!');
            return;
        }
        
        // 渲染文件夹部分
        let foldersHtml = '';
        if (folders.length > 0) {
            const uncategorizedCount = conversations.filter(c => !c.folderId).length;
            
            foldersHtml = `
                <div class="folders-section">
                    <div class="folders-header">
                        <span class="folders-title">文件夹</span>
                        <div class="folders-actions">
                            <button class="folder-action-btn" onclick="App.showFolderModal()" title="新建文件夹">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="12" y1="5" x2="12" y2="19"/>
                                    <line x1="5" y1="12" x2="19" y2="12"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="folders-list">
                        <div class="folder-item ${!this.state.currentFolderId ? 'active' : ''}" 
                             data-folder-id="" onclick="App.filterByFolder(null)">
                            <span class="folder-color" style="background-color: var(--text-muted);"></span>
                            <span class="folder-name">未分类</span>
                            <span class="folder-count">${uncategorizedCount}</span>
                        </div>
                        ${folders.map(folder => {
                            const count = Storage.getFolderConversationCount(folder.id);
                            return `
                                <div class="folder-item ${this.state.currentFolderId === folder.id ? 'active' : ''}" 
                                     data-folder-id="${folder.id}" onclick="App.filterByFolder('${folder.id}')">
                                    <span class="folder-color" style="background-color: ${folder.color};"></span>
                                    <span class="folder-name">${folder.name}</span>
                                    <span class="folder-count">${count}</span>
                                    <div class="folder-dropdown">
                                        <button class="folder-dropdown-btn" onclick="event.stopPropagation(); App.toggleFolderMenu('${folder.id}')">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                                <circle cx="12" cy="12" r="1"/>
                                                <circle cx="12" cy="5" r="1"/>
                                                <circle cx="12" cy="19" r="1"/>
                                            </svg>
                                        </button>
                                        <div class="folder-dropdown-menu" id="folderMenu_${folder.id}">
                                            <div class="folder-dropdown-item" onclick="App.editFolder('${folder.id}')">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                                </svg>
                                                重命名
                                            </div>
                                            <div class="folder-dropdown-item danger" onclick="App.deleteFolder('${folder.id}')">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                    <polyline points="3 6 5 6 21 6"/>
                                                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                                </svg>
                                                删除
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }

        // 根据当前文件夹筛选对话
        const filteredConversations = this.state.currentFolderId 
            ? conversations.filter(c => c.folderId === this.state.currentFolderId)
            : conversations;
        
        console.log('[DEBUG] currentFolderId:', this.state.currentFolderId);
        console.log('[DEBUG] filteredConversations:', filteredConversations);
        console.log('[DEBUG] folders:', folders);

        if (filteredConversations.length === 0) {
            list.innerHTML = foldersHtml + `
                <div class="empty-state" style="padding: 20px;">
                    <p style="color: var(--text-muted); font-size: 14px;">暂无对话历史</p>
                </div>
            `;
            return;
        }

        list.innerHTML = foldersHtml + filteredConversations.map(conv => {
            const date = new Date(conv.updatedAt);
            const dateStr = this.formatDate(date);
            
            console.log('[DEBUG] rendering conversation:', conv.id, conv.title, 'updatedAt:', conv.updatedAt, 'dateStr:', dateStr);
            
            return `
                <div class="conversation-item ${conv.id === this.state.currentConversation?.id ? 'active' : ''}" 
                     data-id="${conv.id}" draggable="true" ondragstart="App.handleDragStart(event, '${conv.id}')">
                    <div class="conversation-item-title">${conv.title || '新对话'}</div>
                    <div class="conversation-item-meta">
                        <span>${dateStr}</span>
                        <span class="conversation-item-delete" onclick="event.stopPropagation(); App.deleteConversation('${conv.id}')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </span>
                    </div>
                </div>
            `;
        }).join('');
        
        console.log('[DEBUG] list.innerHTML set, items count:', list.querySelectorAll('.conversation-item').length);

        // 绑定点击事件
        list.querySelectorAll('.conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                this.loadConversation(item.dataset.id);
            });
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                item.classList.add('drag-over');
            });
            item.addEventListener('dragleave', () => {
                item.classList.remove('drag-over');
            });
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                item.classList.remove('drag-over');
                const conversationId = e.dataTransfer.getData('text/plain');
                this.moveConversationToFolder(conversationId, this.state.currentFolderId);
            });
        });
    },
    
    /**
     * 按文件夹筛选
     * @param {string|null} folderId - 文件夹ID
     */
    filterByFolder(folderId) {
        this.state.currentFolderId = folderId;
        this.loadConversations();
    },
    
    /**
     * 移动对话到文件夹
     * @param {string} conversationId - 对话ID
     * @param {string|null} folderId - 文件夹ID
     */
    moveConversationToFolder(conversationId, folderId) {
        Storage.moveConversationToFolder(conversationId, folderId);
        this.loadConversations();
        this.showToast(folderId ? '已移动到文件夹' : '已移出文件夹', 'success');
    },
    
    /**
     * 处理拖拽开始
     * @param {DragEvent} event - 拖拽事件
     * @param {string} conversationId - 对话ID
     */
    handleDragStart(event, conversationId) {
        event.dataTransfer.setData('text/plain', conversationId);
        event.dataTransfer.effectAllowed = 'move';
    },
    
    /**
     * 切换文件夹菜单
     * @param {string} folderId - 文件夹ID
     */
    toggleFolderMenu(folderId) {
        // 关闭其他菜单
        document.querySelectorAll('.folder-dropdown-menu').forEach(menu => {
            if (menu.id !== `folderMenu_${folderId}`) {
                menu.classList.remove('show');
            }
        });
        
        const menu = document.getElementById(`folderMenu_${folderId}`);
        if (menu) {
            menu.classList.toggle('show');
        }
    },
    
    /**
     * 显示文件夹模态框
     * @param {string|null} folderId - 文件夹ID（编辑模式）
     */
    showFolderModal(folderId = null) {
        const modal = document.getElementById('folderModal');
        const title = document.getElementById('folderModalTitle');
        const nameInput = document.getElementById('folderNameInput');
        const colorOptions = document.querySelectorAll('.folder-color-option');
        
        this.editingFolderId = folderId;
        
        if (folderId) {
            const folder = Storage.getFolders().find(f => f.id === folderId);
            if (folder) {
                title.textContent = '编辑文件夹';
                nameInput.value = folder.name;
                
                colorOptions.forEach(opt => {
                    opt.classList.toggle('selected', opt.dataset.color === folder.color);
                });
                this.selectedFolderColor = folder.color;
            }
        } else {
            title.textContent = '新建文件夹';
            nameInput.value = '新文件夹';
            
            colorOptions.forEach((opt, index) => {
                opt.classList.toggle('selected', index === 0);
            });
            this.selectedFolderColor = '#059669';
        }
        
        modal.classList.add('show');
    },
    
    /**
     * 隐藏文件夹模态框
     */
    hideFolderModal() {
        const modal = document.getElementById('folderModal');
        modal.classList.remove('show');
        this.editingFolderId = null;
    },
    
    /**
     * 保存文件夹
     */
    saveFolder() {
        const nameInput = document.getElementById('folderNameInput');
        const name = nameInput.value.trim();
        
        if (!name) {
            this.showToast('请输入文件夹名称', 'warning');
            return;
        }
        
        if (this.editingFolderId) {
            Storage.updateFolder(this.editingFolderId, {
                name: name,
                color: this.selectedFolderColor
            });
            this.showToast('文件夹已更新', 'success');
        } else {
            Storage.createFolder(name, this.selectedFolderColor);
            this.showToast('文件夹已创建', 'success');
        }
        
        this.hideFolderModal();
        this.loadConversations();
    },
    
    /**
     * 编辑文件夹
     * @param {string} folderId - 文件夹ID
     */
    editFolder(folderId) {
        // 关闭所有菜单
        document.querySelectorAll('.folder-dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
        });
        this.showFolderModal(folderId);
    },
    
    /**
     * 删除文件夹
     * @param {string} folderId - 文件夹ID
     */
    deleteFolder(folderId) {
        // 关闭所有菜单
        document.querySelectorAll('.folder-dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
        });
        
        if (!confirm('确定要删除这个文件夹吗？文件夹中的对话将移至未分类。')) {
            return;
        }
        
        Storage.deleteFolder(folderId);
        this.showToast('文件夹已删除', 'success');
        
        if (this.state.currentFolderId === folderId) {
            this.state.currentFolderId = null;
        }
        
        this.loadConversations();
    },
    
    /**
     * 选择文件夹颜色
     * @param {string} color - 颜色值
     * @param {HTMLElement} element - 点击的元素
     */
    selectFolderColor(color, element) {
        this.selectedFolderColor = color;
        
        document.querySelectorAll('.folder-color-option').forEach(opt => {
            opt.classList.remove('selected');
        });
        element.classList.add('selected');
    },

    /**
     * 加载指定对话
     * @param {string} conversationId - 对话ID
     */
    loadConversation(conversationId) {
        const conversation = Storage.getConversation(conversationId);
        if (!conversation) return;

        this.state.currentConversation = conversation;
        Storage.setCurrentConversationId(conversationId);

        // 更新模型选择
        if (conversation.model) {
            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) {
                modelSelect.value = conversation.model;
            }
            this.state.selectedModel = conversation.model;
        }

        // 清空聊天界面
        const chatHistory = document.getElementById('chatHistory');
        
        if (conversation.messages.length === 0) {
            this.clearChatUI();
        } else {
            chatHistory.innerHTML = '<div class="chat-messages" data-last-date="" data-start-index=""></div>';
            const messagesContainer = chatHistory.querySelector('.chat-messages');
            this.renderMessagesWindow(conversation, messagesContainer);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // 更新列表中的选中状态
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === conversationId);
        });

        // 加载世界观到输入框
        this.loadWorldviewToInput();
    },

    /**
     * 删除对话
     * @param {string} conversationId - 对话ID
     */
    deleteConversation(conversationId) {
        if (!confirm('确定要删除这个对话吗？此操作不可恢复。')) {
            return;
        }

        Storage.deleteConversation(conversationId);
        
        if (this.state.currentConversation?.id === conversationId) {
            this.state.currentConversation = null;
            this.clearChatUI();
        }

        this.loadConversations();
        this.showToast('对话已删除', 'success');
    },

    /**
     * 更新对话使用的模型
     * @param {string} modelName - 模型名称
     */
    updateConversationModel(modelName) {
        if (this.state.currentConversation) {
            Storage.updateConversation(this.state.currentConversation.id, {
                model: modelName
            });
        }
    },

    /**
     * 设置默认对话
     */
    setupDefaultConversation() {
        const currentId = Storage.getCurrentConversationId();
        if (currentId) {
            const conversation = Storage.getConversation(currentId);
            if (conversation) {
                this.state.currentConversation = conversation;
                this.state.selectedModel = conversation.model || '';
                
                // 更新模型选择UI
                if (conversation.model) {
                    const modelSelect = document.getElementById('modelSelect');
                    if (modelSelect) {
                        modelSelect.value = conversation.model;
                    }
                }
                
                // 加载对话
                if (conversation.messages.length > 0) {
                    this.loadConversation(currentId);
                }
            }
        }
        
        // 如果没有选择模型，默认选择 literary-super（超级文学助手）
        if (!this.state.selectedModel) {
            this.state.selectedModel = 'literary-super:latest';
            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) {
                modelSelect.value = 'literary-super:latest';
            }
        }
    },

    /**
     * 自动启动 Ollama 服务
     */
    async autoStartService() {
        try {
            this.showToast('正在检查 Ollama 服务状态...', 'info');
            
            const statusResponse = await fetch(`http://${window.location.hostname || 'localhost'}:5001/api/ollama/status`);
            const statusData = await statusResponse.json();
            
            if (statusData.running) {
                this.showToast('Ollama 服务已经在运行！', 'success');
                this.loadModels();
                return;
            }
            
            this.showToast('正在启动 Ollama 服务...', 'info');
            
            const startResponse = await fetch(`http://${window.location.hostname || 'localhost'}:5001/api/ollama/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!startResponse.ok) {
                console.error('启动服务失败:', startResponse.status, startResponse.statusText);
                this.showManualStartGuide();
                return;
            }
            
            const contentType = startResponse.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.error('启动服务失败: 返回非 JSON 响应');
                this.showManualStartGuide();
                return;
            }
            
            const startData = await startResponse.json();
            
            if (startData.success) {
                if (startData.started === false) {
                    this.showToast('Ollama 服务已经在运行', 'success');
                } else if (startData.waiting) {
                    this.showToast('Ollama 服务正在启动中，请稍候...', 'info');
                    this.loadModels();
                    return;
                } else {
                    this.showToast('Ollama 服务已启动', 'success');
                }
                this.loadModels();
            } else {
                this.showManualStartGuide();
            }
            
        } catch (error) {
            console.error('启动服务失败:', error);
            this.showManualStartGuide();
        }
    },

    /**
     * 显示手动启动指南
     */
    showManualStartGuide() {
        this.showToast('请手动启动 Ollama 服务', 'warning');
        
        const startGuide = `
            <div class="start-guide">
                <h4>启动 Ollama 服务指南：</h4>
                <ol>
                    <li>找到 Ollama 安装目录（默认：C:\\Program Files\\Ollama）</li>
                    <li>双击运行 ollama.exe</li>
                    <li>或在命令提示符中运行：ollama serve</li>
                    <li>等待服务启动完成（约3-5秒）</li>
                    <li>点击 "重新加载" 按钮</li>
                </ol>
            </div>
        `;
        
        const modal = document.createElement('div');
        modal.className = 'modal show';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;
        modal.innerHTML = `
            <div style="
                background: white;
                padding: 30px;
                border-radius: 10px;
                max-width: 500px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            ">
                <h3 style="margin-top: 0;">启动 Ollama 服务</h3>
                ${startGuide}
                <div style="margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="this.closest('.modal').remove();" style="
                        padding: 8px 16px;
                        border: 1px solid #ddd;
                        background: #f5f5f5;
                        border-radius: 5px;
                        cursor: pointer;
                    ">关闭</button>
                    <button onclick="App.loadModels(); this.closest('.modal').remove();" style="
                        padding: 8px 16px;
                        border: 1px solid #7eb5a6;
                        background: #7eb5a6;
                        color: white;
                        border-radius: 5px;
                        cursor: pointer;
                    ">重新加载</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    },

    /**
     * 刷新所有数据
     */
    async refreshAll() {
        this.showToast('正在刷新...', 'info');
        await this.loadModels();
        await this.checkServiceStatus();
        this.showToast('刷新完成', 'success');
    },

    /**
     * 加载设置到UI
     */
    loadSettingsToUI() {
        const settings = Storage.getSettings();

        const mappings = {
            'apiUrl': settings.apiUrl,
            'requestTimeout': settings.requestTimeout,
            'maxTokens': settings.maxTokens,
            'temperature': settings.temperature,
            'contextLength': settings.contextLength,
            'topK': settings.topK,
            'topP': settings.topP,
            'repeatPenalty': settings.repeatPenalty,
            'presencePenalty': settings.presencePenalty,
            'frequencyPenalty': settings.frequencyPenalty,
            'fontSize': settings.fontSize,
            'conversationMode': settings.conversationMode
        };

        for (const [id, value] of Object.entries(mappings)) {
            const element = document.getElementById(id);
            if (element) {
                element.value = value;
            }
        }

        // 更新所有滑块的数值显示
        const valueMappings = {
            'temperatureValue': settings.temperature,
            'topKValue': settings.topK,
            'topPValue': settings.topP,
            'repeatPenaltyValue': settings.repeatPenalty,
            'presencePenaltyValue': settings.presencePenalty,
            'frequencyPenaltyValue': settings.frequencyPenalty,
            'sentenceEndDelayValue': settings.sentenceEndDelay + 'ms',
            'maxWaitCharsValue': settings.maxWaitChars,
            'maxWaitTimeValue': settings.maxWaitTime + 'ms'
        };

        for (const [id, value] of Object.entries(valueMappings)) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        }

        // 更新流式模式选择器状态
        const streamModeBtns = document.querySelectorAll('.stream-mode-btn');
        streamModeBtns.forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.mode === settings.streamMode) {
                btn.classList.add('active');
            }
        });
        const streamModeInput = document.getElementById('streamMode');
        if (streamModeInput) {
            streamModeInput.value = settings.streamMode;
        }

        // 更新字体大小
        document.documentElement.style.setProperty('--font-size-base', settings.fontSize);

        // 更新主题UI状态
        ThemeManager.updateUIState(Storage.getTheme());

        // 初始化角色卡UI
        if (window.AppPersona) {
            AppPersona.init(this);
        } else {
            this.initPersonaUI();
        }

        // 同步 TOKEN 统计开关状态
        if (typeof ApiChat !== 'undefined') {
            const tokenStatsToggle = document.getElementById('tokenStatsEnabled');
            const apiConfig = ApiChat.getConfig();
            if (tokenStatsToggle) {
                tokenStatsToggle.checked = apiConfig.tokenTracking.enabled;
            }
        }

        // 同步自动进入全屏开关状态
        const autoEnterFullscreenToggle = document.getElementById('autoEnterFullscreen');
        if (autoEnterFullscreenToggle && settings.autoEnterFullscreen !== undefined) {
            autoEnterFullscreenToggle.checked = settings.autoEnterFullscreen;
        }

        // 加载模型开关列表
        this.loadModelToggleList();
        
        // 生成API调用信息
        this.renderApiInfo();
    },
    
    // 生成API调用信息显示
    renderApiInfo: function() {
        var container = document.getElementById('modelToggleList');
        if (!container) return;
        
        var localIP = localStorage.getItem('localIP') || '192.168.10.3';
        
        var apiHtml = '<div class="setting-group" style="margin-top:20px;border-top:1px solid var(--border-color);padding-top:20px;">' +
            '<h3>API 调用信息</h3>' +
            '<p class="setting-desc">供外部设备调用本地模型的API地址</p>' +
            '<div style="background:var(--bg-secondary);border-radius:8px;padding:15px;">' +
                '<div style="margin-bottom:12px;">' +
                    '<label style="color:var(--text-secondary);font-size:12px;">对话 API</label>' +
                    '<div style="display:flex;align-items:center;gap:8px;margin-top:4px;">' +
                        '<code style="background:var(--bg-primary);padding:6px 10px;border-radius:4px;font-size:13px;flex:1;">http://' + localIP + ':5001/api/chat</code>' +
                        '<button onclick="navigator.clipboard.writeText(\'http://' + localIP + ':5001/api/chat\')" style="padding:6px 10px;cursor:pointer;">复制</button>' +
                    '</div>' +
                '</div>' +
                '<div style="margin-bottom:12px;">' +
                    '<label style="color:var(--text-secondary);font-size:12px;">本地地址</label>' +
                    '<div style="display:flex;align-items:center;gap:8px;margin-top:4px;">' +
                        '<code style="background:var(--bg-primary);padding:6px 10px;border-radius:4px;font-size:13px;flex:1;">http://' + localIP + ':5001</code>' +
                        '<button onclick="navigator.clipboard.writeText(\'http://' + localIP + ':5001\')" style="padding:6px 10px;cursor:pointer;">复制</button>' +
                    '</div>' +
                '</div>' +
                '<div>' +
                    '<label style="color:var(--text-secondary);font-size:12px;">调用示例 (Python)</label>' +
                    '<pre style="background:var(--bg-primary);padding:10px;border-radius:4px;margin-top:4px;overflow-x:auto;font-size:12px;"><code>import requests\nurl = "http://' + localIP + ':5001/api/chat"\ndata = {"message": "你好", "model": "qwen3:4b"}\nresponse = requests.post(url, json=data)\nprint(response.json())</code></pre>' +
                '</div>' +
            '</div>' +
        '</div>';
        
        container.insertAdjacentHTML('afterend', apiHtml);
    },

    /**
     * 加载模型启用/禁用开关列表
     */
    async loadModelToggleList() {
        const container = document.getElementById('modelToggleList');
        if (!container) return;

        try {
            const models = await API.getModels();
            const disabledModels = Storage.getDisabledModels();

            if (models.length === 0) {
                container.innerHTML = '<p class="no-models">暂无已安装模型</p>';
                return;
            }

            container.innerHTML = models.map(model => {
                const isDisabled = disabledModels.includes(model.name);
                const size = API.formatSize ? API.formatSize(model.size) : this.formatBytes(model.size);
                return `
                    <div class="model-toggle-item ${isDisabled ? 'disabled' : ''}" data-model="${model.name}">
                        <div class="model-toggle-info">
                            <span class="model-toggle-name">${model.name}</span>
                            <span class="model-toggle-size">${size}</span>
                        </div>
                        <label class="model-toggle-switch">
                            <input type="checkbox" ${!isDisabled ? 'checked' : ''} data-model="${model.name}">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                `;
            }).join('');

            // 绑定开关事件
            container.querySelectorAll('.model-toggle-switch input').forEach(toggle => {
                toggle.addEventListener('change', (e) => {
                    const modelName = e.target.dataset.model;
                    if (e.target.checked) {
                        Storage.enableModel(modelName);
                        e.target.closest('.model-toggle-item').classList.remove('disabled');
                        this.showToast(`已启用模型: ${modelName}`, 'success');
                    } else {
                        Storage.disableModel(modelName);
                        e.target.closest('.model-toggle-item').classList.add('disabled');
                        this.showToast(`已禁用模型: ${modelName}`, 'warning');
                    }
                    // 刷新模型列表显示
                    this.loadModels();
                });
            });
        } catch (error) {
            console.error('加载模型开关列表失败:', error);
            container.innerHTML = '<p class="no-models">加载失败</p>';
        }
    },

    /**
     * 格式化字节大小
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * 初始化角色卡UI
     */
    initPersonaUI() {
        this.renderPersonaGrid();
        this.updatePersonaDetail();
        this.bindPersonaEvents();
    },

    /**
     * 渲染角色卡网格
     */
    renderPersonaGrid() {
        const grid = document.getElementById('personaGrid');
        if (!grid) return;

        const personas = Storage.getPersonas();
        const currentPersona = Storage.getCurrentPersona();

        grid.innerHTML = personas.map(persona => `
            <div class="persona-card ${persona.id === currentPersona.id ? 'active' : ''}"
                 data-persona-id="${persona.id}"
                 style="--persona-color: ${persona.color}">
                <div class="persona-card-header">
                    <div class="persona-card-avatar">${persona.avatar}</div>
                    ${persona.isCustom ? '<span class="custom-badge">自定义</span>' : ''}
                </div>
                <div class="persona-card-name">${persona.name}</div>
                <div class="persona-card-desc">${persona.description}</div>
                <button class="persona-edit-btn" title="编辑角色">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
            </div>
        `).join('');
    },

    /**
     * 更新角色详情显示
     */
    updatePersonaDetail() {
        const currentPersona = Storage.getCurrentPersona();

        const avatarEl = document.getElementById('currentPersonaAvatar');
        const nameEl = document.getElementById('currentPersonaName');
        const descEl = document.getElementById('personaDescription');
        const promptEl = document.getElementById('personaSystemPrompt');

        if (avatarEl) avatarEl.textContent = currentPersona.avatar;
        if (nameEl) nameEl.textContent = currentPersona.name;
        if (descEl) descEl.textContent = currentPersona.description;
        if (promptEl) promptEl.value = currentPersona.systemPrompt || '';
    },

    /**
     * 创建角色卡编辑器模态框
     */
    createPersonaEditorModal() {
        const modal = document.createElement('div');
        modal.id = 'personaEditorModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content persona-editor-modal">
                <div class="modal-header">
                    <h3 id="personaEditorTitle">创建新角色</h3>
                    <button class="modal-close" id="closePersonaEditor">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="editingPersonaId">
                    
                    <div class="form-group">
                        <label for="personaNameInput">角色名称 *</label>
                        <input type="text" id="personaNameInput" placeholder="输入角色名称" maxlength="50">
                    </div>
                    
                    <div class="form-group">
                        <label for="personaDescInput">角色描述</label>
                        <textarea id="personaDescInput" placeholder="简短描述这个角色的特点" maxlength="200" rows="2"></textarea>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="personaAvatarInput">头像</label>
                            <div class="avatar-selector">
                                <input type="text" id="personaAvatarInput" placeholder="🤖" maxlength="4" class="avatar-input">
                                <div class="avatar-presets" id="avatarPresets"></div>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label for="personaColorInput">主题颜色</label>
                            <div class="color-picker-wrapper">
                                <input type="color" id="personaColorInput" value="#059669" class="color-input">
                                <div class="color-presets" id="colorPresets"></div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="personaPromptInput">系统提示词 *</label>
                        <div class="prompt-tips">
                            <span class="tip-icon">💡</span>
                            <span>提示：越详细、具体的提示词，角色表现越准确</span>
                        </div>
                        <textarea id="personaPromptInput" placeholder="定义这个AI助手的性格、行为准则、专业领域等。例如：'你是一位资深的产品经理，拥有10年互联网产品经验，擅长用户需求分析和产品规划...'" rows="6" maxlength="5000"></textarea>
                        <div class="char-counter"><span id="promptCharCount">0</span> / 5000</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="personaExampleInput">对话示例（可选）</label>
                        <textarea id="personaExampleInput" placeholder="输入几个对话示例，帮助AI理解期望的回复风格。每行一个示例，格式：用户消息|AI回复" rows="3" maxlength="1000"></textarea>
                    </div>
                    
                    <div class="form-group advanced-toggle">
                        <button class="toggle-btn" id="toggleAdvancedSettings">
                            <span>高级设置</span>
                            <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </button>
                        <div class="advanced-settings" id="advancedSettings" style="display: none;">
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="personaTemperature">回复温度</label>
                                    <input type="range" id="personaTemperature" min="0" max="2" step="0.1" value="0.7">
                                    <span class="range-value" id="temperatureValue">0.7</span>
                                </div>
                                <div class="form-group">
                                    <label for="personaMaxTokens">最大回复长度</label>
                                    <select id="personaMaxTokens">
                                        <option value="512">短 (512 tokens)</option>
                                        <option value="1024" selected>中等 (1024 tokens)</option>
                                        <option value="2048">长 (2048 tokens)</option>
                                        <option value="4096">超长 (4096 tokens)</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="cancelPersonaEdit">取消</button>
                    <button class="btn-danger" id="deletePersonaBtn" style="display: none;">删除</button>
                    <button class="btn-primary" id="savePersonaBtn">保存</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.initPersonaEditorEvents();
    },

    /**
     * 初始化角色卡编辑器事件
     */
    initPersonaEditorEvents() {
        const modal = document.getElementById('personaEditorModal');
        if (!modal) return;

        // 关闭模态框
        document.getElementById('closePersonaEditor')?.addEventListener('click', () => {
            this.closePersonaEditor();
        });

        document.getElementById('cancelPersonaEdit')?.addEventListener('click', () => {
            this.closePersonaEditor();
        });

        // 点击遮罩关闭
        modal?.addEventListener('click', (e) => {
            if (e.target === modal) this.closePersonaEditor();
        });

        // 保存角色卡
        document.getElementById('savePersonaBtn')?.addEventListener('click', () => {
            this.savePersonaFromEditor();
        });

        // 删除角色卡
        document.getElementById('deletePersonaBtn')?.addEventListener('click', () => {
            this.deleteCurrentPersona();
        });

        // 高级设置展开
        document.getElementById('toggleAdvancedSettings')?.addEventListener('click', () => {
            const settings = document.getElementById('advancedSettings');
            const chevron = document.querySelector('#toggleAdvancedSettings .chevron');
            if (settings) {
                const isHidden = settings.style.display === 'none';
                settings.style.display = isHidden ? 'block' : 'none';
                if (chevron) {
                    chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0)';
                }
            }
        });

        // 温度滑块
        document.getElementById('personaTemperature')?.addEventListener('input', (e) => {
            const value = e.target.value;
            const display = document.getElementById('temperatureValue');
            if (display) display.textContent = value;
        });

        // 提示词字符计数
        document.getElementById('personaPromptInput')?.addEventListener('input', (e) => {
            const count = document.getElementById('promptCharCount');
            if (count) count.textContent = e.target.value.length;
        });

        // 初始化头像预设
        this.initAvatarPresets();
        
        // 初始化颜色预设
        this.initColorPresets();
    },

    /**
     * 初始化头像预设
     */
    initAvatarPresets() {
        const presets = [
            '🤖', '👨‍💻', '👩‍💻', '✍️', '📊', '👨‍🏫', '👩‍🏫', '🎨',
            '🎭', '🔬', '🚀', '💡', '🎵', '🏛️', '🧙', '🦸',
            '👩‍🔬', '👨‍🔬', '👩‍⚕️', '👨‍⚕️', '👩‍🌾', '👨‍🌾', '👩‍🍳', '👨‍🍳'
        ];
        const container = document.getElementById('avatarPresets');
        if (!container) return;

        container.innerHTML = presets.map(avatar => `
            <button class="avatar-preset" data-avatar="${avatar}">${avatar}</button>
        `).join('');

        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.avatar-preset');
            if (btn) {
                const input = document.getElementById('personaAvatarInput');
                if (input) input.value = btn.dataset.avatar;
            }
        });
    },

    /**
     * 初始化颜色预设
     */
    initColorPresets() {
        const colors = [
            '#059669', '#3b82f6', '#8b5cf6', '#f59e0b', '#10b981',
            '#ef4444', '#ec4899', '#6366f1', '#14b8a6', '#f97316',
            '#84cc16', '#06b6d4', '#a855f7', '#f43f5e', '#78716c'
        ];
        const container = document.getElementById('colorPresets');
        if (!container) return;

        container.innerHTML = colors.map(color => `
            <button class="color-preset" data-color="${color}" style="background-color: ${color}"></button>
        `).join('');

        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.color-preset');
            if (btn) {
                const input = document.getElementById('personaColorInput');
                if (input) input.value = btn.dataset.color;
            }
        });
    },

    /**
     * 打开角色卡编辑器
     * @param {string|null} personaId - 角色卡ID，null表示新建
     */
    openPersonaEditor(personaId = null) {
        if (!document.getElementById('personaEditorModal')) {
            this.createPersonaEditorModal();
        }

        const modal = document.getElementById('personaEditorModal');
        const title = document.getElementById('personaEditorTitle');
        const deleteBtn = document.getElementById('deletePersonaBtn');
        const idInput = document.getElementById('editingPersonaId');

        if (personaId) {
            const persona = Storage.getPersona(personaId);
            if (!persona) {
                this.showToast('角色卡不存在', 'error');
                return;
            }

            title.textContent = '编辑角色';
            deleteBtn.style.display = 'inline-flex';
            idInput.value = personaId;

            document.getElementById('personaNameInput').value = persona.name;
            document.getElementById('personaDescInput').value = persona.description || '';
            document.getElementById('personaAvatarInput').value = persona.avatar;
            document.getElementById('personaColorInput').value = persona.color;
            document.getElementById('personaPromptInput').value = persona.systemPrompt;
            document.getElementById('promptCharCount').textContent = persona.systemPrompt.length;

            // 高级设置
            if (persona.temperature) {
                document.getElementById('personaTemperature').value = persona.temperature;
                document.getElementById('temperatureValue').textContent = persona.temperature;
            }
            if (persona.maxTokens) {
                document.getElementById('personaMaxTokens').value = persona.maxTokens;
            }
        } else {
            title.textContent = '创建新角色';
            deleteBtn.style.display = 'none';
            idInput.value = '';

            document.getElementById('personaNameInput').value = '';
            document.getElementById('personaDescInput').value = '';
            document.getElementById('personaAvatarInput').value = '🤖';
            document.getElementById('personaColorInput').value = Storage.getRandomColor();
            document.getElementById('personaPromptInput').value = '';
            document.getElementById('promptCharCount').textContent = '0';
            document.getElementById('personaTemperature').value = 0.7;
            document.getElementById('temperatureValue').textContent = '0.7';
            document.getElementById('personaMaxTokens').value = '1024';
        }

        modal.classList.add('active');
    },

    /**
     * 关闭角色卡编辑器
     */
    closePersonaEditor() {
        const modal = document.getElementById('personaEditorModal');
        if (modal) modal.classList.remove('active');
    },

    /**
     * 从编辑器保存角色卡
     */
    savePersonaFromEditor() {
        const id = document.getElementById('editingPersonaId').value;
        const name = document.getElementById('personaNameInput').value.trim();
        const description = document.getElementById('personaDescInput').value.trim();
        const avatar = document.getElementById('personaAvatarInput').value.trim() || '🤖';
        const color = document.getElementById('personaColorInput').value;
        const systemPrompt = document.getElementById('personaPromptInput').value.trim();

        // 验证
        if (!name) {
            this.showToast('请输入角色名称', 'warning');
            return;
        }
        if (!systemPrompt) {
            this.showToast('请输入系统提示词', 'warning');
            return;
        }
        if (name.length > 50) {
            this.showToast('角色名称不能超过50个字符', 'warning');
            return;
        }
        if (systemPrompt.length > 5000) {
            this.showToast('系统提示词不能超过5000个字符', 'warning');
            return;
        }

        // 检查名称是否重复
        const personas = Storage.getPersonas();
        const duplicate = personas.find(p => 
            p.name.toLowerCase() === name.toLowerCase() && p.id !== id
        );
        if (duplicate) {
            this.showToast('角色名称已存在', 'warning');
            return;
        }

        const data = {
            name,
            description,
            avatar,
            color,
            systemPrompt,
            temperature: parseFloat(document.getElementById('personaTemperature').value),
            maxTokens: parseInt(document.getElementById('personaMaxTokens').value)
        };

        if (id) {
            // 更新
            const updated = Storage.updatePersona(id, data);
            if (updated) {
                this.showToast('角色已更新', 'success');
                this.closePersonaEditor();
                this.renderPersonaGrid();
                // 刷新当前角色详情显示
                this.updatePersonaDetail();
            } else {
                this.showToast('更新失败', 'error');
            }
        } else {
            // 新建
            const newPersona = Storage.addPersona(data);
            if (newPersona) {
                this.showToast('角色已创建', 'success');
                this.closePersonaEditor();
                this.renderPersonaGrid();
                // 自动切换到新角色
                Storage.setCurrentPersona(newPersona.id);
                this.renderPersonaGrid();
                this.updatePersonaDetail();
            } else {
                this.showToast('创建失败', 'error');
            }
        }
    },

    /**
     * 删除当前编辑的角色卡
     */
    deleteCurrentPersona() {
        const id = document.getElementById('editingPersonaId').value;
        if (!id) return;

        const persona = Storage.getPersona(id);
        if (!persona) return;

        // 确认删除
        if (!confirm(`确定要删除角色"${persona.name}"吗？此操作不可恢复。`)) {
            return;
        }

        // 不能删除默认角色卡
        if (!persona.isCustom) {
            this.showToast('不能删除默认角色卡', 'warning');
            return;
        }

        const success = Storage.deletePersona(id);
        if (success) {
            this.showToast('角色已删除', 'success');
            this.closePersonaEditor();
            this.renderPersonaGrid();
            this.updatePersonaDetail();
        } else {
            this.showToast('删除失败', 'error');
        }
    },

    /**
     * 打开角色卡导入对话框
     */
    openPersonaImportDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.style.display = 'none';

        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const persona = JSON.parse(event.target.result);
                    if (!persona.name || !persona.systemPrompt) {
                        this.showToast('角色卡格式不正确', 'error');
                        return;
                    }

                    const imported = Storage.importPersona(JSON.stringify(persona));
                    if (imported) {
                        this.showToast(`角色"${imported.name}"导入成功`, 'success');
                        this.renderPersonaGrid();
                    } else {
                        this.showToast('导入失败', 'error');
                    }
                } catch (error) {
                    this.showToast('解析文件失败', 'error');
                }
            };
            reader.readAsText(file);
        });

        document.body.appendChild(input);
        input.click();
        input.remove();
    },

    /**
     * 导出当前角色卡
     */
    exportCurrentPersona() {
        const currentPersona = Storage.getCurrentPersona();
        const json = Storage.exportPersona(currentPersona.id);
        
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentPersona.name}-persona.json`;
        a.click();
        URL.revokeObjectURL(url);

        this.showToast('角色卡已导出', 'success');
    },

    /**
     * 批量导出所有角色卡
     */
    exportAllPersonas() {
        const json = Storage.exportAllPersonas();
        
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `all-personas-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);

        this.showToast('所有角色卡已导出', 'success');
    },

    /**
     * 批量导入角色卡
     */
    openPersonaBatchImport() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.style.display = 'none';

        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const count = Storage.importAllPersonas(event.target.result);
                    if (count > 0) {
                        this.showToast(`成功导入 ${count} 个角色卡`, 'success');
                        this.renderPersonaGrid();
                    } else {
                        this.showToast('导入失败或没有有效角色卡', 'error');
                    }
                } catch (error) {
                    this.showToast('解析文件失败', 'error');
                }
            };
            reader.readAsText(file);
        });

        document.body.appendChild(input);
        input.click();
        input.remove();
    },

    /**
     * 重置所有角色卡
     */
    resetAllPersonas() {
        if (!confirm('确定要重置所有角色卡吗？这将删除所有自定义角色卡，恢复默认设置。')) {
            return;
        }

        Storage.resetPersonas();
        this.renderPersonaGrid();
        this.updatePersonaDetail();
        this.showToast('角色卡已重置为默认', 'success');
    },

    /**
     * 绑定角色卡事件
     */
    bindPersonaEvents() {
        const grid = document.getElementById('personaGrid');
        const promptEl = document.getElementById('personaSystemPrompt');

        // 点击选择角色
        grid?.addEventListener('click', (e) => {
            const card = e.target.closest('.persona-card');
            const editBtn = e.target.closest('.persona-edit-btn');
            
            if (editBtn) {
                e.stopPropagation();
                const personaId = card?.dataset.personaId;
                if (personaId) this.openPersonaEditor(personaId);
                return;
            }

            if (card) {
                const personaId = card.dataset.personaId;
                Storage.setCurrentPersona(personaId);
                this.renderPersonaGrid();
                this.updatePersonaDetail();
                this.showToast(`已切换为: ${Storage.getCurrentPersona().name}`, 'success');
            }
        });

        // 保存系统提示词
        promptEl?.addEventListener('change', () => {
            const currentPersona = Storage.getCurrentPersona();
            const personas = Storage.getPersonas();
            const index = personas.findIndex(p => p.id === currentPersona.id);

            if (index !== -1) {
                personas[index].systemPrompt = promptEl.value;
                Storage.savePersonas(personas);
                this.showToast('系统提示词已保存', 'success');
            }
        });
    },

    /**
     * 导出数据
     */
    exportData() {
        const data = Storage.exportData();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `ollama-hub-backup-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
        this.showToast('数据已导出', 'success');
    },

    /**
     * 导入数据
     */
    importData() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            try {
                const text = await file.text();
                const data = JSON.parse(text);
                
                if (Storage.importData(data)) {
                    this.showToast('数据导入成功', 'success');
                    this.loadSettingsToUI();
                    this.loadConversations();
                } else {
                    this.showToast('数据格式无效', 'error');
                }
            } catch (error) {
                this.showToast('导入失败: ' + error.message, 'error');
            }
        };
        
        input.click();
    },

    /**
     * 清除所有数据
     */
    clearAllData() {
        if (!confirm('确定要清除所有数据吗？这将删除所有对话历史和设置。此操作不可恢复！')) {
            return;
        }

        if (!confirm('再次确认：您确定要继续吗？')) {
            return;
        }

        Storage.clearAllData();
        this.state.currentConversation = null;
        this.clearChatUI();
        this.loadConversations();
        this.loadSettingsToUI();
        this.showToast('所有数据已清除', 'success');
    },

    /**
     * 显示Toast通知
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型 (success/error/warning/info)
     */
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
            warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
            info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;
        
        container.appendChild(toast);
        
        // 关闭按钮
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });
        
        // 自动关闭
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    /**
     * 格式化日期
     * @param {Date} date - 日期对象
     * @returns {string} 格式化后的日期字符串
     */
    formatDate(date) {
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) {
            return '刚刚';
        } else if (diff < 3600000) {
            return Math.floor(diff / 60000) + '分钟前';
        } else if (diff < 86400000) {
            return Math.floor(diff / 3600000) + '小时前';
        } else if (diff < 604800000) {
            return Math.floor(diff / 86400000) + '天前';
        } else {
            return date.toLocaleDateString('zh-CN');
        }
    },

    /**
     * 处理窗口大小变化
     */
    handleResize() {
        // 可以在这里添加响应式处理逻辑
    },

    /**
     * 加载群组列表
     */
    loadGroups() {
        // 如果 AppGroup 模块可用，委托给它处理
        if (window.AppGroup && AppGroup.loadGroups) {
            AppGroup.loadGroups();
            return;
        }
        
        const groups = Storage.getGroups();
        const groupsList = document.getElementById('groupsList');
        
        if (!groupsList) return;
        
        groupsList.innerHTML = groups.map(group => `
            <div class="group-card ${this.state.currentGroup?.id === group.id ? 'active' : ''}" data-group-id="${group.id}">
                <div class="group-card-header">
                    <div class="group-avatar-wrapper">${group.avatar}</div>
                    <div class="group-card-info">
                        <h4 class="group-card-name">${group.name}</h4>
                        <p class="group-card-desc">${group.description || '暂无描述'}</p>
                    </div>
                </div>
                <div class="group-actions">
                    <button class="group-action-btn edit-btn" data-action="edit" data-group-id="${group.id}" title="编辑">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="group-action-btn delete" data-action="delete" data-group-id="${group.id}" title="删除">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');

        groupsList.onclick = (e) => {
            const target = e.target.closest('.group-action-btn');
            if (!target) return;
            
            const action = target.dataset.action;
            const groupId = target.dataset.groupId;
            
            if (action === 'edit') {
                this.showGroupModal('edit', groupId);
            } else if (action === 'delete') {
                this.showDeleteConfirm(groupId);
            }
        };

        groupsList.onmousedown = (e) => {
            const card = e.target.closest('.group-card');
            if (card && !e.target.closest('.group-action-btn')) {
                this.selectGroup(card.dataset.groupId);
            }
        };

        // 绑定隐藏默认群组按钮事件
        const hideBtn = document.getElementById('hideDefaultGroupBtn');
        if (hideBtn) {
            // 移除旧的事件避免重复绑定
            const newHideBtn = hideBtn.cloneNode(true);
            hideBtn.parentNode.replaceChild(newHideBtn, hideBtn);

            newHideBtn.addEventListener('click', () => {
                const currentState = newHideBtn.classList.contains('hidden');
                const newState = !currentState;
                localStorage.setItem('defaultGroupHidden', newState.toString());
                this.updateDefaultGroupVisibility(newState);
            });
        }

        // 应用隐藏状态
        const isHidden = localStorage.getItem('defaultGroupHidden') === 'true';
        this.updateDefaultGroupVisibility(isHidden);
    },

    /**
     * 初始化隐藏默认群组功能
     */
    initHideDefaultGroup() {
        const hideBtn = document.getElementById('hideDefaultGroupBtn');
        if (!hideBtn) return;

        // 从localStorage恢复状态
        const isHidden = localStorage.getItem('defaultGroupHidden') === 'true';
        this.updateDefaultGroupVisibility(isHidden);

        // 绑定点击事件
        hideBtn.addEventListener('click', () => {
            const currentState = hideBtn.classList.contains('hidden');
            const newState = !currentState;
            localStorage.setItem('defaultGroupHidden', newState.toString());
            this.updateDefaultGroupVisibility(newState);
        });
    },

    /**
     * 更新默认群组可见性
     * @param {boolean} hidden - 是否隐藏
     */
    updateDefaultGroupVisibility(hidden) {
        const hideBtn = document.getElementById('hideDefaultGroupBtn');
        const groupChatHeader = document.querySelector('.group-chat-header');

        if (hideBtn) {
            if (hidden) {
                hideBtn.classList.add('hidden');
                hideBtn.dataset.hide = 'true';
                hideBtn.title = '显示默认群组';
            } else {
                hideBtn.classList.remove('hidden');
                hideBtn.dataset.hide = 'false';
                hideBtn.title = '隐藏默认群组';
            }
        }

        // 隐藏/显示整个群组对话头部
        if (groupChatHeader) {
            if (hidden) {
                groupChatHeader.classList.add('header-hidden');
            } else {
                groupChatHeader.classList.remove('header-hidden');
            }
        }
    },

    /**
     * 显示群组模态框
     * @param {string} mode - 'create' | 'edit'
     * @param {string} groupId - 群组ID（编辑模式需要）
     */
    showGroupModal(mode, groupId = null) {
        const modal = document.getElementById('groupModal');
        const title = document.getElementById('groupModalTitle');
        const form = document.getElementById('groupForm');
        const nameInput = document.getElementById('groupNameInput');
        const descInput = document.getElementById('groupDescInput');
        const membersContainer = document.getElementById('groupMembersSelect');

        if (!modal || !title || !form) return;

        const personas = Storage.getPersonas();

        if (mode === 'edit' && groupId) {
            const group = Storage.getGroupDetail(groupId);
            if (group) {
                title.textContent = '编辑群组';
                nameInput.value = group.name;
                descInput.value = group.description || '';
                this.state.editingGroupId = groupId;
            }
        } else {
            title.textContent = '创建群组';
            nameInput.value = '';
            descInput.value = '';
            this.state.editingGroupId = null;
        }

        membersContainer.innerHTML = personas.map((persona, index) => `
            <label class="nature-member-item ${groupId && group?.members?.includes(persona.id) ? 'selected' : ''}" 
                   data-persona-id="${persona.id}"
                   for="member-${persona.id}">
                <input type="checkbox" 
                       id="member-${persona.id}"
                       name="groupMembers" 
                       value="${persona.id}" 
                       ${groupId && group?.members?.includes(persona.id) ? 'checked' : ''}
                       aria-label="选择成员 ${persona.name}">
                <span class="nature-member-avatar">${persona.avatar}</span>
                <span class="nature-member-name">${persona.name}</span>
                <span class="nature-member-check" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                </span>
            </label>
        `).join('');

        membersContainer.querySelectorAll('.nature-member-item').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                option.classList.toggle('selected');
                const checkbox = option.querySelector('input');
                checkbox.checked = !checkbox.checked;
            });
        });

        modal.style.display = 'flex';
    },

    /**
     * 隐藏群组模态框
     */
    hideGroupModal() {
        const modal = document.getElementById('groupModal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.state.editingGroupId = null;
    },

    /**
     * 保存群组
     */
    saveGroup() {
        const nameInput = document.getElementById('groupNameInput');
        const descInput = document.getElementById('groupDescInput');
        const membersContainer = document.getElementById('groupMembersSelect');

        const name = nameInput?.value.trim();
        const description = descInput?.value.trim();
        const selectedMembers = Array.from(membersContainer?.querySelectorAll('input:checked') || [])
            .map(input => input.value);

        if (!name) {
            this.showToast('请输入群组名称', 'warning');
            return;
        }

        const personas = Storage.getPersonas();
        const defaultMembers = personas.slice(0, 3).map(p => p.id);
        const members = selectedMembers.length > 0 ? selectedMembers : defaultMembers;

        if (this.state.editingGroupId) {
            Storage.updateGroup(this.state.editingGroupId, {
                name,
                description,
                members,
                avatar: '👥'
            });
            this.showToast('群组更新成功', 'success');
        } else {
            Storage.createGroup(name, description, members);
            this.showToast('群组创建成功', 'success');
        }

        this.hideGroupModal();
        this.loadGroups();
        this.selectGroup(this.state.editingGroupId || Storage.getGroups()[0]?.id);
    },

    /**
     * 显示删除确认框
     * @param {string} groupId - 群组ID
     */
    showDeleteConfirm(groupId) {
        const group = Storage.getGroupDetail(groupId);
        if (!group) return;

        const modal = document.getElementById('deleteConfirmModal');
        const message = document.getElementById('deleteConfirmMessage');

        if (modal && message) {
            message.textContent = `确定要删除群组 "${group.name}" 吗？删除后无法恢复。`;
            modal.style.display = 'flex';
            this.state.deletingGroupId = groupId;
        }
    },

    /**
     * 确认删除群组
     */
    confirmDeleteGroup() {
        if (this.state.deletingGroupId) {
            Storage.deleteGroup(this.state.deletingGroupId);
            this.showToast('群组已删除', 'success');

            if (this.state.currentGroup?.id === this.state.deletingGroupId) {
                this.state.currentGroup = null;
                const groupsList = document.getElementById('groupChatArea');
                if (groupsList) {
                    groupsList.innerHTML = this.getEmptyStateHTML('暂无群组', '请先创建一个群组来开始群聊');
                }
            }

            this.loadGroups();
            this.hideDeleteConfirm();
        }
    },

    /**
     * 隐藏删除确认框
     */
    hideDeleteConfirm() {
        const modal = document.getElementById('deleteConfirmModal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.state.deletingGroupId = null;
    },

    /**
     * 选择群组
     * @param {string} groupId - 群组ID
     */
    selectGroup(groupId) {
        const group = Storage.getGroupDetail(groupId);
        
        if (!group) {
            this.showToast('群组不存在', 'error');
            return;
        }

        this.state.currentGroup = group;
        
        // 保存上次选择的群组ID
        localStorage.setItem('lastSelectedGroupId', groupId);

        const groupAvatar = document.getElementById('currentGroupAvatar');
        const groupName = document.getElementById('currentGroupName');
        const groupDesc = document.getElementById('currentGroupDesc');
        const groupMembers = document.getElementById('groupMembers');

        if (groupAvatar) groupAvatar.textContent = group.avatar;
        if (groupName) groupName.textContent = group.name;
        if (groupDesc) groupDesc.textContent = group.description || '无描述';

        if (groupMembers) {
            groupMembers.innerHTML = group.memberDetails.map(member => `
                <div class="group-member" style="--persona-color: ${member.color}">
                    <span class="group-member-avatar">${member.avatar}</span>
                    <span class="group-member-name">${member.name}</span>
                </div>
            `).join('');
        }

        this.loadGroups();
        this.loadGroupConversationHistory();
    },

    /**
     * 加载群组对话历史
     */
    loadGroupConversationHistory() {
        const group = this.state.currentGroup;
        if (!group) return;

        const conversations = Storage.getGroupConversations();
        const groupConversations = conversations.filter(c => c.groupId === group.id);

        if (groupConversations.length === 0) {
            this.clearGroupChatUI();
            return;
        }

        const latestConversation = groupConversations.sort((a, b) => 
            new Date(b.updatedAt) - new Date(a.updatedAt)
        )[0];

        this.state.currentGroupConversation = latestConversation;
        this.renderGroupConversationMessages(latestConversation);
    },

    /**
     * 渲染群组对话消息
     * @param {Object} conversation - 对话对象
     */
    renderGroupConversationMessages(conversation) {
        const chatHistory = document.getElementById('groupChatArea');
        if (!chatHistory) return;

        chatHistory.innerHTML = '';

        conversation.messages.forEach(msg => {
            if (msg.role === 'user') {
                this.appendGroupMessage('user', msg.content);
            } else if (msg.role === 'assistant') {
                this.appendGroupAssistantMessage(msg);
            }
        });

        chatHistory.scrollTop = chatHistory.scrollHeight;
    },

    /**
     * 添加智能体消息到界面
     * @param {Object} msg - 消息对象
     */
    appendGroupAssistantMessage(msg) {
        const chatArea = document.getElementById('groupChatArea');

        if (!chatArea) {
            console.warn('[appendGroupAssistantMessage] 群组对话区域不存在，消息未显示');
            return;
        }

        try {
            const messageEl = document.createElement('div');
            messageEl.className = 'group-message assistant';
            messageEl.id = `group-message-${msg.personaId}`;
            messageEl.innerHTML = `
                <div class="group-message-avatar">${msg.personaAvatar}</div>
                <div class="group-message-content">
                    <div class="group-message-name">${msg.personaName}</div>
                    <div class="group-message-text">${this.formatMessageContent(msg.content)}</div>
                </div>
            `;

            chatArea.appendChild(messageEl);
            chatArea.scrollTop = chatArea.scrollHeight;
        } catch (error) {
            console.error('[appendGroupAssistantMessage] 添加消息失败:', error);
        }
    },

    /**
     * 清空群组对话UI
     */
    clearGroupChatUI() {
        const chatHistory = document.getElementById('groupChatArea');
        if (!chatHistory) return;

        chatHistory.innerHTML = `
            <div class="welcome-message">
                <h3>欢迎使用群组对话</h3>
                <p>选择一个群组，让多个智能体一起讨论您的问题</p>

            </div>
        `;
    },

    /**
     * 发送群组消息
     */
    async sendGroupMessage() {
        if (this.state.isGenerating) {
            this.showToast('正在生成回复，请稍候...', 'warning');
            return;
        }

        if (!this.state.currentGroup) {
            this.showToast('请先选择一个群组', 'warning');
            return;
        }

        const input = document.getElementById('groupChatInput');
        const message = input.value.trim();

        if (!message) return;

        // 先显示用户消息到群组对话界面
        this.appendGroupMessage('user', message);
        
        // 滚动到底部
        const chatArea = document.getElementById('groupChatArea');
        if (chatArea) {
            chatArea.scrollTop = chatArea.scrollHeight;
        }

        // 进入群组全屏聊天模式
        this.enterGroupChatOverlay();

        if (typeof GroupChatEnhanced !== 'undefined') {
            input.value = '';
            this.handleGroupChatInput();
            
            // 重置文本框高度
            input.style.height = 'auto';
            input.style.height = '24px';
            this.state.isGenerating = true;
            this.updateGroupSendButtonState();
            this.showGroupPauseButton();

            try {
                await GroupChatEnhanced.sendMessage(message);
            } finally {
                this.state.isGenerating = false;
                this.hideGroupPauseButton();
                this.updateGroupSendButtonState();
            }
        } else {
            this.showToast('群组对话模块未加载', 'error');
        }
    },

    /**
     * 初始化群组对话全屏覆盖层
     */
    initGroupChatOverlay() {
        const overlay = document.getElementById('groupChatOverlay');
        const exitBtn = document.getElementById('exitGroupChatOverlayBtn');
        const overlayInput = document.getElementById('overlayGroupChatInput');
        const overlaySendBtn = document.getElementById('overlayGroupSendBtn');
        const overlayClearBtn = document.getElementById('overlayGroupClearBtn');

        if (!overlay || this._groupChatOverlayInitialized) return;

        const self = this;
        this._groupOverlayEscHandler = function(e) {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                self.exitGroupChatOverlay();
            }
        };
        document.addEventListener('keydown', this._groupOverlayEscHandler);

        this._groupOverlayClickHandler = function(e) {
            if (e.target === overlay) {
                self.exitGroupChatOverlay();
            }
        };
        overlay.addEventListener('click', this._groupOverlayClickHandler);

        // 退出全屏按钮
        if (exitBtn) {
            exitBtn.addEventListener('click', () => this.exitGroupChatOverlay());
        }

        // 覆盖层输入框事件
        if (overlayInput) {
            overlayInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendGroupMessageFromOverlay();
                }
            });

            overlayInput.addEventListener('input', () => {
                this.handleGroupOverlayInput();
            });
        }

        // 覆盖层发送按钮
        if (overlaySendBtn) {
            overlaySendBtn.addEventListener('click', () => this.sendGroupMessageFromOverlay());
        }

        // 覆盖层清空按钮
        if (overlayClearBtn) {
            overlayClearBtn.addEventListener('click', () => {
                const history = document.getElementById('groupChatOverlayHistory');
                if (history) {
                    const messages = history.querySelector('.chat-messages') || history;
                    messages.innerHTML = '';
                }
                this.showToast('对话已清空', 'success');
            });
        }

        this._groupChatOverlayInitialized = true;
    },

    /**
     * 进入群组全屏聊天模式
     */
    enterGroupChatOverlay() {
        const overlay = document.getElementById('groupChatOverlay');
        const overlayMessages = document.querySelector('#groupChatOverlayHistory .chat-messages');
        const originalHistory = document.getElementById('groupChatArea');
        const groupNameBadge = document.getElementById('overlayGroupName');

        if (!overlay || !originalHistory) return;

        // 同步聊天记录
        if (overlayMessages && originalHistory) {
            const originalMessages = originalHistory.querySelector('.chat-messages');
            if (originalMessages) {
                overlayMessages.innerHTML = originalMessages.innerHTML;
            }
        }

        // 同步群组名称
        if (groupNameBadge && this.state.currentGroup) {
            groupNameBadge.textContent = this.state.currentGroup.name;
        }

        // 显示覆盖层
        overlay.classList.add('active');

        // 聚焦输入框
        const overlayInput = document.getElementById('overlayGroupChatInput');
        if (overlayInput) {
            overlayInput.focus();
        }

        // 滚动到底部
        if (overlayMessages) {
            overlayMessages.scrollTop = overlayMessages.scrollHeight;
        }

        // 禁用页面滚动
        ScrollStateManager.acquire();
    },

    /**
     * 退出群组全屏聊天模式
     * 特性：基于动画事件的精确同步
     */
    exitGroupChatOverlay() {
        const overlay = document.getElementById('groupChatOverlay');

        if (!overlay) return;

        // 防止重复触发
        if (overlay.dataset.exiting === 'true') {
            return;
        }
        overlay.dataset.exiting = 'true';

        // 退出动画
        overlay.style.animation = 'overlayExit 0.3s ease forwards';

        // 清理 ESC 和点击背景的事件监听器，防止内存泄漏
        if (this._groupOverlayEscHandler) {
            document.removeEventListener('keydown', this._groupOverlayEscHandler);
        }
        if (this._groupOverlayClickHandler) {
            overlay.removeEventListener('click', this._groupOverlayClickHandler);
        }

        // 基于动画事件的精确同步
        const handleAnimationEnd = () => {
            // 隐藏覆盖层（先隐藏，提升响应速度）
            overlay.classList.remove('active');
            overlay.style.animation = '';

            // 恢复页面滚动（强制重置确保可滚动）
            ScrollStateManager.reset();

            // 清理事件监听器
            overlay.removeEventListener('animationend', handleAnimationEnd);
            delete overlay.dataset.exiting;

            // 延迟同步聊天记录（后台执行，不阻塞UI）
            this.flushPendingStreamingUpdates();
            const syncTask = () => {
                this.syncMessages('groupChatOverlayHistory', 'groupChatArea');
            };
            if (typeof window.requestIdleCallback === 'function') {
                window.requestIdleCallback(syncTask, { timeout: 1000 });
            } else {
                setTimeout(syncTask, 0);
            }
        };

        // 监听动画结束事件
        overlay.addEventListener('animationend', handleAnimationEnd);

        // 备用机制：动画结束后强制清理
        setTimeout(() => {
            if (overlay.dataset.exiting === 'true') {
                handleAnimationEnd();
            }
        }, 350);
    },

    /**
     * 从覆盖层发送群组消息
     */
    sendGroupMessageFromOverlay() {
        if (this.state.isGenerating) {
            this.showToast('正在生成回复，请稍候...', 'warning');
            return;
        }

        if (!this.state.currentGroup) {
            this.showToast('请先选择一个群组', 'warning');
            return;
        }

        const overlayInput = document.getElementById('overlayGroupChatInput');
        const message = overlayInput?.value.trim();

        if (!message) return;

        // 添加用户消息到覆盖层UI
        this.appendGroupMessageToOverlay('user', message);

        // 同步到原群组界面
        this.appendGroupMessage('user', message);

        // 清空输入框
        overlayInput.value = '';
        this.handleGroupOverlayInput();

        // 调整输入框高度
        overlayInput.style.height = 'auto';
        overlayInput.style.height = '24px';

        // 滚动到底部
        const overlayMessages = document.querySelector('#groupChatOverlayHistory .chat-messages');
        if (overlayMessages) {
            overlayMessages.scrollTop = overlayMessages.scrollHeight;
        }

        // 调用群组API
        if (typeof GroupChatEnhanced !== 'undefined') {
            this.state.isGenerating = true;
            this.updateGroupOverlaySendButtonState();

            GroupChatEnhanced.sendMessage(message).finally(() => {
                this.state.isGenerating = false;
                this.updateGroupOverlaySendButtonState();
            });
        }
    },

    /**
     * 处理群组覆盖层输入框输入事件
     */
    handleGroupOverlayInput() {
        const overlayInput = document.getElementById('overlayGroupChatInput');
        const overlaySendBtn = document.getElementById('overlayGroupSendBtn');

        if (overlayInput && overlaySendBtn) {
            overlaySendBtn.disabled = !overlayInput.value.trim() || this.state.isGenerating;
        }
    },

    /**
     * 更新群组覆盖层发送按钮状态
     */
    updateGroupOverlaySendButtonState() {
        const overlayInput = document.getElementById('overlayGroupChatInput');
        const overlaySendBtn = document.getElementById('overlayGroupSendBtn');

        if (overlayInput && overlaySendBtn) {
            overlaySendBtn.disabled = !overlayInput.value.trim() || this.state.isGenerating;
        }
    },

    /**
     * 添加群组消息到覆盖层
     * @param {string} role - 角色: user 或 assistant
     * @param {string} content - 消息内容
     * @param {Object} persona - 角色信息（群组对话时需要）
     */
    appendGroupMessageToOverlay(role, content, persona = null) {
        const messagesContainer = document.querySelector('#groupChatOverlayHistory .chat-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        let avatar = '';
        let bubbleContent = '';
        let actionsHtml = '';

        if (role === 'user') {
            avatar = '<div class="user-avatar">我</div>';
            bubbleContent = this.escapeHtml(content);
            actionsHtml = `
                <button class="message-action-btn" title="复制" onclick="App.copyMessage(this)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                </button>
                <button class="message-action-btn" title="删除" onclick="App.deleteGroupMessage(this)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            `;
        } else if (persona) {
            avatar = `<div class="ai-avatar">${persona.avatar || '🤖'}</div>`;
            bubbleContent = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
            actionsHtml = `
                <button class="message-action-btn" title="复制" onclick="App.copyMessage(this)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                </button>
                <button class="message-action-btn" title="删除" onclick="App.deleteGroupMessage(this)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            `;
        }

        messageDiv.innerHTML = `
            ${avatar}
            <div class="message-content">
                ${persona ? `<div class="message-persona">${persona.name}</div>` : ''}
                <div class="message-bubble ${role === 'user' ? 'user-bubble' : 'ai-bubble'}">
                    ${bubbleContent}
                </div>
                <div class="message-actions">
                    ${actionsHtml}
                </div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        
        // 动画结束后添加 visible 类，确保侧边栏收起时消息不会隐藏
        messageDiv.addEventListener('animationend', function handler() {
            messageDiv.classList.add('visible');
            messageDiv.removeEventListener('animationend', handler);
        }, { once: true });
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    },

    /**
     * 处理群组对话流式输出
     * @param {Object} chunk - 流式数据块
     */
    handleGroupChatChunk(chunk) {
        const { type, persona, content, done, selected, total, isNewSegment } = chunk;

        if (type === 'persona_selection') {
            this.showPersonaSelection(selected, total);
        } else if (type === 'persona_start') {
            this.showGroupTypingIndicator(persona);
        } else if (type === 'stream') {
            this.updateGroupStreamingMessage(persona, content, done, isNewSegment);
        } else if (type === 'persona_complete') {
            this.hideGroupTypingIndicator();
        }
    },

    /**
     * 显示智能体选择通知
     * @param {Array} selected - 被选中的智能体列表
     * @param {number} total - 总智能体数量
     */
    showPersonaSelection(selected, total) {
        const chatHistory = document.getElementById('groupChatArea');
        if (!chatHistory) return;
        
        const notification = document.createElement('div');
        notification.className = 'persona-selection-notification';
        notification.innerHTML = `
            <div class="selection-info">
                <span class="selection-icon">🎲</span>
                <span class="selection-text">随机选择了 ${selected.length} 位智能体参与讨论</span>
            </div>
            <div class="selected-personas">
                ${selected.map(p => `<span class="selected-persona" title="${p.name}">${p.avatar}</span>`).join('')}
            </div>
        `;
        
        chatHistory.appendChild(notification);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    },

    /**
     * 显示群组打字指示器 - 灵动水滴头像
     * @param {Object} persona - 智能体对象
     */
    showGroupTypingIndicator(persona) {
        const chatHistory = document.getElementById('groupChatArea');
        if (!chatHistory) return;
        
        let indicator = document.getElementById('groupTypingIndicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'groupTypingIndicator';
            indicator.className = 'typing-indicator-group droplet-group';
            chatHistory.appendChild(indicator);
        } else {
            if (indicator._hideTimerId) {
                clearTimeout(indicator._hideTimerId);
                indicator._hideTimerId = null;
            }
        }
        
        indicator.classList.remove('is-hiding');
        indicator.dataset.shownAt = String(performance.now());

        indicator.innerHTML = `
            <div class="wave-typing-indicator">
                <div class="wave-bar">
                    <span></span><span></span><span></span><span></span><span></span>
                </div>
                <span class="typing-text">${persona.name} 正在思考...</span>
            </div>
        `;

        chatHistory.scrollTop = chatHistory.scrollHeight;
    },

    /**
     * 隐藏群组打字指示器 - 彻底移除所有类型的打字动画
     */
    hideGroupTypingIndicator() {
        // 1. 移除主打字指示器
        const indicator = document.getElementById('groupTypingIndicator');
        if (indicator) {
             indicator.remove();
        }

        // 2. 移除 GroupChatEnhanced 的打字指示器
        if (typeof GroupChatEnhanced !== 'undefined' && GroupChatEnhanced.removeAllTyping) {
            GroupChatEnhanced.removeAllTyping();
        }
        
        // 3. 移除所有 id 以 typing- 开头的元素
        const typingIndicators = document.querySelectorAll('[id^="typing-"]');
        typingIndicators.forEach(el => el.remove());
        
        // 4. 移除所有 typing 类的消息
        const typingMessages = document.querySelectorAll('.message.typing, .group-message.typing');
        typingMessages.forEach(el => el.remove());
        
        // 5. 移除 wave-typing-indicator 容器
        const waveIndicators = document.querySelectorAll('.wave-typing-indicator');
        waveIndicators.forEach(el => {
            const parent = el.closest('.message, .group-message, [id^="typing-"]');
            if (parent) parent.remove();
        });

        // 6. 清理全屏覆盖层中残留的 typing-indicator (三个点)
        const overlayTypingIndicators = document.querySelectorAll('#groupChatOverlayHistory .typing-indicator');
        overlayTypingIndicators.forEach(el => {
            const bubble = el.closest('.message-bubble');
            if (bubble) {
                // 如果 bubble 里只有 typing-indicator，说明没生成任何内容
                // 我们将其替换为空，或者保留为空白等待内容
                if (bubble.textContent.trim() === '') {
                     // 移除整个 message 元素，因为它是空的
                     const messageEl = bubble.closest('.message');
                     if (messageEl) messageEl.remove();
                } else {
                    el.remove();
                }
            }
        });
    },

    /**
     * 更新群组流式消息
     * @param {Object} persona - 智能体对象
     * @param {string} content - 消息内容
     * @param {boolean} done - 是否完成
     * @param {boolean} isNewSegment - 是否是新段落
     */
    updateGroupStreamingMessage(persona, rawContent, done, isNewSegment) {
        // 清理内容
        const { cleaned, ignore } = this.cleanStreamingContent(rawContent);
        if (ignore && !done) return;
        
        const content = cleaned;
        
        if (content && content.trim()) {
            const indicator = document.getElementById('groupTypingIndicator');
            if (indicator && !indicator.classList.contains('is-hiding')) {
                this.hideGroupTypingIndicator();
            }
        }
        
        const chatHistory = document.getElementById('groupChatArea');
        if (!chatHistory) return;
        let messageEl = document.getElementById(`group-message-${persona.id}`);

        if (isNewSegment && messageEl) {
            messageEl.dataset.streaming = 'false';
            messageEl.classList.remove('streaming');
            messageEl = null;
        }

        if (!messageEl) {
            messageEl = document.createElement('div');
            messageEl.id = `group-message-${persona.id}`;
            messageEl.className = 'group-message assistant';
            messageEl.dataset.streaming = 'true';
            messageEl.dataset.rawContent = '';
            messageEl.innerHTML = `
                <div class="group-message-avatar">${persona.avatar}</div>
                <div class="group-message-content">
                    <div class="group-message-name">${persona.name}</div>
                    <div class="group-message-text"></div>
                </div>
            `;
            chatHistory.appendChild(messageEl);
        }

        const textEl = messageEl.querySelector('.group-message-text');
        if (textEl) {
            const previousContent = messageEl.dataset.rawContent || '';
            const newContent = content.substring(previousContent.length);
            
            if (newContent && !done) {
                textEl.textContent += newContent;
            } else if (done) {
                textEl.textContent = content;
            }
            messageEl.dataset.rawContent = content;
        }

        if (done) {
            messageEl.dataset.streaming = 'false';
            messageEl.classList.remove('streaming');
            messageEl.removeAttribute('data-raw-content');
            if (textEl) {
                textEl.removeAttribute('data-streaming');
            }
            
            // 检查内容是否为空，如果为空则移除消息气泡（避免残留空气泡）
            const finalContent = textEl ? textEl.textContent.trim() : '';
            if (!finalContent) {
                messageEl.remove();
            }

            // 隐藏打字指示器
            this.hideGroupTypingIndicator();
        }

        chatHistory.scrollTop = chatHistory.scrollHeight;
    },

    /**
     * 更新群组对话覆盖层的流式消息
     * @param {Object} persona - 角色信息
     * @param {string} rawContent - 原始内容
     * @param {boolean} done - 是否完成
     */
    updateGroupOverlayStreamingMessage(persona, rawContent, done) {
        const { cleaned, ignore } = this.cleanStreamingContent(rawContent);
        if (ignore && !done) return;
        
        const content = cleaned;
        
        const overlayMessages = document.querySelector('#groupChatOverlayHistory .chat-messages');
        if (!overlayMessages) return;
        
        let messageEl = overlayMessages.querySelector(`[data-persona-id="${persona.id}"]`);

        if (!messageEl) {
            messageEl = document.createElement('div');
            messageEl.dataset.personaId = persona.id;
            messageEl.dataset.rawContent = '';
            messageEl.className = 'message assistant';
            messageEl.innerHTML = `
                <div class="ai-avatar">${persona.avatar || '🤖'}</div>
                <div class="message-content">
                    <div class="message-persona">${persona.name}</div>
                    <div class="message-bubble ai-bubble"></div>
                </div>
            `;
            overlayMessages.appendChild(messageEl);
        }

        const bubbleEl = messageEl.querySelector('.message-bubble');
        if (bubbleEl) {
            const previousContent = messageEl.dataset.rawContent || '';
            const newContent = content.substring(previousContent.length);
            
            if (done) {
                // 流式完成时，先移除 typing-indicator（如果存在）
                const typingIndicator = bubbleEl.querySelector('.typing-indicator');
                if (typingIndicator) {
                    bubbleEl.innerHTML = '';
                }
                bubbleEl.textContent = content;
                // 添加完成动画效果
                messageEl.classList.add('completed');
            } else if (newContent) {
                bubbleEl.textContent += newContent;
            }
            messageEl.dataset.rawContent = content;
        }

        if (done) {
            messageEl.classList.remove('streaming');
            messageEl.removeAttribute('data-raw-content');
            
            // 检查覆盖层中的气泡内容是否为空，如果为空则移除（避免残留空气泡）
            const bubbleEl = messageEl.querySelector('.message-bubble');
            const finalContent = bubbleEl ? bubbleEl.textContent.trim() : '';
            if (!finalContent) {
                 messageEl.remove();
            }
        }

        overlayMessages.scrollTop = overlayMessages.scrollHeight;
    },

    /**
     * 添加群组消息
     * @param {string} role - 角色 (user/assistant)
     * @param {string} content - 消息内容
     */
    appendGroupMessage(role, content) {
        const chatArea = document.getElementById('groupChatArea');
        const overlayMessages = document.querySelector('#groupChatOverlayHistory .chat-messages');

        if (!chatArea) {
            console.warn('[appendGroupMessage] 群组对话区域不存在，消息未显示');
            return;
        }

        try {
            // 创建消息HTML
            const messageHtml = role === 'user' ? `
                <div class="group-message-avatar">👤</div>
                <div class="group-message-content">
                    <div class="group-message-text">${this.formatMessageContent(content)}</div>
                </div>
            ` : '';

            // 添加到原界面
            const messageEl = document.createElement('div');
            messageEl.className = `group-message ${role} new`;
            messageEl.innerHTML = messageHtml;
            chatArea.appendChild(messageEl);
            chatArea.scrollTop = chatArea.scrollHeight;

            // 同步到全屏覆盖层（如果存在）
            if (overlayMessages && role === 'user') {
                const overlayMessageEl = document.createElement('div');
                overlayMessageEl.className = `message ${role}`;
                overlayMessageEl.innerHTML = `
                    <div class="message-avatar">👤</div>
                    <div class="message-content">
                        <div class="message-bubble">${this.formatMessageContent(content)}</div>
                    </div>
                `;
                overlayMessages.appendChild(overlayMessageEl);
                overlayMessages.scrollTop = overlayMessages.scrollHeight;
            }
        } catch (error) {
            console.error('[appendGroupMessage] 添加消息失败:', error);
        }
    },

    /**
     * 处理群组聊天输入
     */
    handleGroupChatInput() {
        const input = document.getElementById('groupChatInput');
        const sendBtn = document.getElementById('groupSendBtn');
        const charCount = document.getElementById('groupCharCount');

        if (!input || !sendBtn) return;

        const value = input.value.trim();
        const length = value.length;

        sendBtn.disabled = length === 0 || this.state.isGenerating;

        if (charCount) {
            charCount.textContent = `${length} / 4000`;

            if (length > 4000) {
                charCount.style.color = 'var(--error-color)';
            } else {
                charCount.style.color = 'var(--text-muted)';
            }
        }
    },

    /**
     * 更新群组发送按钮状态
     */
    updateGroupSendButtonState() {
        const sendBtn = document.getElementById('groupSendBtn');
        if (!sendBtn) return;

        sendBtn.disabled = this.state.isGenerating;
    },

    /**
     * 显示群组暂停按钮
     */
    showGroupPauseButton() {
        const pauseBtn = document.getElementById('pauseGroupChatBtn');
        const sendBtn = document.getElementById('groupSendBtn');
        if (pauseBtn) {
            pauseBtn.style.display = 'flex';
        }
        if (sendBtn) {
            sendBtn.style.display = 'none';
        }
    },

    /**
     * 隐藏群组暂停按钮
     */
    hideGroupPauseButton() {
        const pauseBtn = document.getElementById('pauseGroupChatBtn');
        const sendBtn = document.getElementById('groupSendBtn');
        if (pauseBtn) {
            pauseBtn.style.display = 'none';
        }
        if (sendBtn) {
            sendBtn.style.display = 'flex';
        }
    },

    /**
     * 暂停群组对话回复
     */
    pauseGroupChat() {
        if (typeof GroupChatEnhanced !== 'undefined' && GroupChatEnhanced.abortCurrentChat) {
            GroupChatEnhanced.abortCurrentChat();
            this.showToast('已暂停当前回复', 'info');
        }
        this.state.isGenerating = false;
        this.hideGroupPauseButton();
        this.updateGroupSendButtonState();
    },

    /**
     * 清空群组对话
     */
    clearGroupChat() {
        if (!confirm('确定要清空当前群组对话吗？')) return;

        if (this.state.currentGroupConversation) {
            Storage.deleteGroupConversation(this.state.currentGroupConversation.id);
            this.state.currentGroupConversation = null;
        }

        this.clearGroupChatUI();
        this.showToast('群组对话已清空', 'success');
    },

    // ========================================
    // 文生图功能 - 新增模块
    // ========================================

    /**
     * 初始化文生图模块
     */
    async initImageGen() {
        if (typeof ImageGen !== 'undefined') {
            await ImageGen.init();
            this.updateImageGenStatus();
        }
    },

    /**
     * 初始化视觉理解服务
     */
    async initVisionService() {
        if (typeof VisionAPI !== 'undefined') {
            try {
                const available = await VisionAPI.init();
                this.updateVisionServiceStatus(available);
                console.log('[App] 视觉服务状态:', available ? '可用' : '不可用');
            } catch (error) {
                console.warn('[App] 视觉服务初始化失败:', error.message);
                this.updateVisionServiceStatus(false);
            }
        }
        
        if (typeof ImageGenAPI !== 'undefined') {
            try {
                await ImageGenAPI.init();
                console.log('[App] 图片生成服务状态:', ImageGenAPI.status.available ? '可用' : '不可用');
            } catch (error) {
                console.warn('[App] 图片生成服务初始化失败:', error.message);
            }
        }
    },

    /**
     * 更新视觉服务状态显示
     */
    updateVisionServiceStatus(available) {
        const statusEl = document.getElementById('visionServiceStatus');
        if (!statusEl) return;

        if (available) {
            statusEl.innerHTML = `<span style="color: var(--success-color)">●</span> 视觉理解已就绪`;
        } else {
            statusEl.innerHTML = `<span style="color: var(--warning-color)">●</span> 视觉服务未启动`;
        }
    },

    /**
     * 更新文生图状态显示
     */
    updateImageGenStatus() {
        const statusEl = document.getElementById('imageGenStatus');
        if (!statusEl) return;

        if (typeof ImageGen !== 'undefined') {
            const status = ImageGen.getStatus();
            if (status.modelCount > 0) {
                statusEl.innerHTML = `<span style="color: var(--success-color)">●</span> 文生图已就绪 (${status.modelCount}个模型)`;
            } else {
                statusEl.innerHTML = `<span style="color: var(--warning-color)">●</span> 文生图服务未启动`;
            }
            return;
        }

        if (typeof ImageGenAPI !== 'undefined') {
            const modelCount = Array.isArray(ImageGenAPI.status?.models) ? ImageGenAPI.status.models.length : 0;
            const available = !!ImageGenAPI.status?.available;
            if (available || modelCount > 0) {
                statusEl.innerHTML = `<span style="color: var(--success-color)">●</span> 文生图已就绪 (${modelCount}个模型)`;
            } else {
                statusEl.innerHTML = `<span style="color: var(--warning-color)">●</span> 文生图服务未启动`;
            }
            return;
        }

        statusEl.innerHTML = `<span style="color: var(--warning-color)">●</span> 文生图模块未加载`;
    },

    /**
     * 打开文生图面板
     */
    openImageGenPanel() {
        const panel = document.getElementById('imageGenPanel');
        if (panel) {
            panel.style.display = 'flex';
            this.loadImageGenModels();
            
            // 添加点击空白处关闭面板的功能
            const self = this;
            const handleClickOutside = function(e) {
                // 如果点击的是面板容器（overlay），而不是面板内容，则关闭面板
                if (e.target === panel) {
                    self.closeImageGenPanel();
                }
            };
            
            // 添加事件监听器
            panel.addEventListener('click', handleClickOutside);
            
            // 保存引用以便后续移除
            panel._handleClickOutside = handleClickOutside;
            return;
        }

        // 无弹窗容器时，退化为独立页面模式
        this.switchPage('image-gen');
        this.ensureImageGen();
        this.loadImageGenModels();
    },

    /**
     * 关闭文生图面板
     */
    closeImageGenPanel() {
        const panel = document.getElementById('imageGenPanel');
        if (panel) {
            panel.style.display = 'none';
            // 移除事件监听器
            if (panel._handleClickOutside) {
                panel.removeEventListener('click', panel._handleClickOutside);
                delete panel._handleClickOutside;
            }
            return;
        }

        if (this.state.currentPage === 'image-gen') {
            this.switchPage('chat');
        }
    },

    /**
     * 加载可用模型列表
     */
    async loadImageGenModels() {
        const select = document.getElementById('imageGenModelSelect');
        const modelsContainer = document.getElementById('imageGenModelsGrid');
        const quickSwitchContainer = document.getElementById('imageGenQuickSwitch');
        if (!select || !modelsContainer) return;

        if (typeof ImageGen === 'undefined') {
            select.innerHTML = '<option value="">文生图模块未加载</option>';
            modelsContainer.innerHTML = '';
            if (quickSwitchContainer) quickSwitchContainer.innerHTML = '<div class="quick-switch-error">模块未加载</div>';
            return;
        }

        const response = await ImageGen.getModels();
        
        const models = response?.models || response?.data || {};
        const modelKeys = Object.keys(models);
        
        if (modelKeys.length === 0) {
            select.innerHTML = '<option value="z-image-turbo">Z-Image Turbo (通用)</option>';
            modelsContainer.innerHTML = '<div class="image-model-card active" data-model="z-image-turbo"><div class="model-name">Z-Image Turbo</div><div class="model-style">通用</div></div>';
            return;
        }
        
        select.innerHTML = Object.entries(models).map(([key, model]) =>
            `<option value="${key}">${model.name || key} (${model.style || '通用'})</option>`
        ).join('');

        const firstModelKey = modelKeys[0];
        
        if (quickSwitchContainer) {
            const priorityModels = ['z-image-turbo', 'z-image-turbo-art', 'ssd-1b', 'kook-qwen-2512', 'stable-diffusion-v1-5'];
            const displayModels = priorityModels.filter(k => models[k]).slice(0, 5);
            
            if (displayModels.length === 0) {
                displayModels.push(...modelKeys.slice(0, 5));
            }
            
            quickSwitchContainer.innerHTML = displayModels.map((key, index) => {
                const model = models[key];
                const shortcutKey = index < 9 ? `F${index + 1}` : '';
                return `
                    <div class="quick-switch-btn ${key === firstModelKey ? 'active' : ''}"
                         data-model="${key}"
                         data-shortcut="${shortcutKey}"
                         onclick="App.quickSwitchImageModel('${key}')">
                        <div class="quick-switch-icon">${this.getModelIcon(model?.style)}</div>
                        <div class="quick-switch-info">
                            <div class="quick-switch-name">${model?.name || key}</div>
                            <div class="quick-switch-style">${model?.style || '通用'}</div>
                        </div>
                        ${shortcutKey ? `<div class="quick-switch-key">${shortcutKey}</div>` : ''}
                    </div>
                `;
            }).join('');
            
            this.bindImageGenShortcuts(displayModels);
        }
        
        modelsContainer.innerHTML = Object.entries(models).map(([key, model]) => `
            <div class="image-model-card ${key === firstModelKey ? 'active' : ''}"
                 data-model="${key}"
                 onclick="App.selectImageGenModel('${key}')">
                <div class="model-name">${model?.name || key}</div>
                <div class="model-style">${model?.style || '通用'}</div>
                <div class="model-size">${model?.size || ''}</div>
            </div>
        `).join('');

        this.applyImageGenDefaultPrompt();
    },
    
    /**
     * 根据风格获取模型图标
     */
    getModelIcon(style) {
        const iconMap = {
            '写实摄影': '📷',
            '二次元动漫': '🎨',
            '艺术创作': '🎭',
            '通用': '✨',
            '经典写实': '🖼️'
        };
        return iconMap[style] || '🎨';
    },
    
    /**
     * 绑定快捷键
     */
    bindImageGenShortcuts(models) {
        // 先移除旧的监听器
        if (window._imageGenShortcutHandler) {
            document.removeEventListener('keydown', window._imageGenShortcutHandler);
        }
        
        window._imageGenShortcutHandler = (e) => {
            if (this.state.currentPage !== 'image-gen') return;
            
            const keyNum = parseInt(e.key.replace('F', ''));
            if (e.key.startsWith('F') && keyNum >= 1 && keyNum <= models.length) {
                e.preventDefault();
                const modelKey = models[keyNum - 1];
                this.quickSwitchImageModel(modelKey);
            }
        };
        
        document.addEventListener('keydown', window._imageGenShortcutHandler);
    },
    
    /**
     * 快速切换模型
     */
    async quickSwitchImageModel(modelKey) {
        const btn = document.querySelector(`#imageGenQuickSwitch [data-model="${modelKey}"]`);
        const allBtns = document.querySelectorAll('#imageGenQuickSwitch .quick-switch-btn');
        
        if (!btn) {
            this.selectImageGenModel(modelKey);
            return;
        }
        
        // 添加加载状态
        allBtns.forEach(b => b.classList.remove('loading', 'active'));
        btn.classList.add('loading');
        
        try {
            const result = await ImageGen.switchModel(modelKey);
            
            if (result.success) {
                // 更新 UI
                allBtns.forEach(b => {
                    b.classList.toggle('active', b.dataset.model === modelKey);
                });
                
                // 同时更新传统选择器
                this.selectImageGenModel(modelKey);
                
                this.showToast(`${result.message || '模型切换成功'}`, 'success');
            } else {
                this.showToast(result.error || '切换失败', 'error');
            }
        } catch (error) {
            this.showToast(`切换失败: ${error.message}`, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    },

    /**
     * 选择文生图模型
     */
    selectImageGenModel(modelKey) {
        // 更新UI
        document.querySelectorAll('.image-model-card').forEach(card => {
            card.classList.toggle('active', card.dataset.model === modelKey);
        });

        const modelSelect = document.getElementById('imageGenModelSelect');
        if (modelSelect) {
            modelSelect.value = modelKey;
        }

        // 应用默认提示词
        this.applyImageGenDefaultPrompt();
    },

    /**
     * 应用默认提示词
     */
    applyImageGenDefaultPrompt() {
        const select = document.getElementById('imageGenModelSelect');
        const modelKey = select?.value;
        const defaults = ImageGen.getDefaultPrompt(modelKey);

        const positiveInput = document.getElementById('imageGenPrompt');
        const negativeInput = document.getElementById('imageGenNegativePrompt');

        if (positiveInput && !positiveInput.dataset.userModified) {
            positiveInput.value = defaults.positive.split(', ').slice(0, 3).join(', ');
        }
        if (negativeInput && !negativeInput.dataset.userModified) {
            negativeInput.value = defaults.negative;
        }
    },

    /**
     * 生成图片
     */
    async generateImage() {
        const modelKey = document.getElementById('imageGenModelSelect')?.value;
        const prompt = document.getElementById('imageGenPrompt')?.value.trim();
        const negativePrompt = document.getElementById('ImageGenNegativePrompt')?.value.trim();
        const styleTemplate = document.querySelector('.style-chip.active')?.dataset.value || 'none';
        const width = parseInt(document.getElementById('imageGenWidth')?.value) || 384;
        const height = parseInt(document.getElementById('imageGenHeight')?.value) || 384;
        const steps = parseInt(document.getElementById('imageGenSteps')?.value) || 20;
        const cfgScale = parseFloat(document.getElementById('imageGenCfgScale')?.value) || 7;

        if (!prompt) {
            this.showToast('请输入提示词', 'warning');
            return;
        }

        // 记忆参数
        this.saveImageGenParams({ modelKey, width, height, steps, cfgScale, styleTemplate });

        // 显示进度状态
        const btn = document.getElementById('imageGenGenerateBtn');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="loading-spinner"><span></span><span></span><span></span></span> 生成中...';
        btn.disabled = true;

        const resultContainer = document.getElementById('imageGenResult');
        const progressPrompt = document.getElementById('progressPrompt');
        if (progressPrompt) progressPrompt.textContent = prompt;
        
        // 显示进度动画
        resultContainer.innerHTML = `
            <div class="generation-progress" id="generationProgress">
                <div class="progress-wave">
                    <span></span><span></span><span></span><span></span><span></span>
                </div>
                <p class="progress-text">正在生成图片...</p>
                <p class="progress-prompt">"${prompt}"</p>
            </div>
        `;

        try {
            // 构建完整提示词
            let fullPrompt = prompt;
            if (styleTemplate && styleTemplate !== 'none') {
                const styles = ImageGen.getStyleTemplates();
                if (styles[styleTemplate]) {
                    fullPrompt = `${prompt}, ${styles[styleTemplate].suffix}`;
                }
            }

            // 生成图片
            const result = await ImageGen.generate({
                model: modelKey,
                prompt: fullPrompt,
                negativePrompt: negativePrompt,
                width: width,
                height: height,
                steps: steps,
                cfgScale: cfgScale
            });

            if (result.success) {
                // 保存到历史记录
                this.addToImageHistory(result, prompt);
                
                // 显示结果
                resultContainer.innerHTML = `
                    <div class="image-result">
                        <img src="${result.imageUrl}" alt="生成的图片" loading="lazy" 
                             onclick="App.openImagePreview('${result.imageUrl}', '${result.filename}', '${result.model}', '${prompt}')"
                             style="max-width: 100%; border-radius: 12px; cursor: pointer;">
                        <div class="image-actions">
                            <button class="btn btn-primary" onclick="App.insertImageToChat('${result.imageUrl}', '${result.model}')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                                </svg>
                                插入对话
                            </button>
                            <button class="btn btn-secondary" onclick="ImageGen.downloadImage('${result.imageUrl}', '${result.filename}')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                下载
                            </button>
                        </div>
                    </div>
                `;
                
                // 显示在结果区域
                this.showGeneratedImage(result, prompt);
                this.showToast('图片生成成功！', 'success');
            } else {
                resultContainer.innerHTML = `<div class="image-error">生成失败: ${result.error}</div>`;
                this.showToast(result.error, 'error');
            }
        } catch (error) {
            resultContainer.innerHTML = `<div class="image-error">生成失败: ${error.message}</div>`;
            this.showToast(`生成失败: ${error.message}`, 'error');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    },

    /**
     * 保存图片生成参数到localStorage
     */
    saveImageGenParams(params) {
        try {
            localStorage.setItem('imageGenParams', JSON.stringify(params));
        } catch (e) {}
    },

    /**
     * 加载保存的图片生成参数
     */
    loadImageGenParams() {
        try {
            const saved = localStorage.getItem('imageGenParams');
            return saved ? JSON.parse(saved) : null;
        } catch (e) {
            return null;
        }
    },

    /**
     * 应用保存的参数到界面
     */
    applyImageGenParams() {
        const params = this.loadImageGenParams();
        if (!params) return;
        
        if (params.modelKey) {
            const select = document.getElementById('imageGenModelSelect');
            if (select) select.value = params.modelKey;
        }
        if (params.width) {
            const widthInput = document.getElementById('imageGenWidth');
            if (widthInput) {
                widthInput.value = params.width;
                const widthValue = document.getElementById('widthValue');
                if (widthValue) widthValue.textContent = params.width;
            }
        }
        if (params.height) {
            const heightInput = document.getElementById('imageGenHeight');
            if (heightInput) {
                heightInput.value = params.height;
                const heightValue = document.getElementById('heightValue');
                if (heightValue) heightValue.textContent = params.height;
            }
        }
        if (params.steps) {
            const stepsInput = document.getElementById('imageGenSteps');
            if (stepsInput) {
                stepsInput.value = params.steps;
                const stepsValue = document.getElementById('stepsValue');
                if (stepsValue) stepsValue.textContent = params.steps;
            }
        }
        if (params.cfgScale) {
            const cfgInput = document.getElementById('imageGenCfgScale');
            if (cfgInput) {
                cfgInput.value = params.cfgScale;
                const cfgValue = document.getElementById('cfgValue');
                if (cfgValue) cfgValue.textContent = params.cfgScale;
            }
        }
        if (params.styleTemplate) {
            document.querySelectorAll('.style-chip').forEach(chip => {
                chip.classList.toggle('active', chip.dataset.value === params.styleTemplate);
            });
        }
        
        this.updateParamHint();
    },

    /**
     * 更新参数提示（估算生成时间）
     */
    updateParamHint() {
        const steps = parseInt(document.getElementById('imageGenSteps')?.value) || 20;
        const width = parseInt(document.getElementById('imageGenWidth')?.value) || 384;
        const height = parseInt(document.getElementById('imageGenHeight')?.value) || 384;
        
        // 简单估算：步数 * 尺寸系数 * 基础时间
        const sizeFactor = (width * height) / (384 * 384);
        const estimatedTime = Math.round(steps * sizeFactor * 0.8);
        
        const hint = document.getElementById('paramHint');
        if (hint) hint.textContent = `预计约${estimatedTime}秒`;
    },

    /**
     * 添加图片到历史记录
     */
    addToImageHistory(result, prompt) {
        let history = [];
        try {
            history = JSON.parse(localStorage.getItem('imageGenHistory') || '[]');
        } catch (e) {}
        
        history.unshift({
            url: result.imageUrl,
            filename: result.filename,
            model: result.model,
            prompt: prompt,
            timestamp: Date.now()
        });
        
        // 最多保存50条
        if (history.length > 50) history = history.slice(0, 50);
        
        try {
            localStorage.setItem('imageGenHistory', JSON.stringify(history));
        } catch (e) {}
    },

    /**
     * 显示生成的图片
     */
    showGeneratedImage(result, prompt) {
        const card = document.getElementById('generatedImagesCard');
        const grid = document.getElementById('generatedImagesGrid');
        
        if (card) card.style.display = 'block';
        
        if (grid) {
            const item = document.createElement('div');
            item.className = 'generated-image-item';
            item.innerHTML = `
                <img src="${result.imageUrl}" alt="生成的图片" loading="lazy">
                <div class="image-item-overlay">
                    <div class="image-item-model">${result.model}</div>
                    <div class="image-item-prompt">${prompt}</div>
                </div>
            `;
            item.onclick = () => this.openImagePreview(result.imageUrl, result.filename, result.model, prompt);
            grid.insertBefore(item, grid.firstChild);
        }
    },

    /**
     * 打开图片预览模态框
     */
    openImagePreview(url, filename, model, prompt) {
        const modal = document.getElementById('imagePreviewModal');
        const img = document.getElementById('previewModalImage');
        
        if (modal && img) {
            img.src = url;
            this.currentPreviewImage = { url, filename, model, prompt };
            modal.style.display = 'flex';
        }
    },

    /**
     * 关闭图片预览
     */
    closeImagePreview() {
        const modal = document.getElementById('imagePreviewModal');
        if (modal) modal.style.display = 'none';
    },

    /**
     * 下载当前预览图片
     */
    downloadCurrentImage() {
        if (this.currentPreviewImage) {
            ImageGen.downloadImage(this.currentPreviewImage.url, this.currentPreviewImage.filename);
        }
    },

    /**
     * 插入当前图片到对话
     */
    insertCurrentImageToChat() {
        if (this.currentPreviewImage) {
            this.insertImageToChat(this.currentPreviewImage.url, this.currentPreviewImage.model);
            this.closeImagePreview();
        }
    },

    /**
     * 显示图片历史记录
     */
    showImageHistory() {
        const modal = document.getElementById('imageHistoryModal');
        const grid = document.getElementById('imageHistoryGrid');
        
        if (!modal || !grid) return;
        
        let history = [];
        try {
            history = JSON.parse(localStorage.getItem('imageGenHistory') || '[]');
        } catch (e) {}
        
        grid.innerHTML = history.length ? '' : '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">暂无生成历史</p>';
        
        history.forEach(item => {
            const div = document.createElement('div');
            div.className = 'generated-image-item';
            div.innerHTML = `
                <img src="${item.url}" alt="生成的图片" loading="lazy">
                <div class="image-item-overlay">
                    <div class="image-item-model">${item.model}</div>
                    <div class="image-item-prompt">${item.prompt}</div>
                </div>
            `;
            div.onclick = () => {
                this.closeImageHistory();
                this.openImagePreview(item.url, item.filename, item.model, item.prompt);
            };
            grid.appendChild(div);
        });
        
        modal.style.display = 'flex';
    },

    /**
     * 关闭图片历史
     */
    closeImageHistory() {
        const modal = document.getElementById('imageHistoryModal');
        if (modal) modal.style.display = 'none';
    },

    /**
     * 清空图片历史
     */
    clearImageHistory() {
        try {
            localStorage.removeItem('imageGenHistory');
            this.showImageHistory();
            this.showToast('历史已清空', 'success');
        } catch (e) {}
    },

    /**
     * 卸载模型
     */
    async unloadImageModel() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/image/unload`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (data.success) {
                this.showToast('模型已卸载，内存已释放', 'success');
                this.updateMemoryStatus();
            } else {
                this.showToast(data.error || '卸载失败', 'error');
            }
        } catch (e) {
            this.showToast('卸载请求失败', 'error');
        }
    },

    /**
     * 更新内存状态显示
     */
    async updateMemoryStatus() {
        const statusEl = document.getElementById('ImageMemoryStatus');
        if (!statusEl) return;
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/image/memory`);
            const data = await response.json();
            if (data.success && data.data) {
                const mem = data.data.process || {};
                const valueEl = statusEl.querySelector('.memory-value');
                if (valueEl) {
                    valueEl.textContent = mem.rss_mb ? `${Math.round(mem.rss_mb)}MB` : '--';
                }
            }
        } catch (e) {
            // 静默失败
        }
    },

    /**
     * 将生成的图片插入到聊天输入框
     */
    insertImageToChat(imageUrl, modelName) {
        const input = document.getElementById('chatInput');
        if (input) {
            const imageMarkdown = `\n![生成的图片](${imageUrl})\n*使用 ${modelName} 模型生成*\n`;
            input.value += imageMarkdown;
            input.focus();
            this.handleChatInput();

            // 关闭面板
            this.closeImageGenPanel();
        }
    },

    /**
     * 快速生成图片（从聊天输入）
     */
    async quickGenerateImage() {
        const input = document.getElementById('chatInput');
        const prompt = input?.value.trim();

        if (!prompt) {
            this.showToast('请先输入提示词', 'warning');
            return;
        }

        // 检查文生图服务
        const isHealthy = await ImageGen.checkHealth();
        if (!isHealthy) {
            this.showToast('文生图服务未启动，请先运行服务', 'error');
            return;
        }

        // 获取可用的模型列表
        const response = await ImageGen.getModels();
        let firstModelKey = 'z-image-turbo-art'; // 默认使用Z-Image-Turbo-Art
        if (response && response.success && response.data) {
            const modelKeys = Object.keys(response.data);
            if (modelKeys.length > 0) {
                firstModelKey = modelKeys[0];
            }
        }
        
        // 设置模型为第一个可用模型
        const modelSelect = document.getElementById('imageGenModelSelect');
        const promptInput = document.getElementById('imageGenPrompt');
        const negativePromptInput = document.getElementById('imageGenNegativePrompt');
        if (modelSelect) {
            modelSelect.value = firstModelKey;
        }
        if (promptInput) {
            promptInput.value = prompt;
            promptInput.dataset.userModified = 'true';
        }
        if (negativePromptInput) {
            negativePromptInput.value = '';
            negativePromptInput.dataset.userModified = 'true';
        }

        // 打开面板
        this.openImageGenPanel();
    }
};

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    // 初始化艺术风格欢迎页面
    initArtisticWelcome();
    
    // 初始化 Canvas 马群动画
    initHorseCanvas();
    
    // 延迟初始化主应用（等欢迎页面处理完）
    setTimeout(() => {
        App.init();
    }, 100);
});

// 导出到全局
window.App = App;

// ============================================
// 艺术风格欢迎页面控制
// ============================================
function initArtisticWelcome() {
    const welcome = document.getElementById('artisticWelcome');
    const enterBtn = document.getElementById('enterAppBtn');
    
    if (!welcome || !enterBtn) return;
    
    // 检查是否已经访问过（使用 sessionStorage）
    const hasVisited = sessionStorage.getItem('ollamaHubVisited');
    
    if (hasVisited) {
        // 已经访问过，直接隐藏欢迎页面
        welcome.classList.add('hidden');
        setTimeout(() => {
            welcome.style.display = 'none';
        }, 800);
    } else {
        // 首次访问，显示欢迎页面
        welcome.style.display = 'flex';
        
        // 绑定进入按钮事件
        enterBtn.addEventListener('click', () => {
            // 标记已访问
            sessionStorage.setItem('ollamaHubVisited', 'true');
            
            // 销毁 Canvas 动画释放资源
            if (window.horseAnimation && typeof window.horseAnimation.destroy === 'function') {
                window.horseAnimation.destroy();
                window.horseAnimation = null;
            }
            
            // 添加隐藏动画
            welcome.classList.add('hidden');
            
            // 动画完成后完全隐藏
            setTimeout(() => {
                welcome.style.display = 'none';
            }, 800);
        });
        
        // 点击背景也可以进入（可选）
        welcome.addEventListener('click', (e) => {
            if (e.target === welcome || e.target.classList.contains('welcome-background')) {
                enterBtn.click();
            }
        });
        
        // 按 Enter 键也可以进入
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !welcome.classList.contains('hidden')) {
                enterBtn.click();
            }
        });
    }
}

// ============================================
// Canvas 马群动画初始化
// ============================================
function initHorseCanvas() {
    const canvas = document.getElementById('horseCanvas');
    if (!canvas) return;
    
    if (typeof HorseCanvas !== 'undefined') {
        window.horseAnimation = new HorseCanvas(canvas);
    } else {
        console.warn('HorseCanvas 未加载，尝试延迟初始化');
        setTimeout(() => {
            if (typeof HorseCanvas !== 'undefined') {
                window.horseAnimation = new HorseCanvas(canvas);
            }
        }, 500);
    }
}
