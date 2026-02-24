/**
 * 事件绑定模块
 * 所有 bind* 方法集中管理
 */
(function() {
    const Events = {
        _isBound: false,

        bindAll(app) {
            if (this._isBound) return;
            this.app = app;
            this.bindEvents();
            this.bindWorldviewEvents();
            this.bindSettingsEvents();
            this.bindPullModalEvents();
            this.bindModalEvents();
            this.bindParamGuideEvents();
            this._isBound = true;
        },

        bindEvents() {
            const app = this.app;
            const themeToggle = document.getElementById('themeToggle');
            if (themeToggle) {
                themeToggle.addEventListener('click', () => ThemeManager.toggleTheme());
            }

            document.querySelectorAll('.theme-option').forEach(option => {
                option.addEventListener('click', () => {
                    ThemeManager.applyTheme(option.dataset.theme);
                });
            });

            document.querySelectorAll('.nav-item').forEach(item => {
                item.addEventListener('click', () => app.switchPage(item.dataset.page));
            });

            document.getElementById('pullModelBtn')?.addEventListener('click', () => app.openPullModal());
            document.getElementById('pullModelBtn2')?.addEventListener('click', () => app.openPullModal());
            document.getElementById('newChatBtn')?.addEventListener('click', () => app.startNewChat());
            document.getElementById('newChatBtn2')?.addEventListener('click', () => app.startNewChat());
            document.getElementById('refreshBtn')?.addEventListener('click', () => app.refreshAll());

            const modelSearch = document.getElementById('modelSearch');
            if (modelSearch) {
                modelSearch.addEventListener('input', (e) => app.filterModels(e.target.value));
            }

            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    app.filterModels(document.getElementById('modelSearch')?.value || '', btn.dataset.filter);
                });
            });

            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.addEventListener('input', () => app.handleChatInput());
                chatInput.addEventListener('keydown', (e) => app.handleChatKeydown(e));

                const adjustHeight = () => {
                    chatInput.style.height = 'auto';
                    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
                };

                chatInput.addEventListener('input', adjustHeight);
                setTimeout(adjustHeight, 0);
            }

            document.getElementById('sendBtn')?.addEventListener('click', () => app.sendMessage());

            document.getElementById('enterFullscreenBtn')?.addEventListener('click', () => app.enterChatOverlay());
            document.getElementById('computerAssistBtn')?.addEventListener('click', () => {
                app.handleComputerAssistRequest({
                    forced: true,
                    allowControl: !!app.state?.computerAssistControlEnabled
                });
            });
            document.getElementById('computerAssistControlToggleBtn')?.addEventListener('click', () => {
                app.toggleComputerAssistControlMode();
            });
            document.getElementById('computerAssistRunBtn')?.addEventListener('click', () => {
                app.handleComputerAssistExecution({});
            });

            document.getElementById('imageUploadBtn')?.addEventListener('click', () => {
                document.getElementById('chatImageInput')?.click();
            });

            document.getElementById('chatImageInput')?.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    app.handleChatImageUpload(e.target.files[0]);
                }
            });

            document.getElementById('removeChatImageBtn')?.addEventListener('click', () => {
                app.clearChatImage();
            });

            document.getElementById('clearChatBtn')?.addEventListener('click', () => app.clearCurrentChat());

            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) {
                modelSelect.addEventListener('change', (e) => {
                    app.state.selectedModel = e.target.value;
                    app.updateConversationModel(e.target.value);
                });
            }

            document.getElementById('newConversationBtn')?.addEventListener('click', () => app.startNewChat());

            document.querySelectorAll('.suggestion-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const prompt = btn.dataset.prompt;
                    document.getElementById('chatInput').value = prompt;
                    app.handleChatInput();
                    app.showToast('已填入输入框，请按 Enter 发送或点击发送按钮', 'info');
                });
            });

            document.getElementById('newGroupBtn')?.addEventListener('click', () => app.showGroupModal('create'));

            document.getElementById('selectModelsBtn')?.addEventListener('click', () => {
                if (typeof GroupChatEnhanced !== 'undefined') {
                    GroupChatEnhanced.toggleSelector();
                }
            });

            const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
            const sidebarExpandBtn = document.getElementById('sidebarExpandBtn');
            const groupSidebar = document.getElementById('groupSidebar');
            const mainSidebar = document.getElementById('mainSidebar');

            const mainSidebarExpandBtn = document.getElementById('mainSidebarExpandBtn');
            if (sidebarCollapseBtn && mainSidebar) {
                sidebarCollapseBtn.addEventListener('click', () => {
                    mainSidebar.classList.add('collapsed');
                    localStorage.setItem('mainSidebarCollapsed', 'true');
                });
            }

            if (mainSidebarExpandBtn && mainSidebar) {
                mainSidebarExpandBtn.addEventListener('click', () => {
                    mainSidebar.classList.remove('collapsed');
                    localStorage.setItem('mainSidebarCollapsed', 'false');
                });
            }

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

            const isMainCollapsed = localStorage.getItem('mainSidebarCollapsed') === 'true';
            if (isMainCollapsed && mainSidebar) {
                mainSidebar.classList.add('collapsed');
            }

            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (isCollapsed && groupSidebar) {
                groupSidebar.classList.add('collapsed');
                if (sidebarExpandBtn) {
                    sidebarExpandBtn.classList.add('visible');
                }
            }

            document.getElementById('groupChatInput')?.addEventListener('input', () => app.handleGroupChatInput());
            document.getElementById('groupChatInput')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    app.sendGroupMessage();
                }
            });
            document.getElementById('groupSendBtn')?.addEventListener('click', () => app.sendGroupMessage());
            document.getElementById('pauseGroupChatBtn')?.addEventListener('click', () => app.pauseGroupChat());

            document.getElementById('groupModalClose')?.addEventListener('click', () => app.hideGroupModal());
            document.getElementById('groupModalCancel')?.addEventListener('click', () => app.hideGroupModal());
            document.getElementById('groupForm')?.addEventListener('submit', (e) => {
                e.preventDefault();
                app.saveGroup();
            });
            document.getElementById('deleteConfirmCancel')?.addEventListener('click', () => app.hideDeleteConfirm());
            document.getElementById('deleteConfirmConfirm')?.addEventListener('click', () => app.confirmDeleteGroup());

            document.getElementById('groupModal')?.addEventListener('click', (e) => {
                if (e.target.id === 'groupModal') app.hideGroupModal();
            });
            document.getElementById('deleteConfirmModal')?.addEventListener('click', (e) => {
                if (e.target.id === 'deleteConfirmModal') app.hideDeleteConfirm();
            });

            const groupChatInput = document.getElementById('groupChatInput');
            if (groupChatInput) {
                const adjustGroupHeight = () => {
                    groupChatInput.style.height = 'auto';
                    groupChatInput.style.height = Math.min(groupChatInput.scrollHeight, 200) + 'px';
                };
                groupChatInput.addEventListener('input', adjustGroupHeight);
                setTimeout(adjustGroupHeight, 0);
            }
            document.getElementById('clearGroupChatBtn')?.addEventListener('click', () => app.clearGroupChat());

            window.addEventListener('resize', () => app.handleResize());
        },

        bindWorldviewEvents() {
            const app = this.app;
            const worldviewInput = document.getElementById('overlayWorldviewInput');
            const templateBtn = document.getElementById('worldviewTemplateBtn');
            const modalOverlay = document.getElementById('worldviewModalOverlay');
            const modalClose = document.getElementById('worldviewModalClose');
            const addBtn = document.getElementById('addWorldviewBtn');

            if (worldviewInput) {
                worldviewInput.addEventListener('change', () => {
                    app.saveWorldviewToConversation();
                });
            }

            if (templateBtn) {
                templateBtn.addEventListener('click', () => {
                    app.showWorldviewModal();
                });
            }

            if (modalClose && modalOverlay) {
                modalClose.addEventListener('click', () => {
                    modalOverlay.classList.remove('active');
                });
            }

            if (modalOverlay) {
                modalOverlay.addEventListener('click', (e) => {
                    if (e.target === modalOverlay) {
                        modalOverlay.classList.remove('active');
                    }
                });
            }

            if (addBtn) {
                addBtn.addEventListener('click', () => {
                    const name = document.getElementById('newWorldviewName')?.value.trim();
                    const content = document.getElementById('newWorldviewContent')?.value.trim();
                    if (name && content) {
                        WorldviewManager.add({ name, content });
                        app.renderWorldviewList();
                        document.getElementById('newWorldviewName').value = '';
                        document.getElementById('newWorldviewContent').value = '';
                        app.showToast('世界观添加成功', 'success');
                    } else {
                        app.showToast('请填写名称和内容', 'error');
                    }
                });
            }
        },

        bindSettingsEvents() {
            const app = this.app;
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
                    codeHighlight: document.getElementById('codeHighlight')?.checked || false,
                    codeWrap: document.getElementById('codeWrap')?.checked || false,
                    markdownAnchor: document.getElementById('markdownAnchor')?.checked !== false,
                    thinking: document.getElementById('thinking')?.checked !== false,
                    streamResponse: document.getElementById('streamResponse')?.checked !== false,
                    autoTitle: document.getElementById('autoTitle')?.checked !== false,
                    pasteImage: document.getElementById('pasteImage')?.checked !== false,
                    conversationMode: document.getElementById('conversationMode')?.value || 'single',
                    tokenStatsEnabled: document.getElementById('tokenStatsEnabled')?.checked || false,
                    autoEnterFullscreen: document.getElementById('autoEnterFullscreen')?.checked || false
                };
                localStorage.setItem('ollamaSettings', JSON.stringify(settings));
            };

            const settingsInputs = document.querySelectorAll('#settingsModal input, #settingsModal select, #settingsModal textarea, #settings-page input, #settings-page select, #settings-page textarea');
            settingsInputs.forEach(input => {
                input.addEventListener('change', saveSettings);
            });

            const conversationModeSelect = document.getElementById('conversationMode');
            if (conversationModeSelect) {
                conversationModeSelect.addEventListener('change', (e) => {
                    app.state.conversationMode = e.target.value;
                    if (e.target.value === 'group') {
                        document.getElementById('groupModeSettings')?.classList.remove('hidden');
                    } else {
                        document.getElementById('groupModeSettings')?.classList.add('hidden');
                    }
                });
            }

            document.querySelectorAll('.slider-container').forEach(sliderEl => {
                const valueEl = sliderEl.querySelector('.slider-value');
                const slider = sliderEl.querySelector('input[type="range"]');
                if (sliderEl && valueEl) {
                    slider.addEventListener('input', () => {
                        valueEl.textContent = slider.value;
                    });
                }
            });

            const tokenStatsEnabled = document.getElementById('tokenStatsEnabled');
            if (tokenStatsEnabled) {
                tokenStatsEnabled.addEventListener('change', (e) => {
                    const tokenStatsPanel = document.getElementById('tokenStatsPanel');
                    if (e.target.checked && tokenStatsPanel) {
                        tokenStatsPanel.classList.remove('hidden');
                        if (typeof ApiChat !== 'undefined') {
                            ApiChat.initTokenStats();
                        }
                    } else if (tokenStatsPanel) {
                        tokenStatsPanel.classList.add('hidden');
                    }
                });
            }

            const streamModeHint = document.getElementById('streamModeHint');
            if (streamModeHint) {
                streamModeHint.addEventListener('click', () => {
                    app.showParamGuide();
                });
            }

            const fontSizeSlider = document.querySelector('#fontSizeSlider input');
            if (fontSizeSlider) {
                fontSizeSlider.addEventListener('input', (e) => {
                    document.getElementById('fontSizeValue').textContent = e.target.value + 'px';
                    document.documentElement.style.setProperty('--font-size', e.target.value + 'px');
                });
            }

            const importExportBtn = document.getElementById('importExportBtn');
            const importExportMenu = document.getElementById('importExportMenu');
            if (importExportBtn && importExportMenu) {
                importExportBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    importExportMenu.classList.toggle('show');
                });
                document.addEventListener('click', () => {
                    importExportMenu.classList.remove('show');
                });
            }

            document.querySelectorAll('.settings-section h3').forEach(header => {
                header.addEventListener('click', () => {
                    const targetSection = header.nextElementSibling;
                    if (targetSection) {
                        targetSection.classList.toggle('collapsed');
                    }
                });
            });
        },

        bindPullModalEvents() {
            const app = this.app;
            const modal = document.getElementById('pullModalOverlay');
            const closeBtn = document.getElementById('pullModalClose');
            const cancelBtn = document.getElementById('pullCancelBtn');
            const confirmBtn = document.getElementById('pullConfirmBtn');
            const modelNameInput = document.getElementById('pullModelName');

            if (closeBtn && modal) {
                closeBtn.addEventListener('click', () => {
                    modal.classList.remove('active');
                });
            }

            if (cancelBtn && modal) {
                cancelBtn.addEventListener('click', () => {
                    modal.classList.remove('active');
                });
            }

            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.classList.remove('active');
                    }
                });
            }

            if (confirmBtn) {
                confirmBtn.addEventListener('click', async () => {
                    const modelName = modelNameInput?.value.trim();
                    if (!modelName) {
                        app.showToast('请输入模型名称', 'error');
                        return;
                    }

                    confirmBtn.disabled = true;
                    confirmBtn.textContent = '下载中...';

                    try {
                        await API.pullModel(modelName, (progress) => {
                            const progressBar = document.getElementById('pullProgressBar');
                            const progressText = document.getElementById('pullProgressText');
                            if (progressBar) {
                                progressBar.style.width = progress.percent + '%';
                            }
                            if (progressText) {
                                progressText.textContent = progress.status || '下载中...';
                            }
                        });

                        app.showToast('模型下载完成', 'success');
                        
                        // 确保新下载的模型未被禁用
                        if (window.Storage && typeof Storage.enableModel === 'function') {
                            Storage.enableModel(modelName);
                        }
                        
                        modal.classList.remove('active');
                        app.refreshAll();
                    } catch (error) {
                        app.showToast('下载失败: ' + error.message, 'error');
                    } finally {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = '下载';
                        const progressBar = document.getElementById('pullProgressBar');
                        const progressText = document.getElementById('pullProgressText');
                        if (progressBar) progressBar.style.width = '0%';
                        if (progressText) progressText.textContent = '';
                    }
                });
            }
        },

        hideModelTooltip() {
            const tooltip = document.getElementById('modelTooltip');
            if (tooltip) {
                tooltip.style.display = 'none';
            }
        },

        bindModalEvents() {
            const app = this.app;
            const overlay = document.getElementById('modalOverlay');
            const closeBtn = document.getElementById('modalClose');

            if (closeBtn && overlay) {
                closeBtn.addEventListener('click', () => {
                    overlay.classList.remove('active');
                });
            }

            if (overlay) {
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay) {
                        overlay.classList.remove('active');
                    }
                });
            }
        },

        bindParamGuideEvents() {
            const app = this.app;
            const guideOverlay = document.getElementById('paramGuideOverlay');
            const guideClose = document.getElementById('paramGuideClose');

            if (guideClose && guideOverlay) {
                guideClose.addEventListener('click', () => {
                    guideOverlay.classList.remove('active');
                });
            }

            if (guideOverlay) {
                guideOverlay.addEventListener('click', (e) => {
                    if (e.target === guideOverlay) {
                        guideOverlay.classList.remove('active');
                    }
                });
            }
        }
    };

    window.AppEvents = Events;
})();
