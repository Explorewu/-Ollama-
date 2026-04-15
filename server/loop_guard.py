"""
循环防护模块 (LoopGuard)

功能：
- 检测生成过程中的循环模式
- 低开销实时监控
- 自动提供检测报告

设计原则：
- 简单高效，零额外依赖
- 只在固定间隔检查，减少 CPU 占用
- 多种检测模式，高覆盖率
"""

import re
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class LoopGuardConfig:
    """循环防护配置"""
    max_consecutive_repeats: int = 3      # 连续重复次数阈值
    min_repeat_length: int = 8            # 最小重复长度（避免短词误判）
    max_total_repeats: int = 4            # 总重复次数阈值
    max_length: int = 4096                # 最大生成长度
    check_interval: int = 15              # 检查间隔（字符数）


@dataclass
class LoopReport:
    """循环检测报告"""
    should_stop: bool = False
    reason: Optional[str] = None
    loop_text: str = ""
    confidence: float = 0.0
    repeat_count: int = 0


class LoopGuard:
    """
    轻量级循环检测器

    特点：
    - 简单高效，零额外依赖
    - 只在固定间隔检查
    - 自动中断循环
    """

    def __init__(self, config: Optional[LoopGuardConfig] = None):
        self.config = config or LoopGuardConfig()
        self.generated = ""
        self.sentences = []               # 句子历史
        self.last_sentence = ""
        self.repeat_count = 0             # 连续重复计数
        self.total_repeats = 0            # 总重复次数
        self.last_check_pos = 0
        self.char_patterns = {}           # 字符模式计数
        self.word_patterns = {}           # 词组模式计数

    def reset(self):
        """重置状态"""
        self.generated = ""
        self.sentences = []
        self.last_sentence = ""
        self.repeat_count = 0
        self.total_repeats = 0
        self.last_check_pos = 0
        self.char_patterns = {}
        self.word_patterns = {}

    def check(self, text: str) -> LoopReport:
        """
        检查新文本是否包含循环

        Returns:
            LoopReport: 包含检测结果的报告
        """
        self.generated += text
        current_pos = len(self.generated)

        # 1. 快速检查：长度限制
        if current_pos >= self.config.max_length:
            return LoopReport(
                should_stop=True,
                reason="已达到最大生成长度",
                loop_text="",
                confidence=1.0,
                repeat_count=0
            )

        # 2. 间隔检查（减少 CPU 占用）
        if current_pos - self.last_check_pos < self.config.check_interval:
            return LoopReport(should_stop=False)

        self.last_check_pos = current_pos

        # 3. 提取当前句子
        current_sentence = self._extract_last_sentence(text)

        # 4. 检测连续重复（高置信度）
        if current_sentence and len(current_sentence) >= self.config.min_repeat_length:
            if current_sentence == self.last_sentence:
                self.repeat_count += 1
                self.total_repeats += 1

                if self.repeat_count >= self.config.max_consecutive_repeats:
                    return LoopReport(
                        should_stop=True,
                        reason=f"检测到连续重复 {self.repeat_count} 次",
                        loop_text=current_sentence[:50] + "...",
                        confidence=0.95,
                        repeat_count=self.repeat_count
                    )
            else:
                self.repeat_count = 0

            self.last_sentence = current_sentence

        # 5. 检测历史重复（中等置信度）
        if current_sentence and len(current_sentence) >= self.config.min_repeat_length:
            historical_count = self.sentences.count(current_sentence)
            if historical_count >= self.config.max_total_repeats:
                return LoopReport(
                    should_stop=True,
                    reason=f"文本在历史中出现 {historical_count} 次",
                    loop_text=current_sentence[:50],
                    confidence=0.85,
                    repeat_count=historical_count
                )
            self.sentences.append(current_sentence)

            # 限制历史大小
            if len(self.sentences) > 100:
                self.sentences = self.sentences[-50:]

        # 6. 检测字符级循环（高置信度）
        result = self._check_char_patterns(text)
        if result.should_stop:
            return result

        # 7. 词组检测已禁用（流式输出会导致正常词语被误判）
        # 字符级和句子级检测已足够覆盖循环场景
        return LoopReport(should_stop=False)

    def _extract_last_sentence(self, text: str) -> str:
        """提取最后一个完整句子"""
        sentences = re.split(r'[。！？.!?\n]+', text)
        return sentences[-1].strip() if sentences else ""

    def _check_char_patterns(self, text: str) -> LoopReport:
        """检测字符级循环"""
        for char in set(text):
            # 检测单个字符连续重复（10次以上）
            if char * 10 in text:
                return LoopReport(
                    should_stop=True,
                    reason=f"检测到字符 '{char}' 连续重复",
                    loop_text=char * 5 + "...",
                    confidence=0.98,
                    repeat_count=10
                )

        return LoopReport(should_stop=False)

    def _check_word_patterns(self, text: str) -> LoopReport:
        """检测词组循环"""
        words = text.split()
        if len(words) >= 3:
            phrase = " ".join(words[-3:])
            phrase_lower = phrase.lower()

            # 更新词组计数
            self.word_patterns[phrase_lower] = self.word_patterns.get(phrase_lower, 0) + 1

            # 如果词组重复出现
            if self.word_patterns[phrase_lower] >= 3:
                return LoopReport(
                    should_stop=True,
                    reason="检测到短语重复",
                    loop_text=phrase[:30],
                    confidence=0.90,
                    repeat_count=self.word_patterns[phrase_lower]
                )

        # 清理过时的词组
        if len(self.word_patterns) > 500:
            # 移除一半最旧的词组
            keys_to_remove = list(self.word_patterns.keys())[:250]
            for key in keys_to_remove:
                del self.word_patterns[key]

        return LoopReport(should_stop=False)

    def get_statistics(self) -> dict:
        """获取检测统计信息"""
        return {
            "total_generated": len(self.generated),
            "unique_sentences": len(set(self.sentences)),
            "word_patterns_count": len(self.word_patterns),
            "consecutive_repeats": self.repeat_count,
            "total_repeats": self.total_repeats
        }


def create_loop_guard(config: Optional[LoopGuardConfig] = None) -> LoopGuard:
    """工厂函数：创建循环检测器"""
    return LoopGuard(config)
