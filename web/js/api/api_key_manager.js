/**
 * API Key 管理模块
 * 提供 API Key 的生成、列表、撤销等功能
 */

const APIKeyManager = (function() {
    'use strict';

    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001/api`;
    let keys = [];
    let newKeyData = null;

    /**
     * 初始化 API Key 管理模块
     */
    async function init() {
        try {
            await loadKeys();
            bindEvents();
            updateAddressDisplay();
        } catch (error) {
            console.error('[API Key] 初始化失败:', error);
        }
    }

    /**
     * 从服务器加载 API Keys
     */
    async function loadKeys() {
        try {
            const response = await fetch(`${API_BASE}/api-key/list`);
            const data = await response.json();

            if (data.success) {
                keys = data.data || [];
                renderKeys();
            } else {
                console.error('[API Key] 加载失败:', data.error);
                keys = [];
                renderKeys();
            }
        } catch (error) {
            console.error('[API Key] 加载异常:', error);
            keys = [];
            renderKeys();
        }
    }

    /**
     * 渲染 API Keys 列表
     */
    function renderKeys() {
        const container = document.getElementById('apiKeyList');
        if (!container) return;

        if (keys.length === 0) {
            container.innerHTML = `
                <div class="api-key-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    <p>暂无 API Key</p>
                    <span>点击"生成新 Key"创建第一个密钥</span>
                </div>
            `;
            return;
        }

        container.innerHTML = keys.map(key => `
            <div class="api-key-item" data-key-id="${key.id}">
                <div class="api-key-info">
                    <h4 class="api-key-name">${escapeHtml(key.name)}</h4>
                    <div class="api-key-meta">
                        <span class="api-key-prefix">${escapeHtml(key.prefix)}****</span>
                        <span>创建于 ${formatDate(key.created_at)}</span>
                        <span>调用 ${key.usage_count || 0} 次</span>
                    </div>
                </div>
                <div class="api-key-status ${key.is_active ? 'active' : 'revoked'}">
                    <span class="status-indicator"></span>
                    ${key.is_active ? '活跃' : '已禁用'}
                </div>
                <div class="api-key-actions">
                    <button class="btn btn-secondary" onclick="APIKeyManager.showKeyInfo('${key.id}')" title="查看详情">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>
                    <button class="btn btn-danger" onclick="APIKeyManager.revokeKey('${key.id}')" title="撤销">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');
    }

    /**
     * 显示生成 Key 的模态框
     */
    function showGenerateModal() {
        const modalHtml = `
            <div class="modal-overlay active" id="generateKeyModal">
                <div class="modal-container">
                    <div class="modal-header">
                        <h3>生成 API Key</h3>
                        <button class="modal-close" onclick="APIKeyManager.closeModal()">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="keyName">Key 名称</label>
                            <input type="text" id="keyName" class="text-input" placeholder="例如：我的开发密钥">
                        </div>
                        <div class="form-group">
                            <label for="keyDescription">描述（可选）</label>
                            <textarea id="keyDescription" class="text-input" rows="3" placeholder="描述这个 Key 的用途..."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="APIKeyManager.closeModal()">取消</button>
                        <button class="btn btn-primary" onclick="APIKeyManager.generateKey()">生成</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('keyName').focus();
    }

    /**
     * 生成新的 API Key
     */
    async function generateKey() {
        const name = document.getElementById('keyName')?.value.trim() || '';
        const description = document.getElementById('keyDescription')?.value.trim() || '';

        try {
            const response = await fetch(`${API_BASE}/api-key/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description })
            });

            const data = await response.json();

            if (data.success) {
                newKeyData = data;
                closeModal();
                await loadKeys();
                showSuccessModal(data);
            } else {
                showToast(data.error || '生成失败', 'error');
            }
        } catch (error) {
            console.error('[API Key] 生成异常:', error);
            showToast('生成失败，请稍后重试', 'error');
        }
    }

    /**
     * 显示成功弹窗（显示完整的 Key）
     */
    function showSuccessModal(data) {
        const modalHtml = `
            <div class="modal-overlay active" id="successKeyModal">
                <div class="modal-container success-modal">
                    <div class="modal-header">
                        <h3>API Key 已生成</h3>
                        <button class="modal-close" onclick="APIKeyManager.closeSuccessModal()">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="success-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                        </div>
                        <p class="success-message">请立即复制您的 API Key，关闭此窗口后将无法再次查看。</p>
                        <div class="key-display">
                            <div class="key-display-label">您的 API Key</div>
                            <div class="key-display-value" id="newApiKey">${escapeHtml(data.key)}</div>
                        </div>
                        <div class="api-key-secret-warning">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                            <span>请妥善保管您的 API Key，不要分享给他人或提交到公开仓库。</span>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="APIKeyManager.closeSuccessModal()">关闭</button>
                        <button class="btn btn-primary" onclick="APIKeyManager.copyNewKey()">复制 Key</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    /**
     * 撤销 API Key
     */
    async function revokeKey(keyId) {
        const key = keys.find(k => k.id === keyId);
        if (!key) return;

        if (!confirm(`确定要撤销 "${key.name}" 吗？撤销后将无法使用此 Key 进行 API 调用。`)) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/api-key/revoke`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key_id: keyId })
            });

            const data = await response.json();

            if (data.success) {
                showToast('API Key 已撤销', 'success');
                await loadKeys();
            } else {
                showToast(data.error || '撤销失败', 'error');
            }
        } catch (error) {
            console.error('[API Key] 撤销异常:', error);
            showToast('撤销失败，请稍后重试', 'error');
        }
    }

    /**
     * 显示 Key 详情
     */
    function showKeyInfo(keyId) {
        const key = keys.find(k => k.id === keyId);
        if (!key) return;

        const lastUsed = key.last_used_at ? formatDate(key.last_used_at) : '从未使用';

        const modalHtml = `
            <div class="modal-overlay active" id="keyInfoModal">
                <div class="modal-container">
                    <div class="modal-header">
                        <h3>API Key 详情</h3>
                        <button class="modal-close" onclick="APIKeyManager.closeModal()">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>名称</label>
                            <div class="text-display">${escapeHtml(key.name)}</div>
                        </div>
                        ${key.description ? `
                        <div class="form-group">
                            <label>描述</label>
                            <div class="text-display">${escapeHtml(key.description)}</div>
                        </div>
                        ` : ''}
                        <div class="form-group">
                            <label>Key 前缀</label>
                            <div class="text-display">${escapeHtml(key.prefix)}****</div>
                        </div>
                        <div class="form-group">
                            <label>创建时间</label>
                            <div class="text-display">${formatDate(key.created_at)}</div>
                        </div>
                        <div class="form-group">
                            <label>最后使用</label>
                            <div class="text-display">${lastUsed}</div>
                        </div>
                        <div class="form-group">
                            <label>调用次数</label>
                            <div class="text-display">${key.usage_count || 0} 次</div>
                        </div>
                        <div class="form-group">
                            <label>状态</label>
                            <div class="text-display">
                                <span class="api-key-status ${key.is_active ? 'active' : 'revoked'}">
                                    <span class="status-indicator"></span>
                                    ${key.is_active ? '活跃' : '已禁用'}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="APIKeyManager.closeModal()">关闭</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    /**
     * 关闭模态框
     */
    function closeModal() {
        const modal = document.getElementById('generateKeyModal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * 关闭成功提示弹窗
     */
    function closeSuccessModal() {
        const modal = document.getElementById('successKeyModal');
        if (modal) {
            modal.remove();
        }
        newKeyData = null;
    }

    /**
     * 复制新生成的 Key
     */
    function copyNewKey() {
        const keyElement = document.getElementById('newApiKey');
        if (keyElement) {
            copyToClipboard(keyElement.textContent);
            showToast('已复制到剪贴板', 'success');
        }
    }

    /**
     * 复制 API 地址
     */
    function copyAddress() {
        const address = document.getElementById('externalApiAddress')?.textContent || window.location.origin;
        copyToClipboard(address);
        showToast('已复制 API 地址', 'success');
    }

    /**
     * 复制 cURL 调用示例
     */
    function copyExample() {
        const example = document.getElementById('curlExample')?.textContent;
        if (example) {
            copyToClipboard(example);
            showToast('已复制示例', 'success');
        }
    }

    /**
     * 复制 Python 调用示例
     */
    function copyPythonExample() {
        const example = document.getElementById('pythonExample')?.textContent;
        if (example) {
            copyToClipboard(example);
            showToast('已复制示例', 'success');
        }
    }

    /**
     * 更新地址显示
     */
    function updateAddressDisplay() {
        const addressElement = document.getElementById('externalApiAddress');
        if (addressElement && !addressElement.textContent.trim()) {
            addressElement.textContent = window.location.origin;
        }
    }

    /**
     * 绑定事件
     */
    function bindEvents() {
        document.addEventListener('keydown', function handleKeydown(e) {
            if (e.key === 'Escape') {
                closeModal();
                closeSuccessModal();
            }
        });
    }

    /**
     * 复制到剪贴板
     */
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }

    /**
     * 显示提示消息
     */
    function showToast(message, type = 'info') {
        if (typeof App !== 'undefined' && App.showToast) {
            App.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
            alert(message);
        }
    }

    /**
     * 格式化日期
     */
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * HTML 转义
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return {
        init,
        loadKeys,
        showGenerateModal,
        generateKey,
        revokeKey,
        showKeyInfo,
        closeModal,
        closeSuccessModal,
        copyNewKey,
        copyAddress,
        copyExample,
        copyPythonExample
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = APIKeyManager;
}
