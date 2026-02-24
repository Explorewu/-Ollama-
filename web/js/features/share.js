/**
 * 协作分享模块
 * 提供对话导出、分享链接生成、剪贴板复制等功能
 */

const ShareManager = (function() {
    // 分享链接前缀
    const SHARE_BASE_URL = window.location.origin + window.location.pathname;
    
    /**
     * 导出对话为JSON格式
     * @param {Object} conversation - 对话对象
     * @returns {string} JSON字符串
     */
    function exportToJSON(conversation) {
        const data = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            conversation: {
                id: conversation.id,
                title: conversation.title,
                model: conversation.model,
                createdAt: conversation.createdAt,
                updatedAt: conversation.updatedAt,
                messages: conversation.messages
            }
        };
        
        return JSON.stringify(data, null, 2);
    }
    
    /**
     * 导出对话为Markdown格式
     * @param {Object} conversation - 对话对象
     * @returns {string} Markdown字符串
     */
    function exportToMarkdown(conversation) {
        let md = `# ${conversation.title}\n\n`;
        md += `> 模型: ${conversation.model || '未知'}\n`;
        md += `> 创建时间: ${new Date(conversation.createdAt).toLocaleString('zh-CN')}\n\n`;
        md += `---\n\n`;
        
        conversation.messages.forEach(msg => {
            const role = msg.role === 'user' ? '**用户**' : '**AI**';
            const time = msg.timestamp ? new Date(msg.timestamp).toLocaleString('zh-CN') : '';
            md += `### ${role} ${time}\n\n`;
            md += `${msg.content}\n\n`;
            md += `---\n\n`;
        });
        
        return md;
    }
    
    /**
     * 导出对话为纯文本格式
     * @param {Object} conversation - 对话对象
     * @returns {string} 纯文本字符串
     */
    function exportToText(conversation) {
        let text = `${conversation.title}\n`;
        text += `${'='.repeat(50)}\n\n`;
        
        conversation.messages.forEach(msg => {
            const role = msg.role === 'user' ? '用户' : 'AI';
            text += `[${role}]\n`;
            text += `${msg.content}\n\n`;
        });
        
        return text;
    }
    
    /**
     * 生成导出文件名
     * @param {Object} conversation - 对话对象
     * @param {string} format - 格式扩展名
     * @returns {string} 文件名
     */
    function generateExportFilename(conversation, format) {
        const title = conversation.title.replace(/[<>:"/\\|?*]/g, '_');
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
     * 导出单个对话
     * @param {Object} conversation - 对话对象
     * @param {string} format - 导出格式 (json/md/txt)
     */
    function exportConversation(conversation, format = 'json') {
        let content, filename, mimeType;
        
        switch (format.toLowerCase()) {
            case 'json':
                content = exportToJSON(conversation);
                filename = generateExportFilename(conversation, 'json');
                mimeType = 'application/json';
                break;
            case 'md':
            case 'markdown':
                content = exportToMarkdown(conversation);
                filename = generateExportFilename(conversation, 'md');
                mimeType = 'text/markdown';
                break;
            case 'txt':
            case 'text':
                content = exportToText(conversation);
                filename = generateExportFilename(conversation, 'txt');
                mimeType = 'text/plain';
                break;
            default:
                throw new Error('不支持的导出格式');
        }
        
        downloadFile(content, filename, mimeType);
    }
    
    /**
     * 导出所有对话
     * @param {Array} conversations - 对话列表
     * @param {string} format - 导出格式
     */
    function exportAllConversations(conversations, format = 'json') {
        const data = {
            version: '1.0',
            exportDate: new Date().toISOString(),
            conversations: conversations
        };
        
        let content, filename, mimeType;
        
        if (format === 'json') {
            content = JSON.stringify(data, null, 2);
            filename = `ollama_all_conversations_${new Date().toISOString().split('T')[0]}.json`;
            mimeType = 'application/json';
        } else {
            // Markdown格式
            let md = `# Ollama 对话导出\n\n`;
            md += `> 导出时间: ${new Date().toLocaleString('zh-CN')}\n`;
            md += `> 对话数量: ${conversations.length}\n\n`;
            md += `---\n\n`;
            
            conversations.forEach(conv => {
                md += exportToMarkdown(conv);
            });
            
            content = md;
            filename = `ollama_all_${new Date().toISOString().split('T')[0]}.md`;
            mimeType = 'text/markdown';
        }
        
        downloadFile(content, filename, mimeType);
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
     * 创建导出选项HTML
     * @returns {string} HTML字符串
     */
    function createExportOptions() {
        return `
            <div class="export-options">
                <div class="export-option" onclick="ShareManager.exportCurrent('json')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>JSON</span>
                </div>
                <div class="export-option" onclick="ShareManager.exportCurrent('md')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>Markdown</span>
                </div>
                <div class="export-option" onclick="ShareManager.exportCurrent('txt')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>文本</span>
                </div>
                <div class="export-option" onclick="ShareManager.exportAll()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    <span>全部导出</span>
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
        exportToJSON: exportToJSON,
        exportToMarkdown: exportToMarkdown,
        exportToText: exportToText,
        downloadFile: downloadFile,
        generateExportFilename: generateExportFilename,
        copyToClipboard: copyToClipboard,
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
