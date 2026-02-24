/**
 * 函数调用管理模块
 * 
 * 提供函数调用和 Web 搜索的完整功能：
 * - 函数列表展示
 * - 函数执行
 * - 搜索结果展示
 * - 执行历史记录
 * 
 * 支持的功能分类：
 * - 时间日期函数
 * - 媒体控制函数
 * - 网络搜索函数
 * - 实用工具函数
 */

(function(global) {
    'use strict';

    /**
     * 函数调用管理器
     * 统一管理前端所有函数调用相关功能
     */
    const FunctionManager = {
        // API 基础地址
        API_BASE: `http://${window.location.hostname || 'localhost'}:5001/api`,

        // 状态管理
        state: {
            functions: [],
            history: [],
            searchResults: [],
            currentSearch: null,
            executing: false
        },

        // 缓存
        cache: {
            functions: null,
            history: null
        },

        /**
         * 初始化函数管理器
         */
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

        /**
         * 加载可用函数列表
         */
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

        /**
         * 加载执行历史
         */
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

        /**
         * 获取 API Key
         */
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

        /**
         * 执行函数
         * @param {string} functionName - 函数名称
         * @param {Object} params - 函数参数
         * @param {boolean} requireConfirmation - 是否需要确认
         */
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

        /**
         * 执行网络搜索
         * @param {string} query - 搜索关键词
         * @param {number} maxResults - 最大结果数
         */
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

        /**
         * 获取即时答案
         * @param {string} question - 问题
         */
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

        /**
         * 绑定事件监听器
         */
        bindEvents() {
            // 搜索表单提交
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

        /**
         * 设置聊天集成
         * 在聊天中识别函数调用意图
         */
        setupChatIntegration() {
            // 监听聊天输入框
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

        /**
         * 判断是否为函数调用意图
         * @param {string} message - 用户消息
         */
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

        /**
         * 处理聊天中的函数调用
         * @param {string} message - 用户消息
         */
        async handleFunctionCallFromChat(message) {
            // 时间查询
            const timeMatch = message.match(/^(现在|今天|明天|昨天|后天)\s*(.*)/);
            if (timeMatch) {
                const [, timeWord, rest] = timeMatch;
                
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

            // 搜索
            const searchMatch = message.match(/^(搜索|找|查询)\s+(.+)/);
            if (searchMatch) {
                const [, , query] = searchMatch;
                await this.searchWeb(query);
                return;
            }

            // 播放音乐
            const playMatch = message.match(/^播放\s+(.+)/);
            if (playMatch) {
                const [, target] = playMatch;
                await this.executeFunction('play_music', { query: target });
                return;
            }
        },

        /**
         * 渲染函数面板
         */
        renderFunctionsPanel() {
            const container = document.getElementById('functionList');
            if (!container) return;

            const categories = {
                time: { name: '时间日期', icon: '🕐', color: '#7eb5a6' },
                media: { name: '媒体控制', icon: '🎵', color: '#d4c5a3' },
                search: { name: '网络搜索', icon: '🔍', color: '#a8c8ba' },
                utility: { name: '实用工具', icon: '🛠️', color: '#c9a8a8' }
            };

            // 按分类组织函数
            const grouped = {};
            this.state.functions.forEach(func => {
                const cat = func.category || 'utility';
                if (!grouped[cat]) {
                    grouped[cat] = [];
                }
                grouped[cat].push(func);
            });

            // 渲染
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

        /**
         * 渲染单个函数项
         * @param {Object} func - 函数定义
         */
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

        /**
         * 显示执行对话框
         * @param {string} functionName - 函数名称
         */
        async showExecuteDialog(functionName) {
            const func = this.state.functions.find(f => f.name === functionName);
            if (!func) return;

            const params = func.parameters || [];
            
            // 构建参数输入表单
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

        /**
         * 提交函数执行
         * @param {string} functionName - 函数名称
         */
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

        /**
         * 显示确认对话框
         * @param {Object} data - 确认数据
         */
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

        /**
         * 确认执行危险函数
         */
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

        /**
         * 显示结果对话框
         * @param {string} functionName - 函数名称
         * @param {Object} result - 执行结果
         */
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

        /**
         * 渲染搜索结果
         * @param {string} query - 搜索关键词
         * @param {Object} data - 搜索数据
         */
        renderSearchResults(query, data) {
            const container = document.getElementById('searchResults');
            if (!container) return;

            const results = data.results || [];
            const answer = data.answer;

            let html = '';

            // 即时答案
            if (answer) {
                html += `
                    <div class="instant-answer">
                        <div class="answer-label">答案</div>
                        <div class="answer-content">${escapeHtml(answer)}</div>
                    </div>
                `;
            }

            // 搜索结果列表
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

        /**
         * 渲染历史面板
         */
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

        /**
         * 显示执行中指示器
         * @param {string} functionName - 函数名称
         * @param {boolean} show - 是否显示
         */
        showExecutingIndicator(functionName, show) {
            const indicator = document.getElementById('functionExecutingIndicator');
            if (indicator) {
                indicator.style.display = show ? 'flex' : 'none';
                indicator.querySelector('.executing-function')?.setTextContent?.(`正在执行: ${functionName}`);
            }
        },

        /**
         * 关闭模态框
         * @param {string} modalId - 模态框 ID
         */
        closeModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('active');
                setTimeout(() => modal.remove(), 300);
            }
        },

        /**
         * 显示提示消息
         * @param {string} message - 消息内容
         * @param {string} type - 消息类型 (success/error/warning/info)
         */
        showToast(message, type = 'info') {
            if (typeof App !== 'undefined' && App.showToast) {
                App.showToast(message, type);
            } else {
                console.log(`[${type.toUpperCase()}] ${message}`);
            }
        }
    };

    /**
     * 辅助函数：HTML 转义
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 辅助函数：格式化时间
     */
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

    // 导出到全局
    global.FunctionManager = FunctionManager;

    // AMD / CommonJS 兼容
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = FunctionManager;
    }

})(typeof window !== 'undefined' ? window : this);
