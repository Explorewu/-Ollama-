/**
 * Markdown渲染与代码高亮模块
 * 提供完整的Markdown解析和语法高亮功能
 */

const MarkdownRenderer = (function() {
    // 配置常量
    const CSS_PREFIX = 'md-'; // Markdown Renderer 前缀
    const ALLOWED_PROTOCOLS = ['http:', 'https:', 'mailto:', 'tel:'];
    
    // 分段配置
    const PARAGRAPH_CONFIG = {
        // 段落分隔符：连续2个及以上换行
        paragraphBreak: /\n{2,}/,
        // 需要保护的结构（不参与分段）
        protectedStructures: [
            { type: 'codeBlock', pattern: /```[\s\S]*?```/g },
            { type: 'htmlBlock', pattern: /<[a-zA-Z][^>]*>[\s\S]*?<\/[a-zA-Z][^>]*>/g },
            { type: 'table', pattern: /\|.+\|\n\|[-:| ]+\|\n\|.+\|/g }
        ],
        // 块级元素标记（不应被包裹为段落）
        blockElements: [
            '<h1', '<h2', '<h3', '<h4', '<h5', '<h6',
            '<ul', '<ol', '<li', '<blockquote', '<pre',
            '<div', '<table', '<hr', '<' + CSS_PREFIX
        ],
        // AI回复格式模式
        aiFormats: {
            // 冒号分隔的键值对
            keyValue: /^([^：:]+)[：:]\s*(.+)$/,
            // 编号列表
            numberedItem: /^\s*(\d+)[.．、]\s*(.+)$/,
            // 项目符号
            bulletItem: /^\s*[-*•]\s*(.+)$/
        }
    };
    
    // 语言关键字配置
    const languageKeywords = {
        javascript: [
            'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while',
            'class', 'extends', 'import', 'export', 'default', 'async', 'await',
            'try', 'catch', 'finally', 'throw', 'new', 'this', 'true', 'false', 'null',
            'typeof', 'instanceof', 'in', 'of', 'switch', 'case', 'break', 'continue'
        ],
        python: [
            'def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while', 'try',
            'except', 'finally', 'with', 'as', 'import', 'from', 'raise', 'yield',
            'lambda', 'and', 'or', 'not', 'in', 'is', 'True', 'False', 'None',
            'pass', 'break', 'continue', 'global', 'nonlocal', 'assert', 'async', 'await'
        ],
        html: [
            'html', 'head', 'body', 'div', 'span', 'p', 'a', 'img', 'ul', 'li',
            'table', 'tr', 'td', 'th', 'form', 'input', 'button', 'script', 'style'
        ],
        css: [
            'color', 'background', 'font-size', 'margin', 'padding', 'border',
            'display', 'position', 'width', 'height', 'top', 'left', 'right',
            'bottom', 'flex', 'grid', 'align', 'justify', 'z-index', 'overflow'
        ],
        java: [
            'public', 'private', 'protected', 'class', 'interface', 'extends',
            'implements', 'return', 'void', 'int', 'String', 'boolean', 'if',
            'else', 'for', 'while', 'try', 'catch', 'finally', 'throw', 'new',
            'this', 'super', 'static', 'final', 'null', 'true', 'false', 'package', 'import'
        ],
        cpp: [
            'int', 'char', 'float', 'double', 'void', 'bool', 'class', 'struct',
            'public', 'private', 'protected', 'virtual', 'override', 'return',
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
            'new', 'delete', 'this', 'nullptr', 'true', 'false', 'include', 'using', 'namespace'
        ],
        go: [
            'func', 'var', 'const', 'type', 'struct', 'interface', 'map', 'chan',
            'return', 'if', 'else', 'for', 'range', 'switch', 'case', 'default',
            'break', 'continue', 'goto', 'fallthrough', 'package', 'import', 'defer', 'go', 'select'
        ],
        rust: [
            'fn', 'let', 'mut', 'const', 'struct', 'enum', 'impl', 'trait',
            'return', 'if', 'else', 'match', 'for', 'while', 'loop', 'break',
            'true', 'false', 'self', 'Self', 'pub', 'mod', 'use', 'crate', 'super', 'async', 'await'
        ],
        typescript: [
            'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while',
            'class', 'extends', 'import', 'export', 'default', 'async', 'await',
            'interface', 'type', 'enum', 'public', 'private', 'protected',
            'try', 'catch', 'finally', 'new', 'this', 'true', 'false', 'null', 'undefined'
        ],
        sql: [
            'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE',
            'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE',
            'TABLE', 'INDEX', 'DROP', 'ALTER', 'JOIN', 'LEFT', 'RIGHT',
            'INNER', 'OUTER', 'ON', 'GROUP', 'BY', 'ORDER', 'ASC', 'DESC', 'LIMIT', 'OFFSET'
        ],
        bash: [
            'if', 'then', 'else', 'elif', 'fi', 'case', 'esac', 'for',
            'while', 'until', 'do', 'done', 'in', 'function', 'return',
            'exit', 'echo', 'read', 'local', 'export', 'source', 'alias'
        ],
        json: {
            special: ['{', '}', '[', ']', ':', ',']
        },
        xml: {
            tags: ['<', '>', '</', '/>', '<?', '?>']
        }
    };

    // 代码高亮主题色配置
    const codeColors = {
        keyword: '#D73A49',
        string: '#032F62',
        number: '#005CC5',
        comment: '#6A737D',
        function: '#6F42C1',
        operator: '#D73A49',
        variable: '#E36209',
        type: '#22863A',
        tag: '#22863A',
        attribute: '#6F42C1',
        punctuation: '#24292E',
        title: '#005CC5',
        section: '#6F42C1',
        built_in: '#6F42C1',
        literal: '#032F62',
        symbol: '#032F62'
    };

    // 检测代码语言
    function detectLanguage(code) {
        const lowerCode = code.trim().toLowerCase();
        
        if (lowerCode.startsWith('function') || lowerCode.includes('=>') || 
            lowerCode.includes('console.log') || lowerCode.includes('document.')) {
            return 'javascript';
        }
        if (lowerCode.startsWith('def ') || lowerCode.includes('print(') || 
            lowerCode.includes('import ') || lowerCode.includes('class ')) {
            return 'python';
        }
        if (lowerCode.startsWith('<!') || lowerCode.startsWith('<?') || 
            lowerCode.includes('<html') || lowerCode.includes('<div')) {
            return 'html';
        }
        if (lowerCode.includes('{') && lowerCode.includes(';') && 
            (lowerCode.includes('color') || lowerCode.includes('margin') || 
             lowerCode.includes('display'))) {
            return 'css';
        }
        if (lowerCode.startsWith('public') || lowerCode.startsWith('class ') ||
            lowerCode.includes('system.out')) {
            return 'java';
        }
        if (lowerCode.startsWith('package') || lowerCode.includes('fmt.') ||
            lowerCode.includes('func ') || lowerCode.includes('go ')) {
            return 'go';
        }
        if (lowerCode.startsWith('fn ') || lowerCode.startsWith('let ') ||
            lowerCode.includes('println!') || lowerCode.includes('vec!')) {
            return 'rust';
        }
        if (lowerCode.includes('interface ') || lowerCode.includes(': string') ||
            lowerCode.includes(': number') || lowerCode.includes('type ')) {
            return 'typescript';
        }
        if (lowerCode.includes('SELECT ') || lowerCode.includes('INSERT ') ||
            lowerCode.includes('UPDATE ') || lowerCode.includes('DELETE ')) {
            return 'sql';
        }
        if (lowerCode.startsWith('#!') || lowerCode.includes('echo ') ||
            lowerCode.includes('npm ') || lowerCode.includes('yarn ')) {
            return 'bash';
        }
        
        return 'plaintext';
    }

    // HTML转义
    function escapeHtml(text) {
        const htmlEscapes = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        };
        return text.replace(/[&<>"']/g, char => htmlEscapes[char]);
    }

    // 代码语法高亮
    function highlightCode(code, language) {
        let highlighted = escapeHtml(code);
        
        if (language === 'plaintext' || !languageKeywords[language]) {
            return '<span class="code-plaintext">' + highlighted + '</span>';
        }

        const keywords = languageKeywords[language];
        
        if (Array.isArray(keywords)) {
            // 处理关键字 - 使用函数替换避免 $ 字符问题
            keywords.forEach(keyword => {
                const pattern = new RegExp('\\b(' + keyword + ')\\b', 'g');
                highlighted = highlighted.replace(pattern, function(match, p1) {
                    return '<span class="code-keyword">' + p1 + '</span>';
                });
            });
        }

        // 处理字符串（单引号和双引号）- 使用函数替换
        highlighted = highlighted.replace(
            /(['"`])([\s\S]*?)\1/g,
            function(match) {
                return '<span class="code-string">' + match + '</span>';
            }
        );

        // 处理数字 - 使用函数替换
        highlighted = highlighted.replace(
            /\b(\d+\.?\d*)\b/g,
            function(match, p1) {
                return '<span class="code-number">' + p1 + '</span>';
            }
        );

        // 处理注释 - 使用函数替换
        if (language === 'python' || language === 'bash' || language === 'sql') {
            highlighted = highlighted.replace(
                /(#|---|--)(.*)$/gm,
                function(match) {
                    return '<span class="code-comment">' + match + '</span>';
                }
            );
        } else if (language === 'html' || language === 'xml') {
            highlighted = highlighted.replace(
                /(&lt;!--[\s\S]*?--&gt;)/g,
                function(match, p1) {
                    return '<span class="code-comment">' + p1 + '</span>';
                }
            );
        } else {
            highlighted = highlighted.replace(
                /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
                function(match, p1) {
                    return '<span class="code-comment">' + p1 + '</span>';
                }
            );
        }

        // 处理函数调用 - 使用函数替换
        highlighted = highlighted.replace(
            /\b([a-zA-Z_]\w*)\s*\(/g,
            function(match, p1) {
                return '<span class="code-function">' + p1 + '</span>(';
            }
        );

        // 处理操作符
        const operators = ['===', '!==', '==', '!=', '<=', '>=', '&&', '||', '=>', '+=', '-=', '*=', '/='];
        operators.forEach(op => {
            const pattern = new RegExp('\\' + op.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
            highlighted = highlighted.replace(pattern, function(match) {
                return '<span class="code-operator">' + op + '</span>';
            });
        });

        // 处理JSON键名 - 使用函数替换
        if (language === 'json') {
            highlighted = highlighted.replace(
                /"([^"]+)":/g,
                function(match, p1) {
                    return '<span class="code-attribute">"' + p1 + '"</span>:';
                }
            );
        }

        // 处理HTML标签
        if (language === 'html' || language === 'xml') {
            highlighted = highlighted.replace(
                /(&lt;\/?)([\w-]+)/g,
                function(match, bracket, tagName) {
                    return bracket + '<span class="code-tag">' + tagName + '</span>';
                }
            );
            highlighted = highlighted.replace(
                /([\w-]+)=/g,
                function(match, attrName) {
                    return '<span class="code-attribute">' + attrName + '</span>=';
                }
            );
        }

        return '<span class="code-' + language + '">' + highlighted + '</span>';
    }

    // 解析Markdown代码块
    function parseCodeBlock(text) {
        return text.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
            const language = lang.trim().toLowerCase() || detectLanguage(code);
            const highlightedCode = highlightCode(code.trim(), language);
            return '<div class="code-block" data-language="' + language + '">' +
                   '<div class="code-header">' +
                   '<span class="code-lang">' + (language || 'text') + '</span>' +
                   '<button class="code-copy-btn" onclick="MarkdownRenderer.copyCode(this)">复制</button>' +
                   '</div>' +
                   '<pre><code class="code-content">' + highlightedCode + '</code></pre></div>';
        });
    }

    // 解析Markdown内联代码
    function parseInlineCode(text) {
        return text.replace(/`([^`]+)`/g, function(match, code) {
            return '<code class="inline-code">' + escapeHtml(code) + '</code>';
        });
    }

    // 解析标题
    function parseHeaders(text) {
        let lines = text.split('\n');
        let result = [];
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            
            // H1
            if (line.match(/^#\s+(.+)$/)) {
                result.push('<h1 class="' + CSS_PREFIX + 'h1">' + line.replace(/^#\s+/, function(match) {
                    return '';
                }) + '</h1>');
            }
            // H2
            else if (line.match(/^##\s+(.+)$/)) {
                result.push('<h2 class="' + CSS_PREFIX + 'h2">' + line.replace(/^##\s+/, function(match) {
                    return '';
                }) + '</h2>');
            }
            // H3
            else if (line.match(/^###\s+(.+)$/)) {
                result.push('<h3 class="' + CSS_PREFIX + 'h3">' + line.replace(/^###\s+/, function(match) {
                    return '';
                }) + '</h3>');
            }
            // H4
            else if (line.match(/^####\s+(.+)$/)) {
                result.push('<h4 class="' + CSS_PREFIX + 'h4">' + line.replace(/^####\s+/, function(match) {
                    return '';
                }) + '</h4>');
            }
            // H5
            else if (line.match(/^#####\s+(.+)$/)) {
                result.push('<h5 class="' + CSS_PREFIX + 'h5">' + line.replace(/^#####\s+/, function(match) {
                    return '';
                }) + '</h5>');
            }
            // H6
            else if (line.match(/^######\s+(.+)$/)) {
                result.push('<h6 class="' + CSS_PREFIX + 'h6">' + line.replace(/^######\s+/, function(match) {
                    return '';
                }) + '</h6>');
            }
            else {
                result.push(line);
            }
        }
        
        return result.join('\n');
    }

    // 解析粗体和斜体 - 优化版本：单次遍历完成所有强调格式解析
    function parseEmphasis(text) {
        // 按优先级排序的正则表达式模式（长的优先，避免部分匹配）
        const patterns = [
            { regex: /\*\*\*([^*]+)\*\*\*/g, handler: function(match, p1) { return '<strong class="' + CSS_PREFIX + 'bold"><em class="' + CSS_PREFIX + 'italic">' + p1 + '</em></strong>'; } },
            { regex: /___([^_]+)___/g, handler: function(match, p1) { return '<strong class="' + CSS_PREFIX + 'bold"><em class="' + CSS_PREFIX + 'italic">' + p1 + '</em></strong>'; } },
            { regex: /\*\*([^*]+)\*\*/g, handler: function(match, p1) { return '<strong class="' + CSS_PREFIX + 'bold">' + p1 + '</strong>'; } },
            { regex: /__([^_]+)__/g, handler: function(match, p1) { return '<strong class="' + CSS_PREFIX + 'bold">' + p1 + '</strong>'; } },
            { regex: /~~([^~]+)~~/g, handler: function(match, p1) { return '<del class="' + CSS_PREFIX + 'strike">' + p1 + '</del>'; } },
            { regex: /\*([^*]+)\*/g, handler: function(match, p1) { return '<em class="' + CSS_PREFIX + 'italic">' + p1 + '</em>'; } },
            { regex: /_([^_]+)_/g, handler: function(match, p1) { return '<em class="' + CSS_PREFIX + 'italic">' + p1 + '</em>'; } }
        ];
        
        // 使用单次遍历处理所有模式
        // 策略：先找到所有匹配位置，然后按位置排序后统一替换
        let matches = [];
        
        patterns.forEach(function(patternObj, patternIndex) {
            let match;
            // 重置正则表达式的 lastIndex
            patternObj.regex.lastIndex = 0;
            while ((match = patternObj.regex.exec(text)) !== null) {
                matches.push({
                    index: match.index,
                    length: match[0].length,
                    replacement: patternObj.handler(match[0], match[1]),
                    patternIndex: patternIndex
                });
                // 避免零长度匹配的无限循环
                if (match.index === patternObj.regex.lastIndex) {
                    patternObj.regex.lastIndex++;
                }
            }
        });
        
        // 按位置排序，并移除重叠的匹配（保留优先级高的）
        matches.sort(function(a, b) { return a.index - b.index; });
        
        let filteredMatches = [];
        let lastEnd = -1;
        
        matches.forEach(function(match) {
            if (match.index >= lastEnd) {
                filteredMatches.push(match);
                lastEnd = match.index + match.length;
            }
        });
        
        // 从后向前替换，避免位置偏移问题
        let result = text;
        for (let i = filteredMatches.length - 1; i >= 0; i--) {
            const match = filteredMatches[i];
            result = result.substring(0, match.index) + match.replacement + result.substring(match.index + match.length);
        }
        
        return result;
    }

    // 安全的 URL 检查函数
    function sanitizeUrl(url) {
        try {
            // 解析 URL
            const parsed = new URL(url, window.location.href);
            // 检查协议是否在白名单中
            if (!ALLOWED_PROTOCOLS.includes(parsed.protocol)) {
                console.warn('[MarkdownRenderer] 阻止不安全的 URL 协议:', parsed.protocol);
                return '#';
            }
            return parsed.href;
        } catch (e) {
            // 如果解析失败，检查是否是相对路径或锚点
            if (url.startsWith('#') || url.startsWith('/') || url.startsWith('./')) {
                return url;
            }
            console.warn('[MarkdownRenderer] 无效的 URL:', url);
            return '#';
        }
    }

    // 解析链接
    function parseLinks(text) {
        // [text](url) - 使用函数替换避免 $ 字符问题
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, linkText, url) {
            const safeUrl = sanitizeUrl(url);
            return '<a class="' + CSS_PREFIX + 'link" href="' + escapeHtml(safeUrl) + '" target="_blank" rel="noopener noreferrer">' + linkText + '</a>';
        });
        
        // [text](url "title")
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\s+"([^"]*)"\)/g, function(match, linkText, url, title) {
            const safeUrl = sanitizeUrl(url);
            return '<a class="' + CSS_PREFIX + 'link" href="' + escapeHtml(safeUrl) + '" target="_blank" rel="noopener noreferrer" title="' + escapeHtml(title) + '">' + linkText + '</a>';
        });
        
        return text;
    }

    // 解析图片
    function parseImages(text) {
        // ![alt](url) - 使用函数替换避免 $ 字符问题
        text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(match, alt, src) {
            return '<img class="' + CSS_PREFIX + 'image" src="' + escapeHtml(src) + '" alt="' + escapeHtml(alt) + '" loading="lazy">';
        });

        // ![alt](url "title")
        text = text.replace(/!\[([^\]]*)\]\(([^)]+)\s+"([^"]*)"\)/g, function(match, alt, src, title) {
            return '<img class="' + CSS_PREFIX + 'image" src="' + escapeHtml(src) + '" alt="' + escapeHtml(alt) + '" title="' + escapeHtml(title) + '" loading="lazy">';
        });
        
        return text;
    }

    // 解析列表
    function parseLists(text) {
        let lines = text.split('\n');
        let result = [];
        let stack = []; // 存储 {type, items}
        
        function closeAllLists() {
            // 从后向前关闭所有列表
            while (stack.length > 0) {
                closeList();
            }
        }
        
        function closeList() {
            if (stack.length === 0) return;
            const list = stack.pop();
            let html = '<' + list.type + ' class="' + CSS_PREFIX + (list.type === 'ol' ? 'ordered' : 'unordered') + '-list">';
            
            list.items.forEach(item => {
                html += '<li class="' + CSS_PREFIX + 'list-item">' + item + '</li>';
            });
            
            html += '</' + list.type + '>';
            
            if (stack.length > 0) {
                // 将当前列表作为父列表的最后一个项的内容
                const parentList = stack[stack.length - 1];
                const lastItemIndex = parentList.items.length - 1;
                if (lastItemIndex >= 0) {
                    parentList.items[lastItemIndex] += html;
                }
            } else {
                result.push(html);
            }
        }
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            
            // 计算缩进（每2个空格为一级）
            const indentMatch = line.match(/^(\s*)/);
            const indent = indentMatch ? indentMatch[1].length : 0;
            const level = Math.floor(indent / 2);
            
            // 去除缩进后的内容
            const content = line.trim();
            
            // 有序列表
            let orderedMatch = content.match(/^(\d+)\.\s+(.+)$/);
            // 无序列表
            let unorderedMatch = content.match(/^[-*]\s+(.+)$/);
            
            if (orderedMatch || unorderedMatch) {
                const isOrdered = !!orderedMatch;
                const listType = isOrdered ? 'ol' : 'ul';
                const itemContent = isOrdered ? orderedMatch[2] : unorderedMatch[1];
                
                // 关闭比当前层级深的列表
                while (stack.length > level) {
                    closeList();
                }
                
                // 如果当前层级没有列表，创建新列表
                if (stack.length <= level) {
                    // 如果层级跳跃，先填充中间层级
                    while (stack.length < level) {
                        // 创建一个空的父列表项
                        if (stack.length > 0) {
                            stack[stack.length - 1].items.push('');
                        }
                        stack.push({
                            type: listType,
                            items: []
                        });
                    }
                    
                    // 如果当前层级列表类型不同，关闭并重新创建
                    if (stack.length > 0 && stack[stack.length - 1].type !== listType) {
                        closeList();
                    }
                    
                    // 创建新列表
                    if (stack.length === level) {
                        stack.push({
                            type: listType,
                            items: []
                        });
                    }
                }
                
                // 添加列表项到当前层级的列表
                if (stack.length > 0) {
                    stack[stack.length - 1].items.push(itemContent);
                }
                
            } else {
                // 非列表行，关闭所有列表
                closeAllLists();
                if (content) {
                    result.push(line);
                }
            }
        }
        
        // 关闭剩余的列表
        closeAllLists();
        
        return result.join('\n');
    }

    // 解析引用
    function parseBlockquotes(text) {
        return text.replace(/^>\s+(.+)$/gm, function(match, p1) {
            return '<blockquote class="' + CSS_PREFIX + 'blockquote">' + p1 + '</blockquote>';
        });
    }

    // 解析分割线
    function parseHorizontalRules(text) {
        return text.replace(/^[-*_]{3,}$/gm, function(match) {
            return '<hr class="' + CSS_PREFIX + 'hr">';
        });
    }

    // 解析表格
    function parseTables(text) {
        return text.replace(/\|(.+)\|\n\|[-:| ]+\|\n\|(.+)\|/g, function(match, headerRow, bodyRow) {
            let headers = headerRow.split('|').filter(h => h.trim());
            let rows = bodyRow.split('|').filter(r => r.trim());
            
            let tableHtml = '<table class="' + CSS_PREFIX + 'table"><thead><tr>';
            headers.forEach(h => {
                tableHtml += '<th class="' + CSS_PREFIX + 'table-header">' + h.trim() + '</th>';
            });
            tableHtml += '</tr></thead><tbody><tr>';
            rows.forEach(r => {
                tableHtml += '<td class="' + CSS_PREFIX + 'table-cell">' + r.trim() + '</td>';
            });
            tableHtml += '</tr></tbody></table>';
            
            return tableHtml;
        });
    }

    // ==================== 新版分段系统 ====================
    
    /**
     * 文本预处理管道
     * 统一处理文本清洗和规范化
     */
    function preprocessText(text) {
        if (!text || typeof text !== 'string') {
            return '';
        }
        
        let processed = text;
        
        // 步骤1: 统一换行符
        processed = processed.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        
        // 步骤2: 清理控制字符（保留换行和制表）
        processed = processed.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
        
        // 步骤3: 规范化空白字符
        // 将制表符转为4个空格
        processed = processed.replace(/\t/g, '    ');
        // 清理行尾空格
        processed = processed.replace(/[ \t]+$/gm, '');
        
        // 步骤4: 规范化空行（最多保留2个连续换行）
        processed = processed.replace(/\n{3,}/g, '\n\n');
        
        // 步骤5: 处理AI回复常见格式
        // 将中文冒号后的内容换行，便于分段
        processed = processed.replace(/([：:])([^\n])/g, function(match, colon, content) {
            // 检查是否是URL或路径（避免误处理）
            if (/^\s*https?:\/\//.test(content) || /^\s*[\/.]/.test(content)) {
                return match;
            }
            return colon + '\n' + content;
        });
        
        // 步骤6: 处理列表项格式
        // 将 "1. 内容" 或 "- 内容" 前加空行（如果不是在行首）
        processed = processed.replace(/([^\n])(\n\s*(?:\d+[.．、]\s+|[-*•]\s+))/g, function(match, prev, list) {
            return prev + '\n' + list;
        });
        
        return processed.trim();
    }
    
    /**
     * 结构保护器
     * 识别并保护不应被分段的结构
     */
    function protectStructures(text) {
        const placeholders = [];
        let protectedText = text;
        
        PARAGRAPH_CONFIG.protectedStructures.forEach(struct => {
            protectedText = protectedText.replace(struct.pattern, function(match) {
                const placeholder = `__${struct.type.toUpperCase()}_${placeholders.length}__`;
                placeholders.push({
                    placeholder: placeholder,
                    content: match,
                    type: struct.type
                });
                return placeholder;
            });
        });
        
        return { text: protectedText, placeholders: placeholders };
    }
    
    /**
     * 恢复被保护的结构
     */
    function restoreStructures(text, placeholders) {
        let restored = text;
        placeholders.forEach(item => {
            restored = restored.replace(item.placeholder, function() {
                return item.content;
            });
        });
        return restored;
    }
    
    /**
     * 智能段落分割器
     * 基于状态机的分段算法
     */
    function smartParagraphSplit(text) {
        const lines = text.split('\n');
        const paragraphs = [];
        let currentPara = [];
        let inList = false;
        let inQuote = false;
        let listIndent = 0;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();
            const nextLine = lines[i + 1] || '';
            
            // 空行处理
            if (trimmed === '') {
                if (currentPara.length > 0) {
                    paragraphs.push({
                        type: inList ? 'list' : (inQuote ? 'quote' : 'paragraph'),
                        content: currentPara.join('\n'),
                        indent: listIndent
                    });
                    currentPara = [];
                    inList = false;
                    inQuote = false;
                    listIndent = 0;
                }
                continue;
            }
            
            // 检测列表项
            const isListItem = PARAGRAPH_CONFIG.aiFormats.numberedItem.test(trimmed) ||
                              PARAGRAPH_CONFIG.aiFormats.bulletItem.test(trimmed) ||
                              /^\s+[-*\d]/.test(line);
            
            // 检测引用
            const isQuote = trimmed.startsWith('>');
            
            // 检测缩进变化
            const currentIndent = line.match(/^(\s*)/)[1].length;
            
            // 状态转换逻辑
            if (isListItem && !inList && currentPara.length === 0) {
                // 开始新列表
                inList = true;
                listIndent = currentIndent;
                currentPara.push(line);
            } else if (isListItem && inList) {
                // 继续列表
                if (currentIndent < listIndent && currentPara.length > 0) {
                    // 缩进减少，结束当前列表项
                    paragraphs.push({
                        type: 'list',
                        content: currentPara.join('\n'),
                        indent: listIndent
                    });
                    currentPara = [line];
                    listIndent = currentIndent;
                } else {
                    currentPara.push(line);
                }
            } else if (isQuote && !inQuote && currentPara.length === 0) {
                // 开始新引用
                inQuote = true;
                currentPara.push(line);
            } else if (isQuote && inQuote) {
                // 继续引用
                currentPara.push(line);
            } else if (inList && !isListItem && trimmed !== '') {
                // 列表中的非列表行（可能是列表项的延续）
                if (currentIndent >= listIndent || trimmed.startsWith('  ')) {
                    currentPara.push(line);
                } else {
                    // 结束列表
                    paragraphs.push({
                        type: 'list',
                        content: currentPara.join('\n'),
                        indent: listIndent
                    });
                    currentPara = [line];
                    inList = false;
                    listIndent = 0;
                }
            } else if (inQuote && !isQuote) {
                // 结束引用
                paragraphs.push({
                    type: 'quote',
                    content: currentPara.join('\n'),
                    indent: 0
                });
                currentPara = [line];
                inQuote = false;
            } else {
                // 普通段落
                currentPara.push(line);
            }
        }
        
        // 处理最后一段
        if (currentPara.length > 0) {
            paragraphs.push({
                type: inList ? 'list' : (inQuote ? 'quote' : 'paragraph'),
                content: currentPara.join('\n'),
                indent: listIndent
            });
        }
        
        return paragraphs;
    }
    
    /**
     * 渲染段落块
     */
    function renderParagraphBlock(block) {
        const { type, content } = block;
        
        switch (type) {
            case 'list':
                // 列表在 parseLists 中处理，这里直接返回
                return content;
            case 'quote':
                // 引用在 parseBlockquotes 中处理
                return content;
            case 'paragraph':
            default:
                // 检查是否已经是HTML块
                const isHtmlBlock = PARAGRAPH_CONFIG.blockElements.some(tag => 
                    content.trim().startsWith(tag)
                );
                
                if (isHtmlBlock) {
                    return content;
                }
                
                // 检查是否是独立标点
                if (/^[。．，、；：！？\s]*$/.test(content.trim())) {
                    return '';
                }
                
                return '<p class="' + CSS_PREFIX + 'paragraph">' + content + '</p>';
        }
    }
    
    // 解析段落（新版）
    function parseParagraphs(text) {
        // 步骤1: 预处理
        let processed = preprocessText(text);
        
        // 步骤2: 保护特殊结构
        const { text: protectedText, placeholders } = protectStructures(processed);
        
        // 步骤3: 智能分段
        const blocks = smartParagraphSplit(protectedText);
        
        // 步骤4: 渲染每个段落块
        const renderedBlocks = blocks.map(renderParagraphBlock);
        
        // 步骤5: 合并并恢复保护的结构
        let result = renderedBlocks.join('\n');
        result = restoreStructures(result, placeholders);
        
        return result;
    }
    
    // 保留旧版函数作为备用
    function parseParagraphsLegacy(text) {
        // 预处理：处理AI回复中常见的冒号分隔格式
        // 将"标题：内容"格式转换为段落格式
        // 注意：只匹配中文标点符号，避免匹配$符号
        text = text.replace(/([。！？!?」】）])\s*([：「"''《【（])/gu, function(match, p1, p2) {
            return p1 + '\n\n' + p2;
        });
        
        // 处理连续的冒号分隔项，将其转换为独立段落
        // 匹配 "xxx：xxx" 格式，如果连续出现多个，则将每个转换为一个段落
        text = text.replace(/(^|[。！？!?」】）])\s*([^：\n]+)：([^：\n]+)(?=[。！？!?」】）]|$)/g, function(match, prefix, title, content) {
            // 如果后面紧跟另一个冒号格式，说明这是一个列表项
            return (prefix || '') + title.trim() + '：\n' + content.trim() + '\n\n';
        });
        
        // 进一步处理：将多个连续的冒号格式项分段落
        text = text.replace(/(^|[^。！？!?」】）])\s*([^：\n]+)：/g, function(match, prefix, title) {
            if (prefix && prefix.trim() !== '') {
                return match; // 不是列表项，保留原样
            }
            return '\n\n' + title.trim() + '：';
        });
        
        // 清理多余的空行（3个及以上连续换行变为2个）
        text = text.replace(/\n{3,}/g, '\n\n');
        
        let paragraphs = text.split(/\n\n+/);
        return paragraphs.map(p => {
            p = p.trim();
            if (!p) return '';
            
            // 如果已经包含HTML标签，直接返回
            if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') ||
                p.startsWith('<blockquote') || p.startsWith('<div') || p.startsWith('<pre')) {
                return p;
            }
            
            return '<p class="' + CSS_PREFIX + 'paragraph">' + p + '</p>';
        }).filter(p => p !== '').join('\n');
    }

    // 解析换行
    function parseLineBreaks(text) {
        return text.replace(/\n/g, function(match) {
            return '<br>';
        });
    }

    // 主动暴露的复制代码函数
    function copyCode(button) {
        const codeBlock = button.closest('.code-block');
        const codeContent = codeBlock.querySelector('.code-content');
        const text = codeContent.textContent;
        
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.textContent;
            button.textContent = '已复制！';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('复制失败:', err);
            button.textContent = '复制失败';
            
            setTimeout(() => {
                button.textContent = '复制';
            }, 2000);
        });
    }

    // 处理 DeepSeek R1 模型的思考链格式
    function parseDeepSeekThinking(text) {
        let thinkingContent = '';
        let finalContent = text;
        
        // 策略1：检测特定的 HTML 注释标记 <!-- thinking -->
        const thinkingCommentMatch = text.match(/<!--\s*thinking\s*-->([\s\S]*?)<!--\s*\/thinking\s*-->/i);
        if (thinkingCommentMatch) {
            thinkingContent = thinkingCommentMatch[1].trim();
            finalContent = text.replace(thinkingCommentMatch[0], '').trim();
            return { thinkingContent, finalContent };
        }
        
        // 策略2：检测 **思考过程** 或 **Thinking Process** 等明确标记
        // 使用更严格的模式，要求标记在开头或独立成行
        const thinkingPatterns = [
            { pattern: /^\*\*思考过程\*\*([\s\S]*?)(?=\*\*|$)/im, name: '思考过程' },
            { pattern: /^\*\*Thinking Process\*\*([\s\S]*?)(?=\*\*|$)/im, name: 'Thinking Process' },
            { pattern: /^\*\*推理过程\*\*([\s\S]*?)(?=\*\*|$)/im, name: '推理过程' },
            { pattern: /^\*\*Reasoning\*\*([\s\S]*?)(?=\*\*|$)/im, name: 'Reasoning' }
        ];
        
        for (const { pattern, name } of thinkingPatterns) {
            const match = text.match(pattern);
            if (match) {
                thinkingContent = '**' + name + '**' + match[1];
                finalContent = text.replace(match[0], '').trim();
                break;
            }
        }
        
        // 策略3：检测以 "**" 开头且包含大量星号行的内容（仅作为备选）
        if (!thinkingContent && text.startsWith('**')) {
            const lines = text.split('\n');
            let thinkingEndIndex = 0;
            let starLineCount = 0;
            
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].startsWith('**') && lines[i].includes('**')) {
                    thinkingEndIndex = i + 1;
                    starLineCount++;
                }
            }
            
            // 只有当星号行数 >= 3 时才认为是思考过程（避免误匹配普通加粗文本）
            if (starLineCount >= 3 && thinkingEndIndex > 0 && thinkingEndIndex < lines.length) {
                thinkingContent = lines.slice(0, thinkingEndIndex).join('\n');
                finalContent = lines.slice(thinkingEndIndex).join('\n').trim();
            }
        }
        
        // 清理思考内容中的多余星号和空白
        if (thinkingContent) {
            thinkingContent = thinkingContent
                .replace(/\*\*/g, function(match) {
                    return '';
                })
                .replace(/\n{3,}/g, function(match) {
                    return '\n\n';
                })
                .replace(/^\s*[。．]\s*$/gm, function(match) {
                    return '';
                })
                .trim();
        }
        
        // 清理最终答案中的多余空白和独立句号
        finalContent = finalContent
            .replace(/\n{3,}/g, function(match) {
                return '\n\n';
            })
            .replace(/^\s*[。．]\s*$/gm, function(match) {
                return '';
            })
            .replace(/\*\*/g, function(match) {
                return '';
            })
            .trim();
        
        return { thinkingContent, finalContent };
    }

    // 渲染Markdown文本
    function render(text) {
        if (!text || typeof text !== 'string') {
            return '<p class="' + CSS_PREFIX + 'paragraph"></p>';
        }
        
        // 首先处理 DeepSeek R1 的思考链格式
        const { thinkingContent, finalContent } = parseDeepSeekThinking(text);
        
        let html = finalContent;
        
        // 1. 代码块（必须在最前面处理）
        html = parseCodeBlock(html);
        
        // 2. 内联代码
        html = parseInlineCode(html);
        
        // 3. 标题
        html = parseHeaders(html);
        
        // 4. 引用
        html = parseBlockquotes(html);
        
        // 5. 分割线
        html = parseHorizontalRules(html);
        
        // 6. 列表
        html = parseLists(html);
        
        // 7. 强调
        html = parseEmphasis(html);
        
        // 8. 链接
        html = parseLinks(html);
        
        // 9. 图片
        html = parseImages(html);
        
        // 10. 表格
        html = parseTables(html);
        
        // 11. 段落
        html = parseParagraphs(html);
        
        // 12. 换行
        html = parseLineBreaks(html);
        
        // 如果有思考内容，添加折叠效果
        if (thinkingContent) {
            const thinkingId = 'thinking-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);
            const thinkingHtml = `
                <div class="thinking-chain" id="${thinkingId}">
                    <div class="thinking-header" onclick="window.toggleThinking && window.toggleThinking('${thinkingId}')">
                        <div class="thinking-icon-container">
                            <span class="thinking-icon">💭</span>
                        </div>
                        <span class="thinking-title">思考过程</span>
                        <span class="thinking-toggle" id="${thinkingId}-toggle">▼</span>
                    </div>
                    <div class="thinking-content collapsed" id="${thinkingId}-content">
                        ${escapeHtml(thinkingContent).replace(/\n/g, function(match) {
                            return '<br>';
                        })}
                    </div>
                </div>
            `;
            html = thinkingHtml + html;
        }
        
        return html;
    }

    // 检测文本是否包含Markdown语法
    function isMarkdown(text) {
        const markdownPatterns = [
            /^#{1,6}\s+/m,
            /```[\s\S]*?```/,
            /`[^`]+`/,
            /\*\*[^*]+\*\*/,
            /__[^_]+__/,
            /\[.*?\]\(.*?\)/,
            /!\[.*?\]\(.*?\)/,
            /^[*-]\s/m,
            /^\d+\.\s/m,
            /^>/m,
            /^\s*[-*_]{3,}$/m,
            /\|.+\|.*\|/
        ];
        
        return markdownPatterns.some(pattern => pattern.test(text));
    }

    // 公开API
    return {
        render: render,
        isMarkdown: isMarkdown,
        highlightCode: highlightCode,
        detectLanguage: detectLanguage,
        copyCode: copyCode
    };
})();

// 将复制函数挂载到全局，方便HTML中调用
window.copyCode = function(button) {
    MarkdownRenderer.copyCode(button);
};

// 思考链折叠切换函数
window.toggleThinking = function(thinkingId) {
    console.log('Toggle thinking:', thinkingId);
    const content = document.getElementById(thinkingId + '-content');
    const toggle = document.getElementById(thinkingId + '-toggle');
    
    if (content && toggle) {
        const isCollapsed = content.classList.contains('collapsed');
        if (isCollapsed) {
            content.classList.remove('collapsed');
            toggle.style.transform = 'rotate(0deg)';
        } else {
            content.classList.add('collapsed');
            toggle.style.transform = 'rotate(-90deg)';
        }
        console.log('Thinking toggled:', isCollapsed ? 'expanded' : 'collapsed');
    } else {
        console.warn('Thinking elements not found:', thinkingId);
    }
    
    // 阻止事件冒泡
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
};
window.MarkdownRenderer = MarkdownRenderer;
