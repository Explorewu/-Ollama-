(function(global) {
    'use strict';

    const FunctionManager = {
        get API_BASE() {
            if (window.location.protocol === 'file:') {
                return 'http://localhost:5001/api';
            }
            const host = window.location.hostname || 'localhost';
            return `http://${host}:5001/api`;
        },

        state: {
            functions: [],
            history: [],
            searchResults: [],
            currentSearch: null,
            executing: false
        },

        cache: {
            functions: null,
            history: null
        },

        async init() {
            try {
                await this.loadFunctions();
                await this.loadHistory();
                this.bindEvents();
                this.setupChatIntegration();
                console.log('[FunctionManager] 初始化完成');
            } catch (error) {
                console.error('[FunctionManager] 初始化失败:', error);
            }
        },

        async loadFunctions() {
            try {
                const apiKey = await this.getApiKey();
                const response = await fetch(`${this.API_BASE}/functions/list`, {
                    headers: {
                        'Authorization': `Bearer ${apiKey}`
                    }
                });

                const data = await response.json();

                if (data.success) {
                    this.state.functions = data.data.functions;
                    this.cache.functions = data.data.functions;
                    this.renderFunctionsPanel();
                } else {
                    console.error('[FunctionManager] 加载函数列表失败:', data.error);
                }
            } catch (error) {
                console.error('[FunctionManager] 加载函数失败:', error);
            }
        },

        async loadHistory() {
            try {
                const apiKey = await this.getApiKey();
                const response = await fetch(`${this.API_BASE}/functions/history`, {
                    headers: {
                        'Authorization': `Bearer ${apiKey}`
                    }
                });

                const data = await response.json();

                if (data.success) {
                    this.state.history = data.data.history;
                    this.cache.history = data.data.history;
                    this.renderHistoryPanel();
                }
            } catch (error) {
                console.error('[FunctionManager] 加载历史失败:', error);
            }
        },

        async getApiKey() {
            if (this._apiKey) {
                return this._apiKey;
            }

            try {
                const response = await fetch(`${this.API_BASE}/api-key/list`);
                const data = await response.json();

                if (data.success && data.data.length > 0) {
                    this._apiKey = data.data[0].key;
                    return this._apiKey;
                }
            } catch (e) {
                console.warn('[FunctionManager] 获取 API Key 失败');
            }

            return '';
        },

        async executeFunction(functionName, params, requireConfirmation = false) {
            if (this.state.executing) {
                this.showToast('有函数正在执行中，请稍候...', 'warning');
                return null;
            }

            try {
                const apiKey = await this.getApiKey();
                this.state.executing = true;
                this.showExecutingIndicator(functionName, true);

                const response = await fetch(`${this.API_BASE}/functions/execute`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        function: functionName,
                        arguments: params,
                        require_confirmation: requireConfirmation
                    })
                });

                const data = await response.json();

                if (data.success) {
                    this.showToast(`函数 "${functionName}" 执行成功`, 'success');
                    await this.loadHistory();
                    return data.result;
                } else {
                    if (data.require_confirmation) {
                        this.showConfirmationDialog(data);
                        return { needs_confirmation: true, data };
                    }
                    this.showToast(data.error || '函数执行失败', 'error');
                    return null;
                }
            } catch (error) {
                console.error('[FunctionManager] 执行函数失败:', error);
                this.showToast('函数执行失败，请稍后重试', 'error');
                return null;
            } finally {
                this.state.executing = false;
                this.showExecutingIndicator(functionName, false);
            }
        },

        async searchWeb(query, maxResults = 10) {
            try {
                const apiKey = await this.getApiKey();
                this.showToast(`正在搜索: ${query}`, 'info');

                const response = await fetch(`${this.API_BASE}/search/web`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        query: query,
                        max_results: maxResults
                    })
                });

                const data = await response.json();

                if (data.success) {
                    this.state.searchResults = data.results || [];
                    this.state.currentSearch = query;
                    this.renderSearchResults(query, data);
                    this.showToast(`找到 ${data.total_count || 0} 条结果`, 'success');
                    return data;
                } else {
                    this.showToast(data.error || '搜索失败', 'error');
                    return null;
                }
            } catch (error) {
                console.error('[FunctionManager] 搜索失败:', error);
                this.showToast('搜索失败，请稍后重试', 'error');
                return null;
            }
        },

        async getInstantAnswer(question) {
            try {
                const apiKey = await this.getApiKey();

                const response = await fetch(`${this.API_BASE}/search/instant`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify({
                        question: question
                    })
                });

                const data = await response.json();

                if (data.success) {
                    return data.answer || data.definition || '';
                }
                return null;
            } catch (error) {
                console.error('[FunctionManager] 获取即时答案失败:', error);
                return null;
            }
        },

        bindEvents() {
            const searchForm = document.getElementById('webSearchForm');
            if (searchForm) {
                searchForm.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const input = document.getElementById('webSearchInput');
                    const query = input?.value?.trim();
                    if (query) {
                        await this.searchWeb(query);
                    }
                });
            }
        },

        setupChatIntegration() {
            const chatInput = document.getElementById('chatInput') || document.getElementById('messageInput');

            if (chatInput) {
                chatInput.addEventListener('keydown', async (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        const message = chatInput.value.trim();

                        if (this.isFunctionCallIntent(message)) {
                            e.preventDefault();
                            await this.handleFunctionCallFromChat(message);
                        }
                    }
                });
            }
        },

        isFunctionCallIntent(message) {
            const intentPatterns = [
                /^搜索\s+(.+)/,
                /^找\s+(.+)/,
                /^查询\s+(.+)/,
                /^(现在|今天|明天|昨天)\s+(.+)/,
                /^(.+?)\s+是多少/,
                /^播放\s+(.+)/
            ];

            return intentPatterns.some(pattern => pattern.test(message));
        },

        async handleFunctionCallFromChat(message) {
            const timeMatch = message.match(/^(现在|今天|明天|昨天|后天)\s*(.*)/);
            if (timeMatch) {
                const [, timeWord] = timeMatch;

                if (['现在', '今天'].includes(timeWord)) {
                    await this.executeFunction('get_current_time', { format_type: 'full' });
                    return;
                } else if (timeWord === '明天') {
                    await this.executeFunction('add_days', { days: 1 });
                    return;
                } else if (timeWord === '后天') {
                    await this.executeFunction('add_days', { days: 2 });
                    return;
                } else if (timeWord === '昨天') {
                    await this.executeFunction('add_days', { days: -1 });
                    return;
                }
            }

            const searchMatch = message.match(/^(搜索|找|查询)\s+(.+)/);
            if (searchMatch) {
                const [, , query] = searchMatch;
                await this.searchWeb(query);
                return;
            }

            const playMatch = message.match(/^播放\s+(.+)/);
            if (playMatch) {
                const [, target] = playMatch;
                await this.executeFunction('play_music', { query: target });
                return;
            }
        },

        renderFunctionsPanel() {
            const container = document.getElementById('functionList');
            if (!container) return;

            const categories = {
                time: { name: '时间日期', icon: '🕐', color: '#7eb5a6' },
                media: { name: '媒体控制', icon: '🎵', color: '#d4c5a3' },
                search: { name: '网络搜索', icon: '🔍', color: '#a8c8ba' },
                utility: { name: '实用工具', icon: '🛠️', color: '#c9a8a8' }
            };

            const grouped = {};
            this.state.functions.forEach(func => {
                const cat = func.category || 'utility';
                if (!grouped[cat]) {
                    grouped[cat] = [];
                }
                grouped[cat].push(func);
            });

            let html = '';

            for (const [cat, funcs] of Object.entries(grouped)) {
                const catInfo = categories[cat] || { name: cat, icon: '📦', color: '#999' };

                html += `
                    <div class="function-category">
                        <div class="category-header" style="border-left-color: ${catInfo.color}">
                            <span class="category-icon">${catInfo.icon}</span>
                            <span class="category-name">${catInfo.name}</span>
                        </div>
                        <div class="category-functions">
                            ${funcs.map(func => this.renderFunctionItem(func)).join('')}
                        </div>
                    </div>
                `;
            }

            container.innerHTML = html;
        },

        renderFunctionItem(func) {
            const params = func.parameters || [];
            const paramStr = params.map(p =>
                `${p.required ? '*' : ''}${p.name}: ${p.type}`
            ).join(', ');

            return `
                <div class="function-item" data-function="${func.name}">
                    <div class="function-header">
                        <span class="function-name">${func.name}</span>
                        <span class="function-badge">${func.category}</span>
                    </div>
                    <div class="function-description">${func.description}</div>
                    ${paramStr ? `<div class="function-params">参数: ${paramStr}</div>` : ''}
                    <div class="function-actions">
                        <button class="btn btn-sm btn-secondary" onclick="FunctionManager.showExecuteDialog('${func.name}')">
                            执行
                        </button>
                    </div>
                </div>
            `;
        },

        async showExecuteDialog(functionName) {
            const func = this.state.functions.find(f => f.name === functionName);
            if (!func) return;

            const params = func.parameters || [];

            let formHtml = '';
            params.forEach(param => {
                const required = param.required ? 'required' : '';
                const placeholder = param.description;

                if (param.type === 'boolean') {
                    formHtml += `
                        <div class="form-group">
                            <label>
                                <input type="checkbox" name="${param.name}" ${required}>
                                ${param.name} (${param.description})
                            </label>
                        </div>
                    `;
                } else {
                    formHtml += `
                        <div class="form-group">
                            <label for="param_${param.name}">${param.name} ${required ? '*' : ''}</label>
                            <input type="text"
                                   id="param_${param.name}"
                                   name="${param.name}"
                                   class="text-input"
                                   placeholder="${placeholder}"
                                   ${required}>
                        </div>
                    `;
                }
            });

            if (params.length === 0) {
                formHtml = '<p class="no-params">此函数无需参数</p>';
            }

            const dialogHtml = `
                <div class="modal-overlay active" id="executeFunctionModal">
                    <div class="modal-container">
                        <div class="modal-header">
                            <h3>执行函数: ${functionName}</h3>
                            <button class="modal-close" onclick="FunctionManager.closeModal('executeFunctionModal')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                        <div class="modal-body">
                            <p class="function-desc">${func.description}</p>
                            <form id="executeFunctionForm">
                                ${formHtml}
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" onclick="FunctionManager.closeModal('executeFunctionModal')">取消</button>
                            <button class="btn btn-primary" onclick="FunctionManager.submitExecute('${functionName}')">执行</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', dialogHtml);
        },

        async submitExecute(functionName) {
            const form = document.getElementById('executeFunctionForm');
            if (!form) return;

            const formData = new FormData(form);
            const params = {};

            this.state.functions.find(f => f.name === functionName)?.parameters?.forEach(param => {
                const value = formData.get(param.name);

                if (param.type === 'integer') {
                    params[param.name] = parseInt(value) || 0;
                } else if (param.type === 'number') {
                    params[param.name] = parseFloat(value) || 0;
                } else if (param.type === 'boolean') {
                    params[param.name] = form.querySelector(`[name="${param.name}"]`)?.checked || false;
                } else {
                    params[param.name] = value || '';
                }
            });

            this.closeModal('executeFunctionModal');

            const result = await this.executeFunction(functionName, params);

            if (result) {
                this.showResultDialog(functionName, result);
            }
        },

        showConfirmationDialog(data) {
            const dialogHtml = `
                <div class="modal-overlay active" id="confirmFunctionModal">
                    <div class="modal-container">
                        <div class="modal-header">
                            <h3>确认执行</h3>
                            <button class="modal-close" onclick="FunctionManager.closeModal('confirmFunctionModal')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                        <div class="modal-body">
                            <div class="warning-message">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
                                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                    <line x1="12" y1="9" x2="12" y2="13"/>
                                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                                </svg>
                                <span>此函数需要确认后才能执行</span>
                            </div>
                            <p><strong>函数:</strong> ${data.function}</p>
                            <p><strong>描述:</strong> ${data.description}</p>
                            <p><strong>参数:</strong> ${JSON.stringify(data.arguments)}</p>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" onclick="FunctionManager.closeModal('confirmFunctionModal')">取消</button>
                            <button class="btn btn-danger" onclick="FunctionManager.confirmExecute()">确认执行</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', dialogHtml);
            this.pendingConfirm = data;
        },

        async confirmExecute() {
            if (!this.pendingConfirm) return;

            const { function: functionName, arguments: paramsData } = this.pendingConfirm;

            this.closeModal('confirmFunctionModal');
            const result = await this.executeFunction(functionName, paramsData, true);

            if (result) {
                this.showResultDialog(functionName, result);
            }

            this.pendingConfirm = null;
        },

        showResultDialog(functionName, result) {
            const resultHtml = `
                <div class="modal-overlay active" id="functionResultModal">
                    <div class="modal-container">
                        <div class="modal-header">
                            <h3>执行结果: ${functionName}</h3>
                            <button class="modal-close" onclick="FunctionManager.closeModal('functionResultModal')">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                        <div class="modal-body">
                            <pre class="result-json">${JSON.stringify(result, null, 2)}</pre>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-primary" onclick="FunctionManager.closeModal('functionResultModal')">关闭</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', resultHtml);
        },

        renderSearchResults(query, data) {
            const container = document.getElementById('searchResults');
            if (!container) return;

            const results = data.results || [];
            const answer = data.answer;

            let html = '';

            if (answer) {
                html += `
                    <div class="instant-answer">
                        <div class="answer-label">答案</div>
                        <div class="answer-content">${escapeHtml(answer)}</div>
                    </div>
                `;
            }

            if (results.length > 0) {
                html += `
                    <div class="results-list">
                        <div class="results-header">
                            <span>找到 ${results.length} 条结果</span>
                        </div>
                        ${results.map((result, index) => `
                            <div class="search-result-item">
                                <div class="result-number">${index + 1}</div>
                                <div class="result-content">
                                    <a href="${escapeHtml(result.url)}" target="_blank" class="result-title">${escapeHtml(result.title || '无标题')}</a>
                                    <div class="result-description">${escapeHtml(result.description || '')}</div>
                                    <div class="result-url">${escapeHtml(result.url || '')}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else if (!answer) {
                html = '<div class="no-results">未找到相关结果</div>';
            }

            container.innerHTML = html;
            container.style.display = 'block';
        },

        renderHistoryPanel() {
            const container = document.getElementById('functionHistory');
            if (!container) return;

            const history = this.state.history.slice(-20).reverse();

            if (history.length === 0) {
                container.innerHTML = '<div class="empty-history">暂无执行记录</div>';
                return;
            }

            container.innerHTML = history.map(item => `
                <div class="history-item ${item.status}">
                    <div class="history-function">${item.function}</div>
                    <div class="history-time">${formatTime(item.timestamp)}</div>
                    <div class="history-status ${item.status}">
                        ${item.status === 'success' ? '✓' : item.status === 'error' ? '✗' : '...'}
                    </div>
                </div>
            `).join('');
        },

        showExecutingIndicator(functionName, show) {
            const indicator = document.getElementById('functionExecutingIndicator');
            if (indicator) {
                indicator.style.display = show ? 'flex' : 'none';
                const el = indicator.querySelector('.executing-function');
                if (el) el.textContent = `正在执行: ${functionName}`;
            }
        },

        closeModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('active');
                setTimeout(() => modal.remove(), 300);
            }
        },

        showToast(message, type = 'info') {
            if (typeof App !== 'undefined' && App.showToast) {
                App.showToast(message, type);
            } else {
                console.log(`[${type.toUpperCase()}] ${message}`);
            }
        }
    };

    const SkillManager = {
        _initialized: false,

        get API_BASE() {
            if (window.location.protocol === 'file:') {
                return 'http://localhost:5001/api';
            }
            const host = window.location.hostname || 'localhost';
            return `${window.location.protocol}//${host}:5001/api`;
        },

        state: {
            skills: [],
            stats: {},
            evolutionLog: [],
            governanceLog: [],
            retrieverStats: {},
            teachingMode: false,
            loadError: null,
            searchQuery: '',
            activeFilter: 'all',
            teachStep: 1
        },

        async init() {
            if (this._initialized) return;
            this.state.loadError = null;
            this.renderSkeleton();
            await this.loadSkills();
            await this.loadRetrieverStats();
            await this.loadEvolutionLog();
            await this.loadGovernanceLog();
            this.renderSkillPanel();
            this.bindSkillEvents();
            this._initialized = true;
        },

        async loadSkills() {
            try {
                console.log('[SkillManager] 请求技能列表:', `${this.API_BASE}/skills/list?details=true`);
                const resp = await fetch(`${this.API_BASE}/skills/list?details=true`);
                const data = await resp.json();
                console.log('[SkillManager] 响应:', data);
                if (data.success) {
                    this.state.skills = data.data.skills;
                    this.state.stats = data.data.stats;
                } else {
                    this.state.loadError = data.message || '加载技能列表失败';
                }
            } catch (e) {
                console.warn('[SkillManager] 加载技能列表失败:', e);
                this.state.loadError = '无法连接技能服务，请确认后端已启动';
            }
        },

        async loadRetrieverStats() {
            try {
                const resp = await fetch(`${this.API_BASE}/skills/retriever/stats`);
                const data = await resp.json();
                if (data.success) {
                    this.state.retrieverStats = data.data;
                }
            } catch (e) {
                console.warn('[SkillManager] 加载检索器统计失败:', e);
            }
        },

        async loadEvolutionLog() {
            try {
                const resp = await fetch(`${this.API_BASE}/skills/evolution/log`);
                const data = await resp.json();
                if (data.success) {
                    this.state.evolutionLog = data.data.log;
                }
            } catch (e) {
                console.warn('[SkillManager] 加载进化日志失败:', e);
            }
        },

        async loadGovernanceLog() {
            try {
                const resp = await fetch(`${this.API_BASE}/skills/governance/log`);
                const data = await resp.json();
                if (data.success) {
                    this.state.governanceLog = data.data.log;
                }
            } catch (e) {
                console.warn('[SkillManager] 加载治理日志失败:', e);
            }
        },

        async teachSkill(name, description, pseudoCode, parameters, usageExample) {
            try {
                const apiKey = await FunctionManager.getApiKey();
                const resp = await fetch(`${this.API_BASE}/skills/evolution/teach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
                    body: JSON.stringify({
                        name, description,
                        pseudo_code: pseudoCode,
                        parameters: parameters || [],
                        usage_example: usageExample || '',
                    }),
                });
                const data = await resp.json();
                if (data.success) {
                    await this.loadSkills();
                }
                return data;
            } catch (e) {
                return { success: false, message: e.message };
            }
        },

        async deleteSkill(name) {
            try {
                const apiKey = await FunctionManager.getApiKey();
                const resp = await fetch(`${this.API_BASE}/skills/delete/${name}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${apiKey}` },
                });
                const data = await resp.json();
                if (data.success) {
                    await this.loadSkills();
                }
                return data;
            } catch (e) {
                return { success: false, message: e.message };
            }
        },

        async runGovernance() {
            try {
                const apiKey = await FunctionManager.getApiKey();
                const resp = await fetch(`${this.API_BASE}/skills/governance/run`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${apiKey}` },
                });
                return await resp.json();
            } catch (e) {
                return { success: false, message: e.message };
            }
        },

        async searchSkills(query) {
            try {
                const resp = await fetch(`${this.API_BASE}/skills/retrieve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, top_k: 10 }),
                });
                const data = await resp.json();
                return data.success ? data.data.skills : [];
            } catch (e) {
                return [];
            }
        },

        renderSkeleton() {
            const container = document.getElementById('skillPanel');
            if (!container) return;

            let cardsHtml = '';
            for (let i = 0; i < 6; i++) {
                cardsHtml += `
                    <div class="skills-skeleton-card">
                        <div class="skills-skeleton-line" style="width:70%"></div>
                        <div class="skills-skeleton-line short"></div>
                        <div class="skills-skeleton-line" style="width:90%"></div>
                        <div class="skills-skeleton-line short"></div>
                    </div>
                `;
            }

            container.innerHTML = `
                <div class="skill-panel-inner">
                    <div class="skills-header">
                        <div>
                            <div class="skills-title">技能工坊</div>
                            <div class="skills-subtitle">SELSS 自进化语言技能系统</div>
                        </div>
                    </div>
                    <div class="skills-stats-row">
                        <div class="skills-skeleton-card" style="padding:14px 18px"><div class="skills-skeleton-line short"></div></div>
                        <div class="skills-skeleton-card" style="padding:14px 18px"><div class="skills-skeleton-line short"></div></div>
                        <div class="skills-skeleton-card" style="padding:14px 18px"><div class="skills-skeleton-line short"></div></div>
                        <div class="skills-skeleton-card" style="padding:14px 18px"><div class="skills-skeleton-line short"></div></div>
                    </div>
                    <div class="skills-skeleton">${cardsHtml}</div>
                </div>
            `;
        },

        getFilteredSkills() {
            let skills = this.state.skills || [];

            if (this.state.activeFilter !== 'all') {
                const filterMap = { atomic: 'atomic', logic: 'logic', workflow: 'workflow' };
                const tier = filterMap[this.state.activeFilter];
                if (tier) {
                    skills = skills.filter(s => (s.tier || 'atomic') === tier);
                }
            }

            if (this.state.searchQuery) {
                const q = this.state.searchQuery.toLowerCase();
                skills = skills.filter(s =>
                    (s.name || '').toLowerCase().includes(q) ||
                    (s.description || '').toLowerCase().includes(q)
                );
            }

            return skills;
        },

        handleSearch(query) {
            this.state.searchQuery = (query || '').trim();
            this.renderSkillPanel();
            this.bindSkillEvents();
        },

        handleFilterChange(filter) {
            this.state.activeFilter = filter;
            this.renderSkillPanel();
            this.bindSkillEvents();
        },

        renderSkillPanel() {
            const container = document.getElementById('skillPanel');
            if (!container) {
                console.warn('[SkillManager] skillPanel容器不存在');
                return;
            }

            console.log('[SkillManager] 渲染技能面板, skills:', this.state.skills?.length || 0);

            const tierLabels = { atomic: '原子技能', logic: '逻辑技能', workflow: '工作流' };
            const tierIcons = { atomic: '⚙', logic: '🔗', workflow: '📋' };
            const stats = this.state.stats || {};

            let html = '<div class="skill-panel-inner">';

            html += '<div class="skills-header">';
            html += '<div><div class="skills-title">技能工坊</div><div class="skills-subtitle">SELSS 自进化语言技能系统</div></div>';
            html += '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">';
            html += '<div class="skills-search"><input type="text" id="skillSearchInput" placeholder="搜索技能..." value="' + escapeHtml(this.state.searchQuery) + '"></div>';
            html += '<button class="skill-btn" onclick="SkillManager.showTeachDialog()" style="white-space:nowrap">📝 教学</button>';
            html += '<button class="skill-btn" onclick="SkillManager.runGovernanceAndRefresh()" style="white-space:nowrap">🧹 治理</button>';
            html += '<button class="skill-btn" onclick="SkillManager.refresh()" style="white-space:nowrap">🔄</button>';
            html += '</div></div>';

            html += '<div class="skills-stats-row">';
            html += `<div class="skills-stat-card"><div class="skills-stat-icon tier-total">Σ</div><div><div class="skills-stat-value">${stats.total || 0}</div><div class="skills-stat-label">总计</div></div></div>`;
            html += `<div class="skills-stat-card"><div class="skills-stat-icon tier-atomic">⚙</div><div><div class="skills-stat-value">${stats.atomic || 0}</div><div class="skills-stat-label">原子技能</div></div></div>`;
            html += `<div class="skills-stat-card"><div class="skills-stat-icon tier-logic">🔗</div><div><div class="skills-stat-value">${stats.logic || 0}</div><div class="skills-stat-label">逻辑技能</div></div></div>`;
            html += `<div class="skills-stat-card"><div class="skills-stat-icon tier-workflow">📋</div><div><div class="skills-stat-value">${stats.workflow || 0}</div><div class="skills-stat-label">工作流</div></div></div>`;
            html += '</div>';

            const filters = [
                { key: 'all', label: '全部' },
                { key: 'atomic', label: '原子技能' },
                { key: 'logic', label: '逻辑技能' },
                { key: 'workflow', label: '工作流' }
            ];
            html += '<div class="skills-filter-tabs">';
            for (const f of filters) {
                const activeClass = this.state.activeFilter === f.key ? ' active' : '';
                html += `<button class="skills-filter-tab${activeClass}" data-filter="${f.key}">${f.label}</button>`;
            }
            html += '</div>';

            if (this.state.loadError) {
                html += '<div style="padding:20px;text-align:center;color:var(--error-color, #ef4444);">';
                html += `⚠️ ${escapeHtml(this.state.loadError)}`;
                html += '<br><button class="skill-btn" style="margin-top:10px" onclick="SkillManager.retryLoad()">🔄 重试</button>';
                html += '</div>';
            } else {
                const skills = this.getFilteredSkills();

                if (skills.length === 0) {
                    const hasSearchOrFilter = this.state.searchQuery || this.state.activeFilter !== 'all';
                    if (hasSearchOrFilter) {
                        html += '<div style="padding:30px;text-align:center;color:var(--skill-text-muted, #999);">未找到匹配的技能</div>';
                    } else {
                        html += '<div style="padding:30px;text-align:center;color:var(--skill-text-muted, #999);">暂无技能，点击"教学"添加</div>';
                    }
                } else {
                    html += '<div class="skills-grid">';
                    for (const skill of skills) {
                        const tier = skill.tier || 'atomic';
                        const vitalityPct = Math.round((skill.vitality || 0) * 100);
                        const vitalityClass = vitalityPct >= 70 ? 'high' : vitalityPct >= 30 ? 'medium' : 'low';
                        const confidencePct = Math.round((skill.confidence || 0) * 100);
                        const confidenceClass = confidencePct >= 80 ? 'high' : confidencePct >= 50 ? 'medium' : 'low';
                        const betaTag = skill.is_beta ? ' <span style="font-size:10px;color:var(--skill-accent, #6c9);font-weight:400">beta</span>' : '';

                        html += `<div class="skill-card" data-skill-name="${escapeHtml(skill.name)}">`;
                        html += '<div class="skill-card-header">';
                        html += `<div class="skill-card-name">${escapeHtml(skill.name)}${betaTag}</div>`;
                        html += `<span class="skill-card-tier-badge ${tier}">${tierLabels[tier] || tier}</span>`;
                        html += '</div>';
                        html += `<div class="skill-card-body">${escapeHtml(skill.description)}</div>`;
                        html += '<div class="skill-card-footer">';
                        html += `<div class="skill-vitality-bar"><div class="skill-vitality-fill ${vitalityClass}" style="width:${vitalityPct}%"></div></div>`;
                        html += `<div class="skill-confidence-dot ${confidenceClass}" title="置信度: ${confidencePct}%"></div>`;
                        html += '</div>';
                        html += '</div>';
                    }
                    html += '</div>';
                }
            }

            if (this.state.evolutionLog && this.state.evolutionLog.length > 0) {
                html += this.renderEvolutionTimeline();
            }

            html += '</div>';
            container.innerHTML = html;
        },

        renderEvolutionTimeline() {
            const log = this.state.evolutionLog || [];
            if (log.length === 0) return '';

            let html = '<div style="margin-top:28px">';
            html += '<div style="font-size:13px;font-weight:600;color:var(--skill-text, #ddd);margin-bottom:14px;letter-spacing:0.5px">进化时间线</div>';
            html += '<div class="skills-evolution-timeline">';

            const entries = log.slice(-15).reverse();
            for (const entry of entries) {
                const status = entry.status || entry.verdict || 'pending';
                const dotClass = (status === 'success' || status === 'accepted' || status === 'merged') ? 'success'
                    : (status === 'fail' || status === 'rejected') ? 'fail' : 'pending';
                const time = entry.timestamp ? formatTime(entry.timestamp) : '';

                html += '<div class="skills-evolution-item">';
                html += `<div class="skills-evolution-dot ${dotClass}"></div>`;
                html += `<div>${escapeHtml(entry.skill_name || entry.name || '未知')} <span style="color:var(--skill-text-muted, #888);font-size:11px">${escapeHtml(entry.action || entry.verdict || '')}</span></div>`;
                if (time) {
                    html += `<div style="font-size:10px;color:var(--skill-text-muted, #666);margin-top:2px">${time}</div>`;
                }
                html += '</div>';
            }

            html += '</div></div>';
            return html;
        },

        showSkillDetail(skillName) {
            const skill = (this.state.skills || []).find(s => s.name === skillName);
            if (!skill) return;

            const existing = document.getElementById('skillDetailOverlay');
            if (existing) existing.remove();

            const tier = skill.tier || 'atomic';
            const tierLabels = { atomic: '原子技能', logic: '逻辑技能', workflow: '工作流' };
            const vitalityPct = Math.round((skill.vitality || 0) * 100);
            const confidencePct = Math.round((skill.confidence || 0) * 100);
            const confidenceClass = confidencePct >= 80 ? 'high' : confidencePct >= 50 ? 'medium' : 'low';

            const params = skill.parameters || [];
            let paramsHtml = '';
            if (params.length > 0) {
                paramsHtml = params.map(p =>
                    `<div style="display:flex;gap:8px;font-size:12px;padding:4px 0"><span style="color:var(--skill-accent, #6c9);font-family:var(--skill-font-mono, monospace)">${escapeHtml(p.name)}</span><span style="color:var(--skill-text-muted, #888)">${escapeHtml(p.type || '')}</span>${p.required ? '<span style="color:#ef4444;font-size:10px">必填</span>' : ''}</div>`
                ).join('');
            } else {
                paramsHtml = '<div style="font-size:12px;color:var(--skill-text-muted, #888)">无参数</div>';
            }

            const overlay = document.createElement('div');
            overlay.id = 'skillDetailOverlay';
            overlay.className = 'skill-detail-overlay';
            overlay.innerHTML = `
                <div class="skill-detail-panel">
                    <div class="skill-detail-header">
                        <h3>${escapeHtml(skill.name)}</h3>
                        <button class="skill-detail-close" id="skillDetailClose">✕</button>
                    </div>
                    <div class="skill-detail-body">
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">层级</div>
                            <span class="skill-card-tier-badge ${tier}">${tierLabels[tier] || tier}</span>
                            ${skill.is_beta ? ' <span style="font-size:11px;color:var(--skill-accent, #6c9)">beta</span>' : ''}
                        </div>
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">描述</div>
                            <div style="font-size:13px;color:var(--skill-text-secondary, #bbb);line-height:1.7">${escapeHtml(skill.description)}</div>
                        </div>
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">参数</div>
                            ${paramsHtml}
                        </div>
                        ${skill.pseudo_code ? `
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">伪代码</div>
                            <div class="skill-detail-code">${escapeHtml(skill.pseudo_code)}</div>
                        </div>` : ''}
                        ${skill.usage_example ? `
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">使用示例</div>
                            <div class="skill-detail-code">${escapeHtml(skill.usage_example)}</div>
                        </div>` : ''}
                        <div class="skill-detail-section">
                            <div class="skill-detail-section-title">指标</div>
                            <div style="display:flex;gap:20px;align-items:center">
                                <div>
                                    <div style="font-size:11px;color:var(--skill-text-muted, #888);margin-bottom:4px">生命力</div>
                                    <div style="display:flex;align-items:center;gap:8px">
                                        <div class="skill-vitality-bar" style="width:120px"><div class="skill-vitality-fill ${vitalityPct >= 70 ? 'high' : vitalityPct >= 30 ? 'medium' : 'low'}" style="width:${vitalityPct}%"></div></div>
                                        <span style="font-size:12px;font-family:var(--skill-font-mono, monospace);color:var(--skill-text, #ddd)">${vitalityPct}%</span>
                                    </div>
                                </div>
                                <div>
                                    <div style="font-size:11px;color:var(--skill-text-muted, #888);margin-bottom:4px">置信度</div>
                                    <div style="display:flex;align-items:center;gap:8px">
                                        <div class="skill-confidence-dot ${confidenceClass}"></div>
                                        <span style="font-size:12px;font-family:var(--skill-font-mono, monospace);color:var(--skill-text, #ddd)">${confidencePct}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="skill-detail-section" style="margin-top:24px">
                            <button class="skill-btn" style="width:100%;text-align:center;color:#ef4444;border-color:#ef4444" data-skill-delete="${escapeHtml(skill.name)}">🗑 删除此技能</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            requestAnimationFrame(() => {
                overlay.classList.add('active');
                overlay.querySelector('.skill-detail-panel').classList.add('active');
            });

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    SkillManager.closeSkillDetail();
                }
                const deleteBtn = e.target.closest('[data-skill-delete]');
                if (deleteBtn) {
                    SkillManager.confirmDeleteSkill(deleteBtn.dataset.skillDelete);
                }
            });

            const closeBtn = overlay.querySelector('#skillDetailClose');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    SkillManager.closeSkillDetail();
                });
            }
        },

        closeSkillDetail() {
            const overlay = document.getElementById('skillDetailOverlay');
            if (!overlay) return;
            overlay.querySelector('.skill-detail-panel').classList.remove('active');
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 350);
        },

        async confirmDeleteSkill(name) {
            if (!confirm(`确定要删除技能 "${name}" 吗？此操作不可撤销。`)) return;
            const result = await this.deleteSkill(name);
            if (result.success) {
                FunctionManager.showToast(`技能 "${name}" 已删除`, 'success');
                this.closeSkillDetail();
                this.renderSkillPanel();
                this.bindSkillEvents();
            } else {
                FunctionManager.showToast(`删除失败: ${result.message || '未知错误'}`, 'error');
            }
        },

        showTeachDialog() {
            const existing = document.getElementById('teachSkillModal');
            if (existing) existing.remove();

            this.state.teachStep = 1;
            this._teachDraft = null;

            const dialog = document.createElement('div');
            dialog.id = 'teachSkillModal';
            dialog.className = 'skills-teach-dialog';
            dialog.innerHTML = this.buildTeachDialogContent(1);
            document.body.appendChild(dialog);

            dialog.addEventListener('click', (e) => {
                if (e.target === dialog) {
                    dialog.remove();
                }
            });
        },

        buildTeachDialogContent(step) {
            const steps = [
                { num: 1, label: '基本信息' },
                { num: 2, label: '伪代码' },
                { num: 3, label: '使用示例' },
                { num: 4, label: '确认提交' }
            ];

            let stepsHtml = '';
            steps.forEach((s, i) => {
                const cls = s.num < step ? 'completed' : s.num === step ? 'active' : '';
                stepsHtml += `<div class="skills-teach-step ${cls}">${s.num < step ? '✓' : s.num}</div>`;
                if (i < steps.length - 1) {
                    stepsHtml += `<div class="skills-teach-step-connector${s.num < step ? ' completed' : ''}"></div>`;
                }
            });

            const savedName = this._teachDraft?.name || '';
            const savedDesc = this._teachDraft?.description || '';
            const savedPseudo = this._teachDraft?.pseudoCode || '';
            const savedExample = this._teachDraft?.usageExample || '';

            let bodyHtml = '';

            if (step === 1) {
                bodyHtml = `
                    <div class="form-group">
                        <label>技能名称 (英文下划线)</label>
                        <input id="teachName" type="text" placeholder="如: stock_alert" value="${escapeHtml(savedName)}">
                    </div>
                    <div class="form-group">
                        <label>功能描述</label>
                        <textarea id="teachDesc" rows="3" placeholder="如: 每天检查股票开盘价，涨幅超阈值发短信">${escapeHtml(savedDesc)}</textarea>
                    </div>
                `;
            } else if (step === 2) {
                bodyHtml = `
                    <div class="form-group">
                        <label>伪代码 (可选)</label>
                        <textarea id="teachPseudo" rows="6" placeholder="如: result = call get_price(code=code)&#10;call send_sms(phone=phone, message=result)">${escapeHtml(savedPseudo)}</textarea>
                    </div>
                `;
            } else if (step === 3) {
                bodyHtml = `
                    <div class="form-group">
                        <label>使用示例 (可选)</label>
                        <input id="teachExample" type="text" placeholder="如: 帮我设置开盘预警" value="${escapeHtml(savedExample)}">
                    </div>
                `;
            } else if (step === 4) {
                bodyHtml = `
                    <div style="font-size:13px;color:var(--skill-text-secondary, #bbb);line-height:1.8">
                        <div style="margin-bottom:10px"><strong style="color:var(--skill-text, #ddd)">技能名称:</strong> ${escapeHtml(savedName || '(未填写)')}</div>
                        <div style="margin-bottom:10px"><strong style="color:var(--skill-text, #ddd)">描述:</strong> ${escapeHtml(savedDesc || '(未填写)')}</div>
                        <div style="margin-bottom:10px"><strong style="color:var(--skill-text, #ddd)">伪代码:</strong> ${savedPseudo ? '<pre style="margin:4px 0;font-size:12px;color:var(--skill-text-secondary, #bbb)">' + escapeHtml(savedPseudo) + '</pre>' : '(未填写)'}</div>
                        <div><strong style="color:var(--skill-text, #ddd)">使用示例:</strong> ${escapeHtml(savedExample || '(未填写)')}</div>
                    </div>
                `;
            }

            const isLast = step === 4;
            const isFirst = step === 1;

            return `
                <div class="skills-teach-content">
                    <div class="skills-teach-header">
                        <h3>📝 教学新技能</h3>
                        <button class="skill-detail-close" onclick="document.getElementById('teachSkillModal').remove()">✕</button>
                    </div>
                    <div class="skills-teach-steps">${stepsHtml}</div>
                    <div class="skills-teach-body">${bodyHtml}</div>
                    <div class="skills-teach-footer">
                        ${!isFirst ? '<button class="skill-btn" onclick="SkillManager.teachStepPrev()">上一步</button>' : ''}
                        ${isLast
                            ? '<button class="skill-btn" style="background:var(--skill-accent, #6c9);color:#000;border-color:var(--skill-accent, #6c9);font-weight:600" onclick="SkillManager.submitTeach()">提交学习</button>'
                            : '<button class="skill-btn" onclick="SkillManager.teachStepNext()">下一步</button>'}
                    </div>
                </div>
            `;
        },

        saveTeachDraft() {
            if (!this._teachDraft) this._teachDraft = {};
            const nameEl = document.getElementById('teachName');
            const descEl = document.getElementById('teachDesc');
            const pseudoEl = document.getElementById('teachPseudo');
            const exampleEl = document.getElementById('teachExample');

            if (nameEl) this._teachDraft.name = nameEl.value.trim();
            if (descEl) this._teachDraft.description = descEl.value.trim();
            if (pseudoEl) this._teachDraft.pseudoCode = pseudoEl.value.trim();
            if (exampleEl) this._teachDraft.usageExample = exampleEl.value.trim();
        },

        teachStepNext() {
            this.saveTeachDraft();

            if (this.state.teachStep === 1) {
                if (!this._teachDraft.name || !this._teachDraft.description) {
                    FunctionManager.showToast('技能名称和描述为必填项', 'warning');
                    return;
                }
            }

            if (this.state.teachStep < 4) {
                this.state.teachStep++;
                const dialog = document.getElementById('teachSkillModal');
                if (dialog) {
                    dialog.querySelector('.skills-teach-content').outerHTML =
                        this.buildTeachDialogContent(this.state.teachStep);
                }
            }
        },

        teachStepPrev() {
            this.saveTeachDraft();
            if (this.state.teachStep > 1) {
                this.state.teachStep--;
                const dialog = document.getElementById('teachSkillModal');
                if (dialog) {
                    dialog.querySelector('.skills-teach-content').outerHTML =
                        this.buildTeachDialogContent(this.state.teachStep);
                }
            }
        },

        async submitTeach() {
            this.saveTeachDraft();
            const draft = this._teachDraft || {};

            if (!draft.name || !draft.description) {
                FunctionManager.showToast('技能名称和描述为必填项', 'warning');
                return;
            }

            const result = await this.teachSkill(draft.name, draft.description, draft.pseudoCode, [], draft.usageExample);
            if (result.success) {
                FunctionManager.showToast(`技能 '${draft.name}' 学习成功! (${result.data?.verdict || 'accepted'})`, 'success');
                document.getElementById('teachSkillModal')?.remove();
                this._teachDraft = null;
                this.renderSkillPanel();
                this.bindSkillEvents();
            } else {
                FunctionManager.showToast(`学习失败: ${result.message || result.data?.message || '未知错误'}`, 'error');
            }
        },

        async runGovernanceAndRefresh() {
            FunctionManager.showToast('正在执行治理...', 'info');
            const result = await this.runGovernance();
            if (result.success) {
                const data = result.data || {};
                const msgs = [];
                if (data.deduplication?.length) msgs.push(`去重: ${data.deduplication.length}组`);
                if (data.eviction?.evicted_beta?.length) msgs.push(`淘汰beta: ${data.eviction.evicted_beta.length}个`);
                FunctionManager.showToast(msgs.length ? msgs.join(', ') : '治理完成，无需操作', 'success');
                await this.loadSkills();
                this.renderSkillPanel();
                this.bindSkillEvents();
            } else {
                FunctionManager.showToast('治理执行失败', 'error');
            }
        },

        async refresh() {
            await this.loadSkills();
            await this.loadRetrieverStats();
            this.renderSkillPanel();
            this.bindSkillEvents();
        },

        async retryLoad() {
            await this.init();
        },

        bindSkillEvents() {
            const container = document.getElementById('skillPanel');
            if (!container) return;

            const searchInput = container.querySelector('#skillSearchInput');
            if (searchInput) {
                let debounceTimer = null;
                searchInput.addEventListener('input', (e) => {
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => {
                        SkillManager.handleSearch(e.target.value);
                    }, 250);
                });
            }

            const filterTabs = container.querySelectorAll('.skills-filter-tab');
            filterTabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const filter = tab.getAttribute('data-filter');
                    if (filter) {
                        SkillManager.handleFilterChange(filter);
                    }
                });
            });

            const skillCards = container.querySelectorAll('.skill-card');
            skillCards.forEach(card => {
                card.addEventListener('click', () => {
                    const name = card.getAttribute('data-skill-name');
                    if (name) {
                        SkillManager.showSkillDetail(name);
                    }
                });
            });
        }
    };

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    global.FunctionManager = FunctionManager;
    global.SkillManager = SkillManager;

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = { FunctionManager, SkillManager };
    }

})(typeof window !== 'undefined' ? window : this);
