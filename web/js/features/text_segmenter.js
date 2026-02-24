/**
 * 智能文本分段处理器 (JavaScript 版本)
 * 
 * 功能：
 * - 智能检测中英文字符边界
 * - 防止字符显示分割问题
 * - 优化文本流式输出
 * - 支持多语言混合文本处理
 */

class TextSegment {
    constructor(text, isComplete, segmentType, language, confidence) {
        this.text = text;
        this.isComplete = isComplete;
        this.segmentType = segmentType; // 'word', 'sentence', 'phrase'
        this.language = language; // 'zh', 'en', 'mixed'
        this.confidence = confidence;
    }
}

class TextSegmenter {
    constructor() {
        // 中文标点符号（句子结束）
        this.chinesePunctuation = '。！？；：，、';
        
        // 英文标点符号
        this.englishPunctuation = '.!?;:,';
        
        // 中文字符正则（包括常用汉字、标点）
        this.chinesePattern = /[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/;
        
        // 句子结束模式
        this.sentenceEndPattern = /[。！？.!?]+/g;
        
        // 分段配置
        this.config = {
            maxSegmentLength: 50,  // 最大分段长度
            minSegmentLength: 1,   // 最小分段长度
            preferCompleteWords: true,  // 优先完整单词
            languageDetectionThreshold: 0.3,  // 语言检测阈值
        };
    }
    
    /**
     * 检测文本语言
     */
    detectLanguage(text) {
        if (!text) return 'unknown';
        
        // 统计中文字符数量
        let chineseChars = 0;
        for (let char of text) {
            if (this.chinesePattern.test(char)) {
                chineseChars++;
            }
        }
        
        const totalChars = text.length;
        if (totalChars === 0) return 'unknown';
        
        const chineseRatio = chineseChars / totalChars;
        
        if (chineseRatio > 0.7) return 'zh';  // 中文
        else if (chineseRatio < 0.3) return 'en';  // 英文
        else return 'mixed';  // 混合
    }
    
    /**
     * 智能文本分段
     */
    smartSegment(text, previousSegment = '') {
        if (!text) return [];
        
        // 检测语言
        const language = this.detectLanguage(text);
        
        // 根据语言选择分段策略
        let segments;
        switch (language) {
            case 'zh':
                segments = this._segmentChinese(text, previousSegment);
                break;
            case 'en':
                segments = this._segmentEnglish(text, previousSegment);
                break;
            default:
                segments = this._segmentMixed(text, previousSegment);
        }
        
        return segments;
    }
    
    /**
     * 中文文本分段
     */
    _segmentChinese(text, previousSegment) {
        const segments = [];
        let currentSegment = previousSegment;
        
        for (let char of text) {
            currentSegment += char;
            
            // 检查是否达到句子结束
            if (this.chinesePunctuation.includes(char)) {
                segments.push(new TextSegment(
                    currentSegment,
                    true,
                    'sentence',
                    'zh',
                    0.9
                ));
                currentSegment = '';
            }
            
            // 检查是否达到最大分段长度
            else if (currentSegment.length >= this.config.maxSegmentLength) {
                // 寻找合适的分割点
                const splitPoint = this._findChineseSplitPoint(currentSegment);
                
                if (splitPoint > 0) {
                    segments.push(new TextSegment(
                        currentSegment.substring(0, splitPoint),
                        false,
                        'phrase',
                        'zh',
                        0.7
                    ));
                    currentSegment = currentSegment.substring(splitPoint);
                }
            }
        }
        
        // 处理剩余文本
        if (currentSegment) {
            segments.push(new TextSegment(
                currentSegment,
                false,
                'phrase',
                'zh',
                0.6
            ));
        }
        
        return segments;
    }
    
    /**
     * 英文文本分段
     */
    _segmentEnglish(text, previousSegment) {
        const segments = [];
        const words = text.split(' ');
        let currentSegment = previousSegment;
        
        for (let word of words) {
            if (currentSegment) {
                currentSegment += ' ' + word;
            } else {
                currentSegment = word;
            }
            
            // 检查句子结束
            if (this._endsWithPunctuation(word, this.englishPunctuation)) {
                segments.push(new TextSegment(
                    currentSegment,
                    true,
                    'sentence',
                    'en',
                    0.9
                ));
                currentSegment = '';
            }
            
            // 检查分段长度
            else if (currentSegment.length >= this.config.maxSegmentLength) {
                segments.push(new TextSegment(
                    currentSegment,
                    false,
                    'phrase',
                    'en',
                    0.7
                ));
                currentSegment = '';
            }
        }
        
        // 处理剩余文本
        if (currentSegment) {
            segments.push(new TextSegment(
                currentSegment,
                false,
                'phrase',
                'en',
                0.6
            ));
        }
        
        return segments;
    }
    
    /**
     * 混合语言文本分段
     */
    _segmentMixed(text, previousSegment) {
        const segments = [];
        let currentSegment = previousSegment;
        
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            currentSegment += char;
            
            // 检测语言边界
            if (i > 0) {
                const prevChar = text[i - 1];
                const currentLang = this._detectCharLanguage(char);
                const prevLang = this._detectCharLanguage(prevChar);
                
                // 语言切换时考虑分段
                if (currentLang !== prevLang && currentSegment.length > 1) {
                    segments.push(new TextSegment(
                        currentSegment.substring(0, currentSegment.length - 1),
                        false,
                        'language_boundary',
                        'mixed',
                        0.8
                    ));
                    currentSegment = char;  // 从当前字符重新开始
                }
            }
            
            // 检查标点符号
            if ((this.chinesePunctuation + this.englishPunctuation).includes(char)) {
                segments.push(new TextSegment(
                    currentSegment,
                    true,
                    'sentence',
                    'mixed',
                    0.9
                ));
                currentSegment = '';
            }
            
            // 检查长度限制
            else if (currentSegment.length >= this.config.maxSegmentLength) {
                const splitPoint = this._findMixedSplitPoint(currentSegment);
                
                if (splitPoint > 0) {
                    segments.push(new TextSegment(
                        currentSegment.substring(0, splitPoint),
                        false,
                        'phrase',
                        'mixed',
                        0.7
                    ));
                    currentSegment = currentSegment.substring(splitPoint);
                }
            }
        }
        
        // 处理剩余文本
        if (currentSegment) {
            segments.push(new TextSegment(
                currentSegment,
                false,
                'phrase',
                'mixed',
                0.6
            ));
        }
        
        return segments;
    }
    
    /**
     * 检测单个字符的语言
     */
    _detectCharLanguage(char) {
        if (this.chinesePattern.test(char)) {
            return 'zh';
        } else if (/[a-zA-Z]/.test(char)) {
            return 'en';
        } else {
            return 'other';
        }
    }
    
    /**
     * 寻找中文文本的分割点
     */
    _findChineseSplitPoint(text) {
        // 优先在标点符号后分割
        for (let i = text.length - 1; i > 0; i--) {
            if ('，、；'.includes(text[i])) {
                return i + 1;
            }
        }
        
        // 其次在自然停顿处分割
        for (let i = text.length - 1; i > 0; i--) {
            if (i > 3 && '的得地了着过'.includes(text[i])) {
                return i + 1;
            }
        }
        
        // 最后在中间位置分割
        return Math.floor(text.length / 2);
    }
    
    /**
     * 寻找混合文本的分割点
     */
    _findMixedSplitPoint(text) {
        // 优先在空格处分割
        const lastSpace = text.lastIndexOf(' ');
        if (lastSpace > 0) {
            return lastSpace + 1;
        }
        
        // 其次在标点符号处分割
        const punctuation = this.chinesePunctuation + this.englishPunctuation;
        for (let punct of punctuation) {
            const lastPunct = text.lastIndexOf(punct);
            if (lastPunct > 0) {
                return lastPunct + 1;
            }
        }
        
        // 最后在语言边界处分割
        for (let i = text.length - 1; i > 0; i--) {
            const currentLang = this._detectCharLanguage(text[i]);
            const prevLang = this._detectCharLanguage(text[i - 1]);
            if (currentLang !== prevLang) {
                return i;
            }
        }
        
        return Math.floor(text.length / 2);
    }
    
    /**
     * 检查单词是否以标点符号结尾
     */
    _endsWithPunctuation(word, punctuation) {
        for (let punct of punctuation) {
            if (word.endsWith(punct)) {
                return true;
            }
        }
        return false;
    }
    
    /**
     * 处理文本流
     */
    processStream(textStream) {
        const allSegments = [];
        let previousSegment = '';
        
        for (let textChunk of textStream) {
            const segments = this.smartSegment(textChunk, previousSegment);
            
            if (segments.length > 0) {
                // 最后一个分段可能是不完整的，需要传递给下一次处理
                const lastSegment = segments[segments.length - 1];
                if (!lastSegment.isComplete) {
                    previousSegment = lastSegment.text;
                    segments.pop();  // 移除不完整的分段
                } else {
                    previousSegment = '';
                }
                
                allSegments.push(...segments);
            }
        }
        
        return allSegments;
    }
    
    /**
     * 实时分段处理（用于语音识别实时显示）
     */
    realtimeSegment(text, callback) {
        const segments = this.smartSegment(text);
        
        segments.forEach((segment, index) => {
            // 模拟实时输出效果
            setTimeout(() => {
                if (callback) {
                    callback(segment);
                }
            }, index * 50);  // 50ms 间隔
        });
        
        return segments;
    }
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TextSegmenter, TextSegment };
} else if (typeof window !== 'undefined') {
    window.TextSegmenter = TextSegmenter;
    window.TextSegment = TextSegment;
}

// 测试函数
function testSegmenter() {
    const segmenter = new TextSegmenter();
    
    // 测试中文文本
    const chineseText = "你好，今天天气很好。我想问一下明天的天气预报。谢谢！";
    const chineseSegments = segmenter.smartSegment(chineseText);
    console.log("中文分段结果:");
    chineseSegments.forEach(seg => {
        console.log(`  [${seg.segmentType}] ${seg.text} (完整: ${seg.isComplete})`);
    });
    
    // 测试英文文本
    const englishText = "Hello, how are you today? I want to know the weather forecast for tomorrow. Thank you!";
    const englishSegments = segmenter.smartSegment(englishText);
    console.log("\n英文分段结果:");
    englishSegments.forEach(seg => {
        console.log(`  [${seg.segmentType}] ${seg.text} (完整: ${seg.isComplete})`);
    });
    
    // 测试混合文本
    const mixedText = "Hello你好，今天weather很好。I want to know天气预报。谢谢Thank you!";
    const mixedSegments = segmenter.smartSegment(mixedText);
    console.log("\n混合文本分段结果:");
    mixedSegments.forEach(seg => {
        console.log(`  [${seg.segmentType}] ${seg.text} (完整: ${seg.isComplete})`);
    });
}

// 如果直接运行，执行测试
if (typeof window !== 'undefined' && window.location.href.includes('test')) {
    testSegmenter();
}