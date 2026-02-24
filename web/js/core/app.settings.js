/**
 * 设置模块
 * 应用设置管理功能
 */
(function() {
    const Settings = {
        init(app) {
            this.app = app;
        },

        loadSettings() {
            const app = this.app;
            const saved = localStorage.getItem('ollamaSettings');
            if (saved) {
                try {
                    const settings = JSON.parse(saved);
                    app.state.settings = { ...app.state.settings, ...settings };
                } catch (e) {
                    console.error('加载设置失败:', e);
                }
            }

            this.applySettings();
            this.populateSettingsForm();
        },

        applySettings() {
            const app = this.app;
            const settings = app.state.settings;

            if (settings.fontSize) {
                document.documentElement.style.setProperty('--font-size', settings.fontSize);
            }

            if (settings.theme) {
                ThemeManager.applyTheme(settings.theme);
            }
        },

        populateSettingsForm() {
            const app = this.app;
            const settings = app.state.settings;

            const apiUrl = document.getElementById('apiUrl');
            if (apiUrl) apiUrl.value = settings.apiUrl || `http://${window.location.hostname || 'localhost'}:11434`;

            const requestTimeout = document.getElementById('requestTimeout');
            if (requestTimeout) requestTimeout.value = settings.requestTimeout || 120;

            const maxTokens = document.getElementById('maxTokens');
            if (maxTokens) maxTokens.value = settings.maxTokens || 2048;

            const temperature = document.getElementById('temperature');
            if (temperature) temperature.value = settings.temperature || 0.7;

            const contextLength = document.getElementById('contextLength');
            if (contextLength) contextLength.value = settings.contextLength || 4096;

            const topK = document.getElementById('topK');
            if (topK) topK.value = settings.topK || 40;

            const topP = document.getElementById('topP');
            if (topP) topP.value = settings.topP || 0.9;

            const repeatPenalty = document.getElementById('repeatPenalty');
            if (repeatPenalty) repeatPenalty.value = settings.repeatPenalty || 1.1;

            const streamResponse = document.getElementById('streamResponse');
            if (streamResponse) streamResponse.checked = settings.streamResponse !== false;

            const autoTitle = document.getElementById('autoTitle');
            if (autoTitle) autoTitle.checked = settings.autoTitle !== false;

            const pasteImage = document.getElementById('pasteImage');
            if (pasteImage) pasteImage.checked = settings.pasteImage !== false;

            const thinking = document.getElementById('thinking');
            if (thinking) thinking.checked = settings.thinking !== false;

            const tokenStatsEnabled = document.getElementById('tokenStatsEnabled');
            if (tokenStatsEnabled) tokenStatsEnabled.checked = settings.tokenStatsEnabled || false;
            
            this.renderDisabledModels();
        },

        renderDisabledModels() {
            const list = document.getElementById('disabledModelsList');
            if (!list) return;
            
            const disabled = Storage.getDisabledModels();
            
            if (disabled.length === 0) {
                list.innerHTML = '<div class="empty-text">暂无已禁用模型</div>';
                return;
            }
            
            list.innerHTML = '';
            disabled.forEach(modelName => {
                const chip = document.createElement('div');
                chip.className = 'model-chip disabled';
                chip.textContent = modelName;
                chip.title = '点击启用此模型';
                
                chip.addEventListener('click', () => {
                    if (confirm(`确定要重新启用模型 "${modelName}" 吗？`)) {
                        Storage.enableModel(modelName);
                        this.renderDisabledModels();
                        this.app.showToast(`已启用模型: ${modelName}`, 'success');
                        // 刷新主界面模型列表
                        if (this.app.loadModels) {
                            this.app.loadModels();
                        }
                    }
                });
                
                list.appendChild(chip);
            });
        },

        saveSettings() {
            const app = this.app;

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
                tokenStatsEnabled: document.getElementById('tokenStatsEnabled')?.checked || false
            };

            app.state.settings = settings;
            localStorage.setItem('ollamaSettings', JSON.stringify(settings));

            this.applySettings();
            app.showToast('设置已保存', 'success');
        },

        resetSettings() {
            const app = this.app;
            const defaultSettings = {
                apiUrl: 'http://localhost:11434',
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
                codeHighlight: false,
                codeWrap: false,
                markdownAnchor: true,
                thinking: true,
                streamResponse: true,
                autoTitle: true,
                pasteImage: true,
                conversationMode: 'single',
                tokenStatsEnabled: false
            };

            app.state.settings = defaultSettings;
            localStorage.setItem('ollamaSettings', JSON.stringify(defaultSettings));

            this.populateSettingsForm();
            this.applySettings();
            app.showToast('设置已重置', 'success');
        },

        showSettingsModal() {
            const app = this.app;
            let modal = document.getElementById('settingsModal');

            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'settingsModal';
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content settings-modal">
                        <div class="modal-header">
                            <h3>⚙️ 设置</h3>
                            <button class="modal-close" id="settingsModalClose">&times;</button>
                        </div>
                        <div class="modal-body">
                            <div class="settings-tabs">
                                <button class="settings-tab active" data-tab="general">常规</button>
                                <button class="settings-tab" data-tab="model">模型</button>
                                <button class="settings-tab" data-tab="appearance">外观</button>
                                <button class="settings-tab" data-tab="advanced">高级</button>
                            </div>
                            <div class="settings-content">
                                <div class="settings-panel active" id="generalPanel">
                                    <div class="form-group">
                                        <label for="apiUrl">API 地址</label>
                                        <input type="text" id="apiUrl" value="http://localhost:11434">
                                    </div>
                                    <div class="form-group">
                                        <label for="requestTimeout">请求超时（秒）</label>
                                        <input type="number" id="requestTimeout" value="120" min="10" max="600">
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="streamResponse" checked>
                                            流式响应
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="autoTitle" checked>
                                            自动生成对话标题
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="pasteImage" checked>
                                            允许粘贴图片
                                        </label>
                                    </div>
                                </div>
                                <div class="settings-panel" id="modelPanel">
                                    <div class="form-group">
                                        <label for="maxTokens">最大输出长度</label>
                                        <input type="number" id="maxTokens" value="2048" min="128" max="32768">
                                    </div>
                                    <div class="form-group">
                                        <label for="temperature">温度</label>
                                        <input type="range" id="temperature" min="0" max="2" step="0.1" value="0.7">
                                        <span class="range-value" id="temperatureValue">0.7</span>
                                    </div>
                                    <div class="form-group">
                                        <label for="contextLength">上下文长度</label>
                                        <input type="number" id="contextLength" value="4096" min="512" max="32768">
                                    </div>
                                    <div class="form-group">
                                        <label for="topK">Top K</label>
                                        <input type="number" id="topK" value="40" min="1" max="100">
                                    </div>
                                    <div class="form-group">
                                        <label for="topP">Top P</label>
                                        <input type="range" id="topP" min="0" max="1" step="0.05" value="0.9">
                                        <span class="range-value" id="topPValue">0.9</span>
                                    </div>
                                    <div class="form-group">
                                        <label for="repeatPenalty">重复惩罚</label>
                                        <input type="range" id="repeatPenalty" min="1" max="2" step="0.05" value="1.1">
                                        <span class="range-value" id="repeatPenaltyValue">1.1</span>
                                    </div>
                                    
                                    <div class="settings-divider"></div>
                                    
                                    <div class="form-group">
                                        <label>已禁用的模型</label>
                                        <div class="disabled-models-list" id="disabledModelsList">
                                            <!--Disabled models will be rendered here-->
                                            <div class="empty-text">暂无已禁用模型</div>
                                        </div>
                                        <p class="help-text">点击模型名称以重新启用并在列表中显示。</p>
                                    </div>
                                </div>
                                <div class="settings-panel" id="appearancePanel">
                                    <div class="form-group">
                                        <label for="fontSize">字体大小</label>
                                        <select id="fontSize">
                                            <option value="14px">小 (14px)</option>
                                            <option value="16px" selected>中 (16px)</option>
                                            <option value="18px">大 (18px)</option>
                                            <option value="20px">特大 (20px)</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="codeHighlight">
                                            代码高亮
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="codeWrap">
                                            代码自动换行
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="markdownAnchor" checked>
                                            Markdown 锚点
                                        </label>
                                    </div>
                                </div>
                                <div class="settings-panel" id="advancedPanel">
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="thinking" checked>
                                            启用思考模式
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label>
                                            <input type="checkbox" id="tokenStatsEnabled">
                                            启用 Token 统计
                                        </label>
                                    </div>
                                    <div class="form-group">
                                        <label for="conversationMode">对话模式</label>
                                        <select id="conversationMode">
                                            <option value="single">单模型</option>
                                            <option value="group">群组对话</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" id="resetSettingsBtn">重置</button>
                            <button class="btn btn-primary" id="saveSettingsBtn">保存</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);

                modal.querySelector('#settingsModalClose').addEventListener('click', () => {
                    modal.classList.remove('active');
                });

                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.classList.remove('active');
                    }
                });

                modal.querySelectorAll('.settings-tab').forEach(tab => {
                    tab.addEventListener('click', () => {
                        modal.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
                        modal.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
                        tab.classList.add('active');
                        const panel = document.getElementById(tab.dataset.tab + 'Panel');
                        if (panel) panel.classList.add('active');
                    });
                });

                modal.querySelector('#saveSettingsBtn').addEventListener('click', () => {
                    this.saveSettings();
                    modal.classList.remove('active');
                });

                modal.querySelector('#resetSettingsBtn').addEventListener('click', () => {
                    this.resetSettings();
                });

                const temperatureSlider = document.getElementById('temperature');
                const temperatureValue = document.getElementById('temperatureValue');
                if (temperatureSlider && temperatureValue) {
                    temperatureSlider.addEventListener('input', () => {
                        temperatureValue.textContent = temperatureSlider.value;
                    });
                }

                const topPSlider = document.getElementById('topP');
                const topPValue = document.getElementById('topPValue');
                if (topPSlider && topPValue) {
                    topPSlider.addEventListener('input', () => {
                        topPValue.textContent = topPSlider.value;
                    });
                }

                const repeatPenaltySlider = document.getElementById('repeatPenalty');
                const repeatPenaltyValue = document.getElementById('repeatPenaltyValue');
                if (repeatPenaltySlider && repeatPenaltyValue) {
                    repeatPenaltySlider.addEventListener('input', () => {
                        repeatPenaltyValue.textContent = repeatPenaltySlider.value;
                    });
                }
            }

            this.populateSettingsForm();
            modal.classList.add('active');
        },

        hideSettingsModal() {
            const modal = document.getElementById('settingsModal');
            if (modal) {
                modal.classList.remove('active');
            }
        }
    };

    window.AppSettings = Settings;
})();
