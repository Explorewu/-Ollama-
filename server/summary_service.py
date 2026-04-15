"""
对话摘要服务模块

提供智能对话摘要功能，支持：
- 手动触发摘要（summarize 命令）
- 自动摘要（超过指定轮次后自动生成）
- 摘要分层管理（简要摘要 + 详细摘要）
- 摘要历史记录
- 基于 Ollama 的智能摘要生成
"""

import json
import os
import time
import hashlib
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from typing import List as TypingList
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SummaryLevel(Enum):
    """摘要级别"""

    CONCISE = "concise"      # 简要摘要（核心要点）
    DETAILED = "detailed"    # 详细摘要（完整内容）
    KEY_POINTS = "key_points" # 关键要点列表


@dataclass
class Message:
    """消息结构"""

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time())
        )


@dataclass
class Summary:
    """摘要结构"""

    id: str
    conversation_id: str
    level: str
    content: str
    message_count: int
    created_at: float
    topics: List[str]
    key_points: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Summary':
        return cls(**data)


@dataclass
class Conversation:
    """对话结构"""

    id: str
    title: str
    messages: List[Message]
    summaries: List[Summary]
    created_at: float
    updated_at: float
    message_count: int
    is_archived: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "summaries": [s.to_dict() for s in self.summaries],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "is_archived": self.is_archived
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        return cls(
            id=data["id"],
            title=data["title"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            summaries=[Summary.from_dict(s) for s in data.get("summaries", [])],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            message_count=data["message_count"],
            is_archived=data.get("is_archived", False)
        )


class ConversationStore:
    """

    对话存储管理器
    
    负责对话数据的持久化和基础CRUD操作
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_path = os.path.join(base_dir, 'data', 'conversations.json')
        
        self.storage_path = storage_path
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        
        if not os.path.exists(self.storage_path):
            self._save_all({})
    
    def _save_all(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存对话数据失败: {e}")
            raise
    
    def _load_all(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载对话数据失败: {e}")
            return {}
    
    def create_conversation(self, title: str = "新对话") -> Conversation:
        """创建新对话"""

        timestamp = time.time()
        conversation_id = hashlib.md5(f"{title}{timestamp}".encode()).hexdigest()[:12]
        
        conversation = Conversation(
            id=conversation_id,
            title=title,
            messages=[],
            summaries=[],
            created_at=timestamp,
            updated_at=timestamp,
            message_count=0,
            is_archived=False
        )
        
        data = self._load_all()
        data[conversation_id] = conversation.to_dict()
        self._save_all(data)
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话"""

        data = self._load_all()
        if conversation_id in data:
            return Conversation.from_dict(data[conversation_id])
        return None
    
    def add_message(self, conversation_id: str, role: str, content: str) -> Optional[Conversation]:
        """添加消息"""

        data = self._load_all()
        
        if conversation_id not in data:
            return None
        
        conversation = Conversation.from_dict(data[conversation_id])
        conversation.messages.append(Message(role=role, content=content))
        conversation.message_count += 1
        conversation.updated_at = time.time()
        
        data[conversation_id] = conversation.to_dict()
        self._save_all(data)
        
        return conversation
    
    def add_summary(self, conversation_id: str, summary: Summary) -> bool:
        """添加摘要"""

        data = self._load_all()
        
        if conversation_id not in data:
            return False
        
        conversation = Conversation.from_dict(data[conversation_id])
        conversation.summaries.append(summary)
        
        data[conversation_id] = conversation.to_dict()
        self._save_all(data)
        
        return True

    def get_summary_by_id(self, summary_id: str) -> Optional[Tuple[Conversation, Summary]]:
        """根据摘要ID查找对话和内容"""

        data = self._load_all()
        for item in data.values():
            conv = Conversation.from_dict(item)
            for summary in conv.summaries:
                if summary.id == summary_id:
                    return conv, summary
        return None

    def delete_summary(self, summary_id: str) -> bool:
        """删除摘要"""

        data = self._load_all()
        updated = False
        for conv_id, item in data.items():
            conv = Conversation.from_dict(item)
            before = len(conv.summaries)
            conv.summaries = [s for s in conv.summaries if s.id != summary_id]
            if len(conv.summaries) != before:
                data[conv_id] = conv.to_dict()
                updated = True
                break
        if updated:
            self._save_all(data)
        return updated

    def list_conversations(self, include_archived: bool = False, 
                           limit: int = 50) -> List[Conversation]:
        """列出对话"""

        data = self._load_all()
        conversations = []
        
        for item in data.values():
            conv = Conversation.from_dict(item)
            if include_archived or not conv.is_archived:
                conversations.append(conv)
        
        conversations.sort(key=lambda x: x.updated_at, reverse=True)
        return conversations[:limit]
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""

        data = self._load_all()
        
        if conversation_id not in data:
            return False
        
        del data[conversation_id]
        self._save_all(data)
        return True
    
    def archive_conversation(self, conversation_id: str) -> bool:
        """归档对话"""

        data = self._load_all()
        
        if conversation_id not in data:
            return False
        
        conversation = Conversation.from_dict(data[conversation_id])
        conversation.is_archived = True
        conversation.updated_at = time.time()
        
        data[conversation_id] = conversation.to_dict()
        self._save_all(data)
        
        return True


class SummaryGenerator:
    """

    摘要生成鍣?
    
    负责调用 Ollama API 生成智能摘要
    """

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or "http://localhost:11434"
        self.model = model or "qwen2.5:7b"
    
    def generate_concise_summary(self, messages: List[Message]) -> Tuple[str, List[str], List[str]]:
        """

        生成简要摘要
        
        Args:
            messages: 消息列表
            
        Returns:
            (摘要内容, 主题列表, 关键要点列表)
        """

        if not messages:
            return "", [], []
        
        conversation_text = self._format_messages(messages)
        
        prompt = f"""璇峰浠笅瀵硅瘽生成涓娈电畝娲佺殑摘要锛堜笉瓒呰繃200瀛楋級锛屽苟鎻愬彇3-5涓富棰樻爣绛惧拰3-5涓叧閿鐐广?

'【对话内容】'
{conversation_text}

璇锋寜浠笅鏍煎紡杩斿洖锛?
'【摘要】'
锛堢畝娲佺殑瀵硅瘽摘要锛?

'【主题标签】'
锛堟瘡琛屼竴涓爣绛撅紝鐢腑鏂囬楀彿鍒嗛殧锛?

'【关键要点】'
锛堟瘡琛屼竴涓鐐癸紝鐢腑鏂囧彞鍙风粨鏉燂級

娉剰锛氬彧杩斿洖内容锛屼笉瑕佽繑鍥炲叾浠栬鏄庛?""
        
        response_text = self._call_llm(prompt)
        return self._parse_summary_response(response_text)
    
    def generate_detailed_summary(self, messages: List[Message]) -> Tuple[str, List[str], List[str]]:
        """
        """
        生成详细摘要
        
        Args:
            messages: 消息列表
            
        Returns:
            (摘要内容, 主题列表, 关键要点列表)
        """

        if not messages:
            return "", [], []
        
        conversation_text = self._format_messages(messages)
        
        prompt = f"""璇峰浠笅瀵硅瘽生成涓娈佃缁嗙殑摘要锛?00瀛楀乏鍙筹級锛屽苟鎻愬彇5-8涓富棰樻爣绛惧拰5-8涓叧閿鐐广?

'【对话内容】'
{conversation_text}

璇锋寜浠笅鏍煎紡杩斿洖锛?
'【摘要】'
锛堣缁嗙殑瀵硅瘽摘要锛屽寘鎷富瑕佽璁哄唴瀹广佺粨璁恒佸緟鍔炰簨椤圭瓑锛?

'【主题标签】'
锛堟瘡琛屼竴涓爣绛撅紝鐢腑鏂囬楀彿鍒嗛殧锛?

'【关键要点】'
（每行一个要点，用中文句号结束）

注意：只返回内容，不要返回其他说明。"""
        
        response_text = self._call_llm(prompt)
        return self._parse_summary_response(response_text)
    
    def generate_key_points_summary(self, messages: List[Message]) -> Tuple[str, List[str], List[str]]:
        """

        生成关键要点摘要
        
        Args:
            messages: 消息列表
            
        Returns:
            (摘要内容, 主题列表, 关键要点列表)
        """

        if not messages:
            return "", [], []
        
        conversation_text = self._format_messages(messages)
        
        prompt = f"""璇蜂粠浠笅瀵硅瘽涓彁鍙栧叧閿鐐癸紝浠畝娲佺殑鏉洰褰紡鍛堢幇銆?

'【对话内容】'
{conversation_text}

璇锋寜浠笅鏍煎紡杩斿洖锛?
'【核心要点】'
锛堢敤3-5鏉畝娲佺殑鏉洰鎬荤粨瀵硅瘽鐨勬牳蹇冨唴瀹癸紝姣忔潯涓嶈秴杩?0瀛楋級

'【详细要点】'
锛堢敤5-10鏉潯鐩荤粨瀵硅瘽鐨勮缁嗗唴瀹癸紝姣忔潯涓嶈秴杩?0瀛楋級

'【主题标签】'
锛堟瘡琛屼竴涓爣绛撅紝鐢腑鏂囬楀彿鍒嗛殧锛?

'【结论】'
（如果有明确的结论，用一句话总结）

注意：只返回内容，不要返回其他说明。"""
        
        response_text = self._call_llm(prompt)
        return self._parse_summary_response(response_text)
    
    def _format_messages(self, messages: List[Message]) -> str:
        """格式化消息列表为文本"""

        formatted = []
        for msg in messages:
            role_name = "用户" if msg.role == "user" else "助手"
            formatted.append(f"{role_name}: {msg.content}")
        return "\n\n".join(formatted)
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""

        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 1000,
                        "temperature": 0.3
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(f"LLM API 返回错误: {response.status_code}")
                return ""
                
        except ImportError:
            logger.error("requests 库未安装")
            return ""
        except Exception as e:
            logger.error(f"调用 LLM 失败: {e}")
            return ""
    
    def _parse_summary_response(self, response: str) -> Tuple[str, List[str], List[str]]:
        """瑙瀽摘要鍝嶅簲"""

        summary = ""
        topics = []
        key_points = []
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('【摘要】') or line.startswith('【核心要点】') or line.startswith('【详细要点】'):
                current_section = "summary"
                summary += line.replace('【摘要】', '').replace('【核心要点】', '').replace('【详细要点】', '').strip() + " "
                continue
            elif line.startswith('【主题标签】'):
                current_section = "topics"
            elif line.startswith('【关键要点】'):
                current_section = "key_points"
                continue
            elif line.startswith('【结论】'):
                current_section = "summary"
                continue
                continue
            
            if current_section == "summary":
                summary += line + " "
            elif current_section == "topics":
                topics.extend([t.strip() for t in line.split('，') if t.strip()])
            elif current_section == "key_points":
                key_points.append(line.strip())
        
        return summary.strip(), topics, key_points


class SummaryService:
    """

    瀵硅瘽摘要鏈嶅姟涓荤被
    
    鏁村悎瀵硅瘽瀛樺偍鍜屾憳瑕佺敓鎴愬姛鑳斤紝鎻愪緵锛?
    - 鎵嬪姩摘要生成锛園summarize 鍛戒护锛?
    - 鑷姩摘要生成锛堟秷鎭鏁拌鍙戯級
    - 摘要鍒嗗眰绠悊
    - 摘要鍘嗗彶璁板綍
    """

    def __init__(self, base_url: str = None, model: str = None,
                 auto_summary_threshold: int = 20):
        self.store = ConversationStore()
        self.generator = SummaryGenerator(base_url, model)
        self.auto_summary_threshold = auto_summary_threshold
    
    def create_conversation(self, title: str = "新对话") -> Conversation:
        """创建新对话"""
        return self.store.create_conversation(title)
    
    def add_message(self, conversation_id: str, role: str, content: str) -> Conversation:
        """添加消息并检查是否需要自动摘要"""
        conversation = self.store.add_message(conversation_id, role, content)
        
        if conversation and self._should_auto_summarize(conversation):
            self._auto_generate_summary(conversation)
        
        return conversation
    
    def manual_summarize(self, conversation_id: str, 
                         level: SummaryLevel = SummaryLevel.CONCISE) -> Optional[Summary]:
        """

        手动触发摘要生成
        
        Args:
            conversation_id: 瀵硅瘽ID
            level: 摘要绾埆
            
        Returns:
            生成鐨勬憳瑕侊紝澶辫触杩斿洖 None
        """

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"对话不存在 {conversation_id}")
            return None
        
        if len(conversation.messages) < 3:
            logger.warning("消息太少，不需要摘要")
            return None
        
        if level == SummaryLevel.CONCISE:
            summary_text, topics, key_points = self.generator.generate_concise_summary(
                conversation.messages
            )
        elif level == SummaryLevel.DETAILED:
            summary_text, topics, key_points = self.generator.generate_detailed_summary(
                conversation.messages
            )
        else:
            summary_text, topics, key_points = self.generator.generate_key_points_summary(
                conversation.messages
            )
        
        if not summary_text:
            logger.error("摘要生成澶辫触")
            return None
        
        summary = Summary(
            id=hashlib.md5(f"{conversation_id}{time.time()}".encode()).hexdigest()[:12],
            conversation_id=conversation_id,
            level=level.value,
            content=summary_text,
            message_count=conversation.message_count,
            created_at=time.time(),
            topics=topics,
            key_points=key_points
        )
        
        self.store.add_summary(conversation_id, summary)
        logger.info(f"生成摘要鎴愬姛: {summary.id}")
        
        return summary
    
    def get_summaries(self, conversation_id: str) -> List[Summary]:
        """获取对话的所有摘要"""

        conversation = self.store.get_conversation(conversation_id)
        if conversation:
            return conversation.summaries
        return []
    
    def get_latest_summary(self, conversation_id: str, 
                           level: SummaryLevel = None) -> Optional[Summary]:
        """获取最新摘要"""

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            return None
        
        summaries = conversation.summaries
        if not summaries:
            return None
        
        if level:
            for summary in reversed(summaries):
                if summary.level == level.value:
                    return summary
            return summaries[-1] if summaries else None
        
        return summaries[-1]
    
    def get_context_for_llm(self, conversation_id: str, 
                            max_messages: int = 10) -> List[Message]:
        """

        鑾峰彇娉叆LLM涓婁笅鏂囩殑消息
        
        绛栫暐锛氭憳瑕?+ 鏈杩戞秷鎭?
        """

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            return []
        
        messages = []
        
        latest_summary = self.get_latest_summary(conversation_id)
        if latest_summary:
            system_msg = Message(
                role="system",
                content=f"【对话摘要】{latest_summary.content}",
                timestamp=0
            )
            messages.append(system_msg)
        
        recent_messages = conversation.messages[-max_messages:]
        messages.extend(recent_messages)
        
        return messages
    
    def list_conversations(self, include_archived: bool = False) -> List[Conversation]:
        """列出对话"""

        return self.store.list_conversations(include_archived)
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""

        return self.store.delete_conversation(conversation_id)
    
    def archive_conversation(self, conversation_id: str) -> bool:
        """归档对话"""

        return self.store.archive_conversation(conversation_id)
    
    def _should_auto_summarize(self, conversation: Conversation) -> bool:
        """检查是否需要自动摘要"""
        if not conversation.summaries:
            return conversation.message_count >= self.auto_summary_threshold
        else:
            last_summary = conversation.summaries[-1]
            messages_since_summary = conversation.message_count - last_summary.message_count
            return messages_since_summary >= self.auto_summary_threshold
    
    def _auto_generate_summary(self, conversation: Conversation) -> Optional[Summary]:
        """自动生成摘要"""

        logger.info(f"鑷姩生成摘要锛屽璇? {conversation.id}")
        logger.info(f"自动生成摘要，对话: {conversation.id}")


# 单例实例
_summary_service_instance: Optional[SummaryService] = None

def get_summary_service(base_url: str = None, model: str = None,
                        auto_summary_threshold: int = 20) -> SummaryService:
    """
    获取摘要服务单例
    
    Args:
        base_url: Ollama API 地址
        model: 摘要生成模型
        auto_summary_threshold: 自动摘要消息阈值
        
    Returns:
        SummaryService 实例
    """
    
    global _summary_service_instance
    
    if _summary_service_instance is None:
        _summary_service_instance = SummaryService(base_url, model, auto_summary_threshold)
    
    return _summary_service_instance
    
    return _summary_service_instance


if __name__ == "__main__":
    service = get_summary_service()
    
    print("=" * 60)
    print("对话摘要服务测试")
    print("=" * 60)
    
    print("\n1. 创建测试对话...")
    conv = service.create_conversation("AI项目讨论")
    print(f"  对话ID: {conv.id}")
    
    print("\n2. 添加测试消息...")
    test_messages = [
        ("user", "我想开发一个AI聊天助手"),
        ("assistant", "好的，这是一个很有趣的话题，你想用什么技术呢？"),
        ("user", "使用Python后端，JavaScript前端，Ollama做推理"),
        ("assistant", "不错的选择，Ollama支持多种模型，如Llama、Qwen等。"),
        ("user", "那我们还需要加长期记忆功能吗？"),
        ("assistant", "当然，长期记忆可以让AI记住用户的偏好和历史对话。"),
        ("user", "好的，那先实现记忆功能，摘要后面再加"),
        ("assistant", "明白了，我们先做记忆模块。"),
    ]
    
    for role, content in test_messages:
        service.add_message(conv.id, role, content)
        print(f"  [{role}] {content[:30]}...")
    
    print("\n3. 手动触发摘要...")
    summary = service.manual_summarize(conv.id, SummaryLevel.CONCISE)
    if summary:
        print(f"  摘要ID: {summary.id}")
        print(f"  消息数: {summary.message_count}")
        print(f"  主题: {summary.topics}")
        print(f"  关键要点数量: {len(summary.key_points)}")
        print(f"  内容: {summary.content[:100]}...")
    
    print("\n4. 获取注入上下文的消息...")
    context_messages = service.get_context_for_llm(conv.id, max_messages=4)
    print(f"  消息数量: {len(context_messages)}")
    
    print("\n5. 列出所有对话...")
    conversations = service.list_conversations()
    print(f"  对话数量: {len(conversations)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
