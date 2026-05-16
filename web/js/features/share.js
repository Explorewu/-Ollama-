/**
 * 协作分享模块
 * 提供对话导出、分享链接生成、剪贴板复制等功能
 */

const ShareManager = (function() {
    // 分享链接前缀
    const SHARE_BASE_URL = window.location.origin + window.location.pathname;
    
    /**
     * 导出对话为纯文本格式（简洁版）
     * 只保留用户和AI的对话内容，无额外元数据
     * @param {Object} conversation - 对话对象
     * @returns {string} 纯文本字符串
     */
    function exportToText(conversation) {
        const lines = [];
        
        // 标题
        if (conversation.title) {
            lines.push(conversation.title);
            lines.push('');
        }
        
        // 对话内容
        if (conversation.messages && conversation.messages.length > 0) {
            conversation.messages.forEach(msg => {
                const role = msg.role === 'user' ? '用户' : 'AI';
                lines.push(`${role}: ${msg.content}`);
                lines.push('');
            });
        }
        
        return lines.join('\n');
    }
    
    /**
     * 生成导出文件名
     * @param {Object} conversation - 对话对象
     * @param {string} format - 格式扩展名
     * @returns {string} 文件名
     */
    function generateExportFilename(conversation, format) {
        const title = (conversation.title || 'untitled').replace(/[<>:"/\\|?*]/g, '_');
        const date = new Date().toISOString().split('T')[0];
        return `ollama_${title}_${date}.${format}`;
    }
    
    /**
     * 下载文件
     * @param {string} content - 文件内容
     * @param {string} filename - 文件名
     * @param {string} mimeType - MIME类型
     */
    function downloadFile(content, filename, mimeType = 'text/plain') {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
    
    /**
     * 导出单个对话（仅纯文本）
     * @param {Object} conversation - 对话对象
     */
    function exportConversation(conversation) {
        const content = exportToText(conversation);
        const filename = generateExportFilename(conversation, 'txt');
        downloadFile(content, filename, 'text/plain');
    }
    
    /**
     * 导出当前对话（供UI调用）
     */
    function exportCurrent() {
        const app = window.App;
        if (!app || !app.state.currentConversation) {
            showNotification('请先选择一个对话', 'warning');
            return;
        }
        exportConversation(app.state.currentConversation);
        showNotification('对话已导出', 'success');
    }
    
    /**
     * 导出所有对话（供UI调用）
     */
    function exportAll() {
        const conversations = Storage.getAllConversations();
        if (!conversations || conversations.length === 0) {
            showNotification('没有可导出的对话', 'warning');
            return;
        }
        exportAllConversations(conversations);
        showNotification(`已导出 ${conversations.length} 个对话`, 'success');
    }
    
    /**
     * 导出所有对话（仅纯文本）
     * @param {Array} conversations - 对话列表
     */
    function exportAllConversations(conversations) {
        const lines = [];
        
        conversations.forEach((conv, index) => {
            // 对话标题
            if (conv.title) {
                lines.push(conv.title);
                lines.push('');
            }
            
            // 对话内容
            if (conv.messages && conv.messages.length > 0) {
                conv.messages.forEach(msg => {
                    const role = msg.role === 'user' ? '用户' : 'AI';
                    lines.push(`${role}: ${msg.content}`);
                    lines.push('');
                });
            }
            
            // 对话之间添加分隔
            if (index < conversations.length - 1) {
                lines.push('---');
                lines.push('');
            }
        });
        
        const content = lines.join('\n');
        const filename = `ollama_all_conversations_${new Date().toISOString().split('T')[0]}.txt`;
        downloadFile(content, filename, 'text/plain');
    }
    
    /**
     * 复制到剪贴板
     * @param {string} text - 要复制的文本
     * @returns {Promise<boolean>} 是否复制成功
     */
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            // 降级方案
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            
            try {
                document.execCommand('copy');
                return true;
            } catch (e) {
                console.error('复制失败:', e);
                return false;
            } finally {
                document.body.removeChild(textarea);
            }
        }
    }
    
    /**
     * 复制当前对话内容到剪贴板（纯文本）
     */
    async function copyConversation() {
        const app = window.App;
        if (!app || !app.state.currentConversation) {
            showNotification('请先选择一个对话', 'warning');
            return;
        }
        const text = exportToText(app.state.currentConversation);
        const success = await copyToClipboard(text);
        showNotification(success ? '已复制到剪贴板' : '复制失败', success ? 'success' : 'error');
    }
    
    /**
     * 复制当前对话为纯文本格式（与 copyConversation 相同）
     */
    async function copyMarkdown() {
        // 简化处理：与 copyConversation 相同，都是纯文本
        await copyConversation();
    }
    
    /**
     * 生成分享链接
     * @param {Object} conversation - 对话对象
     * @returns {string} 分享链接
     */
    function generateShareLink(conversation) {
        // 创建一个包含对话数据的编码字符串
        const data = btoa(encodeURIComponent(JSON.stringify({
            id: conversation.id,
            title: conversation.title,
            model: conversation.model,
            messages: conversation.messages.slice(0, 10) // 限制消息数量
        })));
        
        return `${SHARE_BASE_URL}?share=${data}`;
    }
    
    /**
     * 从分享链接解析对话数据
     * @param {string} url - 分享链接
     * @returns {Object|null} 对话数据
     */
    function parseShareLink(url) {
        try {
            const urlObj = new URL(url);
            const shareData = urlObj.searchParams.get('share');
            
            if (shareData) {
                return JSON.parse(decodeURIComponent(atob(shareData)));
            }
        } catch (error) {
            console.error('解析分享链接失败:', error);
        }
        
        return null;
    }
    
    /**
     * 创建分享选项HTML
     * @returns {string} HTML字符串
     */
    function createShareOptions() {
        return `
            <div class="share-options">
                <div class="share-option" onclick="ShareManager.copyConversation()">
                    <div class="share-option-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                        </svg>
                    </div>
                    <div class="share-option-content">
                        <div class="share-option-title">复制对话内容</div>
                        <div class="share-option-desc">将当前对话复制到剪贴板</div>
                    </div>
                </div>
                <div class="share-option" onclick="ShareManager.copyMarkdown()">
                    <div class="share-option-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                            <polyline points="10 9 9 9 8 9"/>
                        </svg>
                    </div>
                    <div class="share-option-content">
                        <div class="share-option-title">复制 Markdown</div>
                        <div class="share-option-desc">以 Markdown 格式复制对话</div>
                    </div>
                </div>
                <div class="share-option" onclick="ShareManager.showShareLink()">
                    <div class="share-option-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/>
                            <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>
                        </svg>
                    </div>
                    <div class="share-option-content">
                        <div class="share-option-title">生成分享链接</div>
                        <div class="share-option-desc">创建可分享的对话链接</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * 创建导出选项HTML（仅纯文本）
     * @returns {string} HTML字符串
     */
    function createExportOptions() {
        return `
            <div class="export-options">
                <div class="export-option" onclick="ShareManager.exportCurrent()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>导出当前对话</span>
                </div>
                <div class="export-option" onclick="ShareManager.exportAll()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    <span>导出全部对话</span>
                </div>
            </div>
        `;
    }
    
    /**
     * 创建分享链接输入框HTML
     * @param {string} link - 分享链接
     * @returns {string} HTML字符串
     */
    function createShareLinkInput(link) {
        return `
            <div class="share-link-container">
                <div class="share-link-input-group">
                    <input type="text" class="share-link-input" value="${link}" readonly id="shareLinkInput">
                    <button class="share-copy-btn" onclick="ShareManager.copyShareLink()">复制链接</button>
                </div>
            </div>
        `;
    }
    
    /**
     * 显示通知消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型 (success/error/warning)
     */
    function showNotification(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // 公开API
    return {
        exportConversation: exportConversation,
        exportAllConversations: exportAllConversations,
        exportCurrent: exportCurrent,
        exportAll: exportAll,
        exportToText: exportToText,
        downloadFile: downloadFile,
        generateExportFilename: generateExportFilename,
        copyToClipboard: copyToClipboard,
        copyConversation: copyConversation,
        copyMarkdown: copyMarkdown,
        generateShareLink: generateShareLink,
        parseShareLink: parseShareLink,
        createShareOptions: createShareOptions,
        createExportOptions: createExportOptions,
        createShareLinkInput: createShareLinkInput,
        showNotification: showNotification,
        SHARE_BASE_URL: SHARE_BASE_URL
    };
})();

// 挂载到全局
window.ShareManager = ShareManager;
