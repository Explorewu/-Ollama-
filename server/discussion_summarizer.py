"""
讨论总结生成器 - DiscussionSummarizer

功能：
1. 基于消息数据提取关键信息、识别讨论主题和结论
2. 支持多种总结类型：全文摘要、主题提取、观点汇总、时间线
3. 使用本地LLM或关键词算法生成总结
4. 支持总结内容的编辑和保存

算法设计：
- 主题提取：基于TF-IDF和关键词共现
- 关键信息提取：基于句子重要度评分
- 观点汇总：基于情感分析和立场分类
- 时间线生成：基于时间戳和事件检测

作者：AI Assistant
日期：2026-02-03
版本：v1.0
"""

import os
import json
import re
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import Counter, defaultdict
import heapq


@dataclass
class DiscussionSummary:
    """讨论总结数据结构"""
    id: str
    conversation_id: str
    created_at: int
    updated_at: int
    
    # 总结内容
    overview: str = ""                    # 总体概述
    key_points: List[str] = field(default_factory=list)  # 关键要点
    topics: List[Dict] = field(default_factory=list)     # 讨论主题
    viewpoints: List[Dict] = field(default_factory=list) # 观点汇总
    timeline: List[Dict] = field(default_factory=list)   # 时间线
    conclusions: List[str] = field(default_factory=list) # 结论建议
    
    # 元数据
    message_count: int = 0
    participant_count: int = 0
    duration_minutes: int = 0
    confidence_score: float = 0.0         # 总结置信度
    
    # 版本控制
    version: int = 1
    is_edited: bool = False
    edited_by: str = ""


@dataclass
class Message:
    """消息数据结构"""
    id: str
    role: str
    content: str
    timestamp: int
    model: str = ""
    character_name: str = ""
    emotions: Dict[str, float] = field(default_factory=dict)


class TextPreprocessor:
    """文本预处理工具"""
    
    # 停用词表
    STOP_WORDS = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '这些', '那些', '这个', '那个', '之', '与', '及', '等', '或', '但', '而', '因为', '所以', '如果', '虽然', '但是', 'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
    }
    
    @classmethod
    def preprocess(cls, text: str) -> str:
        """预处理文本"""
        # 去除特殊字符
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', text)
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """分词（简化版，基于字符和空格）"""
        # 中文按字分词，英文按空格分词
        tokens = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符
                tokens.append(char)
            elif char.isalnum():
                tokens.append(char.lower())
        return tokens
    
    @classmethod
    def extract_keywords(cls, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """提取关键词"""
        text = cls.preprocess(text)
        tokens = cls.tokenize(text)
        
        # 过滤停用词
        tokens = [t for t in tokens if t not in cls.STOP_WORDS and len(t) > 1]
        
        # 统计词频
        word_freq = Counter(tokens)
        total = sum(word_freq.values())
        
        # 计算TF值
        keywords = [(word, freq / total) for word, freq in word_freq.most_common(top_k)]
        
        return keywords


class TFIDFExtractor:
    """TF-IDF特征提取器"""
    
    def __init__(self):
        self.doc_freq = defaultdict(int)  # 文档频率
        self.doc_count = 0
        self.vocab = set()
    
    def fit(self, documents: List[str]):
        """拟合文档集合"""
        self.doc_count = len(documents)
        
        for doc in documents:
            tokens = set(TextPreprocessor.tokenize(TextPreprocessor.preprocess(doc)))
            tokens = tokens - TextPreprocessor.STOP_WORDS
            
            for token in tokens:
                self.doc_freq[token] += 1
                self.vocab.add(token)
    
    def transform(self, document: str) -> Dict[str, float]:
        """转换单个文档为TF-IDF向量"""
        tokens = TextPreprocessor.tokenize(TextPreprocessor.preprocess(document))
        tokens = [t for t in tokens if t not in TextPreprocessor.STOP_WORDS]
        
        # 计算TF
        tf = Counter(tokens)
        total = len(tokens)
        
        # 计算TF-IDF
        tfidf = {}
        for word, freq in tf.items():
            tf_value = freq / total if total > 0 else 0
            # 避免 doc_count 为0导致的 log(0) 错误
            if self.doc_count > 0:
                idf_value = math.log(self.doc_count / (self.doc_freq.get(word, 1) + 1)) + 1
            else:
                idf_value = 1.0  # 默认IDF值
            tfidf[word] = tf_value * idf_value
        
        return tfidf
    
    def extract_top_keywords(self, document: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """提取文档的TopK关键词"""
        tfidf = self.transform(document)
        return heapq.nlargest(top_k, tfidf.items(), key=lambda x: x[1])


class SentenceImportanceScorer:
    """句子重要度评分器"""
    
    def __init__(self):
        self.tfidf = TFIDFExtractor()
    
    def fit(self, documents: List[str]):
        """拟合文档"""
        self.tfidf.fit(documents)
    
    def score_sentences(self, text: str, num_sentences: int = 5) -> List[Tuple[str, float]]:
        """评分并返回TopN重要句子"""
        # 分句
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return []
        
        # 计算每个句子的得分
        sentence_scores = []
        for sent in sentences:
            tfidf = self.tfidf.transform(sent)
            score = sum(tfidf.values()) / (len(sent) + 1)  # 归一化
            sentence_scores.append((sent, score))
        
        # 返回TopN
        return heapq.nlargest(num_sentences, sentence_scores, key=lambda x: x[1])


class TopicExtractor:
    """主题提取器"""
    
    def __init__(self):
        self.tfidf = TFIDFExtractor()
    
    def extract_topics(self, messages: List[Message], num_topics: int = 3) -> List[Dict]:
        """提取讨论主题"""
        if not messages:
            return []
        
        # 合并所有消息内容
        all_text = ' '.join([m.content for m in messages])
        
        # 分句
        sentences = re.split(r'[。！？.!?]', all_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        
        if len(sentences) < num_topics:
            num_topics = len(sentences)
        
        # 使用TF-IDF提取主题句
        self.tfidf.fit(sentences)
        
        topics = []
        for i, (sent, score) in enumerate(self.tfidf.extract_top_keywords(all_text, num_topics)):
            keywords = TextPreprocessor.extract_keywords(sent, 5)
            topics.append({
                'id': f'topic_{i}',
                'title': sent[:30] + '...' if len(sent) > 30 else sent,
                'keywords': [k[0] for k in keywords],
                'score': score,
                'related_messages': self._find_related_messages(messages, sent)
            })
        
        return topics
    
    def _find_related_messages(self, messages: List[Message], topic_text: str) -> List[str]:
        """找到与主题相关的消息ID"""
        related = []
        topic_keywords = set(TextPreprocessor.tokenize(TextPreprocessor.preprocess(topic_text)))
        
        for msg in messages:
            msg_keywords = set(TextPreprocessor.tokenize(TextPreprocessor.preprocess(msg.content)))
            overlap = len(topic_keywords & msg_keywords)
            if overlap > 0:
                related.append(msg.id)
        
        return related[:5]  # 最多返回5条


class ViewpointAnalyzer:
    """观点分析器"""
    
    # 情感词表
    POSITIVE_WORDS = {'同意', '支持', '正确', '好', '不错', '赞同', '赞成', '认可', '肯定', '优秀', '精彩', '有道理', '说得对'}
    NEGATIVE_WORDS = {'反对', '不对', '错误', '不好', '质疑', '怀疑', '不同意', '不赞成', '否定', '错误', '有问题'}
    NEUTRAL_WORDS = {'认为', '觉得', '观点', '看法', '建议', '想法', '意见'}
    
    def analyze_viewpoints(self, messages: List[Message]) -> List[Dict]:
        """分析观点"""
        viewpoints = []
        
        # 按参与者分组
        by_participant = defaultdict(list)
        for msg in messages:
            if msg.role == 'assistant':
                participant = msg.character_name or msg.model
                by_participant[participant].append(msg)
        
        for participant, msgs in by_participant.items():
            # 合并该参与者的所有消息
            combined_text = ' '.join([m.content for m in msgs])
            
            # 分析情感倾向
            sentiment = self._analyze_sentiment(combined_text)
            
            # 提取关键观点
            key_sentences = self._extract_key_sentences(combined_text)
            
            # 提取关键词
            keywords = TextPreprocessor.extract_keywords(combined_text, 8)
            
            viewpoints.append({
                'participant': participant,
                'message_count': len(msgs),
                'sentiment': sentiment,
                'key_points': key_sentences,
                'keywords': [k[0] for k in keywords],
                'stance': self._determine_stance(combined_text)
            })
        
        return viewpoints
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """分析情感"""
        pos_count = sum(1 for w in self.POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in self.NEGATIVE_WORDS if w in text)
        
        total = pos_count + neg_count
        if total == 0:
            return {'label': 'neutral', 'score': 0.5}
        
        score = pos_count / total
        if score > 0.6:
            label = 'positive'
        elif score < 0.4:
            label = 'negative'
        else:
            label = 'neutral'
        
        return {'label': label, 'score': score}
    
    def _extract_key_sentences(self, text: str, num: int = 3) -> List[str]:
        """提取关键句子"""
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        
        # 简单选择包含观点词的句子
        key_sentences = []
        for sent in sentences:
            if any(w in sent for w in self.NEUTRAL_WORDS):
                key_sentences.append(sent)
                if len(key_sentences) >= num:
                    break
        
        return key_sentences
    
    def _determine_stance(self, text: str) -> str:
        """确定立场"""
        pos_count = sum(1 for w in self.POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in self.NEGATIVE_WORDS if w in text)
        
        if pos_count > neg_count:
            return 'supportive'
        elif neg_count > pos_count:
            return 'opposing'
        else:
            return 'neutral'


class TimelineGenerator:
    """时间线生成器"""
    
    def generate_timeline(self, messages: List[Message]) -> List[Dict]:
        """生成讨论时间线"""
        if not messages:
            return []
        
        # 按时间排序
        sorted_msgs = sorted(messages, key=lambda m: m.timestamp)
        
        timeline = []
        current_phase = []
        phase_start_time = sorted_msgs[0].timestamp if sorted_msgs else 0
        
        for i, msg in enumerate(sorted_msgs):
            # 检测阶段变化（时间间隔超过5分钟）
            if i > 0 and msg.timestamp - sorted_msgs[i-1].timestamp > 5 * 60 * 1000:
                # 保存当前阶段
                if current_phase:
                    timeline.append(self._create_phase_entry(current_phase, phase_start_time))
                current_phase = []
                phase_start_time = msg.timestamp
            
            current_phase.append(msg)
        
        # 保存最后一个阶段
        if current_phase:
            timeline.append(self._create_phase_entry(current_phase, phase_start_time))
        
        return timeline
    
    def _create_phase_entry(self, messages: List[Message], start_time: int) -> Dict:
        """创建阶段条目"""
        # 提取阶段主题
        combined_text = ' '.join([m.content for m in messages])
        keywords = TextPreprocessor.extract_keywords(combined_text, 5)
        
        # 确定阶段类型
        phase_type = self._determine_phase_type(messages)
        
        return {
            'start_time': start_time,
            'end_time': messages[-1].timestamp,
            'duration_minutes': (messages[-1].timestamp - start_time) / (60 * 1000),
            'message_count': len(messages),
            'participants': list(set(m.character_name or m.model for m in messages)),
            'keywords': [k[0] for k in keywords],
            'type': phase_type,
            'summary': self._generate_phase_summary(messages)
        }
    
    def _determine_phase_type(self, messages: List[Message]) -> str:
        """确定阶段类型"""
        # 基于消息特征判断阶段类型
        text = ' '.join([m.content for m in messages])
        
        if any(w in text for w in ['问题', '疑问', '为什么', '怎么', '如何']):
            return 'questioning'
        elif any(w in text for w in ['回答', '解答', '解决方案', '建议']):
            return 'answering'
        elif any(w in text for w in ['讨论', '辩论', '不同意见', '但是']):
            return 'debating'
        elif any(w in text for w in ['总结', '结论', '综上所述', '因此']):
            return 'concluding'
        else:
            return 'discussing'
    
    def _generate_phase_summary(self, messages: List[Message]) -> str:
        """生成阶段摘要"""
        # 选择第一条和最后一条消息作为摘要
        if len(messages) >= 2:
            first = messages[0].content[:50]
            last = messages[-1].content[:50]
            return f"从\"{first}...\"到\"{last}...\""
        elif messages:
            return messages[0].content[:100] + '...'
        return ""


class DiscussionSummarizer:
    """讨论总结生成器主类"""
    
    def __init__(self, use_llm: bool = False, llm_config: Dict = None):
        """
        初始化总结器
        
        Args:
            use_llm: 是否使用LLM生成总结
            llm_config: LLM配置（如使用）
        """
        self.use_llm = use_llm
        self.llm_config = llm_config or {}
        
        # 初始化各个组件
        self.text_preprocessor = TextPreprocessor()
        self.tfidf_extractor = TFIDFExtractor()
        self.sentence_scorer = SentenceImportanceScorer()
        self.topic_extractor = TopicExtractor()
        self.viewpoint_analyzer = ViewpointAnalyzer()
        self.timeline_generator = TimelineGenerator()
    
    def generate_summary(self, messages: List[Dict], conversation_id: str) -> DiscussionSummary:
        """
        生成讨论总结
        
        Args:
            messages: 消息列表（字典格式）
            conversation_id: 会话ID
            
        Returns:
            DiscussionSummary对象
        """
        # 转换消息格式
        message_objects = [Message(**m) for m in messages]
        
        if not message_objects:
            return DiscussionSummary(
                id=self._generate_id(),
                conversation_id=conversation_id,
                created_at=int(datetime.now().timestamp() * 1000),
                updated_at=int(datetime.now().timestamp() * 1000)
            )
        
        # 计算基础统计
        message_count = len(message_objects)
        participants = set(m.character_name or m.model for m in message_objects if m.role == 'assistant')
        duration = (max(m.timestamp for m in message_objects) - min(m.timestamp for m in message_objects)) / (60 * 1000)
        
        # 生成总体概述
        overview = self._generate_overview(message_objects)
        
        # 提取关键要点
        key_points = self._extract_key_points(message_objects)
        
        # 提取主题
        topics = self.topic_extractor.extract_topics(message_objects)
        
        # 分析观点
        viewpoints = self.viewpoint_analyzer.analyze_viewpoints(message_objects)
        
        # 生成时间线
        timeline = self.timeline_generator.generate_timeline(message_objects)
        
        # 生成结论
        conclusions = self._generate_conclusions(message_objects, viewpoints)
        
        # 计算置信度
        confidence = self._calculate_confidence(message_objects, topics, viewpoints)
        
        return DiscussionSummary(
            id=self._generate_id(),
            conversation_id=conversation_id,
            created_at=int(datetime.now().timestamp() * 1000),
            updated_at=int(datetime.now().timestamp() * 1000),
            overview=overview,
            key_points=key_points,
            topics=topics,
            viewpoints=viewpoints,
            timeline=timeline,
            conclusions=conclusions,
            message_count=message_count,
            participant_count=len(participants),
            duration_minutes=int(duration),
            confidence_score=confidence
        )
    
    def _generate_overview(self, messages: List[Message]) -> str:
        """生成总体概述"""
        all_text = ' '.join([m.content for m in messages])
        
        # 提取关键句子作为概述
        self.sentence_scorer.fit([m.content for m in messages])
        top_sentences = self.sentence_scorer.score_sentences(all_text, 3)
        
        if top_sentences:
            overview = '。'.join([s[0] for s in top_sentences[:2]])
            return overview + '。'
        
        return "本次讨论涉及多个话题，参与者积极交流观点。"
    
    def _extract_key_points(self, messages: List[Message]) -> List[str]:
        """提取关键要点"""
        all_text = ' '.join([m.content for m in messages])
        
        # 提取重要句子
        self.sentence_scorer.fit([m.content for m in messages])
        top_sentences = self.sentence_scorer.score_sentences(all_text, 5)
        
        return [s[0] for s in top_sentences]
    
    def _generate_conclusions(self, messages: List[Message], viewpoints: List[Dict]) -> List[str]:
        """生成结论建议"""
        conclusions = []
        
        # 基于观点分析生成结论
        supportive = [v for v in viewpoints if v['stance'] == 'supportive']
        opposing = [v for v in viewpoints if v['stance'] == 'opposing']
        
        if supportive and opposing:
            conclusions.append(f"讨论中存在不同观点，{len(supportive)}位参与者持支持态度，{len(opposing)}位持保留意见。")
        elif supportive:
            conclusions.append("参与者普遍达成共识，观点较为一致。")
        elif opposing:
            conclusions.append("讨论中存在较大分歧，需要进一步沟通。")
        
        # 基于消息数量生成结论
        if len(messages) > 50:
            conclusions.append("讨论较为深入，涉及内容广泛。")
        
        return conclusions
    
    def _calculate_confidence(self, messages: List[Message], topics: List[Dict], viewpoints: List[Dict]) -> float:
        """计算总结置信度"""
        score = 0.0
        
        # 消息数量因子
        if len(messages) >= 10:
            score += 0.3
        elif len(messages) >= 5:
            score += 0.2
        elif len(messages) >= 1:
            score += 0.1
        else:
            score += 0.05  # 确保至少有最小值
        
        # 主题清晰度因子
        if topics:
            avg_score = sum(t.get('score', 0) for t in topics) / len(topics)
            score += min(0.3, avg_score)
        
        # 观点多样性因子
        if viewpoints:
            stances = set(v['stance'] for v in viewpoints)
            score += min(0.2, len(stances) * 0.1)
        
        # 消息长度因子
        avg_length = sum(len(m.content) for m in messages) / len(messages) if messages else 0
        if avg_length > 100:
            score += 0.2
        elif avg_length > 50:
            score += 0.1
        elif avg_length > 0:
            score += 0.05  # 确保至少有最小值
        
        # 确保置信度至少为0.1，避免除零错误
        return max(0.1, min(1.0, score))
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import uuid
        return f"summary_{uuid.uuid4().hex[:12]}"
    
    def update_summary(self, summary: DiscussionSummary, updates: Dict) -> DiscussionSummary:
        """
        更新总结内容
        
        Args:
            summary: 原总结对象
            updates: 更新内容
            
        Returns:
            更新后的总结对象
        """
        # 应用更新
        if 'overview' in updates:
            summary.overview = updates['overview']
        if 'key_points' in updates:
            summary.key_points = updates['key_points']
        if 'conclusions' in updates:
            summary.conclusions = updates['conclusions']
        
        # 更新元数据
        summary.updated_at = int(datetime.now().timestamp() * 1000)
        summary.version += 1
        summary.is_edited = True
        summary.edited_by = updates.get('edited_by', 'user')
        
        return summary
    
    def to_dict(self, summary: DiscussionSummary) -> Dict:
        """转换为字典格式"""
        return asdict(summary)
    
    def from_dict(self, data: Dict) -> DiscussionSummary:
        """从字典创建对象"""
        return DiscussionSummary(**data)


# 单例实例
_summarizer = None

def get_summarizer(use_llm: bool = False, llm_config: Dict = None) -> DiscussionSummarizer:
    """获取总结器单例"""
    global _summarizer
    if _summarizer is None:
        _summarizer = DiscussionSummarizer(use_llm, llm_config)
    return _summarizer


if __name__ == '__main__':
    # 测试代码
    test_messages = [
        {
            'id': '1',
            'role': 'user',
            'content': '请大家讨论一下人工智能对未来的影响。',
            'timestamp': 1700000000000,
            'model': '',
            'character_name': 'User'
        },
        {
            'id': '2',
            'role': 'assistant',
            'content': '我认为人工智能将极大地提高生产效率，自动化许多重复性工作。这将使人们有更多时间从事创造性工作。',
            'timestamp': 1700000010000,
            'model': 'qwen2.5:3b',
            'character_name': 'Qwen'
        },
        {
            'id': '3',
            'role': 'assistant',
            'content': '我同意这个观点，但同时也担心AI可能导致部分工作岗位消失，需要社会做好转型准备。',
            'timestamp': 1700000020000,
            'model': 'gemma2:2b',
            'character_name': 'Gemma'
        },
        {
            'id': '4',
            'role': 'assistant',
            'content': '从伦理角度看，我们需要建立完善的AI治理框架，确保技术发展符合人类价值观。',
            'timestamp': 1700000030000,
            'model': 'llama3.2:3b',
            'character_name': 'Llama'
        }
    ]
    
    summarizer = DiscussionSummarizer()
    summary = summarizer.generate_summary(test_messages, 'test-conv')
    
    print("讨论总结生成成功！")
    print(f"概述: {summary.overview}")
    print(f"关键要点: {len(summary.key_points)} 条")
    print(f"主题: {len(summary.topics)} 个")
    print(f"观点: {len(summary.viewpoints)} 个")
    print(f"置信度: {summary.confidence_score:.2f}")
