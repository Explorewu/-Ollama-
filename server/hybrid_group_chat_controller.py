"""
混合智能群聊控制器 - 完整版

功能：
1. 多模型群聊讨论（真正的交互式讨论，非依次回复）
2. 全自动聊天（开始/暂停/停止/状态保存/断点续传）
3. 世界设定和角色设定接入
4. 情感分析可视化
5. 观点聚类显示
6. 角色性格自动匹配音色

作者：AI Assistant
日期：2026-02-03
版本：v1.0
"""

import os
import sys
import json
import time
import logging
import threading
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import copy

from utils.config import (
    DEFAULT_GROUP_CHAT_MODEL,
    DEFAULT_GROUP_CHAT_RUNTIME_CONFIG,
    build_ollama_options,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DiscussionState(Enum):
    """讨论状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ANALYZING = "analyzing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"


class TopicStatus(Enum):
    """话题状态"""
    FRESH = "fresh"           # 新话题刚开始
    ACTIVE = "active"         # 讨论活跃
    MATURING = "maturing"     # 讨论趋于成熟
    CONSENSUS = "consensus"   # 达成共识
    STALLED = "stalled"       # 话题停滞
    EXHAUSTED = "exhausted"   # 话题枯竭


class EmotionType(Enum):
    """情感类型"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    THOUGHTFUL = "thoughtful"
    CURIOUS = "curious"
    ENTHUSIASTIC = "enthusiastic"
    SKEPTICAL = "skeptical"
    ANALYTICAL = "analytical"


@dataclass
class CharacterConfig:
    """角色配置"""
    model_name: str
    name: str
    avatar: str = "🤖"
    personality: str = ""
    style: str = ""
    expertise: List[str] = field(default_factory=list)
    speaking_style: str = "balanced"  # concise/balanced/detailed
    emotional_range: List[str] = field(default_factory=lambda: ["neutral"])
    voice_profile: str = "default"


@dataclass
class WorldSetting:
    """世界设定"""
    title: str = ""
    description: str = ""
    background: str = ""
    rules: List[str] = field(default_factory=list)
    culture: str = ""
    technology_level: str = ""
    main_topics: List[str] = field(default_factory=list)
    discussion_templates: List[Dict] = field(default_factory=list)


@dataclass
class Message:
    """消息结构"""
    id: str
    role: str  # user/assistant
    model_name: str = ""
    character_name: str = ""
    content: str = ""
    timestamp: int = 0
    emotions: Dict[str, float] = field(default_factory=dict)
    viewpoint_tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # 引用的消息ID
    is_summary: bool = False


@dataclass
class DiscussionTurn:
    """讨论轮次"""
    turn_number: int
    topic: str
    participants: List[str]
    messages: List[Message] = field(default_factory=list)
    start_time: int = 0
    end_time: int = 0
    consensus_reached: bool = False
    emotion_summary: Dict[str, float] = field(default_factory=dict)


@dataclass
class ViewpointCluster:
    """观点聚类"""
    cluster_id: str
    viewpoint: str
    supporting_models: List[str]
    sentiment: str
    strength: float
    key_points: List[str]


class EmotionAnalyzer:
    """
    情感分析器
    基于关键词和句式分析文本情感
    """
    
    EMOTION_KEYWORDS = {
        EmotionType.HAPPY: ["开心", "高兴", "快乐", "满意", "太好了", "精彩", "赞同", "同意", "不错"],
        EmotionType.SAD: ["难过", "悲伤", "遗憾", "可惜", "失望", "沮丧", "忧郁"],
        EmotionType.ANGRY: ["生气", "愤怒", "不满", "反感", "讨厌", "过分", "离谱"],
        EmotionType.SURPRISED: ["惊讶", "意外", "震惊", "居然", "没想到", "竟然"],
        EmotionType.THOUGHTFUL: ["思考", "考虑", "分析", "研究", "探讨", "深入"],
        EmotionType.CURIOUS: ["好奇", "想知道", "问问", "能否", "能不能"],
        EmotionType.ENTHUSIASTIC: ["兴奋", "激动", "期待", "太好了", "太棒了", "精彩"],
        EmotionType.SKEPTICAL: ["质疑", "怀疑", "未必", "不见得", "不一定", "真的吗"],
        EmotionType.ANALYTICAL: ["首先", "其次", "然后", "因此", "综上所述", "结论"]
    }
    
    @classmethod
    def analyze(cls, text: str) -> Dict[str, float]:
        """分析文本情感"""
        emotions = {e.value: 0.0 for e in EmotionType}
        text_lower = text.lower()
        
        for emotion, keywords in cls.EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    emotions[emotion.value] += 0.3
        
        for emotion in emotions:
            emotions[emotion] = min(1.0, emotions[emotion])
        
        if max(emotions.values()) < 0.1:
            emotions[EmotionType.NEUTRAL.value] = 1.0
        
        return emotions
    
    @classmethod
    def get_dominant_emotion(cls, emotions: Dict[str, float]) -> str:
        """获取主导情感"""
        if not emotions:
            return EmotionType.NEUTRAL.value
        
        max_emotion = max(emotions, key=emotions.get)
        return max_emotion if emotions[max_emotion] > 0.3 else EmotionType.NEUTRAL.value


class ViewpointClusterer:
    """
    观点聚类器
    将相似的观点归类，高亮分歧点
    """
    
    def __init__(self):
        self.clusters: List[ViewpointCluster] = []
        self.threshold = 0.7
    
    def cluster_viewpoints(self, messages: List[Message]) -> List[ViewpointCluster]:
        """聚类观点"""
        self.clusters = []
        
        viewpoints = []
        for msg in messages:
            if msg.role == "assistant":
                viewpoints.append({
                    "id": msg.id,
                    "content": msg.content,
                    "model": msg.model_name,
                    "tags": msg.viewpoint_tags
                })
        
        for i, v1 in enumerate(viewpoints):
            cluster = None
            for c in self.clusters:
                if self._are_similar(v1["content"], c.viewpoint):
                    cluster = c
                    break
            
            if cluster:
                cluster.supporting_models.append(v1["model"])
            else:
                new_cluster = ViewpointCluster(
                    cluster_id=f"cluster_{len(self.clusters)}",
                    viewpoint=v1["content"][:200],
                    supporting_models=[v1["model"]],
                    sentiment=self._extract_sentiment(v1["content"]),
                    strength=0.5,
                    key_points=self._extract_key_points(v1["content"])
                )
                self.clusters.append(new_cluster)
        
        for cluster in self.clusters:
            cluster.strength = min(1.0, len(cluster.supporting_models) / 5)
        
        return self.clusters
    
    def _are_similar(self, text1: str, text2: str) -> bool:
        """判断两个观点是否相似"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard = intersection / union if union > 0 else 0
        return jaccard > self.threshold
    
    def _extract_sentiment(self, text: str) -> str:
        """提取情感倾向"""
        positive_words = ["同意", "支持", "正确", "好", "不错", "赞同"]
        negative_words = ["反对", "不对", "错误", "不好", "质疑", "怀疑"]
        
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"
    
    def _extract_key_points(self, text: str) -> List[str]:
        """提取关键观点点"""
        points = []
        
        sentences = text.replace("。", ".").split(".")
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 100:
                if any(kw in sent for kw in ["认为", "觉得", "观点", "看法", "应该"]):
                    points.append(sent)
        
        return points[:3]
    
    def get_disagreements(self) -> List[Dict]:
        """获取分歧点"""
        disagreements = []
        
        for i, c1 in enumerate(self.clusters):
            for c2 in self.clusters[i+1:]:
                if c1.sentiment != c2.sentiment and c1.sentiment != "neutral" and c2.sentiment != "neutral":
                    disagreements.append({
                        "cluster_1": c1.cluster_id,
                        "cluster_2": c2.cluster_id,
                        "viewpoint_1": c1.viewpoint[:100],
                        "viewpoint_2": c2.viewpoint[:100],
                        "sentiment_conflict": f"{c1.sentiment} vs {c2.sentiment}"
                    })
        
        return disagreements


class TopicGenerator:
    """
    话题生成器
    基于世界设定自动生成讨论话题
    """
    
    def __init__(self, world_setting: WorldSetting = None):
        self.world_setting = world_setting or WorldSetting()
    
    def generate_topic(self, discussion_history: List[Message] = None) -> str:
        """生成新话题"""
        if self.world_setting.main_topics:
            import random
            return random.choice(self.world_setting.main_topics)
        
        if self.world_setting.discussion_templates:
            import random
            template = random.choice(self.world_setting.discussion_templates)
            return template.get("topic", "讨论一下这个话题")
        
        default_topics = [
            "对这个话题，你有什么独特的见解？",
            "从你的专业角度来看，这个问题应该如何解决？",
            "如果从不同角度分析，会有什么不同的结论？",
            "这个观点是否站得住脚？我们来辩论一下。",
            "让我们深入探讨这个话题的各个方面。"
        ]
        
        import random
        return random.choice(default_topics)
    
    def generate_followup_topic(self, last_topic: str, messages: List[Message]) -> str:
        """生成跟进话题"""
        followups = [
            f"关于{last_topic}，我们能否深入讨论某个方面？",
            f"从{last_topic}引申出去，还有哪些相关问题值得关注？",
            f"针对刚才的讨论，是否有需要补充的观点？",
            f"对于{last_topic}的不同立场，你更支持哪一方？",
        ]
        
        import random
        return random.choice(followups)
    
    def should_end_topic(self, messages: List[Message], max_turns: int = 10) -> tuple:
        """判断是否应该结束当前话题"""
        recent_msgs = messages[-10:]
        
        if len(recent_msgs) >= max_turns:
            return True, "达到最大轮数"
        
        content_lengths = [len(m.content) for m in recent_msgs if m.role == "assistant"]
        if content_lengths:
            avg_length = sum(content_lengths) / len(content_lengths)
            if avg_length < 50:
                return True, "回复内容变短，可能话题枯竭"
        
        return False, ""


class HybridGroupChatController:
    """
    混合智能群聊控制器 - 完整版
    
    核心功能：
    1. 多模型交互讨论（非依次回复，是真正的讨论）
    2. 自动聊天控制（开始/暂停/停止/状态保存）
    3. 状态检测与智能响应
    4. 话题管理（生成/延续/结束）
    5. 情感可视化
    6. 观点聚类
    """
    
    def __init__(self):
        self.state = DiscussionState.IDLE
        self.world_setting = WorldSetting()
        self.characters: Dict[str, CharacterConfig] = {}
        self.messages: List[Message] = []
        self.discussion_turns: List[DiscussionTurn] = []
        self.current_turn = 0
        
        self.auto_chat_enabled = False
        self.max_turns_per_topic = DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["max_turns"]
        self.auto_stop_enabled = False
        self.history_messages_limit = DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["history_messages"]
        self.keep_alive = DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["keep_alive"]
        self.stream_chunk_chars = DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["stream_chunk_chars"]
        self.generation_options = build_ollama_options({
            **DEFAULT_GROUP_CHAT_RUNTIME_CONFIG,
            "sampling_preset": "fast",
        })
        
        self.topic_generator = TopicGenerator(self.world_setting)
        self.emotion_analyzer = EmotionAnalyzer()
        self.viewpoint_clusterer = ViewpointClusterer()
        
        self._lock = threading.RLock()
        self._callbacks: Dict[str, Callable] = {}
        
        self.state_file = Path(__file__).parent.parent / "data" / "group_chat_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._last_state_save_ts = 0.0
        self._state_save_interval = 10.0
        
        logger.info("✓ HybridGroupChatController 初始化完成")
    
    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        self._callbacks[event] = callback
    
    def _emit(self, event: str, data: Any = None):
        """触发事件"""
        with self._lock:
            callback = self._callbacks.get(event)
            if callback:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")
    
    def set_world_setting(self, setting: WorldSetting):
        """设置世界设定"""
        with self._lock:
            self.world_setting = setting
            self.topic_generator = TopicGenerator(setting)
            logger.info(f"✓ 世界设定已更新: {setting.title}")
    
    def add_character(self, character: CharacterConfig):
        """添加角色配置"""
        with self._lock:
            self.characters[character.model_name] = character
            logger.info(f"✓ 角色已添加: {character.name} ({character.model_name})")
    
    def _build_character_label(self, model_name: str, index: int = 0) -> str:
        """Build a readable fallback character label from the model name."""
        base = (model_name or DEFAULT_GROUP_CHAT_MODEL).split(":")[0]
        pretty = base.replace("-", " ").replace("_", " ").strip().title() or "Assistant"
        return f"{pretty} #{index + 1}"

    def ensure_default_characters(self) -> int:
        """
        Seed lightweight default participants from local Ollama models when the
        controller has not been configured yet.
        """
        with self._lock:
            if self.characters:
                return len(self.characters)

        candidates: List[Dict[str, Any]] = []
        try:
            import requests

            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
            response.raise_for_status()
            payload = response.json() or {}
            models = payload.get("models") or payload.get("data", {}).get("models") or []

            for model in models:
                name = model.get("name") or model.get("model") or model.get("id")
                if not name:
                    continue
                lowered = name.lower()
                if any(token in lowered for token in ("embed", "embedding", "vision", "vl", "sdxl", "image")):
                    continue
                candidates.append({
                    "name": name,
                    "size": int(model.get("size") or 0),
                })
        except Exception as exc:
            logger.warning(f"扫描Ollama模型失败: {exc}")

        if not candidates:
            candidates = [{"name": DEFAULT_GROUP_CHAT_MODEL, "size": 0}]

        preferred_order = {
            "qwen2.5:3b": 0,
            "literary-assistant:latest": 1,
            "llama3.2:3b": 2,
            "gemma2:2b": 3,
            "qwen2.5:1.5b": 4,
            DEFAULT_GROUP_CHAT_MODEL: 5,
            "qwen3.5:0.8b": 98,
        }
        candidates.sort(
            key=lambda item: (
                preferred_order.get(item["name"], 50),
                item["size"] <= 0,
                item["size"],
                item["name"],
            )
        )

        selected: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            name = candidate["name"]
            if name in seen:
                continue
            seen.add(name)
            selected.append(candidate)
            if len(selected) >= 2:
                break

        with self._lock:
            if self.characters:
                return len(self.characters)

            for index, candidate in enumerate(selected):
                model_name = candidate["name"]
                self.characters[model_name] = CharacterConfig(
                    model_name=model_name,
                    name=self._build_character_label(model_name, index),
                    avatar="assistant",
                    personality="你是一个积极参与讨论的智能助手",
                    style="简洁明了，观点鲜明",
                    expertise=["通用知识", "逻辑分析"],
                    speaking_style="concise",
                )

            if self.characters:
                logger.info(
                    "自动添加默认角色: %s",
                    ", ".join(self.characters.keys()),
                )

            return len(self.characters)

    def get_character(self, model_name: str) -> Optional[CharacterConfig]:
        """获取角色配置"""
        return self.characters.get(model_name)
    
    def build_system_prompt(self, model_name: str, include_world: bool = True) -> str:
        """构建系统提示词"""
        parts = []
        
        if include_world and self.world_setting.title:
            parts.append(f"【世界背景】{self.world_setting.title}")
            if self.world_setting.background:
                parts.append(self.world_setting.background)
            if self.world_setting.rules:
                parts.append("【世界规则】" + "；".join(self.world_setting.rules))
        
        character = self.get_character(model_name)
        if character:
            parts.append(f"【角色身份】你是{character.name}")
            if character.personality:
                parts.append(f"【性格特点】{character.personality}")
            if character.style:
                parts.append(f"【说话风格】{character.style}")
            if character.expertise:
                parts.append(f"【专长领域】{', '.join(character.expertise)}")
        
        if self.messages:
            recent = self.messages[-6:]
            history = []
            for msg in recent:
                if msg.role == "user":
                    history.append(f"用户: {msg.content[:100]}")
                elif msg.role == "assistant":
                    char = msg.character_name or msg.model_name
                    history.append(f"{char}: {msg.content[:100]}")
            if history:
                parts.append("【最近讨论】" + "\n".join(history))
        
        return "\n\n".join(parts) if parts else "你是一个智能助手。"
    
    def start_auto_chat(self, initial_topic: str = None):
        """开始自动聊天"""
        with self._lock:
            if self.state == DiscussionState.RUNNING:
                logger.warning("讨论已在运行中")
                return False

            if not self.characters:
                self.ensure_default_characters()
            if not self.characters:
                logger.warning("没有可用的角色参与讨论")
                return False

            self.state = DiscussionState.RUNNING
            self.auto_chat_enabled = True
            
            if not initial_topic:
                initial_topic = self.topic_generator.generate_topic()
            
            self.current_turn += 1
            turn = DiscussionTurn(
                turn_number=self.current_turn,
                topic=initial_topic,
                participants=list(self.characters.keys()),
                start_time=int(time.time() * 1000)
            )
            self.discussion_turns.append(turn)
            self._append_system_message(f"Group chat started: {initial_topic}", turn)
            
            logger.info(f"✓ 开始自动讨论: 话题 #{self.current_turn}")
            
            self._emit("auto_chat_started", {"topic": initial_topic})
            
            self._start_background_worker()
            
            return True
    
    def pause_auto_chat(self):
        """暂停自动聊天"""
        with self._lock:
            if self.state == DiscussionState.RUNNING:
                self.state = DiscussionState.PAUSED
                self.auto_chat_enabled = False
                self._save_state()
                logger.info("✓ 自动讨论已暂停")
                self._emit("auto_chat_paused", {})
                return True
            return False
    
    def resume_auto_chat(self):
        """继续自动聊天"""
        with self._lock:
            if self.state == DiscussionState.PAUSED:
                self.state = DiscussionState.RUNNING
                self.auto_chat_enabled = True
                self._start_background_worker()
                logger.info("✓ 自动讨论已继续")
                self._emit("auto_chat_resumed", {})
                return True
            return False
    
    def stop_auto_chat(self, reason: str = "手动停止"):
        """停止自动聊天"""
        with self._lock:
            self.state = DiscussionState.COMPLETED
            self.auto_chat_enabled = False
            
            if self.discussion_turns:
                self.discussion_turns[-1].end_time = int(time.time() * 1000)
            
            self._save_state()
            logger.info(f"✓ 自动讨论已停止: {reason}")
            self._emit("auto_chat_stopped", {"reason": reason})
            return True
    
    def _start_background_worker(self):
        """启动后台工作线程"""
        consecutive_errors = 0
        max_consecutive_errors = 3

        def worker():
            nonlocal consecutive_errors
            while self.auto_chat_enabled and self.state == DiscussionState.RUNNING:
                try:
                    self._process_discussion_step()
                    consecutive_errors = 0
                    time.sleep(2)
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"讨论处理错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("连续错误过多，自动停止讨论")
                        self.auto_chat_enabled = False
                        self.state = DiscussionState.IDLE
                        self._emit("auto_chat_stopped", {"reason": f"连续{max_consecutive_errors}次错误"})
                        break
                    time.sleep(3)
            
            if self.state == DiscussionState.RUNNING:
                self.state = DiscussionState.IDLE
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _process_discussion_step(self):
        """处理讨论步骤"""
        current_turn = self.discussion_turns[-1] if self.discussion_turns else None
        if not current_turn:
            return
        
        participants = current_turn.participants
        if not participants:
            return
        
        last_msg = self.messages[-1] if self.messages else None
        
        if last_msg and last_msg.role == "assistant":
            next_participant = self._select_next_speaker(participants, last_msg.model_name)
        else:
            next_participant = participants[0]
        
        if not next_participant:
            return
        
        self._generate_response(next_participant)
        
        should_end, reason = self.topic_generator.should_end_topic(
            self.messages, self.max_turns_per_topic
        )
        
        if should_end:
            self._handle_topic_transition(reason)
    
    def _select_next_speaker(self, participants: List[str], last_speaker: str) -> Optional[str]:
        """选择下一个发言者（随机选择，避免总是同一顺序）"""
        import random
        remaining = [p for p in participants if p != last_speaker]
        if remaining:
            return random.choice(remaining)
        return participants[0] if participants else None
    
    def _append_system_message(self, content: str, current_turn: Optional[DiscussionTurn] = None):
        """Append a visible system message so the frontend is never left silent."""
        msg = Message(
            id=self._generate_id(),
            role="assistant",
            model_name="system",
            character_name="system",
            content=content,
            timestamp=int(time.time() * 1000),
        )
        with self._lock:
            self.messages.append(msg)
            if current_turn:
                current_turn.messages.append(msg)
        self._maybe_save_state()
        self._emit("message_generated", {"message": asdict(msg), "dominant_emotion": "neutral"})
        return msg

    def _generate_response(self, model_name: str, stream: bool = True):
        """
        生成回复
        
        Args:
            model_name: 模型名称
            stream: 是否启用流式输出（默认启用）
        """
        character = self.get_character(model_name)
        char_name = character.name if character else model_name
        
        system_prompt = self.build_system_prompt(model_name)
        
        context_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg in self.messages[-self.history_messages_limit:]:
            context_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        current_turn = self.discussion_turns[-1] if self.discussion_turns else None
        topic_prompt = f"当前话题: {current_turn.topic if current_turn else '讨论'}"
        
        context_messages.append({
            "role": "user",
            "content": topic_prompt + "\n请基于你的角色观点发表看法。"
        })
        
        self._emit("model_thinking", {
            "model": model_name,
            "character": char_name
        })
        
        try:
            import requests
            import json
            
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model_name or DEFAULT_GROUP_CHAT_MODEL,
                    "messages": context_messages,
                    "stream": stream,
                    "options": self.generation_options,
                    "keep_alive": self.keep_alive
                },
                timeout=(10, 120),
                stream=True
            )
            
            if response.status_code == 200:
                # 流式处理
                full_content = ""
                sentence_buffer = ""
                
                if stream:
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line.decode('utf-8'))
                                content = chunk.get('message', {}).get('content', '')
                                if content:
                                    full_content += content
                                    sentence_buffer += content
                                    
                                    # 检测句子边界并发送事件
                                    while True:
                                        sentence_end = -1
                                        for i, char in enumerate(sentence_buffer):
                                            if char in '。！？.!?':
                                                sentence_end = i + 1
                                                break
                                        
                                        if sentence_end > 0:
                                            # 有完整句子，发送增量事件
                                            sentence = sentence_buffer[:sentence_end]
                                            sentence_buffer = sentence_buffer[sentence_end:]
                                            
                                            self._emit("stream_chunk", {
                                                "model": model_name,
                                                "character": char_name,
                                                "content": sentence,
                                                "is_sentence": True,
                                                "done": False
                                            })
                                        else:
                                            # 没有完整句子，检查是否积累了足够多的内容
                                            if len(sentence_buffer) >= self.stream_chunk_chars:
                                                self._emit("stream_chunk", {
                                                    "model": model_name,
                                                    "character": char_name,
                                                    "content": sentence_buffer,
                                                    "is_sentence": False,
                                                    "done": False
                                                })
                                                sentence_buffer = ""
                                            break
                            except json.JSONDecodeError:
                                continue
                    
                    # 处理剩余的缓冲区内容
                    if sentence_buffer.strip():
                        self._emit("stream_chunk", {
                            "model": model_name,
                            "character": char_name,
                            "content": sentence_buffer.strip(),
                            "is_sentence": True,
                            "done": False
                        })
                else:
                    # 非流式处理
                    data = response.json()
                    full_content = data.get("message", {}).get("content", "")
                
                emotions = self.emotion_analyzer.analyze(full_content)
                
                msg = Message(
                    id=self._generate_id(),
                    role="assistant",
                    model_name=model_name,
                    character_name=char_name,
                    content=full_content,
                    timestamp=int(time.time() * 1000),
                    emotions=emotions
                )
                
                with self._lock:
                    self.messages.append(msg)
                    if current_turn:
                        current_turn.messages.append(msg)

                self._maybe_save_state()
                
                self._emit("message_generated", {
                    "message": asdict(msg),
                    "dominant_emotion": EmotionAnalyzer.get_dominant_emotion(emotions)
                })
                
                logger.info(f"✓ {char_name} 发言完成 ({len(full_content)} 字)")
                
                return msg

            error_text = (response.text or "").strip()[:160]
            logger.warning("group chat upstream request failed for %s: %s", model_name, error_text)
            local_result = self._try_local_model(model_name, context_messages, char_name, current_turn)
            if local_result:
                return local_result
            return self._append_system_message(
                f"Ollama request failed for {char_name}: {error_text or 'unknown error'}",
                current_turn,
            )

        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            local_result = self._try_local_model(model_name, context_messages, char_name, current_turn)
            if local_result:
                return local_result
            return self._append_system_message(
                f"Ollama request failed for {char_name}: {str(e)[:160]}",
                current_turn,
            )

    def _try_local_model(self, model_name: str, messages: List[Dict], char_name: str, current_turn) -> Optional[Message]:
        """尝试使用本地模型生成回复"""
        try:
            from local_model_loader import get_local_model_path, LOCAL_MODEL_AVAILABLE
            
            if not LOCAL_MODEL_AVAILABLE:
                logger.info("本地模型不可用")
                return None
            
            local_path = get_local_model_path(model_name)
            if not local_path:
                logger.info(f"本地模型不存在: {model_name}")
                return None
            
            logger.info(f"尝试使用本地模型: {local_path}")
            
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            tokenizer = AutoTokenizer.from_pretrained(local_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                local_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )
            
            if torch.cuda.is_available():
                model = model.cuda()
            else:
                model = model.cpu()
            
            prompt = ""
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system":
                    prompt += f"系统: {content}\n"
                elif role == "user":
                    prompt += f"用户: {content}\n"
                elif role == "assistant":
                    prompt += f"助手: {content}\n"
            
            prompt += f"{char_name}: "
            
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            response_text = generated_text[len(prompt):].strip()
            
            if not response_text:
                return None
            
            emotions = self.emotion_analyzer.analyze(response_text)
            
            msg = Message(
                id=self._generate_id(),
                role="assistant",
                model_name=model_name,
                character_name=char_name,
                content=response_text,
                timestamp=int(time.time() * 1000),
                emotions=emotions
            )
            
            with self._lock:
                self.messages.append(msg)
                if current_turn:
                    current_turn.messages.append(msg)
            
            self._maybe_save_state()
            
            self._emit("message_generated", {
                "message": asdict(msg),
                "dominant_emotion": EmotionAnalyzer.get_dominant_emotion(emotions)
            })
            
            logger.info(f"✓ {char_name} 发言完成 (本地模型, {len(response_text)} 字)")
            
            return msg
            
        except Exception as e:
            logger.error(f"本地模型生成失败: {e}")
            return None
    def _handle_topic_transition(self, reason: str):
        """处理话题转换"""
        current_turn = self.discussion_turns[-1]
        current_turn.end_time = int(time.time() * 1000)
        
        clusters = self.viewpoint_clusterer.cluster_viewpoints(self.messages)
        disagreements = self.viewpoint_clusterer.get_disagreements()
        
        summary = self._generate_summary(current_turn, clusters, "full")
        
        summary_msg = Message(
            id=self._generate_id(),
            role="assistant",
            model_name="system",
            character_name="总结",
            content=summary,
            timestamp=int(time.time() * 1000),
            is_summary=True
        )
        
        with self._lock:
            self.messages.append(summary_msg)
            current_turn.messages.append(summary_msg)
            current_turn.consensus_reached = len(clusters) <= 2

        self._maybe_save_state()
        
        self._emit("topic_summary", {
            "turn": current_turn.turn_number,
            "reason": reason,
            "summary": summary,
            "clusters": [asdict(c) for c in clusters],
            "disagreements": disagreements
        })
        
        if self.auto_stop_enabled:
            self.stop_auto_chat("自动停止：讨论已完成")
        else:
            new_topic = self.topic_generator.generate_followup_topic(
                current_turn.topic, self.messages
            )
            
            self.current_turn += 1
            new_turn = DiscussionTurn(
                turn_number=self.current_turn,
                topic=new_topic,
                participants=list(self.characters.keys()),
                start_time=int(time.time() * 1000)
            )
            
            with self._lock:
                self.discussion_turns.append(new_turn)
            
            self._emit("topic_changed", {
                "old_topic": current_turn.topic,
                "new_topic": new_topic,
                "turn_number": self.current_turn
            })
            
            logger.info(f"→ 切换到新话题: {new_topic}")
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        timestamp = str(int(time.time() * 1000))
        random_part = hashlib.md5(f"{timestamp}{len(self.messages)}".encode()).hexdigest()[:8]
        return f"msg_{random_part}"
    
    def _save_state(self):
        """保存状态"""
        try:
            state_data = {
                "state": self.state.value,
                "auto_chat_enabled": self.auto_chat_enabled,
                "current_turn": self.current_turn,
                "message_count": len(self.messages),
                "last_updated": datetime.now().isoformat(),
                "characters": [asdict(c) for c in self.characters.values()],
                "messages": [asdict(m) for m in self.messages],
                "discussion_turns": [asdict(t) for t in self.discussion_turns]
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            logger.debug("✓ 状态已保存")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    

    def _maybe_save_state(self):
        now = time.time()
        if now - self._last_state_save_ts >= self._state_save_interval:
            self._save_state()
            self._last_state_save_ts = now

    def _message_from_dict(self, data: Dict[str, Any]) -> Message:
        return Message(
            id=data.get("id", self._generate_id()),
            role=data.get("role", "assistant"),
            model_name=data.get("model_name", ""),
            character_name=data.get("character_name", ""),
            content=data.get("content", ""),
            timestamp=int(data.get("timestamp", 0) or 0),
            emotions=data.get("emotions", {}) or {},
            viewpoint_tags=data.get("viewpoint_tags", []) or [],
            references=data.get("references", []) or [],
            is_summary=bool(data.get("is_summary", False))
        )

    def _turn_from_dict(self, data: Dict[str, Any]) -> DiscussionTurn:
        messages = [self._message_from_dict(m) for m in data.get("messages", []) or []]
        return DiscussionTurn(
            turn_number=int(data.get("turn_number", 0) or 0),
            topic=data.get("topic", ""),
            participants=data.get("participants", []) or [],
            messages=messages,
            start_time=int(data.get("start_time", 0) or 0),
            end_time=int(data.get("end_time", 0) or 0),
            consensus_reached=bool(data.get("consensus_reached", False)),
            emotion_summary=data.get("emotion_summary", {}) or {}
        )

    def load_state(self) -> bool:
        """加载状态"""
        try:
            if not self.state_file.exists():
                return False
            
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            self.state = DiscussionState(state_data.get("state", "idle"))
            self.auto_chat_enabled = state_data.get("auto_chat_enabled", False)
            self.current_turn = state_data.get("current_turn", 0)
            self.characters = {
                c.get("model_name"): CharacterConfig(
                    model_name=c.get("model_name", DEFAULT_GROUP_CHAT_MODEL),
                    name=c.get("name") or self._build_character_label(c.get("model_name", ""), 0),
                    avatar=c.get("avatar", "assistant"),
                    personality=c.get("personality", ""),
                    style=c.get("style", ""),
                    expertise=c.get("expertise", []) or [],
                    speaking_style=c.get("speaking_style", "balanced"),
                    emotional_range=c.get("emotional_range", ["neutral"]) or ["neutral"],
                    voice_profile=c.get("voice_profile", "default"),
                )
                for c in state_data.get("characters", []) or []
                if c.get("model_name")
            }
            self.messages = [self._message_from_dict(m) for m in state_data.get("messages", []) or []]
            self.discussion_turns = [self._turn_from_dict(t) for t in state_data.get("discussion_turns", []) or []]
            if not self.characters:
                self.ensure_default_characters()

            logger.info(f"加载状态: {self.state.value}")
            return True
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        clusters = self.viewpoint_clusterer.cluster_viewpoints(self.messages)
        
        return {
            "state": self.state.value,
            "auto_chat_enabled": self.auto_chat_enabled,
            "current_turn": self.current_turn,
            "message_count": len(self.messages),
            "participants": list(self.characters.keys()),
            "topic": self.discussion_turns[-1].topic if self.discussion_turns else None,
            "emotions": self._get_emotion_summary(),
            "viewpoint_clusters": len(clusters),
            "is_consensus": self.discussion_turns[-1].consensus_reached if self.discussion_turns else False,
            "config": {
                "max_turns": self.max_turns_per_topic,
                "auto_stop": self.auto_stop_enabled,
                "history_messages": self.history_messages_limit,
                "stream_chunk_chars": self.stream_chunk_chars,
                "keep_alive": self.keep_alive,
                "generation_options": dict(self.generation_options),
            }
        }
    
    def _get_emotion_summary(self) -> Dict[str, float]:
        """获取情感汇总"""
        emotion_totals = {}
        
        for msg in self.messages[-20:]:
            if msg.emotions:
                for emotion, score in msg.emotions.items():
                    emotion_totals[emotion] = emotion_totals.get(emotion, 0) + score
        
        if emotion_totals:
            total = sum(emotion_totals.values())
            return {k: round(v / total, 3) for k, v in sorted(emotion_totals.items(), key=lambda x: -x[1])}
        
        return {"neutral": 1.0}
    
    def get_messages(self, limit: int = 50) -> List[Dict]:
        """获取消息列表"""
        return [asdict(m) for m in self.messages[-limit:]]
    
    def get_emotion_history(self) -> List[Dict]:
        """获取情感历史"""
        history = []
        
        for msg in self.messages:
            if msg.emotions:
                history.append({
                    "timestamp": msg.timestamp,
                    "model": msg.model_name,
                    "character": msg.character_name,
                    "dominant": EmotionAnalyzer.get_dominant_emotion(msg.emotions),
                    "emotions": msg.emotions
                })
        
        return history
    
    def get_viewpoint_clusters(self) -> List[Dict]:
        """获取观点聚类"""
        clusters = self.viewpoint_clusterer.cluster_viewpoints(self.messages)
        disagreements = self.viewpoint_clusterer.get_disagreements()
        
        return {
            "clusters": [asdict(c) for c in clusters],
            "disagreements": disagreements
        }
    
    def set_max_turns(self, turns: int):
        """设置最大轮数"""
        self.max_turns_per_topic = max(3, min(20, turns))
        self._save_state()
        logger.info(f"✓ 最大轮数已设置为: {self.max_turns_per_topic}")

    def update_generation_config(self, config: Dict[str, Any]):
        """Update lightweight generation settings used by the group chat worker."""
        if "history_messages" in config:
            self.history_messages_limit = max(2, min(10, int(config["history_messages"])))
        if "stream_chunk_chars" in config:
            self.stream_chunk_chars = max(20, min(200, int(config["stream_chunk_chars"])))
        if "keep_alive" in config and str(config["keep_alive"]).strip():
            self.keep_alive = str(config["keep_alive"]).strip()

        runtime_cfg = {
            **DEFAULT_GROUP_CHAT_RUNTIME_CONFIG,
            "num_predict": self.generation_options.get("num_predict", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["num_predict"]),
            "num_ctx": self.generation_options.get("num_ctx", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["num_ctx"]),
            "num_threads": self.generation_options.get("num_thread", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["num_threads"]),
            "temperature": self.generation_options.get("temperature", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["temperature"]),
            "repeat_penalty": self.generation_options.get("repeat_penalty", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["repeat_penalty"]),
            "top_k": self.generation_options.get("top_k", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["top_k"]),
            "top_p": self.generation_options.get("top_p", DEFAULT_GROUP_CHAT_RUNTIME_CONFIG["top_p"]),
            "sampling_preset": "fast",
        }

        if "num_predict" in config:
            runtime_cfg["num_predict"] = max(64, min(1024, int(config["num_predict"])))
        if "num_ctx" in config:
            runtime_cfg["num_ctx"] = max(512, min(8192, int(config["num_ctx"])))
        if "num_threads" in config:
            runtime_cfg["num_threads"] = max(1, min(32, int(config["num_threads"])))
        if "temperature" in config:
            runtime_cfg["temperature"] = max(0.0, min(1.5, float(config["temperature"])))
        if "repeat_penalty" in config:
            runtime_cfg["repeat_penalty"] = max(1.0, min(2.0, float(config["repeat_penalty"])))
        if "top_k" in config:
            runtime_cfg["top_k"] = max(1, min(100, int(config["top_k"])))
        if "top_p" in config:
            runtime_cfg["top_p"] = max(0.1, min(1.0, float(config["top_p"])))

        self.generation_options = build_ollama_options(runtime_cfg, "fast")
        self._save_state()
    
    def set_auto_stop(self, enabled: bool):
        """设置是否自动停止"""
        self.auto_stop_enabled = enabled
        self._save_state()
        logger.info(f"✓ 自动停止已{'启用' if enabled else '禁用'}")
    
    def clear_history(self):
        """清空历史"""
        with self._lock:
            self.messages = []
            self.discussion_turns = []
            self.current_turn = 0
            self.state = DiscussionState.IDLE
            self.auto_chat_enabled = False
            
            self._save_state()
            logger.info("✓ 历史记录已清空")

    def send_user_message(self, content: str, target_model: str = None) -> Message:
        """
        用户发送消息
        
        Args:
            content: 消息内容
            target_model: 指定回复的模型（可选）
            
        Returns:
            用户消息对象
        """
        with self._lock:
            msg = Message(
                id=self._generate_id(),
                role="user",
                model_name="user",
                character_name="用户",
                content=content,
                timestamp=int(time.time() * 1000)
            )
            self.messages.append(msg)
            
            current_turn = self.discussion_turns[-1] if self.discussion_turns else None
            if current_turn:
                current_turn.messages.append(msg)
            
            self._maybe_save_state()
            self._emit("user_message", {"message": asdict(msg)})
            
            logger.info(f"✓ 用户消息: {content[:50]}...")
            
            if target_model and target_model in self.characters:
                threading.Thread(
                    target=self._generate_response,
                    args=(target_model,),
                    daemon=True
                ).start()
            
            return msg

    def ask_model(self, model_name: str, question: str = None) -> Optional[Message]:
        """
        指定模型回答问题
        
        Args:
            model_name: 模型名称
            question: 问题内容（可选，不提供则回答最后一条消息）
            
        Returns:
            模型回复消息（异步生成，返回 None 表示已开始生成）
        """
        with self._lock:
            # 检查模型是否存在，如果不存在则动态添加
            if model_name not in self.characters:
                char = CharacterConfig(
                    model_name=model_name,
                    name=model_name.split(":")[0].replace("-", " ").replace("_", " ").title(),
                    avatar="assistant",
                    personality="",
                    expertise=[]
                )
                self.characters[model_name] = char
                logger.info(f"动态添加模型角色：{model_name}")
            
            if question:
                user_msg = Message(
                    id=self._generate_id(),
                    role="user",
                    model_name="user",
                    character_name="用户",
                    content=question,
                    timestamp=int(time.time() * 1000)
                )
                self.messages.append(user_msg)
                current_turn = self.discussion_turns[-1] if self.discussion_turns else None
                if current_turn:
                    current_turn.messages.append(user_msg)
            
            threading.Thread(
                target=self._generate_response,
                args=(model_name,),
                daemon=True
            ).start()
            
            logger.info(f"✓ 请求模型回答: {model_name}")
            return None

    def request_summary(self, summary_type: str = "full") -> str:
        """
        手动请求总结
        
        Args:
            summary_type: 总结类型 (full/brief/keypoints)
            
        Returns:
            总结内容
        """
        with self._lock:
            current_turn = self.discussion_turns[-1] if self.discussion_turns else None
            if not current_turn:
                return "暂无讨论内容"
            
            clusters = self.viewpoint_clusterer.cluster_viewpoints(self.messages)
            summary = self._generate_summary(current_turn, clusters, summary_type)
            
            summary_msg = Message(
                id=self._generate_id(),
                role="assistant",
                model_name="system",
                character_name="总结",
                content=summary,
                timestamp=int(time.time() * 1000),
                is_summary=True
            )
            self.messages.append(summary_msg)
            if current_turn:
                current_turn.messages.append(summary_msg)
            
            self._maybe_save_state()
            self._emit("summary_generated", {"summary": summary, "type": summary_type})
            
            logger.info(f"✓ 生成总结 ({summary_type})")
            return summary

    def _generate_summary(self, turn: DiscussionTurn, clusters: List[ViewpointCluster], summary_type: str = "full") -> str:
        """生成讨论总结"""
        if summary_type == "brief":
            lines = [f"【简要总结 - 第{turn.turn_number}轮】"]
            lines.append(f"话题: {turn.topic}")
            lines.append(f"消息数: {len(turn.messages)}")
            lines.append(f"参与者: {', '.join(turn.participants)}")
            if clusters:
                lines.append(f"主要观点数: {len(clusters)}")
            return "\n".join(lines)
        
        elif summary_type == "keypoints":
            lines = [f"【关键观点 - 第{turn.turn_number}轮】"]
            for i, cluster in enumerate(clusters[:5]):
                lines.append(f"{i+1}. {cluster.viewpoint[:100]}")
                lines.append(f"   支持者: {', '.join(cluster.supporting_models[:3])}")
            return "\n".join(lines)
        
        else:
            lines = [f"【讨论总结 - 第{turn.turn_number}轮】", ""]
            lines.append(f"话题: {turn.topic}")
            lines.append(f"消息数: {len(turn.messages)}")
            lines.append("")
            
            if clusters:
                lines.append("主要观点：")
                for i, cluster in enumerate(clusters):
                    models = ", ".join(cluster.supporting_models[:3])
                    lines.append(f"  {i+1}. {cluster.viewpoint[:80]}...")
                    lines.append(f"     支持者: {models}")
                lines.append("")
            
            if turn.consensus_reached:
                lines.append("✓ 各模型在此话题上达成较多共识")
            else:
                lines.append("○ 各模型保留了不同观点，可进一步讨论")
            
            return "\n".join(lines)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        models = []
        existing_ids = set()
        
        # 先获取已配置的角色
        for model_name, char in self.characters.items():
            models.append({
                "id": model_name,
                "name": char.name,
                "avatar": char.avatar,
                "personality": char.personality[:50] if char.personality else "",
                "expertise": char.expertise[:3] if char.expertise else []
            })
            existing_ids.add(model_name)
        
        # 如果没有角色，自动添加默认角色
        if not models:
            self.ensure_default_characters()
            for model_name, char in self.characters.items():
                models.append({
                    "id": model_name,
                    "name": char.name,
                    "avatar": char.avatar,
                    "personality": char.personality[:50] if char.personality else "",
                    "expertise": char.expertise[:3] if char.expertise else []
                })
                existing_ids.add(model_name)
        
        # 扫描 Ollama 所有模型并添加未包含的
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=3)
            if response.status_code == 200:
                data = response.json()
                ollama_models = data.get("models", []) or data.get("data", {}).get("models", [])
                
                for model in ollama_models:
                    model_name = model.get("name") or model.get("model") or model.get("id")
                    if not model_name:
                        continue
                    
                    # 跳过嵌入模型和视觉模型
                    lowered = model_name.lower()
                    if any(token in lowered for token in ("embed", "embedding", "vision", "vl", "sdxl", "image")):
                        continue
                    
                    # 只添加未包含的模型
                    if model_name not in existing_ids:
                        models.append({
                            "id": model_name,
                            "name": model_name.split(":")[0].replace("-", " ").replace("_", " ").title(),
                            "avatar": "assistant",
                            "personality": "",
                            "expertise": []
                        })
                        existing_ids.add(model_name)
        except Exception as e:
            logger.warning(f"扫描 Ollama 模型失败：{e}")
            # Ollama 离线时，扫描本地模型
            try:
                from local_model_loader import LOCAL_MODEL_AVAILABLE
                if LOCAL_MODEL_AVAILABLE:
                    # 扫描新的统一模型目录
                    local_models_dirs = [
                        r'D:\Explore\ollma\models\llm\hf',
                        r'D:\Explore\ollma\models\vlm',
                        r'D:\Explore\ollma\models\llm',
                    ]
                    for local_models_dir in local_models_dirs:
                        if os.path.exists(local_models_dir):
                            for root, dirs, files in os.walk(local_models_dir):
                                # 跳过隐藏目录和临时目录
                                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '._____temp']
                                
                                for dir_name in dirs:
                                    if dir_name not in existing_ids:
                                        # 检查是否为有效模型目录
                                        model_dir = os.path.join(root, dir_name)
                                        if os.path.exists(os.path.join(model_dir, 'config.json')):
                                            models.append({
                                                "id": dir_name,
                                                "name": dir_name.replace("-", " ").replace("_", " ").title(),
                                                "avatar": "assistant",
                                                "personality": "",
                                                "expertise": []
                                            })
                                            existing_ids.add(dir_name)
                        logger.info(f"扫描到 {len(models)} 个本地模型")
            except Exception as local_e:
                logger.error(f"扫描本地模型失败：{local_e}")
        
        return models


controller = HybridGroupChatController()


def get_group_chat_controller() -> HybridGroupChatController:
    """获取控制器单例"""
    return controller


if __name__ == "__main__":
    print("=== 混合智能群聊控制器测试 ===")
    
    controller = get_group_chat_controller()
    
    controller.add_character(CharacterConfig(
        model_name="qwen2.5:3b",
        name="Qwen助手",
        personality="高效、实用、反应迅速",
        style="简洁有力，侧重实际应用",
        expertise=["通用知识", "实用建议"]
    ))
    
    controller.add_character(CharacterConfig(
        model_name="llama3.2:3b",
        name="Llama学者",
        personality="开放、知识渊博、友好",
        style="详细且易于理解",
        expertise=["技术", "科学", "教育"]
    ))
    
    print(f"已添加 {len(controller.characters)} 个角色")
    print(f"控制器状态: {controller.get_status()}")
