/**
 * 讨论总结面板组件 - SummaryPanel
 * 
 * 功能：
 * 1. 展示讨论总结结果
 * 2. 支持生成新总结
 * 3. 支持查看历史总结
 * 4. 支持导出总结（JSON/Markdown/Text）
 * 5. 支持编辑总结内容
 * 
 * 依赖：
 * - 后端API: /api/summary/*
 * - 样式: summary-panel.css
 * 
 * 作者：AI Assistant
 * 日期：2026-02-03
 * 版本：v1.0
 */

class SummaryPanel {
    /**
     * 创建总结面板实例
     * @param {Object} options - 配置选项
     * @param {string} options.containerId - 容器元素ID
     * @param {string} options.conversationId - 当前会话ID
     * @param {Function} options.onGenerate - 生成总结回调
     * @param {Function} options.onExport - 导出总结回调
     * @param {string} options.apiBaseUrl - API基础URL
     */
    constructor(options = {}) {
        this.containerId = options.containerId || 'summary-panel';
        this.conversationId = options.conversationId || '';
        this.onGenerate = options.onGenerate || (() => {});
        this.onExport = options.onExport || (() => {});
        this.apiBaseUrl = options.apiBaseUrl || `http://${window.location.hostname || 'localhost'}:5001`;
        
        // 状态
        this.summaries = [];
        this.currentSummary = null;
        this.isLoading = false;
        this.isGenerating = false;
        
        // DOM元素引用
        this.container = null;
        this.elements = {};
        
        // 初始化
        this._init();
    }
    
    /**
     * 初始化面板
     * @private
     */
    _init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.error(`SummaryPanel: 容器元素 #${this.containerId} 不存在`);
            return;
        }
        
        this._render();
        this._bindEvents();
        
        // 如果有会话ID，自动加载历史总结
        if (this.conversationId) {
            this.loadSummaries();
        }
    }
    
    /**
     * 渲染面板HTML结构
     * @private
     */
    _render() {
        this.container.innerHTML = `
            <div class="summary-panel">
                <!-- 头部 -->
                <div class="summary-panel-header">
                    <h3 class="summary-panel-title">
                        <span class="icon">📋</span>
                        讨论总结
                    </h3>
                    <div class="summary-panel-actions">
                        <button class="btn btn-primary btn-generate" title="生成新总结">
                            <span class="icon">✨</span>
                            生成总结
                        </button>
                        <button class="btn btn-secondary btn-history" title="查看历史">
                            <span class="icon">📚</span>
                            历史
                        </button>
                        <button class="btn btn-icon btn-close" title="关闭">✕</button>
                    </div>
                </div>
                
                <!-- 内容区域 -->
                <div class="summary-panel-content">
                    <!-- 空状态 -->
                    <div class="summary-empty-state">
                        <div class="empty-icon">📝</div>
                        <h4>暂无讨论总结</h4>
                        <p>点击"生成总结"按钮，AI将自动分析对话内容并生成总结</p>
                        <button class="btn btn-primary btn-generate-empty">
                            <span class="icon">✨</span>
                            生成总结
                        </button>
                    </div>
                    
                    <!-- 加载状态 -->
                    <div class="summary-loading-state" style="display: none;">
                        <div class="loading-spinner"><span></span><span></span><span></span></div>
                        <p>正在分析对话内容...</p>
                        <div class="loading-progress">
                            <div class="progress-bar">
                                <div class="progress-fill"></div>
                            </div>
                            <span class="progress-text">0%</span>
                        </div>
                    </div>
                    
                    <!-- 总结内容 -->
                    <div class="summary-content" style="display: none;">
                        <!-- 元信息 -->
                        <div class="summary-meta">
                            <div class="meta-item">
                                <span class="meta-label">生成时间</span>
                                <span class="meta-value summary-created-at">-</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">消息数</span>
                                <span class="meta-value summary-message-count">-</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">参与人数</span>
                                <span class="meta-value summary-participant-count">-</span>
                            </div>
                            <div class="meta-item">
                                <span class="meta-label">置信度</span>
                                <span class="meta-value summary-confidence">-</span>
                            </div>
                        </div>
                        
                        <!-- 总体概述 -->
                        <div class="summary-section">
                            <h4 class="section-title">
                                <span class="icon">📖</span>
                                总体概述
                            </h4>
                            <div class="section-content summary-overview"></div>
                        </div>
                        
                        <!-- 关键要点 -->
                        <div class="summary-section">
                            <h4 class="section-title">
                                <span class="icon">🎯</span>
                                关键要点
                            </h4>
                            <ul class="key-points-list summary-key-points"></ul>
                        </div>
                        
                        <!-- 讨论主题 -->
                        <div class="summary-section summary-topics-section" style="display: none;">
                            <h4 class="section-title">
                                <span class="icon">🏷️</span>
                                讨论主题
                            </h4>
                            <div class="topics-list summary-topics"></div>
                        </div>
                        
                        <!-- 观点汇总 -->
                        <div class="summary-section summary-viewpoints-section" style="display: none;">
                            <h4 class="section-title">
                                <span class="icon">💭</span>
                                观点汇总
                            </h4>
                            <div class="viewpoints-list summary-viewpoints"></div>
                        </div>
                        
                        <!-- 结论建议 -->
                        <div class="summary-section summary-conclusions-section" style="display: none;">
                            <h4 class="section-title">
                                <span class="icon">💡</span>
                                结论建议
                            </h4>
                            <ul class="conclusions-list summary-conclusions"></ul>
                        </div>
                        
                        <!-- 讨论时间线 -->
                        <div class="summary-section summary-timeline-section" style="display: none;">
                            <h4 class="section-title">
                                <span class="icon">⏱️</span>
                                讨论时间线
                            </h4>
                            <div class="timeline-list summary-timeline"></div>
                        </div>
                    </div>
                </div>
                
                <!-- 底部操作栏 -->
                <div class="summary-panel-footer" style="display: none;">
                    <div class="footer-actions">
                        <button class="btn btn-secondary btn-edit">
                            <span class="icon">✏️</span>
                            编辑
                        </button>
                        <div class="export-dropdown">
                            <button class="btn btn-secondary btn-export">
                                <span class="icon">📤</span>
                                导出
                                <span class="dropdown-arrow">▼</span>
                            </button>
                            <div class="dropdown-menu">
                                <button class="dropdown-item" data-format="json">JSON格式</button>
                                <button class="dropdown-item" data-format="markdown">Markdown</button>
                                <button class="dropdown-item" data-format="text">纯文本</button>
                            </div>
                        </div>
                        <button class="btn btn-danger btn-delete">
                            <span class="icon">🗑️</span>
                            删除
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 历史总结弹窗 -->
            <div class="summary-history-modal" style="display: none;">
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h4>历史总结记录</h4>
                        <button class="btn btn-icon btn-close-modal">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="history-list"></div>
                    </div>
                </div>
            </div>
            
            <!-- 编辑弹窗 -->
            <div class="summary-edit-modal" style="display: none;">
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h4>编辑总结</h4>
                        <button class="btn btn-icon btn-close-modal">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>总体概述</label>
                            <textarea class="form-control edit-overview" rows="4"></textarea>
                        </div>
                        <div class="form-group">
                            <label>关键要点（每行一个）</label>
                            <textarea class="form-control edit-key-points" rows="6"></textarea>
                        </div>
                        <div class="form-group">
                            <label>结论建议（每行一个）</label>
                            <textarea class="form-control edit-conclusions" rows="4"></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary btn-cancel">取消</button>
                        <button class="btn btn-primary btn-save">保存</button>
                    </div>
                </div>
            </div>
        `;
        
        // 缓存DOM元素引用
        this.elements = {
            emptyState: this.container.querySelector('.summary-empty-state'),
            loadingState: this.container.querySelector('.summary-loading-state'),
            content: this.container.querySelector('.summary-content'),
            footer: this.container.querySelector('.summary-panel-footer'),
            generateBtn: this.container.querySelector('.btn-generate'),
            generateEmptyBtn: this.container.querySelector('.btn-generate-empty'),
            historyBtn: this.container.querySelector('.btn-history'),
            closeBtn: this.container.querySelector('.btn-close'),
            editBtn: this.container.querySelector('.btn-edit'),
            deleteBtn: this.container.querySelector('.btn-delete'),
            exportBtn: this.container.querySelector('.btn-export'),
            exportDropdown: this.container.querySelector('.export-dropdown'),
            historyModal: this.container.querySelector('.summary-history-modal'),
            editModal: this.container.querySelector('.summary-edit-modal'),
            historyList: this.container.querySelector('.history-list'),
            progressFill: this.container.querySelector('.progress-fill'),
            progressText: this.container.querySelector('.progress-text')
        };
    }
    
    /**
     * 绑定事件处理器
     * @private
     */
    _bindEvents() {
        // 生成总结按钮
        this.elements.generateBtn?.addEventListener('click', () => this.generateSummary());
        this.elements.generateEmptyBtn?.addEventListener('click', () => this.generateSummary());
        
        // 历史记录按钮
        this.elements.historyBtn?.addEventListener('click', () => this.showHistoryModal());
        
        // 关闭按钮
        this.elements.closeBtn?.addEventListener('click', () => this.close());
        
        // 编辑按钮
        this.elements.editBtn?.addEventListener('click', () => this.showEditModal());
        
        // 删除按钮
        this.elements.deleteBtn?.addEventListener('click', () => this.deleteSummary());
        
        // 导出下拉菜单
        this.elements.exportBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.elements.exportDropdown?.classList.toggle('open');
        });
        
        // 导出选项
        this.container.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const format = e.target.dataset.format;
                this.exportSummary(format);
                this.elements.exportDropdown?.classList.remove('open');
            });
        });
        
        // 点击外部关闭下拉菜单
        document.addEventListener('click', () => {
            this.elements.exportDropdown?.classList.remove('open');
        });
        
        // 历史记录弹窗关闭
        this.elements.historyModal?.querySelector('.btn-close-modal')?.addEventListener('click', () => {
            this.elements.historyModal.style.display = 'none';
        });
        this.elements.historyModal?.querySelector('.modal-overlay')?.addEventListener('click', () => {
            this.elements.historyModal.style.display = 'none';
        });
        
        // 编辑弹窗
        this.elements.editModal?.querySelector('.btn-close-modal')?.addEventListener('click', () => {
            this.elements.editModal.style.display = 'none';
        });
        this.elements.editModal?.querySelector('.btn-cancel')?.addEventListener('click', () => {
            this.elements.editModal.style.display = 'none';
        });
        this.elements.editModal?.querySelector('.modal-overlay')?.addEventListener('click', () => {
            this.elements.editModal.style.display = 'none';
        });
        this.elements.editModal?.querySelector('.btn-save')?.addEventListener('click', () => {
            this.saveEdit();
        });
    }
    
    /**
     * 设置会话ID
     * @param {string} conversationId - 会话ID
     */
    setConversationId(conversationId) {
        this.conversationId = conversationId;
        this.currentSummary = null;
        this.summaries = [];
        
        if (conversationId) {
            this.loadSummaries();
        } else {
            this._showEmptyState();
        }
    }
    
    /**
     * 加载会话的历史总结
     */
    async loadSummaries() {
        if (!this.conversationId) return;
        
        try {
            this._setLoading(true);
            
            const response = await fetch(
                `${this.apiBaseUrl}/api/summary/conversation/${this.conversationId}?limit=10`
            );
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.summaries = result.data || [];
                
                if (this.summaries.length > 0) {
                    // 显示最新的总结
                    this.displaySummary(this.summaries[0]);
                } else {
                    this._showEmptyState();
                }
            } else {
                throw new Error(result.error || '加载失败');
            }
        } catch (error) {
            console.error('加载总结失败:', error);
            this._showError('加载总结失败: ' + error.message);
        } finally {
            this._setLoading(false);
        }
    }
    
    /**
     * 生成新的讨论总结
     * @param {Array} messages - 消息数组（可选，不传则从外部获取）
     */
    async generateSummary(messages = null) {
        if (this.isGenerating) return;
        
        // 如果没有传入消息，尝试从回调获取
        if (!messages && this.onGenerate) {
            messages = await this.onGenerate();
        }
        
        if (!messages || messages.length === 0) {
            this._showError('没有可总结的消息');
            return;
        }
        
        if (!this.conversationId) {
            this._showError('未设置会话ID');
            return;
        }
        
        try {
            this.isGenerating = true;
            this._showGeneratingState();
            
            // 模拟进度更新
            this._updateProgress(10);
            
            const response = await fetch(`${this.apiBaseUrl}/api/summary/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    messages: messages,
                    options: {
                        include_timeline: true,
                        include_viewpoints: true,
                        max_key_points: 5
                    }
                })
            });
            
            this._updateProgress(70);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            this._updateProgress(90);
            
            if (result.success) {
                this.currentSummary = result.data;
                this.summaries.unshift(this.currentSummary);
                this.displaySummary(this.currentSummary);
                this._showNotification('总结生成成功', 'success');
            } else {
                throw new Error(result.error || '生成失败');
            }
        } catch (error) {
            console.error('生成总结失败:', error);
            this._showError('生成总结失败: ' + error.message);
            this._showEmptyState();
        } finally {
            this.isGenerating = false;
            this._updateProgress(100);
        }
    }
    
    /**
     * 显示总结内容
     * @param {Object} summary - 总结数据对象
     */
    displaySummary(summary) {
        if (!summary) return;
        
        this.currentSummary = summary;
        
        // 更新元信息
        const createdAt = new Date(summary.created_at);
        this.container.querySelector('.summary-created-at').textContent = 
            createdAt.toLocaleString('zh-CN');
        this.container.querySelector('.summary-message-count').textContent = 
            summary.message_count || 0;
        this.container.querySelector('.summary-participant-count').textContent = 
            summary.participant_count || 0;
        
        const confidence = (summary.confidence_score || 0) * 100;
        this.container.querySelector('.summary-confidence').textContent = 
            `${confidence.toFixed(1)}%`;
        
        // 总体概述
        this.container.querySelector('.summary-overview').textContent = 
            summary.overview || '暂无概述';
        
        // 关键要点
        const keyPointsList = this.container.querySelector('.summary-key-points');
        keyPointsList.innerHTML = '';
        if (summary.key_points && summary.key_points.length > 0) {
            summary.key_points.forEach(point => {
                const li = document.createElement('li');
                li.textContent = point;
                keyPointsList.appendChild(li);
            });
        } else {
            keyPointsList.innerHTML = '<li class="empty">暂无关键要点</li>';
        }
        
        // 讨论主题
        const topicsSection = this.container.querySelector('.summary-topics-section');
        const topicsList = this.container.querySelector('.summary-topics');
        if (summary.topics && summary.topics.length > 0) {
            topicsSection.style.display = 'block';
            topicsList.innerHTML = summary.topics.map(topic => `
                <div class="topic-item">
                    <div class="topic-title">${topic.title || '未命名主题'}</div>
                    <div class="topic-keywords">
                        ${(topic.keywords || []).map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                    </div>
                    <div class="topic-score">相关度: ${(topic.score || 0).toFixed(3)}</div>
                </div>
            `).join('');
        } else {
            topicsSection.style.display = 'none';
        }
        
        // 观点汇总
        const viewpointsSection = this.container.querySelector('.summary-viewpoints-section');
        const viewpointsList = this.container.querySelector('.summary-viewpoints');
        if (summary.viewpoints && summary.viewpoints.length > 0) {
            viewpointsSection.style.display = 'block';
            viewpointsList.innerHTML = summary.viewpoints.map(vp => `
                <div class="viewpoint-item">
                    <div class="viewpoint-header">
                        <span class="participant-name">${vp.participant || '未知参与者'}</span>
                        <span class="message-count">${vp.message_count || 0} 条消息</span>
                    </div>
                    <div class="viewpoint-stance stance-${vp.stance || 'neutral'}">
                        立场: ${this._getStanceText(vp.stance)}
                    </div>
                    ${vp.key_points ? `
                        <ul class="viewpoint-points">
                            ${vp.key_points.map(p => `<li>${p}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
            `).join('');
        } else {
            viewpointsSection.style.display = 'none';
        }
        
        // 结论建议
        const conclusionsSection = this.container.querySelector('.summary-conclusions-section');
        const conclusionsList = this.container.querySelector('.summary-conclusions');
        if (summary.conclusions && summary.conclusions.length > 0) {
            conclusionsSection.style.display = 'block';
            conclusionsList.innerHTML = '';
            summary.conclusions.forEach(conclusion => {
                const li = document.createElement('li');
                li.textContent = conclusion;
                conclusionsList.appendChild(li);
            });
        } else {
            conclusionsSection.style.display = 'none';
        }
        
        // 讨论时间线
        const timelineSection = this.container.querySelector('.summary-timeline-section');
        const timelineList = this.container.querySelector('.summary-timeline');
        if (summary.timeline && summary.timeline.length > 0) {
            timelineSection.style.display = 'block';
            timelineList.innerHTML = summary.timeline.map(phase => {
                const startTime = new Date(phase.start_time).toLocaleTimeString('zh-CN', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                const endTime = new Date(phase.end_time).toLocaleTimeString('zh-CN', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                return `
                    <div class="timeline-item">
                        <div class="timeline-time">${startTime} - ${endTime}</div>
                        <div class="timeline-type type-${phase.type || 'discussing'}">
                            ${this._getPhaseTypeText(phase.type)}
                        </div>
                        <div class="timeline-summary">${phase.summary || ''}</div>
                        <div class="timeline-participants">
                            ${(phase.participants || []).map(p => `<span class="participant-tag">${p}</span>`).join('')}
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            timelineSection.style.display = 'none';
        }
        
        // 显示内容区域
        this.elements.emptyState.style.display = 'none';
        this.elements.loadingState.style.display = 'none';
        this.elements.content.style.display = 'block';
        this.elements.footer.style.display = 'flex';
    }
    
    /**
     * 显示历史总结弹窗
     */
    async showHistoryModal() {
        if (!this.conversationId) {
            this._showError('未设置会话ID');
            return;
        }
        
        // 重新加载历史记录
        await this.loadSummaries();
        
        const historyList = this.elements.historyList;
        historyList.innerHTML = '';
        
        if (this.summaries.length === 0) {
            historyList.innerHTML = '<div class="empty-state">暂无历史总结</div>';
        } else {
            this.summaries.forEach((summary, index) => {
                const createdAt = new Date(summary.created_at);
                const item = document.createElement('div');
                item.className = 'history-item' + (index === 0 ? ' active' : '');
                item.innerHTML = `
                    <div class="history-time">${createdAt.toLocaleString('zh-CN')}</div>
                    <div class="history-meta">
                        ${summary.message_count} 条消息 · 
                        ${summary.participant_count} 人参与 · 
                        置信度 ${((summary.confidence_score || 0) * 100).toFixed(1)}%
                    </div>
                    <div class="history-overview">${(summary.overview || '').substring(0, 100)}...</div>
                `;
                item.addEventListener('click', () => {
                    this.displaySummary(summary);
                    this.elements.historyModal.style.display = 'none';
                });
                historyList.appendChild(item);
            });
        }
        
        this.elements.historyModal.style.display = 'block';
    }
    
    /**
     * 显示编辑弹窗
     */
    showEditModal() {
        if (!this.currentSummary) return;
        
        const overviewInput = this.elements.editModal.querySelector('.edit-overview');
        const keyPointsInput = this.elements.editModal.querySelector('.edit-key-points');
        const conclusionsInput = this.elements.editModal.querySelector('.edit-conclusions');
        
        overviewInput.value = this.currentSummary.overview || '';
        keyPointsInput.value = (this.currentSummary.key_points || []).join('\n');
        conclusionsInput.value = (this.currentSummary.conclusions || []).join('\n');
        
        this.elements.editModal.style.display = 'block';
    }
    
    /**
     * 保存编辑内容
     */
    async saveEdit() {
        if (!this.currentSummary) return;
        
        const overview = this.elements.editModal.querySelector('.edit-overview').value.trim();
        const keyPointsText = this.elements.editModal.querySelector('.edit-key-points').value.trim();
        const conclusionsText = this.elements.editModal.querySelector('.edit-conclusions').value.trim();
        
        const updates = {
            overview: overview,
            key_points: keyPointsText.split('\n').filter(p => p.trim()),
            conclusions: conclusionsText.split('\n').filter(c => c.trim()),
            edited_by: 'user',
            edited_at: Date.now()
        };
        
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/summary/${this.currentSummary.id}`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.currentSummary = result.data;
                this.displaySummary(this.currentSummary);
                this.elements.editModal.style.display = 'none';
                this._showNotification('保存成功', 'success');
            } else {
                throw new Error(result.error || '保存失败');
            }
        } catch (error) {
            console.error('保存编辑失败:', error);
            this._showError('保存失败: ' + error.message);
        }
    }
    
    /**
     * 删除当前总结
     */
    async deleteSummary() {
        if (!this.currentSummary) return;
        
        if (!confirm('确定要删除这个总结吗？此操作不可撤销。')) {
            return;
        }
        
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/summary/${this.currentSummary.id}`,
                { method: 'DELETE' }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.summaries = this.summaries.filter(s => s.id !== this.currentSummary.id);
                this.currentSummary = null;
                
                if (this.summaries.length > 0) {
                    this.displaySummary(this.summaries[0]);
                } else {
                    this._showEmptyState();
                }
                
                this._showNotification('删除成功', 'success');
            } else {
                throw new Error(result.error || '删除失败');
            }
        } catch (error) {
            console.error('删除总结失败:', error);
            this._showError('删除失败: ' + error.message);
        }
    }
    
    /**
     * 导出总结
     * @param {string} format - 导出格式：json, markdown, text
     */
    async exportSummary(format) {
        if (!this.currentSummary) return;
        
        try {
            const response = await fetch(
                `${this.apiBaseUrl}/api/summary/${this.currentSummary.id}/export?format=${format}`
            );
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            let content, filename, mimeType;
            
            if (format === 'json') {
                const result = await response.json();
                content = JSON.stringify(result.data, null, 2);
                filename = `summary_${this.currentSummary.id}.json`;
                mimeType = 'application/json';
            } else {
                content = await response.text();
                filename = `summary_${this.currentSummary.id}.${format === 'markdown' ? 'md' : 'txt'}`;
                mimeType = format === 'markdown' ? 'text/markdown' : 'text/plain';
            }
            
            // 下载文件
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this._showNotification(`已导出为 ${format.toUpperCase()}`, 'success');
            
            if (this.onExport) {
                this.onExport(format, content);
            }
        } catch (error) {
            console.error('导出失败:', error);
            this._showError('导出失败: ' + error.message);
        }
    }
    
    /**
     * 关闭面板
     */
    close() {
        this.container.style.display = 'none';
    }
    
    /**
     * 显示面板
     */
    show() {
        this.container.style.display = 'block';
    }
    
    /**
     * 切换面板显示状态
     */
    toggle() {
        if (this.container.style.display === 'none') {
            this.show();
        } else {
            this.close();
        }
    }
    
    /**
     * 显示空状态
     * @private
     */
    _showEmptyState() {
        this.elements.emptyState.style.display = 'block';
        this.elements.loadingState.style.display = 'none';
        this.elements.content.style.display = 'none';
        this.elements.footer.style.display = 'none';
    }
    
    /**
     * 显示生成中状态
     * @private
     */
    _showGeneratingState() {
        this.elements.emptyState.style.display = 'none';
        this.elements.loadingState.style.display = 'block';
        this.elements.content.style.display = 'none';
        this.elements.footer.style.display = 'none';
        this._updateProgress(0);
    }
    
    /**
     * 更新进度条
     * @param {number} percent - 进度百分比
     * @private
     */
    _updateProgress(percent) {
        if (this.elements.progressFill) {
            this.elements.progressFill.style.width = `${percent}%`;
        }
        if (this.elements.progressText) {
            this.elements.progressText.textContent = `${percent}%`;
        }
    }
    
    /**
     * 设置加载状态
     * @param {boolean} loading - 是否加载中
     * @private
     */
    _setLoading(loading) {
        this.isLoading = loading;
        this.container.classList.toggle('loading', loading);
    }
    
    /**
     * 显示错误消息
     * @param {string} message - 错误消息
     * @private
     */
    _showError(message) {
        // 可以替换为更友好的错误提示组件
        alert(message);
    }
    
    /**
     * 显示通知
     * @param {string} message - 通知消息
     * @param {string} type - 通知类型：success, error, warning, info
     * @private
     */
    _showNotification(message, type = 'info') {
        // 可以替换为更友好的通知组件
        console.log(`[${type}] ${message}`);
    }
    
    /**
     * 获取立场文本
     * @param {string} stance - 立场代码
     * @returns {string} 立场文本
     * @private
     */
    _getStanceText(stance) {
        const stanceMap = {
            'support': '支持',
            'oppose': '反对',
            'neutral': '中立',
            'question': '质疑'
        };
        return stanceMap[stance] || '未知';
    }
    
    /**
     * 获取阶段类型文本
     * @param {string} type - 阶段类型代码
     * @returns {string} 类型文本
     * @private
     */
    _getPhaseTypeText(type) {
        const typeMap = {
            'opening': '开场',
            'discussing': '讨论',
            'debating': '辩论',
            'concluding': '总结',
            'closing': '结束'
        };
        return typeMap[type] || '讨论';
    }
    
    /**
     * 销毁面板
     */
    destroy() {
        // 清理事件监听器
        // 清理DOM
        if (this.container) {
            this.container.innerHTML = '';
        }
        
        // 重置状态
        this.summaries = [];
        this.currentSummary = null;
        this.elements = {};
    }
}

// 导出组件
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SummaryPanel;
}
