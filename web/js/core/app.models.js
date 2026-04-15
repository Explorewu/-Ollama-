/**
 * 模型管理模块
 * 模型加载、渲染、筛选等功能
 */
(function() {
    const Models = {
        init(app) {
            this.app = app;
        },

        async loadModels() {
            console.log('[AppModels.loadModels] 开始执行，this.app =', this.app);
            console.log('[AppModels.loadModels] API 对象存在吗？', typeof API !== 'undefined');
            console.log('[AppModels.loadModels] window.API 存在吗？', typeof window.API !== 'undefined');
            
            const app = this.app;
            
            // 检查 app 是否已正确初始化
            if (!app) {
                console.error('[错误] AppModels 未初始化，无法加载模型');
                return;
            }
            
            // 检查 API 对象是否存在
            if (typeof API === 'undefined') {
                console.error('[错误] API 对象未定义，无法加载模型');
                console.error('[调试] 当前全局对象:', Object.keys(window).filter(k => k.includes('API')));
                return;
            }
            
            const grid = document.getElementById('modelsGrid');

            try {
                // 获取所有模型（包括未下载的）
                console.log('[AppModels.loadModels] 准备调用 API.getAllModels()');
                const allModels = await API.getAllModels();
                console.log('[AppModels.loadModels] API 调用成功，模型数量:', allModels.length);
                app.state.allModels = allModels;
                
                // 获取已下载且可运行的模型
                const downloadedModels = allModels.filter(m => m.isDownloaded && m.runnable);
                app.state.installedModels = downloadedModels;

                const settingsModelSelect = document.getElementById('modelSelectNew');
                if (settingsModelSelect) {
                    this.updateSettingsModelSelect(downloadedModels);
                }

                this.renderModelCards(allModels);

                // 模型加载完成后，重新设置默认模型选择
                if (!app.state.selectedModel || app.state.selectedModel === 'literary-super:latest') {
                    app.selectDefaultModel();
                }

            } catch (error) {
                console.error('加载模型失败:', error);
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">⚠️</div>
                        <h3>无法连接到 Ollama 服务</h3>
                        <p>请确保 Ollama 正在运行（默认地址: http://${window.location.hostname || 'localhost'}:11434）</p>
                        <div class="empty-state-actions">
                            <button class="btn btn-primary" onclick="App.refreshAll()">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M23 4v6h-6"/>
                                    <path d="M1 20v-6h6"/>
                                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                                </svg>
                                重新加载
                            </button>
                            <button class="btn btn-secondary" onclick="App.autoStartService()">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M12 2v4"/>
                                    <path d="M12 18v4"/>
                                    <path d="M4.93 4.93l2.83 2.83"/>
                                    <path d="M16.24 16.24l2.83 2.83"/>
                                    <path d="M2 12h4"/>
                                    <path d="M18 12h4"/>
                                    <path d="M4.93 19.07l2.83-2.83"/>
                                    <path d="M16.24 7.76l2.83-2.83"/>
                                </svg>
                                自动启动服务
                            </button>
                        </div>
                    </div>
                `;
                app.updateServiceStatus(false);
            }
        },

        updateSettingsModelSelect(models) {
            const app = this.app;
            const select = document.getElementById('modelSelectNew');
            if (!select) return;

            const currentValue = select.value;

            const disabledModels = Storage.getDisabledModels();
            const enabledModels = models.filter(model => !disabledModels.includes(model.name));
            const runnableModels = enabledModels.filter(model => model.runnable);

            select.innerHTML = '<option value="">选择模型...</option>';

            runnableModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.name;
                select.appendChild(option);
            });

            if (currentValue && runnableModels.find(m => m.name === currentValue)) {
                select.value = currentValue;
                app.state.selectedModel = currentValue;
            } else if (runnableModels.length > 0) {
                select.value = runnableModels[0].name;
                app.state.selectedModel = runnableModels[0].name;
            }

            const modelCountEl = document.getElementById('modelCount');
            if (modelCountEl) {
                modelCountEl.textContent = `${runnableModels.length}/${models.length}`;
            }
        },

        renderModelCards(models) {
            const app = this.app;
            const grid = document.getElementById('modelsGrid');

            const disabledModels = Storage.getDisabledModels();
            const enabledModels = models.filter(model => !disabledModels.includes(model.name));
            const runnableModels = enabledModels.filter(model => model.runnable);

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

            const sortedModels = [...enabledModels].sort((a, b) => {
                if (a.name.includes('literary-super')) return -1;
                if (b.name.includes('literary-super')) return 1;
                if (a.name.includes('literary-assistant')) return -1;
                if (b.name.includes('literary-assistant')) return 1;
                return 0;
            });
            
            grid.innerHTML = sortedModels.map(model => {
                const icon = '🤖';
                const isDownloaded = model.isDownloaded !== false;
                const isRunnable = model.runnable !== false;
                const statusText = isRunnable ? (isDownloaded ? '可直接使用' : '已注册') : '需要注册';
                const statusClass = isRunnable ? (isDownloaded ? 'status-downloaded' : 'status-registered') : 'status-locked';
                const description = isRunnable
                    ? '点击使用此模型进行对话，或删除模型以释放空间。'
                    : '需要先通过 Ollama 注册才可运行该模型。';

                const downloadButton = !isDownloaded ? `
                    <button class="btn btn-download" onclick="AppModels.downloadModel('${model.name}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        下载
                    </button>
                ` : '';
                
                return `
                <div class="model-card ${isDownloaded ? '' : 'not-downloaded'}" data-model="${model.name}">
                    <div class="model-card-header">
                        <div class="model-icon-large">${icon}</div>
                        <div class="model-info">
                            <div class="model-name">${model.name}</div>
                            <div class="model-status ${statusClass}">
                                <span class="status-dot"></span>
                                ${statusText}
                            </div>
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
                        <div class="model-meta">
                            <span class="provider">${model.provider ? model.provider.toUpperCase() : 'OLLAMA'}</span>
                            <span class="source">${model.source || 'ollama'}</span>
                        </div>
                    </div>
                    <div class="model-actions">
                        ${downloadButton}
                        ${isDownloaded && isRunnable ? `
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
                        ` : ''}
                    </div>
                </div>
            `}).join('');
        },

        filterModels(query = '', filter = 'all') {
            const cards = document.querySelectorAll('.model-card');
            const lowercaseQuery = query.toLowerCase();

            cards.forEach(card => {
                const modelName = card.dataset.model.toLowerCase();
                const isDownloaded = !card.classList.contains('not-downloaded');
                const matchesQuery = modelName.includes(lowercaseQuery);
                
                // 筛选逻辑
                let matchesFilter = true;
                if (filter === 'downloaded') {
                    matchesFilter = isDownloaded;
                } else if (filter === 'not-downloaded') {
                    matchesFilter = !isDownloaded;
                }
                // 'all' 显示所有
                
                card.style.display = matchesQuery && matchesFilter ? '' : 'none';
            });
        },

        useModel(modelName) {
            const app = this.app;
            app.switchPage('chat');
            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) {
                modelSelect.value = modelName;
                app.state.selectedModel = modelName;
            }
        },

        async deleteModel(modelName) {
            const app = this.app;
            if (!confirm(`确定要删除模型 "${modelName}" 吗？删除后需要重新下载。`)) {
                return;
            }

            try {
                app.showToast('正在删除模型...', 'info');
                await API.deleteModel(modelName);
                app.showToast('模型已删除', 'success');
                await this.loadModels();
            } catch (error) {
                app.showToast(`删除失败: ${error.message}`, 'error');
            }
        },

        async downloadModel(modelName) {
            const app = this.app;
            
            try {
                app.showToast(`开始下载模型: ${modelName}`, 'info');
                
                await API.pullModel(modelName, (progress) => {
                    const status = progress.status || '下载中...';
                    const percent = progress.percent || 0;
                    
                    console.log(`下载进度: ${percent}% - ${status}`);
                    
                    if (progress.total > 0 && progress.completed > 0) {
                        app.showToast(`下载中: ${percent}%`, 'info');
                    }
                });

                app.showToast(`模型下载完成: ${modelName}`, 'success');
                await this.loadModels();
            } catch (error) {
                console.error('下载模型失败:', error);
                app.showToast(`下载失败: ${error.message}`, 'error');
            }
        },

        openPullModal() {
            const app = this.app;
            let modal = document.getElementById('pullModalOverlay');

            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'pullModalOverlay';
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3>下载新模型</h3>
                            <button class="modal-close" id="pullModalClose">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="form-group">
                                <label for="pullModelName">模型名称</label>
                                <input type="text" id="pullModelName" placeholder="例如: llama2, mistral, codellama">
                            </div>
                            <div class="form-group">
                                <label>常用模型</label>
                                <div class="quick-models">
                                    <button class="quick-model-btn" data-model="llama2">llama2</button>
                                    <button class="quick-model-btn" data-model="mistral">mistral</button>
                                    <button class="quick-model-btn" data-model="codellama">codellama</button>
                                    <button class="quick-model-btn" data-model="qwen2.5:7b">qwen2.5:7b</button>
                                </div>
                            </div>
                            <div class="progress-container" id="pullProgressContainer" style="display: none;">
                                <div class="progress-bar">
                                    <div class="progress-fill" id="pullProgressBar"></div>
                                </div>
                                <div class="progress-text" id="pullProgressText"></div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" id="pullCancelBtn">取消</button>
                            <button class="btn btn-primary" id="pullConfirmBtn">下载</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);

                modal.querySelector('#pullModalClose').addEventListener('click', () => {
                    modal.classList.remove('active');
                });

                modal.querySelector('#pullCancelBtn').addEventListener('click', () => {
                    modal.classList.remove('active');
                });

                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.classList.remove('active');
                    }
                });

                modal.querySelectorAll('.quick-model-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        document.getElementById('pullModelName').value = btn.dataset.model;
                    });
                });

                modal.querySelector('#pullConfirmBtn').addEventListener('click', async () => {
                    const modelName = document.getElementById('pullModelName').value.trim();
                    if (!modelName) {
                        app.showToast('请输入模型名称', 'error');
                        return;
                    }

                    const confirmBtn = modal.querySelector('#pullConfirmBtn');
                    const progressContainer = document.getElementById('pullProgressContainer');
                    
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = '下载中...';
                    progressContainer.style.display = 'block';

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
                        modal.classList.remove('active');
                        await this.loadModels();
                    } catch (error) {
                        app.showToast(`下载失败: ${error.message}`, 'error');
                    } finally {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = '下载';
                        progressContainer.style.display = 'none';
                        document.getElementById('pullProgressBar').style.width = '0%';
                    }
                });
            }

            modal.classList.add('active');
            document.getElementById('pullModelName').value = '';
            document.getElementById('pullModelName').focus();
            
            // 设置默认选中的推荐模型
            const recommendedModels = ['qwen2.5:7b', 'llama2', 'mistral'];
            const installedModelNames = app.state.installedModels?.map(m => m.name) || [];
            
            // 选择第一个未安装的推荐模型作为默认值
            const defaultModel = recommendedModels.find(model => 
                !installedModelNames.includes(model)
            ) || recommendedModels[0];
            
            if (defaultModel) {
                document.getElementById('pullModelName').value = defaultModel;
            }
        }
    };

    window.AppModels = Models;
})();
