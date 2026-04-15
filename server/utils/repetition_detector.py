"""
重复检测与动态惩罚模块

检测流式输出中的重复模式，提供截断建议和参数调整建议。
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RepetitionConfig:
    """重复检测配置"""
    enabled: bool = True
    window_size: int = 10
    min_repeat_count: int = 3
    max_repeat_count: int = 5
    token_threshold: int = 5
    phrase_threshold: int = 3
    base_penalty: float = 1.08
    max_penalty: float = 1.5
    penalty_increment: float = 0.1
    truncate_on_max: bool = True


@dataclass
class RepetitionState:
    """重复检测状态"""
    recent_tokens: deque = field(default_factory=lambda: deque(maxlen=10))
    recent_phrases: deque = field(default_factory=lambda: deque(maxlen=5))
    repeat_count: int = 0
    current_penalty: float = 1.08
    detected_pattern: Optional[str] = None
    should_truncate: bool = False
    suggested_penalty: float = 1.08


class RepetitionDetector:
    """
    重复检测器
    
    检测两种重复模式：
    1. Token 级重复：连续相同的 token（如 "the the the"）
    2. 短语级重复：重复的短语模式（如 "I think I think I think"）
    """
    
    def __init__(self, config: RepetitionConfig = None):
        self.config = config or RepetitionConfig()
        self.state = RepetitionState()
        self._token_buffer: List[str] = []
        self._phrase_buffer: List[str] = []
    
    def reset(self):
        """重置检测器状态"""
        self.state = RepetitionState()
        self._token_buffer = []
        self._phrase_buffer = []
    
    def process_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        处理单个 token，检测重复
        
        Args:
            token: 当前 token
            
        Returns:
            (should_stop, reason): 是否应该停止输出，停止原因
        """
        if not self.config.enabled or not token.strip():
            return False, None
        
        token = token.strip()
        self.state.recent_tokens.append(token)
        self._token_buffer.append(token)
        
        should_stop = False
        reason = None
        
        if len(self.state.recent_tokens) >= self.config.min_repeat_count:
            tokens_list = list(self.state.recent_tokens)
            
            if len(set(tokens_list[-self.config.min_repeat_count:])) == 1:
                consecutive_count = 1
                for i in range(len(tokens_list) - 2, -1, -1):
                    if tokens_list[i] == tokens_list[-1]:
                        consecutive_count += 1
                    else:
                        break
                
                self.state.repeat_count = consecutive_count
                repeated_token = tokens_list[-1]
                self.state.detected_pattern = f"token:{repeated_token}"
                
                self._update_penalty()
                
                if self.state.repeat_count >= self.config.max_repeat_count:
                    should_stop = True
                    reason = f"检测到连续重复 token '{repeated_token}' {self.state.repeat_count} 次"
                    self.state.should_truncate = True
                    
                    logger.warning(
                        f"重复检测触发截断: token='{repeated_token}', "
                        f"count={self.state.repeat_count}, "
                        f"suggested_penalty={self.state.suggested_penalty:.2f}"
                    )
        
        return should_stop, reason
    
    def process_chunk(self, chunk: str) -> Tuple[bool, Optional[str], str]:
        """
        处理文本块，检测短语级重复
        
        Args:
            chunk: 文本块
            
        Returns:
            (should_stop, reason, filtered_chunk): 是否停止，原因，过滤后的文本
        """
        if not self.config.enabled or not chunk:
            return False, None, chunk
        
        words = chunk.split()
        should_stop = False
        reason = None
        filtered_chunk = chunk
        
        if len(words) >= 2:
            phrase = ' '.join(words[-3:]) if len(words) >= 3 else ' '.join(words)
            self.state.recent_phrases.append(phrase)
            
            if len(self.state.recent_phrases) >= self.config.phrase_threshold:
                phrases_list = list(self.state.recent_phrases)
                
                recent_phrases = phrases_list[-self.config.phrase_threshold:]
                if len(set(recent_phrases)) == 1:
                    should_stop = True
                    reason = f"检测到重复短语模式: '{phrase}'"
                    self.state.should_truncate = True
                    self.state.detected_pattern = f"phrase:{phrase}"
                    
                    logger.warning(
                        f"短语重复检测触发: phrase='{phrase}', "
                        f"suggested_penalty={self.state.suggested_penalty:.2f}"
                    )
        
        return should_stop, reason, filtered_chunk
    
    def _update_penalty(self):
        """更新建议的惩罚值"""
        increment = (self.state.repeat_count - self.config.min_repeat_count + 1) * self.config.penalty_increment
        self.state.suggested_penalty = min(
            self.config.base_penalty + increment,
            self.config.max_penalty
        )
        self.state.current_penalty = self.state.suggested_penalty
    
    def get_suggested_params(self) -> dict:
        """
        获取建议的参数调整
        
        Returns:
            建议的参数字典
        """
        return {
            "repeat_penalty": self.state.suggested_penalty,
            "repeat_last_n": 128,
            "temperature": 0.7,
            "top_k": 40,
            "top_p": 0.9,
        }
    
    def get_truncation_info(self) -> dict:
        """
        获取截断信息
        
        Returns:
            截断信息字典
        """
        return {
            "truncated": self.state.should_truncate,
            "pattern": self.state.detected_pattern,
            "repeat_count": self.state.repeat_count,
            "suggested_params": self.get_suggested_params(),
        }


def detect_repetition_in_text(text: str, window: int = 20) -> dict:
    """
    检测文本中的重复模式（静态方法）
    
    Args:
        text: 待检测文本
        window: 检测窗口大小
        
    Returns:
        检测结果字典
    """
    if not text or len(text) < 10:
        return {"has_repetition": False}
    
    words = text.split()
    if len(words) < window:
        return {"has_repetition": False}
    
    recent = deque(maxlen=window)
    repeat_patterns = []
    
    for i, word in enumerate(words):
        recent.append(word)
        
        if len(recent) == window:
            recent_list = list(recent)
            half = window // 2
            
            if recent_list[:half] == recent_list[half:2*half]:
                pattern = ' '.join(recent_list[:half])
                repeat_patterns.append({
                    "position": i - half + 1,
                    "pattern": pattern,
                    "type": "phrase"
                })
    
    return {
        "has_repetition": len(repeat_patterns) > 0,
        "patterns": repeat_patterns,
        "suggestion": "建议提高 repeat_penalty 至 1.15-1.2" if repeat_patterns else None
    }


def create_detector(config_dict: dict = None) -> RepetitionDetector:
    """
    工厂函数：创建重复检测器
    
    Args:
        config_dict: 配置字典
        
    Returns:
        RepetitionDetector 实例
    """
    if config_dict:
        config = RepetitionConfig(
            enabled=config_dict.get("enabled", True),
            window_size=config_dict.get("window_size", 10),
            min_repeat_count=config_dict.get("min_repeat_count", 3),
            max_repeat_count=config_dict.get("max_repeat_count", 5),
            base_penalty=config_dict.get("base_penalty", 1.08),
            max_penalty=config_dict.get("max_penalty", 1.5),
        )
    else:
        config = RepetitionConfig()
    
    return RepetitionDetector(config)
