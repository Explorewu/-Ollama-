"""
智能文本分段处理器

功能：
- 智能检测中英文字符边界
- 防止字符显示分割问题
- 优化文本流式输出
- 支持多语言混合文本处理
"""

import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class TextSegment:
    """文本分段结果"""
    text: str
    is_complete: bool
    segment_type: str  # 'word', 'sentence', 'phrase'
    language: str  # 'zh', 'en', 'mixed'
    confidence: float


class TextSegmenter:
    """智能文本分段处理器"""
    
    def __init__(self):
        # 中文标点符号（句子结束）
        self.chinese_punctuation = '。！？；：，、'
        
        # 英文标点符号
        self.english_punctuation = '.!?;:,'
        
        # 中文字符正则（包括常用汉字、标点）
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')
        
        # 英文单词正则
        self.english_word_pattern = re.compile(r'\b[a-zA-Z]+\b')
        
        # 句子结束模式
        self.sentence_end_pattern = re.compile(r'[。！？.!?]+')
        
        # 分段配置
        self.config = {
            'max_segment_length': 50,  # 最大分段长度
            'min_segment_length': 1,   # 最小分段长度
            'prefer_complete_words': True,  # 优先完整单词
            'language_detection_threshold': 0.3,  # 语言检测阈值
        }
    
    def detect_language(self, text: str) -> str:
        """检测文本语言"""
        if not text:
            return 'unknown'
        
        # 统计中文字符数量
        chinese_chars = len(self.chinese_pattern.findall(text))
        total_chars = len(text)
        
        if total_chars == 0:
            return 'unknown'
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.7:
            return 'zh'  # 中文
        elif chinese_ratio < 0.3:
            return 'en'  # 英文
        else:
            return 'mixed'  # 混合
    
    def smart_segment(self, text: str, previous_segment: str = '') -> List[TextSegment]:
        """智能文本分段"""
        
        if not text:
            return []
        
        # 检测语言
        language = self.detect_language(text)
        
        # 根据语言选择分段策略
        if language == 'zh':
            segments = self._segment_chinese(text, previous_segment)
        elif language == 'en':
            segments = self._segment_english(text, previous_segment)
        else:
            segments = self._segment_mixed(text, previous_segment)
        
        return segments
    
    def _segment_chinese(self, text: str, previous_segment: str) -> List[TextSegment]:
        """中文文本分段"""
        segments = []
        
        # 中文分段策略：按句子和短语分割
        current_segment = previous_segment
        
        for char in text:
            current_segment += char
            
            # 检查是否达到句子结束
            if char in self.chinese_punctuation:
                segments.append(TextSegment(
                    text=current_segment,
                    is_complete=True,
                    segment_type='sentence',
                    language='zh',
                    confidence=0.9
                ))
                current_segment = ''
            
            # 检查是否达到最大分段长度
            elif len(current_segment) >= self.config['max_segment_length']:
                # 寻找合适的分割点
                split_point = self._find_chinese_split_point(current_segment)
                
                if split_point > 0:
                    segments.append(TextSegment(
                        text=current_segment[:split_point],
                        is_complete=False,
                        segment_type='phrase',
                        language='zh',
                        confidence=0.7
                    ))
                    current_segment = current_segment[split_point:]
        
        # 处理剩余文本
        if current_segment:
            segments.append(TextSegment(
                text=current_segment,
                is_complete=False,
                segment_type='phrase',
                language='zh',
                confidence=0.6
            ))
        
        return segments
    
    def _segment_english(self, text: str, previous_segment: str) -> List[TextSegment]:
        """英文文本分段"""
        segments = []
        
        # 英文分段策略：按单词和句子分割
        words = text.split()
        current_segment = previous_segment
        
        for word in words:
            if current_segment:
                current_segment += ' ' + word
            else:
                current_segment = word
            
            # 检查句子结束
            if word.endswith(tuple(self.english_punctuation)):
                segments.append(TextSegment(
                    text=current_segment,
                    is_complete=True,
                    segment_type='sentence',
                    language='en',
                    confidence=0.9
                ))
                current_segment = ''
            
            # 检查分段长度
            elif len(current_segment) >= self.config['max_segment_length']:
                segments.append(TextSegment(
                    text=current_segment,
                    is_complete=False,
                    segment_type='phrase',
                    language='en',
                    confidence=0.7
                ))
                current_segment = ''
        
        # 处理剩余文本
        if current_segment:
            segments.append(TextSegment(
                text=current_segment,
                is_complete=False,
                segment_type='phrase',
                language='en',
                confidence=0.6
            ))
        
        return segments
    
    def _segment_mixed(self, text: str, previous_segment: str) -> List[TextSegment]:
        """混合语言文本分段"""
        segments = []
        
        # 混合语言分段策略：智能边界检测
        current_segment = previous_segment
        
        for i, char in enumerate(text):
            current_segment += char
            
            # 检测语言边界
            if i > 0:
                prev_char = text[i-1]
                current_lang = self._detect_char_language(char)
                prev_lang = self._detect_char_language(prev_char)
                
                # 语言切换时考虑分段
                if current_lang != prev_lang and len(current_segment) > 1:
                    segments.append(TextSegment(
                        text=current_segment[:-1],  # 排除当前字符
                        is_complete=False,
                        segment_type='language_boundary',
                        language='mixed',
                        confidence=0.8
                    ))
                    current_segment = char  # 从当前字符重新开始
            
            # 检查标点符号
            if char in self.chinese_punctuation + self.english_punctuation:
                segments.append(TextSegment(
                    text=current_segment,
                    is_complete=True,
                    segment_type='sentence',
                    language='mixed',
                    confidence=0.9
                ))
                current_segment = ''
            
            # 检查长度限制
            elif len(current_segment) >= self.config['max_segment_length']:
                split_point = self._find_mixed_split_point(current_segment)
                
                if split_point > 0:
                    segments.append(TextSegment(
                        text=current_segment[:split_point],
                        is_complete=False,
                        segment_type='phrase',
                        language='mixed',
                        confidence=0.7
                    ))
                    current_segment = current_segment[split_point:]
        
        # 处理剩余文本
        if current_segment:
            segments.append(TextSegment(
                text=current_segment,
                is_complete=False,
                segment_type='phrase',
                language='mixed',
                confidence=0.6
            ))
        
        return segments
    
    def _detect_char_language(self, char: str) -> str:
        """检测单个字符的语言"""
        if self.chinese_pattern.match(char):
            return 'zh'
        elif char.isalpha():
            return 'en'
        else:
            return 'other'
    
    def _find_chinese_split_point(self, text: str) -> int:
        """寻找中文文本的分割点"""
        # 优先在标点符号后分割
        for i in range(len(text)-1, 0, -1):
            if text[i] in '，、；':
                return i + 1
        
        # 其次在自然停顿处分割
        for i in range(len(text)-1, 0, -1):
            if i > 3 and text[i] in '的得地了着过':
                return i + 1
        
        # 最后在中间位置分割
        return len(text) // 2
    
    def _find_mixed_split_point(self, text: str) -> int:
        """寻找混合文本的分割点"""
        # 优先在空格处分割
        last_space = text.rfind(' ')
        if last_space > 0:
            return last_space + 1
        
        # 其次在标点符号处分割
        for punctuation in self.chinese_punctuation + self.english_punctuation:
            last_punct = text.rfind(punctuation)
            if last_punct > 0:
                return last_punct + 1
        
        # 最后在语言边界处分割
        for i in range(len(text)-1, 0, -1):
            current_lang = self._detect_char_language(text[i])
            prev_lang = self._detect_char_language(text[i-1])
            if current_lang != prev_lang:
                return i
        
        return len(text) // 2
    
    def process_stream(self, text_stream: List[str]) -> List[TextSegment]:
        """处理文本流"""
        all_segments = []
        previous_segment = ''
        
        for text_chunk in text_stream:
            segments = self.smart_segment(text_chunk, previous_segment)
            
            if segments:
                # 最后一个分段可能是不完整的，需要传递给下一次处理
                last_segment = segments[-1]
                if not last_segment.is_complete:
                    previous_segment = last_segment.text
                    segments = segments[:-1]  # 移除不完整的分段
                else:
                    previous_segment = ''
                
                all_segments.extend(segments)
        
        return all_segments


# 使用示例
def test_segmenter():
    """测试分段器"""
    segmenter = TextSegmenter()
    
    # 测试中文文本
    chinese_text = "你好，今天天气很好。我想问一下明天的天气预报。谢谢！"
    segments = segmenter.smart_segment(chinese_text)
    print("中文分段结果:")
    for seg in segments:
        print(f"  [{seg.segment_type}] {seg.text} (完整: {seg.is_complete})")
    
    # 测试英文文本
    english_text = "Hello, how are you today? I want to know the weather forecast for tomorrow. Thank you!"
    segments = segmenter.smart_segment(english_text)
    print("\n英文分段结果:")
    for seg in segments:
        print(f"  [{seg.segment_type}] {seg.text} (完整: {seg.is_complete})")
    
    # 测试混合文本
    mixed_text = "Hello你好，今天weather很好。I want to know天气预报。谢谢Thank you!"
    segments = segmenter.smart_segment(mixed_text)
    print("\n混合文本分段结果:")
    for seg in segments:
        print(f"  [{seg.segment_type}] {seg.text} (完整: {seg.is_complete})")


if __name__ == "__main__":
    test_segmenter()