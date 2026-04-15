"""
对话上下文记忆管理模块

功能：
- 对话历史记忆（最近10轮）
- 上下文语义关联
- 话题状态跟踪
- 智能上下文注入
"""

import time
import json
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ConversationTurn:
    """对话轮次数据类"""
    user_input: str
    assistant_response: str
    timestamp: float
    intent: str = ""
    entities: List[str] = None
    emotion: str = "neutral"
    confidence: float = 1.0
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "user": self.user_input,
            "assistant": self.assistant_response,
            "timestamp": self.timestamp,
            "intent": self.intent,
            "entities": self.entities or [],
            "emotion": self.emotion,
            "confidence": self.confidence
        }


class ConversationMemory:
    """对话历史记忆管理"""
    
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.history: List[ConversationTurn] = []
        self.current_topic: str = ""
        self.topic_history: List[str] = []
        
    def add_turn(self, user_input: str, assistant_response: str, 
                 intent: str = "", entities: List[str] = None, 
                 emotion: str = "neutral", confidence: float = 1.0) -> None:
        """添加一轮对话"""
        
        turn = ConversationTurn(
            user_input=user_input,
            assistant_response=assistant_response,
            timestamp=time.time(),
            intent=intent,
            entities=entities or [],
            emotion=emotion,
            confidence=confidence
        )
        
        self.history.append(turn)
        
        # 保持历史在限制范围内
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]
        
        # 更新当前话题
        self._update_current_topic()
        
        print(f"✅ 对话记忆已更新，当前轮次: {len(self.history)}")
    
    def get_recent_turns(self, count: int = 5) -> List[ConversationTurn]:
        """获取最近的对话轮次"""
        return self.history[-count:]
    
    def get_context_for_llm(self, include_system_prompt: bool = True) -> str:
        """构建发送给 LLM 的上下文"""
        
        context_parts = []
        
        if include_system_prompt:
            # 系统提示
            system_prompt = """你是一个友好、亲切的数字人助手。
请记住以下对话历史，保持对话的连贯性和上下文关联。
当前对话历史："""
            context_parts.append(system_prompt)
        
        # 添加最近的对话历史（最多5轮）
        recent_turns = self.get_recent_turns(5)
        
        for i, turn in enumerate(recent_turns, 1):
            context_parts.append(f"[对话{i}]")
            context_parts.append(f"用户: {turn.user_input}")
            context_parts.append(f"你: {turn.assistant_response}")
        
        # 添加当前话题信息
        if self.current_topic:
            context_parts.append(f"\n当前话题: {self.current_topic}")
        
        return '\n'.join(context_parts)
    
    def get_summary_context(self) -> str:
        """获取摘要形式的上下文（用于长对话）"""
        
        if len(self.history) <= 3:
            return self.get_context_for_llm(include_system_prompt=False)
        
        # 提取关键信息进行摘要
        summary_parts = []
        
        # 添加最近3轮详细对话
        recent_turns = self.get_recent_turns(3)
        for i, turn in enumerate(recent_turns, 1):
            summary_parts.append(f"用户{i}: {turn.user_input}")
            summary_parts.append(f"助手{i}: {turn.assistant_response}")
        
        # 添加话题总结
        if self.current_topic:
            summary_parts.append(f"当前讨论: {self.current_topic}")
        
        return '\n'.join(summary_parts)
    
    def _update_current_topic(self) -> None:
        """检测和更新当前话题"""
        
        if not self.history:
            self.current_topic = ""
            return
        
        # 提取最近3轮的关键词
        recent_text = ' '.join([
            turn.user_input + ' ' + turn.assistant_response
            for turn in self.history[-3:]
        ])
        
        # 简单关键词提取（实际可使用 NLP 库）
        keywords = self._extract_keywords(recent_text)
        
        if keywords:
            self.current_topic = ' > '.join(keywords[:2])
            
            # 记录话题历史（避免重复）
            if not self.topic_history or self.topic_history[-1] != self.current_topic:
                self.topic_history.append(self.current_topic)
        else:
            self.current_topic = ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """简单关键词提取"""
        
        # 停用词列表
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这个', '那', '现在', '什么', '还', '我们', '这样', '因为', '所以', '但是', '然后', '可以', '知道', '应该', '如果', '可能', '已经', '还是', '怎么', '为什么', '怎么', '如何', '能不能', '可不可以', '请', '谢谢', '你好', '再见'}
        
        # 简单分词和频率统计
        words = text.split()
        word_freq = {}
        
        for word in words:
            # 过滤停用词和短词
            if (len(word) > 1 and 
                word not in stop_words and 
                not word.isdigit()):
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, freq in sorted_words[:5]]  # 返回前5个关键词
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.history.clear()
        self.current_topic = ""
        self.topic_history.clear()
        print("🗑️ 对话历史已清空")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "total_turns": len(self.history),
            "current_topic": self.current_topic,
            "topic_history": self.topic_history,
            "memory_usage": f"{len(self.history)}/{self.max_turns}"
        }
    
    def export_history(self) -> str:
        """导出对话历史为 JSON"""
        history_data = {
            "turns": [turn.to_dict() for turn in self.history],
            "current_topic": self.current_topic,
            "export_time": time.time()
        }
        return json.dumps(history_data, ensure_ascii=False, indent=2)
    
    def import_history(self, json_data: str) -> bool:
        """从 JSON 导入对话历史"""
        try:
            data = json.loads(json_data)
            
            self.history.clear()
            for turn_data in data.get("turns", []):
                turn = ConversationTurn(
                    user_input=turn_data["user"],
                    assistant_response=turn_data["assistant"],
                    timestamp=turn_data["timestamp"],
                    intent=turn_data.get("intent", ""),
                    entities=turn_data.get("entities", []),
                    emotion=turn_data.get("emotion", "neutral"),
                    confidence=turn_data.get("confidence", 1.0)
                )
                self.history.append(turn)
            
            self.current_topic = data.get("current_topic", "")
            
            print(f"✅ 对话历史已导入，共 {len(self.history)} 轮对话")
            return True
            
        except Exception as e:
            print(f"❌ 导入对话历史失败: {e}")
            return False


# 全局对话记忆实例
conversation_memory = ConversationMemory()


# 使用示例
if __name__ == "__main__":
    # 测试对话记忆功能
    memory = ConversationMemory(max_turns=5)
    
    # 添加几轮对话
    memory.add_turn("你好！", "嗨！很高兴见到你！我是你的数字人助手。")
    memory.add_turn("今天天气怎么样？", "今天天气晴朗，气温适宜。")
    memory.add_turn("那北京呢？", "北京今天也是好天气，适合外出。")
    
    # 查看上下文
    print("=== 完整上下文 ===")
    print(memory.get_context_for_llm())
    
    print("\n=== 统计信息 ===")
    print(memory.get_statistics())
    
    print("\n=== 导出历史 ===")
    print(memory.export_history())