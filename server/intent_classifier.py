"""
用户意图识别分类器

功能：
- 多类别意图识别（问候、问题、命令、请求等）
- 置信度计算
- 实体提取
- 情感分析辅助

目标准确率：≥92%
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: str
    confidence: float
    all_intents: List[Tuple[str, float]]
    entities: List[str]
    emotion: str
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "primary_intent": self.primary_intent,
            "confidence": self.confidence,
            "all_intents": self.all_intents,
            "entities": self.entities,
            "emotion": self.emotion
        }


class IntentClassifier:
    """用户意图识别器"""
    
    def __init__(self):
        # 意图定义和关键词
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
            }
        }
        
        # 情感关键词
        self.emotion_keywords = {
            'positive': ['开心', '高兴', '喜欢', '满意', '棒', '赞', '优秀', '完美'],
            'negative': ['生气', '愤怒', '失望', '难过', '糟糕', '差', '不好', '讨厌'],
            'neutral': ['知道', '了解', '明白', '清楚', '一般', '还行']
        }
        
        # 实体提取模式
        self.entity_patterns = {
            'time': r'(\d{1,2}[:：]\d{1,2}|\d+点|\d+分钟|\d+秒)',
            'date': r'(\d+月\d+日|\d{4}年|今天|明天|昨天|下周|上月)',
            'location': r'(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆)',
            'number': r'(\d+)',
            'url': r'(https?://[^\s]+)',
            'email': r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)'
        }
    
    def classify(self, text: str) -> IntentResult:
        """识别用户意图及置信度"""
        
        if not text or not text.strip():
            return self._create_empty_result()
        
        text_lower = text.lower().strip()
        scores = {}
        
        # 关键词匹配
        for intent, config in self.intent_patterns.items():
            score = 0
            
            # 关键词匹配
            for keyword in config['keywords']:
                if keyword in text_lower:
                    score += 1
            
            # 正则模式匹配
            for pattern in config['patterns']:
                if re.search(pattern, text_lower):
                    score += 2  # 模式匹配权重更高
            
            # 应用权重
            scores[intent] = min(score * config['weight'], 1.0)
        
        # 归一化并排序
        total_score = sum(scores.values()) or 1
        normalized_scores = {k: v / total_score for k, v in scores.items()}
        sorted_intents = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 提取实体
        entities = self._extract_entities(text)
        
        # 分析情感
        emotion = self._analyze_emotion(text)
        
        # 创建结果
        primary_intent = sorted_intents[0][0] if sorted_intents else 'unknown'
        confidence = sorted_intents[0][1] if sorted_intents else 0.0
        
        return IntentResult(
            primary_intent=primary_intent,
            confidence=round(confidence, 3),
            all_intents=sorted_intents,
            entities=entities,
            emotion=emotion
        )
    
    def _extract_entities(self, text: str) -> List[str]:
        """提取文本中的实体"""
        
        entities = []
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text)
            for match in matches:
                entities.append(f"{entity_type}:{match}")
        
        return entities
    
    def _analyze_emotion(self, text: str) -> str:
        """分析文本情感"""
        
        text_lower = text.lower()
        positive_count = sum(1 for word in self.emotion_keywords['positive'] if word in text_lower)
        negative_count = sum(1 for word in self.emotion_keywords['negative'] if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _create_empty_result(self) -> IntentResult:
        """创建空结果"""
        
        return IntentResult(
            primary_intent='unknown',
            confidence=0.0,
            all_intents=[],
            entities=[],
            emotion='neutral'
        )
    
    def get_intent_description(self, intent: str) -> str:
        """获取意图描述"""
        
        descriptions = {
            'greeting': '问候意图',
            'question': '问题意图',
            'command': '命令意图',
            'request': '请求意图',
            'complaint': '投诉意图',
            'praise': '表扬意图',
            'farewell': '告别意图',
            'small_talk': '闲聊意图',
            'technical': '技术意图',
            'personal': '个人意图',
            'unknown': '未知意图'
        }
        
        return descriptions.get(intent, '未知意图')
    
    def validate_confidence(self, result: IntentResult, threshold: float = 0.3) -> bool:
        """验证置信度是否达标"""
        
        return result.confidence >= threshold
    
    def get_statistics(self) -> Dict:
        """获取分类器统计信息"""
        
        return {
            'total_intents': len(self.intent_patterns),
            'intent_list': list(self.intent_patterns.keys()),
            'entity_types': list(self.entity_patterns.keys()),
            'emotion_types': list(self.emotion_keywords.keys())
        }


# 使用示例
def demo_intent_classifier():
    """演示意图识别功能"""
    
    classifier = IntentClassifier()
    
    test_cases = [
        "你好，今天天气怎么样？",
        "请帮我设置闹钟",
        "这个功能太差了，总是出错",
        "你真厉害，回答得很好",
        "再见，下次再聊",
        "我想了解编程技术",
        "我的名字叫小明"
    ]
    
    print("🧠 意图识别演示\n")
    
    for text in test_cases:
        result = classifier.classify(text)
        
        print(f"输入: {text}")
        print(f"主要意图: {result.primary_intent} ({classifier.get_intent_description(result.primary_intent)})")
        print(f"置信度: {result.confidence:.3f}")
        print(f"情感: {result.emotion}")
        print(f"实体: {result.entities}")
        
        # 显示所有意图
        print("所有意图:")
        for intent, score in result.all_intents[:3]:  # 显示前3个
            print(f"  - {intent}: {score:.3f}")
        
        print("-" * 50)
    
    # 显示统计信息
    print("\n📊 分类器统计:")
    stats = classifier.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    demo_intent_classifier()