"""
用户意图识别分类器

双引擎架构:
- legacy: 原有关键词+正则匹配引擎
- casc:   CASC(置信度自适应结构化级联)引擎
          多步二分类替代一次多分类, 小参数下精准识别意图

默认使用 casc 引擎, 不可用时回退到 legacy
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IntentResult:
    primary_intent: str
    confidence: float
    all_intents: List[Tuple[str, float]]
    entities: List[str]
    emotion: str
    engine: str = "legacy"
    exit_level: int = -1
    latency_ms: float = 0.0
    pragmatic_features: Optional[Dict] = None
    intent_analysis: Optional[Dict] = None
    emotion_detail: Optional[Dict] = None

    def to_dict(self) -> Dict:
        d = {
            "primary_intent": self.primary_intent,
            "confidence": round(self.confidence, 4),
            "all_intents": [(k, round(v, 4)) for k, v in self.all_intents],
            "entities": self.entities,
            "emotion": self.emotion,
            "engine": self.engine,
            "exit_level": self.exit_level,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.pragmatic_features:
            d["pragmatic_features"] = self.pragmatic_features
        if self.intent_analysis:
            d["intent_analysis"] = self.intent_analysis
        if self.emotion_detail:
            d["emotion_detail"] = self.emotion_detail
        return d


class IntentClassifier:

    def __init__(self, engine: str = "casc", model: str = "", ollama_url: str = "http://127.0.0.1:11434", user_id: str = "default", session_id: str = ""):
        self.engine_name = engine
        self._casc = None
        self._legacy = _LegacyEngine()

        if engine == "casc":
            try:
                from casc_engine import CASCEngine
                self._casc = CASCEngine.get_instance(ollama_url=ollama_url, model=model, user_id=user_id, session_id=session_id)
            except ImportError:
                self.engine_name = "legacy"

    def classify(self, text: str, history: Optional[List[Dict]] = None) -> IntentResult:
        if not text or not text.strip():
            return IntentResult(
                primary_intent="unknown", confidence=0.0,
                all_intents=[], entities=[], emotion="neutral",
                engine=self.engine_name,
            )

        if self._casc and self.engine_name == "casc":
            return self._classify_casc(text, history)
        return self._classify_legacy(text)

    def _classify_casc(self, text: str, history: Optional[List[Dict]] = None) -> IntentResult:
        result = self._casc.classify(text, history=history)
        pf_dict = None
        if result.pragmatic_features:
            pf = result.pragmatic_features
            pf_dict = {
                "utterance_type": pf.utterance_type.value,
                "illocutionary_force": pf.illocutionary_force.value,
                "politeness": pf.politeness.value,
                "hedging": round(pf.hedging, 2),
                "negation": pf.negation,
                "contrast": pf.contrast,
                "vagueness": round(pf.vagueness, 2),
                "intensity": round(pf.intensity, 2),
                "grice_violation": pf.grice_violation,
                "implicit_force": pf.implicit_force.value if pf.implicit_force else None,
            }
        return IntentResult(
            primary_intent=result.primary_intent.value,
            confidence=result.confidence,
            all_intents=[(result.primary_intent.value, result.confidence)],
            entities=result.entities,
            emotion=result.emotion,
            engine="casc",
            exit_level=result.exit_level,
            latency_ms=result.latency_ms,
            pragmatic_features=pf_dict,
            intent_analysis=result.intent_analysis,
            emotion_detail=result.emotion_detail,
        )

    def _classify_legacy(self, text: str) -> IntentResult:
        return self._legacy.classify(text)

    def get_intent_description(self, intent: str) -> str:
        descriptions = {
            'greeting': '问候意图', 'question': '问题意图',
            'command': '命令意图', 'request': '请求意图',
            'complaint': '投诉意图', 'praise': '表扬意图',
            'farewell': '告别意图', 'small_talk': '闲聊意图',
            'technical': '技术意图', 'personal': '个人意图',
            'creative_write': '创意写作意图', 'brainstorm': '头脑风暴意图',
            'unknown': '未知意图',
        }
        return descriptions.get(intent, '未知意图')

    def validate_confidence(self, result: IntentResult, threshold: float = 0.3) -> bool:
        return result.confidence >= threshold

    def get_statistics(self) -> Dict:
        stats = {
            'engine': self.engine_name,
            'total_intents': 12,
            'intent_list': [
                'greeting', 'question', 'command', 'request',
                'complaint', 'praise', 'farewell', 'small_talk',
                'technical', 'personal', 'creative_write', 'brainstorm',
            ],
        }
        if self._casc:
            stats['casc_available'] = True
            stats['casc_model'] = self._casc.model or 'rules-only'
        return stats


class _LegacyEngine:

    def __init__(self):
        self.intent_patterns = {
            'greeting': {
                'keywords': ['你好', '嗨', 'hello', 'hi', '在吗', '您好', '早上好', '晚上好'],
                'patterns': [r'^你好', r'^嗨', r'^hello', r'^hi'],
                'weight': 1.0
            },
            'question': {
                'keywords': ['?', '？', '怎么', '为什么', '什么', '如何', '能否', '哪', '多少', '什么时候'],
                'patterns': [r'.*[?？]$', r'.*怎么.*', r'.*为什么.*', r'.*什么.*', r'.*如何.*'],
                'weight': 0.9
            },
            'command': {
                'keywords': ['播放', '打开', '关闭', '设置', '启动', '停止', '搜索', '查找', '显示', '隐藏'],
                'patterns': [r'^播放', r'^打开', r'^关闭', r'^设置', r'^启动'],
                'weight': 0.8
            },
            'request': {
                'keywords': ['请', '帮我', '能不能', '可不可以', '麻烦', '帮忙', '求助'],
                'patterns': [r'.*请.*', r'.*帮我.*', r'.*能不能.*', r'.*可不可以.*'],
                'weight': 0.85
            },
            'complaint': {
                'keywords': ['太差', '不对', '坏了', '问题', '解决', '错误', '失败', '不好', '不满意'],
                'patterns': [r'.*太差.*', r'.*不对.*', r'.*坏了.*', r'.*问题.*'],
                'weight': 0.7
            },
            'praise': {
                'keywords': ['很好', '不错', '厉害', '优秀', '喜欢', '棒', '赞', '完美', '满意'],
                'patterns': [r'.*很好.*', r'.*不错.*', r'.*厉害.*', r'.*优秀.*'],
                'weight': 0.75
            },
            'farewell': {
                'keywords': ['再见', '拜拜', 'bye', '结束', '退出', '关闭', '下次聊'],
                'patterns': [r'.*再见.*', r'.*拜拜.*', r'.*bye.*', r'^结束$'],
                'weight': 0.9
            },
            'small_talk': {
                'keywords': ['天气', '时间', '日期', '今天', '明天', '最近', '怎么样'],
                'patterns': [r'.*天气.*', r'.*时间.*', r'.*日期.*', r'.*今天.*'],
                'weight': 0.6
            },
            'technical': {
                'keywords': ['代码', '编程', '技术', '算法', 'bug', '错误', '调试', '配置'],
                'patterns': [r'.*代码.*', r'.*编程.*', r'.*技术.*', r'.*算法.*'],
                'weight': 0.7
            },
            'personal': {
                'keywords': ['我', '我的', '自己', '个人', '名字', '年龄', '家乡'],
                'patterns': [r'.*我.*', r'.*我的.*', r'.*自己.*'],
                'weight': 0.65
            },
        }

        self.emotion_keywords = {
            'positive': ['开心', '高兴', '喜欢', '满意', '棒', '赞', '优秀', '完美'],
            'negative': ['生气', '愤怒', '失望', '难过', '糟糕', '差', '不好', '讨厌'],
            'neutral': ['知道', '了解', '明白', '清楚', '一般', '还行'],
        }

        self.entity_patterns = {
            'time': r'(\d{1,2}[:：]\d{1,2}|\d+点|\d+分钟|\d+秒)',
            'date': r'(\d+月\d+日|\d{4}年|今天|明天|昨天|下周|上月)',
            'location': r'(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆)',
            'number': r'(\d+)',
            'url': r'(https?://[^\s]+)',
            'email': r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)',
        }

    def classify(self, text: str) -> IntentResult:
        text_lower = text.lower().strip()
        scores = {}

        for intent, config in self.intent_patterns.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in text_lower:
                    score += 1
            for pattern in config['patterns']:
                if re.search(pattern, text_lower):
                    score += 2
            scores[intent] = min(score * config['weight'], 1.0)

        total_score = sum(scores.values()) or 1
        normalized = {k: v / total_score for k, v in scores.items()}
        sorted_intents = sorted(normalized.items(), key=lambda x: x[1], reverse=True)

        entities = self._extract_entities(text)
        emotion = self._analyze_emotion(text)
        primary = sorted_intents[0][0] if sorted_intents else 'unknown'
        conf = sorted_intents[0][1] if sorted_intents else 0.0

        return IntentResult(
            primary_intent=primary,
            confidence=round(conf, 3),
            all_intents=sorted_intents,
            entities=entities,
            emotion=emotion,
            engine="legacy",
        )

    def _extract_entities(self, text: str) -> List[str]:
        entities = []
        for etype, pat in self.entity_patterns.items():
            for m in re.findall(pat, text):
                entities.append(f"{etype}:{m}")
        return entities

    def _analyze_emotion(self, text: str) -> str:
        tl = text.lower()
        pos = sum(1 for w in self.emotion_keywords['positive'] if w in tl)
        neg = sum(1 for w in self.emotion_keywords['negative'] if w in tl)
        if pos > neg:
            return 'positive'
        if neg > pos:
            return 'negative'
        return 'neutral'


def demo():
    classifier = IntentClassifier(engine="casc")

    test_cases = [
        "你好，今天天气怎么样？",
        "请帮我设置闹钟",
        "这个功能太差了，总是出错",
        "你真厉害，回答得很好",
        "再见，下次再聊",
        "我想了解编程技术",
        "帮我写一个排序算法",
        "播放一首歌",
    ]

    print("CASC Intent Classifier Demo\n")
    print("=" * 60)

    results = []
    for text in test_cases:
        result = classifier.classify(text)
        results.append(result)
        desc = classifier.get_intent_description(result.primary_intent)
        print(f"  Input:    {text}")
        print(f"  Intent:   {result.primary_intent} ({desc})")
        print(f"  Conf:     {result.confidence:.4f}")
        print(f"  Engine:   {result.engine} | Exit: L{result.exit_level} | {result.latency_ms:.1f}ms")
        print("-" * 60)

    if results:
        from casc_engine import CASCEngine
        stats = CASCEngine.get_instance().get_stats(results)
        print(f"\nStats: {stats}")


if __name__ == "__main__":
    demo()
