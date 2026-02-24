/**
 * 格式化工具模块
 * 
 * 提供通用的格式化函数，包括：
 * - HTML转义
 * - 时间格式化
 * - 文件大小格式化
 * - 文本截断
 */

const IntelligentFormatters = (function() {
    
    /**
     * HTML转义，防止XSS攻击
     * @param {string} text - 原始文本
     * @returns {string} 转义后的HTML文本
     */
    function escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * 格式化时间戳为相对时间
     * @param {number} timestamp - Unix时间戳（秒）
     * @returns {string} 格式化后的时间字符串
     */
    function formatTime(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diff = now - date;
        
        // 小于1分钟
        if (diff < 60000) return '刚刚';
        
        // 小于1小时
        if (diff < 3600000) {
            return Math.floor(diff / 60000) + '分钟前';
        }
        
        // 小于24小时
        if (diff < 86400000) {
            return Math.floor(diff / 3600000) + '小时前';
        }
        
        // 小于7天
        if (diff < 604800000) {
            return Math.floor(diff / 86400000) + '天前';
        }
        
        // 超过7天，显示日期
        return date.toLocaleDateString('zh-CN');
    }
    
    /**
     * 格式化日期时间
     * @param {number|string|Date} date - 日期对象或时间戳
     * @param {string} format - 格式模板，默认 'YYYY-MM-DD HH:mm:ss'
     * @returns {string} 格式化后的日期字符串
     */
    function formatDateTime(date, format = 'YYYY-MM-DD HH:mm:ss') {
        if (!date) return '';
        
        const d = date instanceof Date ? date : new Date(date);
        
        if (isNaN(d.getTime())) return '';
        
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const seconds = String(d.getSeconds()).padStart(2, '0');
        
        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds);
    }
    
    /**
     * 格式化文件大小
     * @param {number} bytes - 字节数
     * @param {number} decimals - 小数位数，默认2
     * @returns {string} 格式化后的文件大小字符串
     */
    function formatFileSize(bytes, decimals = 2) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
    }
    
    /**
     * 截断文本
     * @param {string} text - 原始文本
     * @param {number} maxLength - 最大长度
     * @param {string} suffix - 后缀，默认'...'
     * @returns {string} 截断后的文本
     */
    function truncateText(text, maxLength, suffix = '...') {
        if (!text || text.length <= maxLength) return text || '';
        
        return text.substring(0, maxLength - suffix.length) + suffix;
    }
    
    /**
     * 格式化数字（添加千位分隔符）
     * @param {number} num - 数字
     * @returns {string} 格式化后的数字字符串
     */
    function formatNumber(num) {
        if (num === null || num === undefined) return '0';
        
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }
    
    /**
     * 格式化百分比
     * @param {number} value - 0-1之间的小数
     * @param {number} decimals - 小数位数，默认1
     * @returns {string} 格式化后的百分比字符串
     */
    function formatPercent(value, decimals = 1) {
        if (value === null || value === undefined) return '0%';
        
        return (value * 100).toFixed(decimals) + '%';
    }
    
    /**
     * 格式化持续时间（秒转时分秒）
     * @param {number} seconds - 秒数
     * @returns {string} 格式化后的时间字符串
     */
    function formatDuration(seconds) {
        if (!seconds || seconds < 0) return '0秒';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}小时${minutes}分钟${secs}秒`;
        } else if (minutes > 0) {
            return `${minutes}分钟${secs}秒`;
        } else {
            return `${secs}秒`;
        }
    }
    
    /**
     * 生成唯一ID
     * @param {string} prefix - ID前缀
     * @returns {string} 唯一ID
     */
    function generateId(prefix = 'id') {
        return prefix + '_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * 将数组分块
     * @param {Array} array - 原始数组
     * @param {number} size - 每块大小
     * @returns {Array} 分块后的数组
     */
    function chunkArray(array, size) {
        if (!Array.isArray(array) || size <= 0) return [];
        
        const chunks = [];
        for (let i = 0; i < array.length; i += size) {
            chunks.push(array.slice(i, i + size));
        }
        return chunks;
    }
    
    /**
     * 去重数组（基于指定键）
     * @param {Array} array - 原始数组
     * @param {string} key - 用于去重的键
     * @returns {Array} 去重后的数组
     */
    function uniqueByKey(array, key) {
        if (!Array.isArray(array)) return [];
        
        const seen = new Set();
        return array.filter(item => {
            const val = item[key];
            if (seen.has(val)) return false;
            seen.add(val);
            return true;
        });
    }
    
    // 公共API
    return {
        escapeHtml,
        formatTime,
        formatDateTime,
        formatFileSize,
        truncateText,
        formatNumber,
        formatPercent,
        formatDuration,
        generateId,
        chunkArray,
        uniqueByKey
    };
})();

// 导出模块
window.IntelligentFormatters = IntelligentFormatters;
