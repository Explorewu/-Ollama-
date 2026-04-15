"""
上下文窗口管理器模块

提供智能上下文管理功能，支持：
- 层级化上下文管理（系统提示 > 摘要 > 核心对话 > 普通对话）
- 基于重要性评分的消息筛选
- 滑动窗口机制管理普通对话
- 上下文压缩和优化
- 自动 Token 估算和限制
"""

import time
import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from typing import List as TypingList
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContextLevel(Enum):
    """上下文层级"""
    SYSTEM = "system"      # 系统提示（永久保留）
    SUMMARY = "summary"    # 对话摘要（定期更新）
    CORE = "core"          # 核心对话（关键转折）
    REGULAR = "regular"    # 普通对话（滑动窗口）


@dataclass
class ContextMessage:
    """上下文消息"""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    level: str = ContextLevel.REGULAR.value
    importance: float = 0.5
    token_count: int = 0
    is_compressed: bool = False
    original_content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "level": self.level,
            "importance": self.importance,
            "token_count": self.token_count,
            "is_compressed": self.is_compressed,
            "original_content": self.original_content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextMessage':
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            level=data.get("level", ContextLevel.REGULAR.value),
            importance=data.get("importance", 0.5),
            token_count=data.get("token_count", 0),
            is_compressed=data.get("is_compressed", False),
            original_content=data.get("original_content")
        )


@dataclass
class ContextConfig:
    """上下文配置"""
    max_total_tokens: int = 8000
    system_prompt_tokens: int = 500
    summary_tokens: int = 800
    core_messages_max: int = 5
    regular_window_size: int = 10
    min_importance_threshold: float = 0.3
    compression_ratio: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_total_tokens": self.max_total_tokens,
            "system_prompt_tokens": self.system_prompt_tokens,
            "summary_tokens": self.summary_tokens,
            "core_messages_max": self.core_messages_max,
            "regular_window_size": self.regular_window_size,
            "min_importance_threshold": self.min_importance_threshold,
            "compression_ratio": self.compression_ratio
        }


class TokenEstimator:
    """
    Token 估算器
    
    估算文本的 Token 数量（中文约 1.5 字符 ≈ 1 Token）
    """
    
    CHINESE_CHARS_PER_TOKEN = 1.5
    ENGLISH_WORDS_PER_TOKEN = 0.75
    
    @staticmethod
    def estimate(text: str) -> int:
        """
        估算文本的 Token 数量
        
        Args:
            text: 输入文本
            
        Returns:
            估算的 Token 数量
        """
        if not text:
            return 0
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        other_chars = len(text) - chinese_chars - english_chars
        
        token_count = (
            chinese_chars / TokenEstimator.CHINESE_CHARS_PER_TOKEN +
            english_words / TokenEstimator.ENGLISH_WORDS_PER_TOKEN +
            other_chars / 2
        )
        
        return max(1, int(token_count))
    
    @staticmethod
    def estimate_messages(messages: List[ContextMessage]) -> int:
        """估算消息列表的总 Token 数量"""
        total = 0
        for msg in messages:
            if msg.role == "user":
                total += 4
            elif msg.role == "assistant":
                total += 4
            else:
                total += 3
            total += msg.token_count
        return total


class ImportanceScorer:
    """
    重要性评分器
    
    基于多种规则评估消息的重要性
    """
    
    KEYWORDS_HIGH = [
        "重要", "关键", "核心", "必须", "应该", "记住", "千万",
        "maintain", "remember", "important", "critical", "key",
        "结论", "决定", "确定", "方案", "计划"
    ]
    
    KEYWORDS_MEDIUM = [
        "建议", "可以", "试试", "可能", "也许", "一般",
        "建议", "推荐", "最好", "通常", "一般"
    ]
    
    PATTERNS_TURNING = [
        r"但是", r"然而", r"不过", r"然而", r"因此", r"所以",
        r"总之", r"最终", r"结果", r"确定", r"决定"
    ]
    
    PATTERNS_QUESTION = [
        r"为什么", r"怎么", r"如何", r"什么", r"哪个",
        r"why", r"how", r"what", r"which"
    ]
    
    @staticmethod
    def score(message: Dict[str, Any], 
              position: int, 
              total_messages: int) -> float:
        """
        计算消息的重要性分数
        
        Args:
            message: 消息内容
            position: 消息位置（0为最老）
            total_messages: 总消息数
            
        Returns:
            重要性分数 [0, 1]
        """
        content = message.get("content", "")
        role = message.get("role", "user")
        
        score = 0.5
        
        content_lower = content.lower()
        
        for keyword in ImportanceScorer.KEYWORDS_HIGH:
            if keyword in content or keyword in content_lower:
                score += 0.15
                break
        
        for keyword in ImportanceScorer.KEYWORDS_MEDIUM:
            if keyword in content or keyword in content_lower:
                score += 0.05
                break
        
        for pattern in ImportanceScorer.PATTERNS_TURNING:
            if re.search(pattern, content):
                score += 0.1
                break
        
        for pattern in ImportanceScorer.PATTERNS_QUESTION:
            if re.search(pattern, content):
                score -= 0.05
        
        if role == "assistant":
            score += 0.05
        
        if position == 0:
            score += 0.1
        elif position >= total_messages - 3:
            score += 0.1
        
        if len(content) > 1000:
            score += 0.1
        elif len(content) > 500:
            score += 0.05
        
        return min(1.0, max(0.0, score))
    
    @staticmethod
    def is_turning_point(prev_message: Dict[str, Any],
                         current_message: Dict[str, Any]) -> bool:
        """判断是否为转折点消息"""
        current_content = current_message.get("content", "")
        
        for pattern in ImportanceScorer.PATTERNS_TURNING:
            if re.search(pattern, current_content):
                return True
        
        if current_message.get("role") == "assistant":
            prev_content = prev_message.get("content", "")
            if len(current_content) > len(prev_content) * 1.5:
                return True
        
        return False


class ContextManager:
    """
    上下文窗口管理器主类
    
    负责管理对话上下文，提供：
    - 层级化消息管理
    - Token 限制和优化
    - 重要性筛选
    - 滑动窗口机制
    """
    
    def __init__(self, config: ContextConfig = None):
        self.config = config or ContextConfig()
        self.token_estimator = TokenEstimator()
        self.importance_scorer = ImportanceScorer()
        
        self._system_prompt: Optional[str] = None
        self._contexts: Dict[str, List[ContextMessage]] = {
            ContextLevel.SYSTEM.value: [],
            ContextLevel.SUMMARY.value: [],
            ContextLevel.CORE.value: [],
            ContextLevel.REGULAR.value: []
        }
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        设置系统提示词
        
        Args:
            prompt: 系统提示词内容
        """
        self._system_prompt = prompt
        
        if prompt:
            token_count = self.token_estimator.estimate(prompt)
            system_message = ContextMessage(
                role="system",
                content=prompt,
                level=ContextLevel.SYSTEM.value,
                importance=1.0,
                token_count=token_count
            )
            self._contexts[ContextLevel.SYSTEM.value] = [system_message]
        else:
            self._contexts[ContextLevel.SYSTEM.value] = []
    
    def add_message(self, role: str, content: str,
                    importance: float = None) -> ContextMessage:
        """
        添加消息到上下文
        
        Args:
            role: 消息角色
            content: 消息内容
            importance: 重要性分数（可选，自动计算）
            
        Returns:
            创建的上下文消息
        """
        token_count = self.token_estimator.estimate(content)
        
        regular_messages = self._contexts[ContextLevel.REGULAR.value]
        
        if importance is None:
            messages_data = [msg.to_dict() for msg in regular_messages]
            messages_data.append({"role": role, "content": content})
            importance = self.importance_scorer.score(
                {"role": role, "content": content},
                len(regular_messages),
                len(regular_messages) + 1
            )
        
        message = ContextMessage(
            role=role,
            content=content,
            level=ContextLevel.REGULAR.value,
            importance=importance,
            token_count=token_count
        )
        
        self._contexts[ContextLevel.REGULAR.value].append(message)
        
        self._check_and_optimize()
        
        return message
    
    def add_summary(self, summary_content: str, 
                    topics: List[str] = None) -> None:
        """
        添加对话摘要到上下文
        
        Args:
            summary_content: 摘要内容
            topics: 主题标签
        """
        token_count = self.token_estimator.estimate(summary_content)
        
        summary_message = ContextMessage(
            role="system",
            content=f"[对话摘要] {summary_content}",
            level=ContextLevel.SUMMARY.value,
            importance=0.9,
            token_count=token_count
        )
        
        self._contexts[ContextLevel.SUMMARY.value] = [summary_message]
    
    def add_core_message(self, role: str, content: str,
                         importance: float = 0.8) -> ContextMessage:
        """
        添加核心消息到上下文
        
        Args:
            role: 消息角色
            content: 消息内容
            importance: 重要性分数
            
        Returns:
            创建的核心消息
        """
        token_count = self.token_estimator.estimate(content)
        
        message = ContextMessage(
            role=role,
            content=content,
            level=ContextLevel.CORE.value,
            importance=importance,
            token_count=token_count
        )
        
        core_messages = self._contexts[ContextLevel.CORE.value]
        core_messages.append(message)
        
        while len(core_messages) > self.config.core_messages_max:
            core_messages.pop(0)
        
        return message
    
    def get_optimized_context(self) -> List[Dict[str, str]]:
        """
        获取优化后的上下文消息列表
        
        Returns:
            适合发送给 LLM 的消息列表
        """
        available_tokens = (
            self.config.max_total_tokens - 
            self.config.system_prompt_tokens - 
            self.config.summary_tokens
        )
        
        messages = []
        
        for level in [ContextLevel.SUMMARY, ContextLevel.CORE, ContextLevel.REGULAR]:
            level_messages = self._contexts[level.value]
            for msg in level_messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        total_tokens = self.token_estimator.estimate_messages([
            ContextMessage(**m) if isinstance(m, dict) else m 
            for m in messages
        ])
        
        if total_tokens > available_tokens:
            messages = self._prune_messages(messages, available_tokens)
        
        return messages
    
    def get_all_contexts(self) -> Dict[str, List[ContextMessage]]:
        """获取所有层级上下文"""
        return self._contexts
    
    def get_context_statistics(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        stats = {}
        
        for level in ContextLevel:
            messages = self._contexts[level.value]
            token_count = sum(m.token_count for m in messages)
            stats[level.value] = {
                "count": len(messages),
                "tokens": token_count,
                "avg_importance": (
                    sum(m.importance for m in messages) / len(messages)
                    if messages else 0
                )
            }
        
        total_tokens = TokenEstimator.estimate_messages(
            [msg for msgs in self._contexts.values() for msg in msgs]
        )
        stats["total_tokens"] = total_tokens
        stats["max_tokens"] = self.config.max_total_tokens
        stats["usage_ratio"] = total_tokens / self.config.max_total_tokens
        
        return stats
    
    def clear_context(self, levels: List[ContextLevel] = None) -> None:
        """
        清空上下文
        
        Args:
            levels: 要清空的层级列表，None 表示清空所有非系统层级
        """
        if levels is None:
            self._contexts[ContextLevel.SUMMARY.value] = []
            self._contexts[ContextLevel.CORE.value] = []
            self._contexts[ContextLevel.REGULAR.value] = []
        else:
            for level in levels:
                self._contexts[level.value] = []
    
    def reset(self) -> None:
        """完全重置上下文管理器"""
        self._system_prompt = None
        for level in ContextLevel:
            self._contexts[level.value] = []
    
    def _check_and_optimize(self) -> None:
        """检查并优化上下文"""
        regular_messages = self._contexts[ContextLevel.REGULAR.value]
        
        if len(regular_messages) > self.config.regular_window_size * 3:
            self._apply_sliding_window()
    
    def _apply_sliding_window(self) -> None:
        """应用滑动窗口策略"""
        regular_messages = self._contexts[ContextLevel.REGULAR.value]
        
        if len(regular_messages) <= self.config.regular_window_size:
            return
        
        messages_to_keep = self.config.regular_window_size
        
        if regular_messages:
            last_user_msg = None
            last_assistant_msg = None
            for msg in reversed(regular_messages):
                if msg.role == "user" and not last_user_msg:
                    last_user_msg = msg
                elif msg.role == "assistant" and not last_assistant_msg:
                    last_assistant_msg = msg
                if last_user_msg and last_assistant_msg:
                    break
            
            if last_user_msg and last_assistant_msg:
                keep_indices = []
                for i, msg in enumerate(regular_messages):
                    if msg.importance >= self.config.min_importance_threshold:
                        keep_indices.append(i)
                
                if len(keep_indices) > messages_to_keep:
                    low_importance = [
                        (i, m) for i, m in enumerate(regular_messages)
                        if m.importance < self.config.min_importance_threshold
                    ]
                    
                    if low_importance:
                        indices_to_remove = [i for i, _ in low_importance[:5]]
                        regular_messages[:] = [
                            m for i, m in enumerate(regular_messages)
                            if i not in indices_to_remove
                        ]
        
        if len(regular_messages) > messages_to_keep:
            self._contexts[ContextLevel.REGULAR.value] = regular_messages[-messages_to_keep:]
    
    def _prune_messages(self, messages: List[Dict[str, str]],
                        max_tokens: int) -> List[Dict[str, str]]:
        """
        修剪消息以适应 Token 限制
        
        Args:
            messages: 消息列表
            max_tokens: 最大 Token 数量
            
        Returns:
            修剪后的消息列表
        """
        if not messages:
            return messages
        
        current_tokens = TokenEstimator.estimate_messages([
            ContextMessage(**m) if isinstance(m, dict) else m 
            for m in messages
        ])
        
        if current_tokens <= max_tokens:
            return messages
        
        removable_indices = []
        for i, msg in enumerate(messages):
            if msg["role"] not in ["system"]:
                removable_indices.append(i)
        
        removable_indices.sort(
            key=lambda i: self.importance_scorer.score(
                messages[i], i, len(messages)
            )
        )
        
        for idx in removable_indices:
            if current_tokens <= max_tokens:
                break
            removed_msg = messages.pop(idx)
            current_tokens -= self.token_estimator.estimate(removed_msg["content"])
            
            for j in range(len(removable_indices)):
                if removable_indices[j] > idx:
                    removable_indices[j] -= 1
        
        return messages
    
    def _compress_message(self, message: ContextMessage) -> ContextMessage:
        """
        压缩消息内容
        
        Args:
            message: 原始消息
            
        Returns:
            压缩后的消息
        """
        if message.is_compressed:
            return message
        
        content = message.content
        original = content
        
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) > 5:
            sentences = sentences[:5]
            content = "。".join(sentences) + "。"
        
        if len(content) > 500:
            content = content[:500] + "..."
        
        message.content = content
        message.original_content = original
        message.is_compressed = True
        message.token_count = self.token_estimator.estimate(content)
        
        return message


class ContextOptimizer:
    """
    上下文优化器
    
    提供高级上下文优化策略
    """
    
    def __init__(self, manager: ContextManager = None):
        self.manager = manager or ContextManager()
    
    def compress_old_messages(self, hours: int = 24) -> int:
        """
        压缩旧消息
        
        Args:
            hours: 超过多少小时的消息需要压缩
            
        Returns:
            压缩的消息数量
        """
        threshold = time.time() - hours * 3600
        compressed_count = 0
        
        regular_messages = self.manager._contexts[ContextLevel.REGULAR.value]
        
        for msg in regular_messages:
            if msg.timestamp < threshold and not msg.is_compressed:
                self.manager._compress_message(msg)
                compressed_count += 1
        
        return compressed_count
    
    def merge_similar_messages(self) -> int:
        """
        合并相似消息
        
        Returns:
            合并的消息数量
        """
        regular_messages = self.manager._contexts[ContextLevel.REGULAR.value]
        merged_count = 0
        
        if len(regular_messages) < 4:
            return 0
        
        merged = []
        i = 0
        while i < len(regular_messages):
            if i + 1 < len(regular_messages):
                curr = regular_messages[i]
                next_msg = regular_messages[i + 1]
                
                if (curr.role == next_msg.role and 
                    curr.importance < self.manager.config.min_importance_threshold):
                    merged_content = f"{curr.content}\n\n{next_msg.content}"
                    curr.content = merged_content
                    curr.token_count = self.manager.token_estimator.estimate(merged_content)
                    regular_messages.pop(i + 1)
                    merged_count += 1
                    continue
            
            merged.append(regular_messages[i])
            i += 1
        
        self.manager._contexts[ContextLevel.REGULAR.value] = merged
        return merged_count
    
    def extract_key_information(self, conversation: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从对话中提取关键信息
        
        Args:
            conversation: 对话历史
            
        Returns:
            关键信息字典
        """
        key_info = {
            "topics": [],
            "decisions": [],
            "tasks": [],
            "preferences": []
        }
        
        for msg in conversation:
            content = msg.get("content", "")
            
            topic_match = re.search(r'主题[：:]\s*(.+?)(?:\n|$)', content)
            if topic_match:
                key_info["topics"].append(topic_match.group(1).strip())
            
            decision_keywords = ["决定", "确定", "方案", "选择"]
            for keyword in decision_keywords:
                if keyword in content:
                    key_info["decisions"].append({
                        "keyword": keyword,
                        "context": content[:100]
                    })
                    break
            
            task_keywords = ["待办", "需要", "应该", "要做"]
            for keyword in task_keywords:
                if keyword in content:
                    key_info["tasks"].append({
                        "keyword": keyword,
                        "context": content[:100]
                    })
                    break
        
        return key_info


# 单例实例
_context_manager_instance: Optional[ContextManager] = None


def get_context_manager(config: ContextConfig = None) -> ContextManager:
    """
    获取上下文管理器单例
    
    Args:
        config: 上下文配置
        
    Returns:
        ContextManager 实例
    """
    global _context_manager_instance
    
    if _context_manager_instance is None:
        _context_manager_instance = ContextManager(config)
    
    return _context_manager_instance


if __name__ == "__main__":
    print("=" * 60)
    print("上下文窗口管理器测试")
    print("=" * 60)
    
    manager = get_context_manager()
    
    print("\n1. 设置系统提示词...")
    manager.set_system_prompt("你是一个智能助手，请用简洁的语言回答问题。")
    
    print("\n2. 添加测试消息...")
    test_messages = [
        ("user", "我想开发一个AI聊天机器人"),
        ("assistant", "好的，这是一个很有趣的项目。你想用什么技术栈？"),
        ("user", "使用Python和Ollama"),
        ("assistant", "不错的选择！Python有丰富的AI库支持。"),
        ("user", "我们需要支持长期记忆功能"),
        ("assistant", "长期记忆是个重要的功能，可以让AI记住用户的偏好。"),
        ("user", "对，还要支持对话摘要"),
        ("assistant", "好的，对话摘要可以帮助总结长对话的内容。"),
        ("user", "语音输入也需要支持"),
        ("assistant", "语音输入可以使用Whisper模型来实现。"),
        ("user", "那我们开始实现吧"),
        ("assistant", "好的，我们按照优先级来实现这些功能。"),
    ]
    
    for role, content in test_messages:
        manager.add_message(role, content)
    
    print("\n3. 添加核心消息...")
    manager.add_core_message(
        "assistant", 
        "[核心决策] 确定使用层级化上下文管理策略：系统提示 > 摘要 > 核心对话 > 普通对话",
        importance=0.95
    )
    
    print("\n4. 添加摘要...")
    manager.add_summary(
        "用户想要开发一个AI聊天机器人，包含长期记忆、对话摘要和语音输入功能。技术栈选择Python + Ollama。",
        topics=["AI开发", "聊天机器人", "长期记忆"]
    )
    
    print("\n5. 获取统计信息...")
    stats = manager.get_context_statistics()
    for level, info in stats.items():
        if isinstance(info, dict):
            print(f"  {level}: {info['count']}条消息, {info['tokens']}tokens")
    
    print("\n6. 获取优化后的上下文...")
    context = manager.get_optimized_context()
    print(f"  消息数量: {len(context)}")
    
    print("\n7. Token 使用情况...")
    usage = stats.get("usage_ratio", 0)
    print(f"  Token 使用率: {usage:.1%}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
