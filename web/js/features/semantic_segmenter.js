/**
 * ASS++ v2 (Adaptive Semantic Segmentation Plus v2)
 *
 * 核心改进：
 * 1. TF-IDF + L2归一化：解决词袋模型μ≈0问题
 * 2. 分位数自适应阈值：基于文档自身分布，非硬编码
 * 3. 零方差细粒度处理：μ>0.65不切，μ<0.35按提示词/轮次切
 * 4. 词汇线索-0.2偏移：强提示词直接降低相似度
 * 5. 双阈值+局部谷底：强边界直接切，候选需谷底确认
 * 6. 多跳语义粘合：前瞻sim(i,i+2)识别假连贯
 * 7. 聚类后验修正：合并过切段
 *
 * 特性：完全确定、O(n)线性、支持流式、真正自适应
 */

const SemanticSegmenter = (function() {
    const CONFIG = {
        minSentences: 2,
        maxSentences: 20,
        minSegmentChars: 10,
        maxSegmentChars: 512,
        enableCache: true,
        cacheMaxSize: 500,
        windowSize: 3,
        valleyWindow: 2,
        valleyDropRatio: 0.12,
        multiHopWeight: 0.3,
        multiHopDropThreshold: 0.25,
        mergeCentroidThreshold: 0.8,
        hierarchicalWindowSize: 60,
        streamingWindowSize: 15,
        lexicalOffset: 0.2,
        strongMargin: 0.1,
        candidateMargin: 0.05,
        idfSmoothing: 1.0
    };

    let cache = new Map();
    let cacheKeys = [];
    let globalIdf = new Map();
    let globalDocCount = 0;

    const STOP_WORDS = new Set([
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一',
        '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
        '看', '好', '自己', '这', 'that', 'the', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        '着', '过', '吧', '呢', '啊', '哦', '嗯', '呀', '啦', '呗',
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'it', 'this', 'that', 'these', 'those'
    ]);

    const STRONG_CUE_WORDS = [
        '首先', '其次', '再次', '最后', '第一', '第二', '第三', '第四', '第五',
        '总之', '综上所述', '总而言之', '概而言之', '简而言之', '一言以蔽之',
        '但是', '然而', '不过', '可是', '尽管如此', '另一方面', '反观',
        '此外', '另外', '与此同时', '值得注意的是', '需要指出的是', '特别说明',
        '接着', '然后', '接下来', '最终', '到头来', '到头来',
        'in contrast', 'on the other hand', 'however', 'nevertheless', 'conversely',
        'firstly', 'secondly', 'thirdly', 'fourthly', 'finally', 'lastly', 'in conclusion',
        'moreover', 'furthermore', 'additionally', 'meanwhile', 'subsequently',
        'to sum up', 'all in all', 'in summary', 'to begin with', 'in brief'
    ];

    const PUNCTUATION = {
        sentenceEnd: ['。', '！', '？', '?', '!'],
        ellipsis: ['……', '。。。', '......', '....'],
        colon: ['：', ':', ';', '；']
    };

    const QUOTE_PAIRS = { '"': '"', "'": "'", '「': '」', '『': '』' };
    const BRACKET_PAIRS = { '（': '）', '(': ')', '【': '】', '[': ']', '{': '}' };

    // ==================== 基础工具 ====================

    function countChar(text, char) {
        let count = 0;
        for (let i = 0; i < text.length; i++) if (text[i] === char) count++;
        return count;
    }

    function isInQuote(text, position) {
        const before = text.slice(0, position);
        let depth = 0;
        for (const [open, close] of Object.entries(QUOTE_PAIRS)) {
            depth += countChar(before, open) - countChar(before, close);
        }
        return depth > 0;
    }

    function isInBracket(text, position) {
        const before = text.slice(0, position);
        let depth = 0;
        for (const [open, close] of Object.entries(BRACKET_PAIRS)) {
            depth += countChar(before, open) - countChar(before, close);
        }
        return depth > 0;
    }

    function isInCodeBlock(text, position) {
        const before = text.slice(0, position);
        return ((before.match(/```/g) || []).length % 2) === 1;
    }

    function isMarkdownHeading(text) {
        return /^#{1,6}\s/.test(text) || /^第[一二三四五六七八九十百千]+[章节点]/.test(text);
    }

    function isListItem(text) {
        return /^\s*[\d一二三四五六七八九十百千]+[.、．、)）]/.test(text) ||
               /^\s*[-*•]\s/.test(text) ||
               /^\s*[a-zA-Z][.、．\)）]/.test(text);
    }

    // ==================== 句子切分 ====================

    function splitIntoSentences(text) {
        if (!text || typeof text !== 'string') return [];
        const sentences = [];
        let current = '';
        let i = 0;

        while (i < text.length) {
            const char = text[i];
            current += char;
            const nextChar = i + 1 < text.length ? text[i + 1] : '';
            const nextNextChar = i + 2 < text.length ? text[i + 2] : '';

            if (isInCodeBlock(text, i) && char === '\n') {
                if (current.trim().length > 0) { sentences.push(current.trim()); current = ''; }
                i++; continue;
            }

            let isSentenceEnd = false;
            let endPos = -1;

            if (PUNCTUATION.sentenceEnd.includes(char) && !isInQuote(text, i) && !isInBracket(text, i)) {
                if (PUNCTUATION.ellipsis.includes(char + nextChar) ||
                    PUNCTUATION.ellipsis.includes(char + nextChar + nextNextChar)) {
                    endPos = i + (PUNCTUATION.ellipsis.some(e => e.startsWith(char + nextChar)) ? 2 : 3);
                    isSentenceEnd = true;
                } else if (nextChar === ' ' || nextChar === '\n' || nextChar === '' || /[\u4e00-\u9fffA-ZА-Я]/.test(nextChar)) {
                    endPos = i + 1;
                    isSentenceEnd = true;
                }
            }

            if (!isSentenceEnd && char === '\n' && nextChar === '\n') {
                if (current.trim().length > 0) { sentences.push(current.trim()); current = ''; }
                i += 2; continue;
            }

            if (isSentenceEnd && endPos > 0) {
                const sentence = current.trim();
                if (sentence.length > 0) sentences.push(sentence);
                current = '';
                i = endPos - 1;
            }
            i++;
        }

        if (current.trim().length > 0) sentences.push(current.trim());
        return sentences.filter(s => s.length > 0);
    }

    // ==================== 分词 ====================

    function tokenize(text) {
        if (!text || typeof text !== 'string') return [];
        const tokens = [];
        const englishBuffer = [];

        // 统一处理所有字符（中文+英文+数字），使用滑动窗口n-gram
        const chars = [];
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            // 跳过标点和空白
            if (/\s/.test(char) || /[，。？！；：""''（）【】《》、]/.test(char)) continue;
            chars.push(char.toLowerCase());
        }

        // 字符级 bigram（跨语言通用，增加重叠）
        for (let i = 0; i < chars.length - 1; i++) {
            const bigram = chars[i] + chars[i + 1];
            if (!STOP_WORDS.has(bigram)) tokens.push(bigram);
        }

        // 字符级 trigram
        for (let i = 0; i < chars.length - 2; i++) {
            const trigram = chars[i] + chars[i + 1] + chars[i + 2];
            if (!STOP_WORDS.has(trigram)) tokens.push(trigram);
        }

        // 英文单词（保留语义信息）
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const isLetter = /[a-zA-Z]/.test(char);
            const isDigit = /[0-9]/.test(char);
            if (isLetter || isDigit) {
                englishBuffer.push(char.toLowerCase());
            } else {
                if (englishBuffer.length > 0) { flushEnglishBuffer(tokens, englishBuffer); englishBuffer.length = 0; }
            }
        }
        if (englishBuffer.length > 0) flushEnglishBuffer(tokens, englishBuffer);

        return tokens;
    }

    function flushEnglishBuffer(tokens, buffer) {
        const word = buffer.join('');
        if (word.length > 1 && !STOP_WORDS.has(word)) tokens.push(word);
    }

    // ==================== TF-IDF + L2归一化 ====================

    function computeIdf(sentences) {
        const docFreq = new Map();
        const n = sentences.length;

        for (const sent of sentences) {
            const tokens = tokenize(sent);
            const seen = new Set();
            for (const token of tokens) {
                if (!seen.has(token)) {
                    seen.add(token);
                    docFreq.set(token, (docFreq.get(token) || 0) + 1);
                }
            }
        }

        const idf = new Map();
        for (const [token, df] of docFreq) {
            idf.set(token, Math.log((n + CONFIG.idfSmoothing) / (df + CONFIG.idfSmoothing)) + 1);
        }
        return idf;
    }

    function vectorize(sentence, idf) {
        const tokens = tokenize(sentence);
        if (tokens.length === 0) return null;

        const tf = new Map();
        for (const token of tokens) tf.set(token, (tf.get(token) || 0) + 1);

        const vec = new Map();
        for (const [token, count] of tf) {
            const idfWeight = idf && idf.has(token) ? idf.get(token) : 1.0;
            vec.set(token, (count / tokens.length) * idfWeight);
        }

        // L2归一化
        let norm = 0;
        for (const weight of vec.values()) norm += weight * weight;
        norm = Math.sqrt(norm);
        if (norm === 0) return null;

        const normalized = new Map();
        for (const [token, weight] of vec) normalized.set(token, weight / norm);
        return normalized;
    }

    function cosineSimilarity(vecA, vecB) {
        if (!vecA || !vecB) return 0;
        let dot = 0;
        for (const [token, weightA] of vecA) {
            const weightB = vecB.get(token);
            if (weightB !== undefined) dot += weightA * weightB;
        }
        // L2归一化后点积即余弦相似度，范围[-1,1]，钳位到[0,1]
        return Math.max(0, Math.min(1, dot));
    }

    // 新增：Jaccard重叠率作为补充相似度度量
    function jaccardSimilarity(vecA, vecB) {
        if (!vecA || !vecB) return 0;
        let intersection = 0;
        let union = new Set();
        for (const token of vecA.keys()) {
            union.add(token);
            if (vecB.has(token)) intersection++;
        }
        for (const token of vecB.keys()) union.add(token);
        return union.size > 0 ? intersection / union.size : 0;
    }

    // 综合相似度：余弦 + Jaccard加权
    function combinedSimilarity(vecA, vecB) {
        const cos = cosineSimilarity(vecA, vecB);
        const jac = jaccardSimilarity(vecA, vecB);
        // Jaccard对稀疏特征更敏感，给予更高权重
        return cos * 0.3 + jac * 0.7;
    }

    // ==================== 缓存 ====================

    function addToCache(key, value) {
        if (cache.size >= CONFIG.cacheMaxSize) { const k = cacheKeys.shift(); if (k) cache.delete(k); }
        cacheKeys.push(key);
        cache.set(key, value);
    }

    function getCachedSimilarity(sent1, sent2) {
        const key = sent1 + '|||' + sent2;
        return (CONFIG.enableCache && cache.has(key)) ? cache.get(key) : null;
    }

    // ==================== 词汇线索 ====================

    function hasStrongCue(sentence) {
        if (!sentence) return false;
        const lower = sentence.toLowerCase().trim();
        for (const cue of STRONG_CUE_WORDS) {
            if (lower.startsWith(cue.toLowerCase())) return true;
        }
        return false;
    }

    function isDialogueTurn(sentences, index) {
        if (index < 1) return false;
        const prev = sentences[index - 1];
        const curr = sentences[index];
        // 检测问答模式：前句以?结尾，当前句以!或陈述开头
        const prevIsQuestion = /[？\?]\s*$/.test(prev);
        const currIsShort = curr.length < 15;
        return prevIsQuestion && currIsShort;
    }

    // ==================== 局部谷底检测 ====================

    function isLocalValley(similarities, index, window) {
        const w = window || CONFIG.valleyWindow;
        const sim = similarities[index];
        let leftSum = 0, leftCount = 0;
        for (let j = Math.max(0, index - w); j < index; j++) { leftSum += similarities[j]; leftCount++; }
        let rightSum = 0, rightCount = 0;
        for (let j = index + 1; j < Math.min(similarities.length, index + w + 1); j++) { rightSum += similarities[j]; rightCount++; }

        if (leftCount === 0 && rightCount === 0) return false;
        const neighborMean = (leftSum + rightSum) / (leftCount + rightCount);
        return neighborMean > 0 && sim < neighborMean * (1 - CONFIG.valleyDropRatio);
    }

    // ==================== 多跳语义粘合 ====================

    function computeMultiHopScore(similarities, vectors, index) {
        const sim1 = similarities[index];
        if (index + 1 >= similarities.length) return sim1;
        const sim2 = combinedSimilarity(vectors[index], vectors[index + 2] || null);
        const drop = Math.max(0, sim1 - sim2);
        if (drop > CONFIG.multiHopDropThreshold) {
            return sim1 - CONFIG.multiHopWeight * drop;
        }
        return sim1;
    }

    // ==================== 相似度计算（含词汇线索偏移） ====================

    function computeSimilarities(sentences) {
        const idf = computeIdf(sentences);
        const vectors = sentences.map(s => vectorize(s, idf));
        const similarities = [];

        for (let i = 0; i < vectors.length - 1; i++) {
            const cached = getCachedSimilarity(sentences[i], sentences[i + 1]);
            if (cached !== null) { similarities.push(cached); continue; }

            let sim = combinedSimilarity(vectors[i], vectors[i + 1]);

            // 优化4：强提示词-0.2偏移，更容易触发分段
            if (hasStrongCue(sentences[i + 1])) {
                sim = Math.max(0, sim - CONFIG.lexicalOffset);
            }

            // 对话轮次检测：问答对降低相似度
            if (isDialogueTurn(sentences, i + 1)) {
                sim = Math.max(0, sim - 0.1);
            }

            similarities.push(sim);
            if (CONFIG.enableCache) addToCache(sentences[i] + '|||' + sentences[i + 1], sim);
        }

        return { similarities, vectors };
    }

    // ==================== 分位数自适应阈值 ====================

    function percentile(arr, p) {
        if (arr.length === 0) return 0;
        const sorted = [...arr].sort((a, b) => a - b);
        const idx = (sorted.length - 1) * p;
        const lower = Math.floor(idx);
        const upper = Math.ceil(idx);
        if (lower === upper) return sorted[lower];
        return sorted[lower] * (upper - idx) + sorted[upper] * (idx - lower);
    }

    function computeAdaptiveThreshold(similarities) {
        if (similarities.length === 0) return { threshold: 0.5, mean: 0, std: 0, p25: 0 };

        const n = similarities.length;
        let sum = 0;
        for (const sim of similarities) sum += sim;
        const mean = sum / n;

        let sqSum = 0;
        for (const sim of similarities) sqSum += (sim - mean) * (sim - mean);
        const std = Math.sqrt(sqSum / n);

        // 优化2：基于分位数的自适应阈值
        const p25 = percentile(similarities, 0.25);
        const p50 = percentile(similarities, 0.5);

        let threshold;

        if (std < 1e-6) {
            // 优化3：零方差细粒度处理
            if (mean > 0.65) {
                // 高度相似，近乎不切
                threshold = 0.85;
            } else if (mean < 0.35) {
                // 句子间不相似但均匀，检测是否为对话
                threshold = 0.35;
            } else {
                // 中间状态，略高于均值
                threshold = mean * 1.1;
            }
        } else if (n < 5) {
            // 短文本：更保守，基于中位数
            threshold = Math.max(0.2, Math.min(0.8, p50 - 0.5 * std));
        } else {
            // 正常文本：基于下四分位数微调
            threshold = Math.max(0.15, Math.min(0.8, p25 - 0.5 * std));
        }

        return { threshold, mean, std, p25, p50 };
    }

    // ==================== 分段点检测（双阈值+局部谷底） ====================

    function findBreakpoints(similarities, threshold, vectors, sentences) {
        const breakpoints = [];
        let currentLen = 0;
        const strongThreshold = threshold - CONFIG.strongMargin;
        const candidateThreshold = threshold + CONFIG.candidateMargin;

        for (let i = 0; i < similarities.length; i++) {
            currentLen++;

            // 路径B增强：强制词汇线索分段——检测到强提示词时无条件切分
            // 列表项（首先/其次/然后/最后）允许单句成段
            const isListCue = sentences && /^\s*(首先|其次|再次|然后|接着|最后|第一|第二|第三|第四|第五)/.test(sentences[i + 1]);
            const minLenForCue = isListCue ? 1 : CONFIG.minSentences;
            if (sentences && hasStrongCue(sentences[i + 1]) && currentLen >= minLenForCue) {
                breakpoints.push(i);
                currentLen = 0;
                continue;
            }

            const boundaryScore = vectors
                ? computeMultiHopScore(similarities, vectors, i)
                : similarities[i];

            // 强边界：直接低于 strongThreshold，直接切
            if (boundaryScore < strongThreshold && currentLen >= CONFIG.minSentences) {
                breakpoints.push(i);
                currentLen = 0;
                continue;
            }

            // 候选边界：在 [strongThreshold, candidateThreshold) 区间，需局部谷底确认
            if (boundaryScore < candidateThreshold && currentLen >= CONFIG.minSentences) {
                if (isLocalValley(similarities, i, CONFIG.valleyWindow)) {
                    breakpoints.push(i);
                    currentLen = 0;
                    continue;
                }
            }

            // 强制长度限制
            if (currentLen >= CONFIG.maxSentences) {
                const windowStart = Math.max(0, i - CONFIG.maxSentences + 1);
                let minSim = similarities[windowStart], minIdx = windowStart;
                for (let j = windowStart + 1; j <= i; j++) {
                    if (similarities[j] < minSim) { minSim = similarities[j]; minIdx = j; }
                }
                breakpoints.push(minIdx);
                currentLen = i - minIdx;
            }
        }

        return breakpoints;
    }

    function buildSegments(sentences, breakpoints) {
        if (breakpoints.length === 0) return sentences.length > 0 ? [sentences.join('')] : [];
        const segments = [];
        let start = 0;
        for (const bp of breakpoints) {
            const seg = sentences.slice(start, bp + 1).join('');
            if (seg.length >= CONFIG.minSegmentChars) segments.push(seg);
            start = bp + 1;
        }
        const last = sentences.slice(start).join('');
        if (last.length >= CONFIG.minSegmentChars) segments.push(last);
        return segments;
    }

    // ==================== 聚类后验修正 ====================

    function computeSegmentCentroid(sentences, start, end, vectors) {
        if (start >= end || !vectors) return null;
        const centroid = new Map();
        let count = 0;
        for (let i = start; i < end && i < vectors.length; i++) {
            if (!vectors[i]) continue;
            for (const [token, weight] of vectors[i]) {
                centroid.set(token, (centroid.get(token) || 0) + weight);
            }
            count++;
        }
        if (count === 0) return null;
        for (const [token, weight] of centroid) centroid.set(token, weight / count);
        return centroid;
    }

    function postCorrection(sentences, breakpoints, vectors) {
        if (breakpoints.length === 0 || !vectors) return breakpoints;
        const corrected = [...breakpoints];
        const segmentRanges = [];
        let prev = 0;
        for (const bp of corrected) { segmentRanges.push([prev, bp + 1]); prev = bp + 1; }
        segmentRanges.push([prev, sentences.length]);

        const toMerge = new Set();
        for (let i = 0; i < segmentRanges.length - 1; i++) {
            const [s1Start, s1End] = segmentRanges[i];
            const [s2Start, s2End] = segmentRanges[i + 1];
            const c1 = computeSegmentCentroid(sentences, s1Start, s1End, vectors);
            const c2 = computeSegmentCentroid(sentences, s2Start, s2End, vectors);
            const sim = combinedSimilarity(c1, c2);
            if (sim > CONFIG.mergeCentroidThreshold) toMerge.add(i);
        }

        if (toMerge.size > 0) {
            const newBreakpoints = [];
            for (let i = 0; i < corrected.length; i++) {
                if (!toMerge.has(i)) newBreakpoints.push(corrected[i]);
            }
            return newBreakpoints;
        }
        return corrected;
    }

    // ==================== 分层分段 ====================

    function hierarchicalSegment(text) {
        const sentences = splitIntoSentences(text);
        if (sentences.length <= CONFIG.hierarchicalWindowSize) return segment(text);

        const macroBlocks = [];
        for (let i = 0; i < sentences.length; i += CONFIG.hierarchicalWindowSize) {
            macroBlocks.push(sentences.slice(i, Math.min(i + CONFIG.hierarchicalWindowSize, sentences.length)));
        }

        const allBreakpoints = [];
        let offset = 0;
        for (const block of macroBlocks) {
            const result = segment(block.join(''));
            for (const bp of result.breakpoints) allBreakpoints.push(offset + bp);
            offset += block.length;
        }

        const { similarities, vectors } = computeSimilarities(sentences);
        const { threshold } = computeAdaptiveThreshold(similarities);

        const macroBoundaries = new Set();
        for (let i = 1; i < macroBlocks.length; i++) {
            macroBoundaries.add(macroBlocks.slice(0, i).reduce((s, b) => s + b.length, 0) - 1);
        }

        const verifiedBreakpoints = allBreakpoints.filter(bp => {
            if (macroBoundaries.has(bp) && bp < similarities.length) return similarities[bp] < threshold;
            return true;
        });

        const correctedBreakpoints = postCorrection(sentences, verifiedBreakpoints, vectors);
        return { segments: buildSegments(sentences, correctedBreakpoints), breakpoints: correctedBreakpoints, threshold, similarities };
    }

    // ==================== 流式滑动窗口 ====================

    function streamingSegment(text) {
        const sentences = splitIntoSentences(text);
        if (sentences.length < 2) return { segments: [text], breakpoints: [], threshold: 0 };

        const { similarities, vectors } = computeSimilarities(sentences);
        const wSize = CONFIG.streamingWindowSize;
        const breakpoints = [];
        let currentLen = 0;

        for (let i = 0; i < similarities.length; i++) {
            currentLen++;
            const wStart = Math.max(0, i - wSize + 1);
            const wEnd = i + 1;
            let wSum = 0;
            for (let j = wStart; j < wEnd; j++) wSum += similarities[j];
            const wMean = wSum / (wEnd - wStart);
            let wSqSum = 0;
            for (let j = wStart; j < wEnd; j++) wSqSum += (similarities[j] - wMean) ** 2;
            const wStd = Math.sqrt(wSqSum / (wEnd - wStart));

            const localP25 = percentile(similarities.slice(wStart, wEnd), 0.25);
            let localThreshold = Math.max(0.15, Math.min(0.8, localP25 - 0.5 * wStd));

            const boundaryScore = computeMultiHopScore(similarities, vectors, i);
            const strongLocal = localThreshold - CONFIG.strongMargin;
            const candidateLocal = localThreshold + CONFIG.candidateMargin;

            if (boundaryScore < strongLocal && currentLen >= CONFIG.minSentences) {
                breakpoints.push(i);
                currentLen = 0;
            } else if (boundaryScore < candidateLocal && currentLen >= CONFIG.minSentences && isLocalValley(similarities, i, CONFIG.valleyWindow)) {
                breakpoints.push(i);
                currentLen = 0;
            } else if (currentLen >= CONFIG.maxSentences) {
                breakpoints.push(i);
                currentLen = 0;
            }
        }

        const correctedBreakpoints = postCorrection(sentences, breakpoints, vectors);
        return { segments: buildSegments(sentences, correctedBreakpoints), breakpoints: correctedBreakpoints, threshold: 0, similarities };
    }

    // ==================== 核心入口 ====================

    function segment(text) {
        if (!text || text.length < CONFIG.minSegmentChars) {
            return { segments: [text], breakpoints: [], threshold: 0 };
        }
        const sentences = splitIntoSentences(text);
        if (sentences.length < 2) return { segments: [text], breakpoints: [], threshold: 0 };

        const { similarities, vectors } = computeSimilarities(sentences);
        const { threshold, mean, std, p25, p50 } = computeAdaptiveThreshold(similarities);
        const breakpoints = findBreakpoints(similarities, threshold, vectors, sentences);
        const correctedBreakpoints = postCorrection(sentences, breakpoints, vectors);
        const segments = buildSegments(sentences, correctedBreakpoints);

        return { segments, breakpoints: correctedBreakpoints, threshold, similarities, mean, std, p25, p50 };
    }

    // ==================== 兼容旧接口 ====================

    function shouldSegment(text, lastSentences, options = {}) {
        const opts = {
            minChars: options.minChars || CONFIG.minSegmentChars,
            forceChars: options.forceChars || CONFIG.maxSegmentChars,
            minSentences: options.minSentences || CONFIG.minSentences,
            maxSentences: options.maxSentences || CONFIG.maxSentences
        };

        if (!text || text.length < opts.minChars) return { shouldSegment: false, reason: 'text_too_short' };
        const sentences = splitIntoSentences(text);
        if (sentences.length < 2) return { shouldSegment: false, reason: 'only_one_sentence' };

        const { similarities, vectors } = computeSimilarities(sentences);
        const { threshold } = computeAdaptiveThreshold(similarities);

        const lastSim = similarities[similarities.length - 1];
        const lastBoundaryScore = computeMultiHopScore(similarities, vectors, similarities.length - 1);
        const strongThreshold = threshold - CONFIG.strongMargin;
        const candidateThreshold = threshold + CONFIG.candidateMargin;

        const isLastBreak = lastBoundaryScore < strongThreshold
            || (lastBoundaryScore < candidateThreshold && isLocalValley(similarities, similarities.length - 1, CONFIG.valleyWindow));

        if (sentences.length >= opts.maxSentences) {
            return { shouldSegment: true, reason: 'force_max_length', position: estimateCutPosition(text, sentences, opts.maxSentences) };
        }

        if (isLastBreak && sentences.length >= opts.minSentences) {
            return { shouldSegment: true, reason: 'low_coherence', score: lastSim, threshold };
        }

        if (text.length >= opts.forceChars) {
            const pos = estimateCutPosition(text, sentences);
            if (pos > 0) return { shouldSegment: true, reason: 'force_chars', position: pos };
        }

        return { shouldSegment: false, reason: 'coherent_continue', score: lastSim, threshold };
    }

    function estimateCutPosition(text, sentences, maxSentences) {
        if (!sentences || sentences.length < 2) return -1;
        let cutIdx = 0;
        const limit = maxSentences ? Math.min(maxSentences, sentences.length - 1) : sentences.length - 1;
        for (let i = 0; i < limit; i++) cutIdx += sentences[i].length;
        return cutIdx > 0 && cutIdx <= text.length ? cutIdx : -1;
    }

    function calculateSimilarity(sent1, sent2) {
        const cached = getCachedSimilarity(sent1, sent2);
        if (cached !== null) return cached;
        const sim = cosineSimilarity(vectorize(sent1, globalIdf), vectorize(sent2, globalIdf));
        if (CONFIG.enableCache) addToCache(sent1 + '|||' + sent2, sim);
        return sim;
    }

    function calculateCoherenceScore(sentences, windowSize) {
        if (!sentences || sentences.length < 2) return 1.0;
        let total = 0, count = 0;
        const start = Math.max(0, sentences.length - (windowSize || CONFIG.windowSize));
        for (let i = start; i < sentences.length - 1; i++) { total += calculateSimilarity(sentences[i], sentences[i + 1]); count++; }
        return count > 0 ? total / count : 1.0;
    }

    function isCompleteSentence(text) {
        if (!text || typeof text !== 'string') return false;
        const t = text.trim();
        if (t.length < 4) return false;
        if (isMarkdownHeading(t) || isListItem(t)) return true;
        return PUNCTUATION.sentenceEnd.some(p => t.endsWith(p)) || PUNCTUATION.ellipsis.some(e => t.endsWith(e)) || t.length >= 15;
    }

    function calculateAdaptiveDelay(text) {
        const sentences = splitIntoSentences(text);
        if (sentences.length === 0) return 15;
        const last = sentences[sentences.length - 1];
        const base = 15;
        if (isMarkdownHeading(last)) return base + 10;
        if (last.endsWith('！') || last.endsWith('!?') || last.endsWith('?!')) return base + 15;
        if (PUNCTUATION.ellipsis.some(e => last.endsWith(e))) return base + 8;
        return Math.min(base + last.length * 0.05, 30);
    }

    function detectCoherenceMarkers(text) {
        const markers = [];
        const COHERENCE_MARKERS = {
            conclusion: ['总之', '综上所述', 'in conclusion', 'to sum up', 'all in all'],
            contrast: ['但是', '然而', 'but', 'however', 'although'],
            transition: ['首先', '其次', 'firstly', 'secondly', 'to begin with']
        };
        const lower = text.toLowerCase();
        for (const [type, words] of Object.entries(COHERENCE_MARKERS)) {
            for (const word of words) {
                const idx = lower.indexOf(word.toLowerCase());
                if (idx !== -1) markers.push({ type, word, index: idx });
            }
        }
        return markers.sort((a, b) => a.index - b.index);
    }

    function findBestSegmentPoint(text, sentLength, options) {
        const result = shouldSegment(text, [], options || {});
        return result.shouldSegment && result.position ? result.position : -1;
    }

    function clearCache() { cache.clear(); cacheKeys = []; }
    function updateConfig(newConfig) { Object.assign(CONFIG, newConfig); }
    function getConfig() { return { ...CONFIG }; }

    return {
        segment,
        hierarchicalSegment,
        streamingSegment,
        splitIntoSentences,
        vectorize,
        cosineSimilarity,
        computeSimilarities,
        computeAdaptiveThreshold,
        findBreakpoints,
        buildSegments,
        isLocalValley,
        computeMultiHopScore,
        postCorrection,
        hasStrongCue,
        shouldSegment,
        calculateSimilarity,
        calculateCoherenceScore,
        calculateAdaptiveDelay,
        detectCoherenceMarkers,
        isCompleteSentence,
        isMarkdownHeading,
        isListItem,
        findBestSegmentPoint,
        clearCache,
        updateConfig,
        getConfig
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SemanticSegmenter;
}
