/**
 * 智能语义分段器 - 重写版
 * 
 * 功能：基于语义连贯性的智能分段
 * 特点：
 * - 支持中文引号、括号、省略号、混合标点
 * - 明确4层分段优先级
 * - 智能处理代码块和列表
 * - 修复标题导致的空白问题
 */

const SemanticSegmenter = (function() {
    const CONFIG = {
        similarityThreshold: 0.2,
        minSentenceLength: 4,
        maxSentenceLength: 500,
        coherenceCheckWindow: 3,
        enableCache: true,
        cacheMaxSize: 500,
        minSegmentChars: 10,
        maxSegmentChars: 150
    };
    
    let cache = new Map();
    let cacheKeys = [];
    
    const STOP_WORDS = new Set([
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一',
        '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
        '看', '好', '自己', '这', 'that', 'the', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        '着', '过', '吧', '呢', '啊', '哦', '嗯', '呀', '啦', '呗'
    ]);
    
    const COHERENCE_MARKERS = {
        continuation: ['然后', '接着', '此外', '另外', '并且', '同时', '更重要的是',
                      '之后', '随后', '于是', '于是说', 'then', 'next', 'after', 
                      'also', 'furthermore', 'moreover', 'besides', 'afterwards'],
        contrast: ['但是', '然而', '不过', '可是', '虽然', '尽管', '可是',
                  'but', 'however', 'although', 'though', 'nevertheless', 'yet', 
                  'nonetheless', 'except', 'unless'],
        cause: ['因为', '所以', '因此', '由于', '为了', '既然', '于是',
               'because', 'therefore', 'thus', 'hence', 'since', 'for', 'so'],
        example: ['比如', '例如', '譬如', '比如说', '例如说', '像',
                 'for example', 'for instance', 'such as', 'like', 'e.g.'],
        conclusion: ['总之', '总而言之', '综上所述', '最后', '最终', '总之',
                    'in conclusion', 'to sum up', 'finally', 'ultimately', 
                    'in the end', 'to conclude', 'all in all'],
        transition: ['首先', '其次', '再次', '最后', '第一', '第二', '第三',
                    'firstly', 'secondly', 'thirdly', 'finally', 'lastly',
                    'in the first place', 'to begin with', 'for one thing']
    };
    
    const QUOTE_PAIRS = {
        '"': '"',
        "'": "'",
        '「': '」',
        '『': '』'
    };
    
    const BRACKET_PAIRS = {
        '（': '）',
        '（': '）',
        '(': ')',
        '【': '】',
        '[': ']',
        '{': '}'
    };
    
    const PUNCTUATION = {
        sentenceEnd: ['。', '！', '？', '?', '!'],
        sentenceEndDouble: ['。', '！', '？', '!?', '?!', '。！', '！？'],
        ellipsis: ['……', '。。。', '......', '....'],
        list: ['、', ',', '，'],
        colon: ['：', ':', ';', '；']
    };
    
    function tokenize(text) {
        if (!text || typeof text !== 'string') return [];
        
        const tokens = [];
        let currentToken = '';
        
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const isChinese = char >= '\u4e00' && char <= '\u9fff';
            const isLetter = /[a-zA-Z]/.test(char);
            const isDigit = /[0-9]/.test(char);
            
            if (isChinese) {
                if (currentToken && !isLetter && !isDigit) {
                    const token = currentToken.toLowerCase();
                    if (token.length > 1 && !STOP_WORDS.has(token)) {
                        tokens.push(token);
                    }
                    currentToken = '';
                }
                currentToken += char;
            } else if (isLetter || isDigit) {
                currentToken += char.toLowerCase();
            } else {
                if (currentToken) {
                    const token = currentToken.toLowerCase();
                    if (token.length > 1 && !STOP_WORDS.has(token)) {
                        tokens.push(token);
                    }
                    currentToken = '';
                }
            }
        }
        
        if (currentToken) {
            const token = currentToken.toLowerCase();
            if (token.length > 1 && !STOP_WORDS.has(token)) {
                tokens.push(token);
            }
        }
        
        return tokens;
    }
    
    function calculateSimilarity(sent1, sent2) {
        if (!sent1 || !sent2 || sent1.length < 2 || sent2.length < 2) {
            return 0;
        }
        
        const cacheKey = sent1 + '|||' + sent2;
        
        if (CONFIG.enableCache && cache.has(cacheKey)) {
            return cache.get(cacheKey);
        }
        
        const tokens1 = tokenize(sent1);
        const tokens2 = tokenize(sent2);
        
        if (tokens1.length === 0 || tokens2.length === 0) {
            const result = 0;
            if (CONFIG.enableCache) {
                addToCache(cacheKey, result);
            }
            return result;
        }
        
        const set1 = new Set(tokens1);
        const set2 = new Set(tokens2);
        
        let intersection = 0;
        for (const token of set1) {
            if (set2.has(token)) {
                intersection++;
            }
        }
        
        const union = set1.size + set2.size - intersection;
        const similarity = union > 0 ? intersection / union : 0;
        
        if (CONFIG.enableCache) {
            addToCache(cacheKey, similarity);
        }
        
        return similarity;
    }
    
    function addToCache(key, value) {
        if (cache.size >= CONFIG.cacheMaxSize) {
            const firstKey = cacheKeys.shift();
            if (firstKey) {
                cache.delete(firstKey);
            }
        }
        cacheKeys.push(key);
        cache.set(key, value);
    }
    
    function extractKeywords(sentences) {
        const keywords = new Map();
        
        for (const sentence of sentences) {
            const tokens = tokenize(sentence);
            const counts = new Map();
            
            for (const token of tokens) {
                counts.set(token, (counts.get(token) || 0) + 1);
            }
            
            for (const [token, count] of counts) {
                keywords.set(token, (keywords.get(token) || 0) + count);
            }
        }
        
        return keywords;
    }
    
    function calculateCoherenceScore(sentences, windowSize) {
        if (!sentences || sentences.length < 2) {
            return 1.0;
        }
        
        let totalScore = 0;
        let comparisons = 0;
        
        const startIdx = Math.max(0, sentences.length - windowSize);
        
        for (let i = startIdx; i < sentences.length - 1; i++) {
            const sim = calculateSimilarity(sentences[i], sentences[i + 1]);
            totalScore += sim;
            comparisons++;
        }
        
        return comparisons > 0 ? totalScore / comparisons : 1.0;
    }
    
    function detectCoherenceMarkers(text) {
        if (!text || typeof text !== 'string') {
            return [];
        }
        
        const markers = [];
        const lowerText = text.toLowerCase();
        
        for (const [type, words] of Object.entries(COHERENCE_MARKERS)) {
            for (const word of words) {
                const lowerWord = word.toLowerCase();
                const index = lowerText.indexOf(lowerWord);
                if (index !== -1) {
                    markers.push({ type, word, index });
                }
            }
        }
        
        return markers.sort((a, b) => a.index - b.index);
    }
    
    function isInQuote(text, position) {
        const beforeText = text.slice(0, position);
        let depth = 0;
        
        for (const [open, close] of Object.entries(QUOTE_PAIRS)) {
            let openCount = (beforeText.match(new RegExp(open, 'g')) || []).length;
            let closeCount = (beforeText.match(new RegExp(close, 'g')) || []).length;
            depth += openCount - closeCount;
        }
        
        return depth > 0;
    }
    
    function isInBracket(text, position) {
        const beforeText = text.slice(0, position);
        let depth = 0;
        
        for (const [open, close] of Object.entries(BRACKET_PAIRS)) {
            let openCount = (beforeText.match(new RegExp(open, 'g')) || []).length;
            let closeCount = (beforeText.match(new RegExp(close, 'g')) || []).length;
            depth += openCount - closeCount;
        }
        
        return depth > 0;
    }
    
    function isInCodeBlock(text, position) {
        const beforeText = text.slice(0, position);
        const codeBlockStart = (beforeText.match(/```/g) || []).length;
        return codeBlockStart % 2 === 1;
    }
    
    function isMarkdownHeading(text) {
        return /^#{1,6}\s/.test(text) || /^第[一二三四五六七八九十百千]+[章节点]/.test(text);
    }
    
    function isListItem(text) {
        return /^\s*[\d一二三四五六七八九十百千]+[.、．、)）]/.test(text) ||
               /^\s*[-*•]\s/.test(text) ||
               /^\s*[a-zA-Z][.、．\)）]/.test(text);
    }
    
    function isCompleteSentence(text) {
        if (!text || typeof text !== 'string') {
            return false;
        }
        
        const trimmed = text.trim();
        
        if (trimmed.length < CONFIG.minSentenceLength) {
            return false;
        }
        
        if (trimmed.length > CONFIG.maxSentenceLength) {
            return false;
        }
        
        if (isMarkdownHeading(trimmed)) {
            return true;
        }
        
        if (isListItem(trimmed)) {
            return true;
        }
        
        const endingPunctuation = PUNCTUATION.sentenceEnd.some(p => trimmed.endsWith(p));
        const doublePunctuation = PUNCTUATION.sentenceEndDouble.some(p => trimmed.endsWith(p));
        const hasEllipsis = PUNCTUATION.ellipsis.some(e => trimmed.endsWith(e));
        const hasColon = trimmed.endsWith(':') || trimmed.endsWith('：');
        
        if (endingPunctuation || doublePunctuation || hasEllipsis) {
            return true;
        }
        
        if (hasColon && trimmed.length > 15) {
            const afterColon = trimmed.split(/[：:]/).pop();
            if (afterColon && afterColon.trim().length > 10) {
                return true;
            }
        }
        
        const hasSubjectOrPredicate = (
            /[\u4e00-\u9fff]/.test(trimmed) || 
            /[a-zA-Z]/.test(trimmed)
        );
        
        if (!hasSubjectOrPredicate) {
            return false;
        }
        
        const commonEndings = ['等等', '而已', '罢了', '这样的话', '也就是说', '换句话说'];
        for (const ending of commonEndings) {
            if (trimmed.endsWith(ending)) {
                return true;
            }
        }
        
        return trimmed.length >= 15 && endingPunctuation;
    }
    
    function isEndOfSentence(text, position) {
        if (position >= text.length) return false;
        
        const char = text[position];
        const nextChar = position + 1 < text.length ? text[position + 1] : '';
        
        if (isInQuote(text, position) || isInBracket(text, position)) {
            return false;
        }
        
        if (isInCodeBlock(text, position)) {
            return char === '\n';
        }
        
        if (PUNCTUATION.sentenceEnd.includes(char)) {
            if (PUNCTUATION.sentenceEndDouble.includes(char + nextChar)) {
                return true;
            }
            if (PUNCTUATION.ellipsis.includes(char + nextChar) || 
                PUNCTUATION.ellipsis.includes(char + text[position + 2])) {
                return true;
            }
            return !isInQuote(text, position);
        }
        
        if (char === '\n' && nextChar === '\n') {
            return true;
        }
        
        if ((char === '.' || char === '。') && 
            (/[A-ZА-Я]/.test(nextChar) || nextChar === '\n')) {
            return true;
        }
        
        return false;
    }
    
    function findSentenceEnd(text, startPos = 0) {
        if (!text || startPos >= text.length) {
            return -1;
        }
        
        let i = startPos;
        
        while (i < text.length) {
            if (isEndOfSentence(text, i)) {
                const endPos = i + 1;
                
                if (endPos < text.length) {
                    const nextChar = text[endPos];
                    if (nextChar === ' ' || nextChar === '\t') {
                        const afterSpace = text.slice(endPos + 1).trim();
                        if (afterSpace.length > 0 && /[\u4e00-\u9fffA-ZА-Я]/.test(afterSpace[0])) {
                            return endPos;
                        }
                    } else if (/[\u4e00-\u9fffA-ZА-Я]/.test(nextChar)) {
                        return endPos;
                    } else if (nextChar === '\n') {
                        return endPos;
                    }
                }
                
                return endPos;
            }
            i++;
        }
        
        return -1;
    }
    
    function splitIntoSentences(text) {
        if (!text || typeof text !== 'string') {
            return [];
        }
        
        const sentences = [];
        let currentSentence = '';
        let i = 0;
        
        while (i < text.length) {
            const char = text[i];
            currentSentence += char;
            
            const nextChar = i + 1 < text.length ? text[i + 1] : '';
            const nextNextChar = i + 2 < text.length ? text[i + 2] : '';
            
            let isSentenceEnd = false;
            let endPos = -1;
            
            if (isInCodeBlock(text, i) && char === '\n') {
                if (currentSentence.trim().length > 0) {
                    sentences.push(currentSentence.trim());
                    currentSentence = '';
                }
                i++;
                continue;
            }
            
            if (PUNCTUATION.sentenceEnd.includes(char)) {
                if (!isInQuote(text, i) && !isInBracket(text, i)) {
                    if (PUNCTUATION.sentenceEndDouble.includes(char + nextChar)) {
                        endPos = i + 2;
                        isSentenceEnd = true;
                    } else if (PUNCTUATION.ellipsis.includes(char + nextChar) || 
                               PUNCTUATION.ellipsis.includes(char + nextChar + nextNextChar)) {
                        endPos = i + (PUNCTUATION.ellipsis.some(e => e.startsWith(char + nextChar)) ? 2 : 3);
                        isSentenceEnd = true;
                    } else if (nextChar === ' ' || nextChar === '\n' || 
                               nextChar === '' || /[\u4e00-\u9fffA-ZА-Я]/.test(nextChar)) {
                        endPos = i + 1;
                        isSentenceEnd = true;
                    }
                }
            }
            
            if (!isSentenceEnd && char === '\n' && nextChar === '\n') {
                if (currentSentence.trim().length > 0) {
                    sentences.push(currentSentence.trim());
                    currentSentence = '';
                }
                i += 2;
                continue;
            }
            
            if (isSentenceEnd && endPos > 0) {
                const sentence = currentSentence.trim();
                if (sentence.length > 0) {
                    sentences.push(sentence);
                }
                currentSentence = '';
                i = endPos - 1;
            }
            
            i++;
        }
        
        if (currentSentence.trim().length > 0) {
            sentences.push(currentSentence.trim());
        }
        
        return sentences.filter(s => s.length > 0);
    }
    
    function findBestSegmentPoint(text, sentLength, options = {}) {
        if (!text || text.length < CONFIG.minSegmentChars) {
            return -1;
        }
        
        const { forceChars = 150 } = options;
        
        const sentences = splitIntoSentences(text);
        
        if (sentences.length < 2) {
            return -1;
        }
        
        let currentPos = 0;
        let candidates = [];
        
        for (let i = 0; i < sentences.length - 1; i++) {
            currentPos += sentences[i].length;
            
            const currentSentence = sentences[i];
            const nextSentence = sentences[i + 1];
            
            const currentIsComplete = isCompleteSentence(currentSentence);
            const nextIsComplete = isCompleteSentence(nextSentence);
            
            if (!currentIsComplete) {
                continue;
            }
            
            const similarity = calculateSimilarity(currentSentence, nextSentence);
            
            let score = similarity;
            
            if (nextIsComplete) {
                score += 0.3;
            }
            
            if (i > 0 && i < sentences.length - 2) {
                const prevSimilarity = calculateSimilarity(sentences[i - 1], currentSentence);
                score = score * 0.6 + prevSimilarity * 0.4;
            }
            
            if (isListItem(nextSentence) || isMarkdownHeading(nextSentence)) {
                score += 0.2;
            }
            
            const markers = detectCoherenceMarkers(nextSentence);
            const hasBreak = markers.some(m => 
                m.type === 'conclusion' || m.type === 'contrast' || m.type === 'transition'
            );
            if (hasBreak) {
                score += 0.2;
            }
            
            candidates.push({
                position: sentLength + currentPos,
                score: score,
                reason: nextIsComplete ? 'complete_sentence' : 'incomplete_sentence',
                isNewSegment: nextIsComplete || isListItem(nextSentence) || isMarkdownHeading(nextSentence)
            });
        }
        
        candidates.sort((a, b) => b.score - a.score);
        
        for (const candidate of candidates) {
            if (candidate.score >= CONFIG.similarityThreshold) {
                return candidate.position;
            }
        }
        
        if (candidates.length > 0) {
            const best = candidates[0];
            if (best.score > 0.15 && text.length < forceChars * 2) {
                return best.position;
            }
        }
        
        return -1;
    }
    
    function calculateAdaptiveDelay(text, options = {}) {
        const { baseDelay = 30, sentenceEndDelay = 60 } = options;
        
        if (!text || text.length < 5) {
            return baseDelay;
        }
        
        const sentences = splitIntoSentences(text);
        if (sentences.length === 0) {
            return baseDelay;
        }
        
        const lastSentence = sentences[sentences.length - 1];
        const length = lastSentence.length;
        
        let delay = baseDelay;
        
        const isDoubleEnd = PUNCTUATION.sentenceEndDouble.some(p => lastSentence.endsWith(p));
        const hasEllipsis = PUNCTUATION.ellipsis.some(e => lastSentence.endsWith(e));
        const hasList = isListItem(lastSentence);
        const hasColon = lastSentence.endsWith(':') || lastSentence.endsWith('：');
        const isHeading = isMarkdownHeading(lastSentence);
        
        // 优化：减少延迟以提升响应速度
        if (isHeading) {
            delay = baseDelay + 10;
        } else if (isDoubleEnd) {
            delay = sentenceEndDelay / 2 + 5;
        } else if (hasEllipsis) {
            delay = sentenceEndDelay / 2 + 3;
        } else if (hasList || hasColon) {
            delay = sentenceEndDelay / 2 + 2;
        } else {
            delay = Math.min(baseDelay + length * 0.1, sentenceEndDelay / 2);
        }
        
        return Math.round(Math.max(delay, baseDelay / 2));
    }
    
    function shouldSegment(text, lastSentences, options = {}) {
        // 优化：使用更快的默认参数
        const {
            forceTime = 150,
            forceChars = 100,
            baseDelay = 15,
            sentenceEndDelay = 30,
            minChars = 5
        } = options;
        
        if (!text || text.length < minChars) {
            return { shouldSegment: false, reason: 'text_too_short', minChars };
        }
        
        const sentences = splitIntoSentences(text);
        
        if (sentences.length < 2) {
            return { shouldSegment: false, reason: 'only_one_sentence', count: sentences.length };
        }
        
        const lastSentence = sentences[sentences.length - 1];
        
        const isLastComplete = isCompleteSentence(lastSentence);
        const isFirstComplete = isCompleteSentence(sentences[0]);
        
        if (!isLastComplete && !isFirstComplete) {
            return { shouldSegment: false, reason: 'both_incomplete' };
        }
        
        if (isLastComplete && sentences.length >= 2) {
            const lastSent = lastSentences.length > 0 ? lastSentences[lastSentences.length - 1] : '';
            const similarity = lastSent ? calculateSimilarity(lastSent, lastSentence) : 1;
            const coherenceScore = calculateCoherenceScore(
                lastSentences.concat([lastSentence]), 
                CONFIG.coherenceCheckWindow
            );
            
            if (similarity < CONFIG.similarityThreshold && coherenceScore < CONFIG.similarityThreshold) {
                return {
                    shouldSegment: true,
                    reason: 'low_coherence',
                    score: similarity,
                    coherence: coherenceScore
                };
            }
            
            const markers = detectCoherenceMarkers(lastSentence);
            const hasStrongBreak = markers.some(m => 
                m.type === 'conclusion' || m.type === 'contrast' || m.type === 'transition'
            );
            
            if (hasStrongBreak) {
                return {
                    shouldSegment: true,
                    reason: 'coherence_marker',
                    markerType: markers.find(m => 
                        m.type === 'conclusion' || m.type === 'contrast' || m.type === 'transition'
                    )?.type
                };
            }
            
            if (isMarkdownHeading(lastSentence) || isListItem(lastSentence)) {
                return {
                    shouldSegment: true,
                    reason: 'heading_or_list',
                    isNewSegment: true
                };
            }
        }
        
        if (text.length >= forceChars) {
            const bestPoint = findBestSegmentPoint(text, 0, { forceChars });
            if (bestPoint > 0) {
                return {
                    shouldSegment: true,
                    reason: 'force_length',
                    position: bestPoint
                };
            }
        }
        
        return {
            shouldSegment: false,
            reason: 'coherent_continue',
            sentences: sentences.length,
            lastComplete: isLastComplete
        };
    }
    
    function clearCache() {
        cache.clear();
        cacheKeys = [];
    }
    
    function updateConfig(newConfig) {
        Object.assign(CONFIG, newConfig);
    }
    
    return {
        shouldSegment,
        calculateAdaptiveDelay,
        calculateSimilarity,
        splitIntoSentences,
        isCompleteSentence,
        findBestSegmentPoint,
        detectCoherenceMarkers,
        calculateCoherenceScore,
        isMarkdownHeading,
        isListItem,
        clearCache,
        updateConfig,
        getConfig: () => ({ ...CONFIG })
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SemanticSegmenter;
}
