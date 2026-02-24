/**
 * 验证工具模块
 * 
 * 提供通用的验证函数，包括：
 * - 字符串验证
 * - 数字验证
 * - 对象验证
 * - 表单验证
 */

const IntelligentValidators = (function() {
    
    /**
     * 验证字符串是否为空
     * @param {string} value - 要验证的值
     * @returns {boolean}
     */
    function isEmpty(value) {
        if (value === null || value === undefined) return true;
        if (typeof value === 'string') return value.trim().length === 0;
        if (Array.isArray(value)) return value.length === 0;
        if (typeof value === 'object') return Object.keys(value).length === 0;
        return false;
    }
    
    /**
     * 验证字符串最小长度
     * @param {string} value - 要验证的字符串
     * @param {number} minLength - 最小长度
     * @returns {boolean}
     */
    function minLength(value, minLength) {
        if (typeof value !== 'string') return false;
        return value.length >= minLength;
    }
    
    /**
     * 验证字符串最大长度
     * @param {string} value - 要验证的字符串
     * @param {number} maxLength - 最大长度
     * @returns {boolean}
     */
    function maxLength(value, maxLength) {
        if (typeof value !== 'string') return false;
        return value.length <= maxLength;
    }
    
    /**
     * 验证字符串长度范围
     * @param {string} value - 要验证的字符串
     * @param {number} min - 最小长度
     * @param {number} max - 最大长度
     * @returns {boolean}
     */
    function lengthRange(value, min, max) {
        if (typeof value !== 'string') return false;
        const len = value.length;
        return len >= min && len <= max;
    }
    
    /**
     * 验证是否为有效数字
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isNumber(value) {
        return typeof value === 'number' && !isNaN(value) && isFinite(value);
    }
    
    /**
     * 验证数字范围
     * @param {number} value - 要验证的数字
     * @param {number} min - 最小值
     * @param {number} max - 最大值
     * @returns {boolean}
     */
    function numberRange(value, min, max) {
        if (!isNumber(value)) return false;
        return value >= min && value <= max;
    }
    
    /**
     * 验证是否为整数
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isInteger(value) {
        return isNumber(value) && Number.isInteger(value);
    }
    
    /**
     * 验证是否为正数
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isPositive(value) {
        return isNumber(value) && value > 0;
    }
    
    /**
     * 验证是否为非负数
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isNonNegative(value) {
        return isNumber(value) && value >= 0;
    }
    
    /**
     * 验证邮箱格式
     * @param {string} value - 要验证的邮箱
     * @returns {boolean}
     */
    function isEmail(value) {
        if (typeof value !== 'string') return false;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(value);
    }
    
    /**
     * 验证URL格式
     * @param {string} value - 要验证的URL
     * @returns {boolean}
     */
    function isUrl(value) {
        if (typeof value !== 'string') return false;
        try {
            new URL(value);
            return true;
        } catch {
            return false;
        }
    }
    
    /**
     * 验证是否为有效的JSON字符串
     * @param {string} value - 要验证的字符串
     * @returns {boolean}
     */
    function isJson(value) {
        if (typeof value !== 'string') return false;
        try {
            JSON.parse(value);
            return true;
        } catch {
            return false;
        }
    }
    
    /**
     * 验证是否为数组
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isArray(value) {
        return Array.isArray(value);
    }
    
    /**
     * 验证是否为对象
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isObject(value) {
        return typeof value === 'object' && value !== null && !Array.isArray(value);
    }
    
    /**
     * 验证是否为函数
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isFunction(value) {
        return typeof value === 'function';
    }
    
    /**
     * 验证是否为日期对象
     * @param {any} value - 要验证的值
     * @returns {boolean}
     */
    function isDate(value) {
        return value instanceof Date && !isNaN(value.getTime());
    }
    
    /**
     * 验证数组是否包含指定值
     * @param {Array} array - 要检查的数组
     * @param {any} value - 要查找的值
     * @returns {boolean}
     */
    function contains(array, value) {
        if (!Array.isArray(array)) return false;
        return array.includes(value);
    }
    
    /**
     * 验证数组长度
     * @param {Array} array - 要验证的数组
     * @param {number} min - 最小长度
     * @param {number} max - 最大长度
     * @returns {boolean}
     */
    function arrayLength(array, min, max) {
        if (!Array.isArray(array)) return false;
        const len = array.length;
        return len >= min && len <= max;
    }
    
    /**
     * 验证表单字段
     * @param {Object} data - 表单数据
     * @param {Object} rules - 验证规则
     * @returns {Object} 验证结果 { valid: boolean, errors: Object }
     */
    function validateForm(data, rules) {
        const errors = {};
        let valid = true;
        
        for (const field in rules) {
            if (!rules.hasOwnProperty(field)) continue;
            
            const value = data[field];
            const fieldRules = rules[field];
            const fieldErrors = [];
            
            for (const rule of fieldRules) {
                const { type, message, ...params } = rule;
                let isValid = true;
                
                switch (type) {
                    case 'required':
                        isValid = !isEmpty(value);
                        break;
                    case 'minLength':
                        isValid = minLength(value, params.length);
                        break;
                    case 'maxLength':
                        isValid = maxLength(value, params.length);
                        break;
                    case 'lengthRange':
                        isValid = lengthRange(value, params.min, params.max);
                        break;
                    case 'number':
                        isValid = isNumber(value);
                        break;
                    case 'numberRange':
                        isValid = numberRange(value, params.min, params.max);
                        break;
                    case 'integer':
                        isValid = isInteger(value);
                        break;
                    case 'email':
                        isValid = isEmail(value);
                        break;
                    case 'url':
                        isValid = isUrl(value);
                        break;
                    case 'pattern':
                        isValid = params.regex.test(value);
                        break;
                    case 'custom':
                        isValid = params.validator(value, data);
                        break;
                    default:
                        break;
                }
                
                if (!isValid) {
                    fieldErrors.push(message);
                    valid = false;
                }
            }
            
            if (fieldErrors.length > 0) {
                errors[field] = fieldErrors;
            }
        }
        
        return { valid, errors };
    }
    
    /**
     * 验证记忆内容
     * @param {Object} memory - 记忆对象
     * @returns {Object} 验证结果
     */
    function validateMemory(memory) {
        return validateForm(memory, {
            content: [
                { type: 'required', message: '记忆内容不能为空' },
                { type: 'minLength', length: 1, message: '记忆内容不能为空' },
                { type: 'maxLength', length: 5000, message: '记忆内容不能超过5000字符' }
            ],
            category: [
                { type: 'required', message: '分类不能为空' }
            ],
            importance: [
                { type: 'numberRange', min: 1, max: 10, message: '重要性必须在1-10之间' }
            ]
        });
    }
    
    /**
     * 验证上下文配置
     * @param {Object} config - 配置对象
     * @returns {Object} 验证结果
     */
    function validateContextConfig(config) {
        return validateForm(config, {
            max_total_tokens: [
                { type: 'integer', message: '最大Token数必须是整数' },
                { type: 'numberRange', min: 1000, max: 32000, message: '最大Token数必须在1000-32000之间' }
            ],
            regular_window_size: [
                { type: 'integer', message: '窗口大小必须是整数' },
                { type: 'numberRange', min: 1, max: 100, message: '窗口大小必须在1-100之间' }
            ],
            core_messages_max: [
                { type: 'integer', message: '核心消息数必须是整数' },
                { type: 'numberRange', min: 1, max: 20, message: '核心消息数必须在1-20之间' }
            ],
            min_importance_threshold: [
                { type: 'number', message: '重要性阈值必须是数字' },
                { type: 'numberRange', min: 0, max: 1, message: '重要性阈值必须在0-1之间' }
            ]
        });
    }
    
    // 公共API
    return {
        isEmpty,
        minLength,
        maxLength,
        lengthRange,
        isNumber,
        numberRange,
        isInteger,
        isPositive,
        isNonNegative,
        isEmail,
        isUrl,
        isJson,
        isArray,
        isObject,
        isFunction,
        isDate,
        contains,
        arrayLength,
        validateForm,
        validateMemory,
        validateContextConfig
    };
})();

// 导出模块
window.IntelligentValidators = IntelligentValidators;
