# -*- coding: utf-8 -*-
"""
RAG 检索增强模块

功能：
- 建立本地知识库索引
- 语义检索相关文档
- 增强模型回答质量
- 支持多种数据源

使用方式：
    # 建立索引
    python rag_system.py --build --data "data/premium_classics/raw"
    
    # 检索测试
    python rag_system.py --query "什么是正义？"
    
    # 集成到模型
    from rag_system import RAGRetriever
    retriever = RAGRetriever()
    context = retriever.retrieve("用户问题", top_k=5)

依赖安装：
    pip install sentence-transformers faiss-cpu rank_bm25
"""

import os

import re
import json
import hashlib
import logging
import time
import argparse
import math
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import pickle
import base64

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rag_system.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    logger.warning("Cross-Encoder 未安装，重排序功能不可用")


def load_config(config_path: str = None) -> Dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，默认为 config.yaml
        
    Returns:
        配置字典
    """
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'
    else:
        config_path = Path(config_path)
    
    default_config = {
        'data_dir': './data/premium_classics',
        'index_dir': './data/rag_index',
        'chunk_size': 512,
        'chunk_overlap': 50,
        'top_k': 8,
        'score_threshold': 0.25,
        'semantic_weight': 0.7,
        'keyword_weight': 0.3,
        'cache_size': 1000,
        'cache_ttl': 7200,
        'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2',
        'reranker_model': 'cross-encoder/ms-marco-MiniLM-L6-v2',
        'use_fusion': True,
        'use_cache': True,
        'use_rerank': True,
        'eager_load': False
    }
    
    if not config_path.exists():
        logger.info(f"配置文件不存在，使用默认配置: {config_path}")
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            logger.info("配置文件为空，使用默认配置")
            return default_config
        
        rag_config = config.get('rag', {})
        merged_config = {**default_config, **rag_config}
        logger.info(f"配置加载成功: {config_path}")
        return merged_config
    except Exception as e:
        logger.warning(f"配置加载失败，使用默认配置: {e}")
        return default_config


class RAGConfig:
    """RAG 配置管理器"""
    
    DEFAULT_CONFIG = {
        'data_dir': './data/premium_classics',
        'index_dir': './data/rag_index',
        'chunk_size': 512,
        'chunk_overlap': 50,
        'top_k': 8,
        'score_threshold': 0.25,
        'semantic_weight': 0.7,
        'keyword_weight': 0.3,
        'cache_size': 1000,
        'cache_ttl': 7200,
        'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2',
        'reranker_model': 'cross-encoder/ms-marco-MiniLM-L6-v2',
        'use_fusion': True,
        'use_cache': True,
        'use_rerank': True,
        'eager_load': False
    }
    
    def __init__(self, config_path: str = None, **kwargs):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
            **kwargs: 覆盖配置的参数
        """
        self._config = self._load_config(config_path)
        self._merge_params(kwargs)
    
    def _load_config(self, config_path: str) -> Dict:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            logger.info(f"配置文件不存在，使用默认配置: {config_path}")
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if config is None:
                logger.info("配置文件为空，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
            
            rag_config = config.get('rag', {})
            merged_config = {**self.DEFAULT_CONFIG, **rag_config}
            logger.info(f"配置加载成功: {config_path}")
            return merged_config
        except Exception as e:
            logger.warning(f"配置加载失败，使用默认配置: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _merge_params(self, params: Dict):
        """
        合并参数，覆盖配置文件
        
        Args:
            params: 参数字典
        """
        for key, value in params.items():
            if value is not None:
                self._config[key] = value
    
    def get(self, key: str, default=None):
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self._config.get(key, default)
    
    def to_dict(self) -> Dict:
        """
        转换为字典
        
        Returns:
            配置字典的副本
        """
        return self._config.copy()


class TextChunker:
    """文本分块器"""
    
    _CLEAN_PATTERNS = {
        r'\r\n': '\n',
        r'\n{3,}': '\n\n',
        r'[ \t]+': ' ',
        r'　+': '',
        r'\xa0': ' ',
    }
    _CLEAN_COMPILED = {re.compile(p): r for p, r in _CLEAN_PATTERNS.items()}
    _SENTENCE_PATTERN = re.compile(r'[。！？；.!?;]+')
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(
        self,
        text: str,
        source: str = '',
        title: str = ''
    ) -> List[Dict]:
        """
        将文本分块
        
        Args:
            text: 原始文本
            source: 来源标识
            title: 文档标题
            
        Returns:
            分块列表
        """
        if not text or len(text) < 50:
            return []
        
        cleaned_text = self._clean_text(text)
        
        sentences = self._split_into_sentences(cleaned_text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size > self.chunk_size:
                if current_chunk:
                    chunk_text = ''.join(current_chunk)
                    
                    if len(chunk_text) >= 50:
                        chunk = self._create_chunk(
                            chunk_text,
                            source,
                            title,
                            len(chunks)
                        )
                        if chunk:
                            chunks.append(chunk)
                    
                    overlap_start = max(0, len(current_chunk) - self.chunk_overlap // 10)
                    current_chunk = current_chunk[overlap_start:]
                    current_size = sum(len(s) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        if current_chunk:
            chunk_text = ''.join(current_chunk)
            if len(chunk_text) >= 50:
                chunk = self._create_chunk(
                    chunk_text,
                    source,
                    title,
                    len(chunks)
                )
                if chunk:
                    chunks.append(chunk)
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清洗文本（使用预编译正则）"""
        cleaned = text
        
        for pattern, replacement in self._CLEAN_COMPILED.items():
            cleaned = pattern.sub(replacement, cleaned)
        
        return cleaned.strip()
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """分割句子（使用预编译正则）"""
        sentences = self._SENTENCE_PATTERN.split(text)
        
        filtered = []
        for s in sentences:
            s = s.strip()
            if s and len(s) > 5:
                filtered.append(s)
        
        return filtered
    
    def _create_chunk(
        self,
        text: str,
        source: str,
        title: str,
        chunk_id: int
    ) -> Dict:
        """创建分块"""
        content = text[:self.chunk_size]

        if len(content) < 50:
            return None

        preview_start = max(0, len(content) - 200)
        preview_end = min(len(content), 200)
        preview = content[preview_start:preview_end]

        chunk_hash = hashlib.md5(
            (content + source + str(chunk_id)).encode()
        ).hexdigest()[:16]

        return {
            'id': chunk_hash,
            'content': content,
            'source': source,
            'title': title,
            'chunk_id': chunk_id,
            'preview': preview,
            'char_count': len(content),
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'chunk_size': self.chunk_size,
            }
        }


class FileEncodingReader:
    """文件编码读取器
    
    自动检测文件编码并读取文件内容，支持多种常见编码格式。
    """
    
    DEFAULT_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    
    def __init__(self, encodings: List[str] = None):
        """
        初始化文件编码读取器
        
        Args:
            encodings: 支持的编码列表，默认为常见中文编码
        """
        self.encodings = encodings or self.DEFAULT_ENCODINGS
    
    def read(self, file_path: Path) -> Optional[str]:
        """
        自动检测文件编码并读取
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容，失败返回 None
        """
        for encoding in self.encodings:
            try:
                content = file_path.read_text(encoding=encoding)
                if content.strip():
                    return content
            except (UnicodeDecodeError, IOError):
                continue
        
        logger.warning(f"无法读取文件（编码不支持）: {file_path.name}")
        return None


class IndexPathManager:
    """索引文件路径管理器
    
    统一管理所有 RAG 索引文件的路径和命名规范，避免硬编码路径分散在多个类中。
    
    Attributes:
        index_dir: 索引目录的 Path 对象
    """
    
    def __init__(self, index_dir: str):
        """
        初始化路径管理器
        
        Args:
            index_dir: 索引目录路径
        """
        self.index_dir = Path(index_dir)
    
    @property
    def faiss_index(self) -> Path:
        """FAISS 向量索引文件路径"""
        return self.index_dir / 'faiss_index.bin'
    
    @property
    def chunks(self) -> Path:
        """文档分块数据文件路径"""
        return self.index_dir / 'chunks.pkl'
    
    @property
    def bm25_docs(self) -> Path:
        """BM25 索引数据文件路径"""
        return self.index_dir / 'bm25_docs.pkl'
    
    def ensure_dir(self):
        """确保索引目录存在"""
        self.index_dir.mkdir(parents=True, exist_ok=True)


class LRUCache:
    """LRU 缓存（带 TTL 过期和统计）"""
    
    def __init__(self, capacity: int = 1000, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.order = []
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def _make_key(self, query: str, top_k: int) -> str:
        """生成缓存键"""
        return f"{hash(query)}:{top_k}"
    
    def get(self, query: str, top_k: int) -> Optional[List[Dict]]:
        """获取缓存"""
        key = self._make_key(query, top_k)
        
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                self.order.remove(key)
                self.order.append(key)
                self._hits += 1
                return data
            else:
                del self.cache[key]
                self.order.remove(key)
        self._misses += 1
        return None
    
    def set(self, query: str, top_k: int, value: List[Dict]):
        """设置缓存"""
        key = self._make_key(query, top_k)
        
        if key in self.cache:
            self.order.remove(key)
        elif len(self.order) >= self.capacity:
            oldest_key = self.order.pop(0)
            if oldest_key in self.cache:
                del self.cache[oldest_key]
                self._evictions += 1
        
        self.cache[key] = (value, time.time())
        self.order.append(key)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.order.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def invalidate(self, query: str, top_k: int = None):
        """使缓存失效"""
        if top_k is None:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{hash(query)}:")]
        else:
            key = self._make_key(query, top_k)
            keys_to_remove = [key] if key in self.cache else []
        
        for key in keys_to_remove:
            if key in self.cache:
                del self.cache[key]
            if key in self.order:
                self.order.remove(key)
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total * 100 if total > 0 else 0.0
        return {
            'hits': self._hits,
            'misses': self._misses,
            'evictions': self._evictions,
            'size': len(self.cache),
            'hit_rate_percent': round(hit_rate, 2)
        }


class SemanticRetriever:
    """语义检索器"""
    
    def __init__(
        self,
        model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2',
        top_k: int = 5,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        index_path: str = './data/rag_index'
    ):
        self.model = None
        self.model_name = model_name
        self.top_k = top_k
        self.documents = []
        self.chunk_map = {}
        self._index_cache = None
        self._index_path = None
        self._cache = LRUCache(capacity=cache_size, ttl_seconds=cache_ttl)
        self._default_index_path = index_path
        self.path_manager = IndexPathManager(index_path)
    
    def load_model(self):
        """加载模型"""
        if self.model is None:
            logger.info(f"加载语义模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("模型加载完成")
    
    def build_index(
        self,
        chunks: List[Dict],
        index_path: str = None
    ):
        """
        构建向量索引
        
        Args:
            chunks: 分块列表
            index_path: 索引保存路径，如果为 None 则使用初始化时的路径
        """
        self.load_model()
        
        if not chunks:
            logger.warning("没有分块数据")
            return
        
        if index_path:
            self.path_manager = IndexPathManager(index_path)
        
        self.path_manager.ensure_dir()
        
        logger.info(f"构建索引：{len(chunks)} 个分块")
        
        contents = [chunk['content'] for chunk in chunks]
        
        logger.info("生成向量...")
        embeddings = self.model.encode(
            contents,
            show_progress_bar=True,
            batch_size=32
        )
        
        embedding_array = np.array(embeddings).astype('float32')
        
        dimension = embedding_array.shape[1]
        
        index = faiss.IndexFlatIP(dimension)
        index.add(embedding_array)
        
        faiss.write_index(index, str(self.path_manager.faiss_index))
        
        self.documents = contents
        self.chunk_map = {i: chunks[i] for i in range(len(chunks))}
        
        with open(self.path_manager.chunks, 'wb') as f:
            pickle.dump(chunks, f)
        
        logger.info(f"索引已保存：{self.path_manager.index_dir}")
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        score_threshold: float = 0.3,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            score_threshold: 相似度阈值
            use_cache: 是否使用缓存
            
        Returns:
            相关文档列表
        """
        self.load_model()
        
        if not self.documents:
            logger.warning("索引为空，请先构建索引")
            return []
        
        top_k = top_k or self.top_k
        
        if use_cache:
            cached_result = self._cache.get(query, top_k)
            if cached_result is not None:
                logger.debug(f"缓存命中: {query[:30]}...")
                return [r for r in cached_result if r['similarity_score'] >= score_threshold]
        
        results = self._search_index(query, top_k)
        
        results = [r for r in results if r['similarity_score'] >= score_threshold]
        
        if use_cache:
            self._cache.set(query, top_k, results)
        
        return results
    
    def _search_index(self, query: str, top_k: int) -> List[Dict]:
        """
        执行向量搜索（内部方法）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            搜索结果列表
        """
        query_embedding = self.model.encode([query])
        query_array = np.array(query_embedding).astype('float32')

        index_file = str(self.path_manager.faiss_index)
        if self._index_cache is None or self._index_path != index_file:
            try:
                self._index_cache = faiss.read_index(index_file)
                self._index_path = index_file
            except RuntimeError as e:
                logger.error(f"加载faiss索引失败: {e}")
                raise RuntimeError(f"索引文件不存在或损坏，请重新构建索引: {index_file}")

        scores, indices = self._index_cache.search(query_array, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunk_map):
                chunk = self.chunk_map[idx].copy()
                chunk['similarity_score'] = float(score)
                results.append(chunk)
        
        return results
    
    def retrieve_with_expansion(
        self,
        query: str,
        top_k: int = None,
        num_expansions: int = 3,
        score_threshold: float = 0.3,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        检索（查询扩展版）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            num_expansions: 扩展数量
            score_threshold: 相似度阈值
            use_cache: 是否使用缓存
            
        Returns:
            相关文档列表
        """
        self.load_model()
        
        if not self.documents:
            logger.warning("索引为空，请先构建索引")
            return []
        
        top_k = top_k or self.top_k
        
        expanded_queries = self._expand_query(query, num_expansions)
        
        all_results = []
        seen_ids = set()
        
        for q in expanded_queries:
            if use_cache:
                cached_result = self._cache.get(q, top_k)
                if cached_result is not None:
                    logger.debug(f"扩展查询缓存命中: {q[:30]}...")
                    for r in cached_result:
                        if r['id'] not in seen_ids:
                            seen_ids.add(r['id'])
                            all_results.append(r)
                    continue
            
            results = self._search_index(q, top_k)
            
            for r in results:
                if r['id'] not in seen_ids:
                    seen_ids.add(r['id'])
                    all_results.append(r)
        
        if use_cache and all_results:
            self._cache.set(query, top_k, all_results)
        
        filtered_results = [r for r in all_results if r['similarity_score'] >= score_threshold]
        filtered_results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return filtered_results[:top_k]
    
    def _expand_query(self, query: str, num: int) -> List[str]:
        """查询扩展"""
        expansions = [query]
        
        keywords = re.findall(r'[\w]+', query.lower())
        keywords = [w for w in keywords if len(w) > 2]
        
        if len(keywords) >= 2:
            expansions.append(' '.join(keywords[:3]))
        
        if keywords:
            expansions.append(keywords[0])
        
        return expansions[:num + 1]


class Reranker:
    """Cross-Encoder 重排序器"""
    
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        self.model_name = model_name
        self.model = None
    
    def _load_model(self):
        """懒加载模型"""
        if not CROSS_ENCODER_AVAILABLE:
            logger.warning("Cross-Encoder 未安装，跳过重排序")
            return
        
        if self.model is None:
            logger.info(f"加载重排序模型: {self.model_name}")
            try:
                self.model = CrossEncoder(self.model_name, max_length=512)
                logger.info("重排序模型加载完成")
            except Exception as e:
                logger.warning(f"重排序模型加载失败: {e}")
                self.model = None
    
    def rerank(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        对检索结果重排序
        
        Args:
            query: 查询文本
            results: 检索结果列表
            top_k: 返回数量
            
        Returns:
            重排序后的结果
        """
        self._load_model()

        if not self.model or not results:
            return results[:top_k]
        
        if len(results) <= top_k:
            return results
        
        try:
            pairs = [[query, r['content']] for r in results]
            scores = self.model.predict(pairs)
            
            for i, r in enumerate(results):
                r['rerank_score'] = float(scores[i])
            
            results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            return results[:top_k]
        except Exception as e:
            logger.warning(f"重排序失败: {e}")
            return results[:top_k]


class KeywordRetriever:
    """关键词检索器（BM25）"""
    
    def __init__(self, k1: float = 1.2, b: float = 0.75, bm25_max_score: float = 10.0):
        self.documents = []
        self.doc_map = {}
        self.k1 = k1
        self.b = b
        self.bm25_max_score = bm25_max_score
        self._idf = {}
        self._doc_lengths = []
        self._avg_doc_length = 0
        self._num_docs = 0
        self.path_manager = None
    
    def build_index(self, chunks: List[Dict], index_path: str = None):
        """
        构建 BM25 索引（预计算 IDF 和文档长度）
        
        Args:
            chunks: 分块列表
            index_path: 索引保存路径，如果为 None 则使用初始化时的路径
        """
        if not chunks:
            return
        
        if index_path:
            self.path_manager = IndexPathManager(index_path)
        
        if self.path_manager is None:
            raise ValueError("必须先指定 index_path 或调用 build_index 时传入 index_path")
        
        self.path_manager.ensure_dir()
        
        self.documents = [chunk['content'] for chunk in chunks]
        self.doc_map = {i: chunks[i] for i in range(len(chunks))}
        
        self._num_docs = len(self.documents)
        self._doc_lengths = [len(doc) for doc in self.documents]
        self._avg_doc_length = sum(self._doc_lengths) / self._num_docs
        
        term_doc_freq = defaultdict(set)
        
        for i, doc in enumerate(self.documents):
            terms = set(re.findall(r'[\w]+', doc.lower()))
            for term in terms:
                term_doc_freq[term].add(i)
        
        self._idf = {}
        for term, docs in term_doc_freq.items():
            n_t = len(docs)
            idf = math.log((self._num_docs - n_t + 0.5) / (n_t + 0.5) + 1)
            self._idf[term] = idf
        
        index_data = {
            'documents': self.documents,
            'doc_map': self.doc_map,
            'idf': self._idf,
            'doc_lengths': self._doc_lengths,
            'avg_doc_length': self._avg_doc_length,
            'num_docs': self._num_docs,
            'k1': self.k1,
            'b': self.b,
            'bm25_max_score': self.bm25_max_score
        }
        
        with open(self.path_manager.bm25_docs, 'wb') as f:
            pickle.dump(index_data, f)
        
        logger.info(f"BM25 索引已保存：{self._num_docs} 篇文档，{len(self._idf)} 个词项")
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """检索（使用BM25算法）"""
        if not self.documents:
            return []
        
        query_terms = re.findall(r'[\w]+', query.lower())
        if not query_terms:
            return []
        
        scores = [0.0] * self._num_docs
        
        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            doc_len = self._doc_lengths[i]
            
            for term in query_terms:
                if term in self._idf:
                    tf = doc_lower.count(term)
                    if tf > 0:
                        tf_saturation = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_length))
                        scores[i] += self._idf[term] * tf_saturation
        
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score in indexed_scores[:top_k]:
            if idx in self.doc_map and score > 0:
                chunk = self.doc_map[idx].copy()
                chunk['bm25_score'] = score
                results.append(chunk)
        
        return results


class HybridRetriever:
    """混合检索器（语义 + 关键词 + 重排序）"""
    
    def __init__(
        self,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = 5,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        embedding_model: str = 'paraphrase-multilingual-MiniLM-L12-v2',
        reranker_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        use_rerank: bool = True,
        index_path: str = './data/rag_index'
    ):
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.top_k = top_k
        self.use_rerank = use_rerank
        self.index_built = False
        self._cache = LRUCache(capacity=cache_size, ttl_seconds=cache_ttl)
        self._num_retrievals = 0
        self._total_time_ms = 0.0
        self._last_query_time_ms = 0.0
        
        self.path_manager = IndexPathManager(index_path)
        
        if semantic_weight > 0:
            self.semantic_retriever = SemanticRetriever(
                model_name=embedding_model,
                top_k=top_k * 2,
                cache_size=cache_size,
                cache_ttl=cache_ttl,
                index_path=index_path
            )
            self.semantic_retriever.path_manager = self.path_manager
        else:
            self.semantic_retriever = None
            logger.info("语义检索已禁用，仅使用关键词检索")
        
        self.keyword_retriever = KeywordRetriever()
        self.keyword_retriever.path_manager = self.path_manager
        
        if use_rerank:
            self.reranker = Reranker(model_name=reranker_model)
        else:
            self.reranker = None
    
    def build_index(
        self,
        chunks: List[Dict],
        index_path: str = None
    ):
        """
        构建索引
        
        Args:
            chunks: 分块列表
            index_path: 索引保存路径，如果为 None 则使用初始化时的路径
        """
        if index_path:
            self.path_manager = IndexPathManager(index_path)
            self.semantic_retriever.path_manager = self.path_manager
            self.keyword_retriever.path_manager = self.path_manager
        
        self.path_manager.ensure_dir()
        
        if self.semantic_retriever is not None:
            self.semantic_retriever.build_index(chunks)
        else:
            logger.info("跳过语义索引构建（已禁用）")
        
        self.keyword_retriever.build_index(chunks)
        
        self.index_built = True
        logger.info("混合索引构建完成")
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_fusion: bool = True,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        混合检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            use_fusion: 是否使用分数融合
            use_cache: 是否使用缓存
            
        Returns:
            检索结果
        """
        if not self.index_built:
            logger.warning("索引未构建")
            return []
        
        top_k = top_k or self.top_k
        
        if use_cache:
            cached = self._cache.get(query, top_k)
            if cached is not None:
                logger.debug(f"Hybrid缓存命中: {query[:30]}...")
                self._num_retrievals += 1
                self._last_query_time_ms = 0.0
                return cached
        
        start_time = time.perf_counter()
        
        # 语义检索
        if self.semantic_retriever is not None:
            semantic_results = self.semantic_retriever.retrieve(query, top_k=top_k)
        else:
            semantic_results = []
        
        # 关键词检索
        keyword_results = self.keyword_retriever.retrieve(query, top_k=top_k)
        
        if not use_fusion:
            combined = semantic_results + keyword_results
            seen = set()
            unique = []
            for r in combined:
                if r['id'] not in seen:
                    seen.add(r['id'])
                    unique.append(r)
            unique.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            final_results = unique[:top_k]
            
            if use_cache:
                self._cache.set(query, top_k, final_results)
            
            elapsed = (time.perf_counter() - start_time) * 1000
            self._num_retrievals += 1
            self._total_time_ms += elapsed
            self._last_query_time_ms = elapsed
            return final_results
        
        score_map = {}
        
        for r in semantic_results:
            score = r.get('similarity_score', 0)
            normalized_score = (score + 1) / 2
            fused_score = normalized_score * self.semantic_weight
            score_map[r['id']] = {
                'chunk': r,
                'score': fused_score
            }
        
        for r in keyword_results:
            if r['id'] in score_map:
                bm25_score = r.get('bm25_score', 0)
                normalized_bm25 = min(bm25_score / self.keyword_retriever.bm25_max_score, 1.0)
                score_map[r['id']]['score'] += normalized_bm25 * self.keyword_weight
            else:
                bm25_score = r.get('bm25_score', 0)
                normalized_bm25 = min(bm25_score / self.keyword_retriever.bm25_max_score, 1.0)
                score_map[r['id']] = {
                    'chunk': r,
                    'score': normalized_bm25 * self.keyword_weight
                }
        
        results = [item['chunk'] for item in score_map.values()]
        results.sort(key=lambda x: score_map[x['id']]['score'], reverse=True)
        final_results = results[:top_k]
        
        if self.use_rerank and self.reranker and final_results:
            final_results = self.reranker.rerank(query, final_results, top_k)
        
        if use_cache:
            self._cache.set(query, top_k, final_results)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        self._num_retrievals += 1
        self._total_time_ms += elapsed
        self._last_query_time_ms = elapsed
        
        return final_results
    
    def get_stats(self) -> Dict:
        """获取检索统计"""
        avg_time = self._total_time_ms / self._num_retrievals if self._num_retrievals > 0 else 0.0
        cache_stats = self._cache.get_stats()
        return {
            'num_retrievals': self._num_retrievals,
            'total_time_ms': round(self._total_time_ms, 2),
            'avg_time_ms': round(avg_time, 2),
            'last_query_time_ms': round(self._last_query_time_ms, 2),
            'cache': cache_stats
        }


class ContextBuilder:
    """上下文构建器
    
    将检索结果格式化为上下文字符串，支持自定义最大字符数限制。
    """
    
    def __init__(self, max_chars: int = 3000):
        """
        初始化上下文构建器
        
        Args:
            max_chars: 默认最大字符数
        """
        self.max_chars = max_chars
    
    def build(self, results: List[Dict], max_chars: int = None) -> str:
        """
        构建上下文
        
        Args:
            results: 检索结果列表
            max_chars: 最大字符数，覆盖默认值
            
        Returns:
            上下文字符串
        """
        max_chars = max_chars or self.max_chars
        context_parts = []
        total_chars = 0
        
        for r in results:
            source = r.get('title', r.get('source', 'Unknown'))
            content = r.get('content', '')
            
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
                    context_parts.append(f"[来源: {source}]\n{content[:remaining]}")
                break
            
            context_parts.append(f"[来源: {source}]\n{content}")
            total_chars += len(content)
        
        return '\n\n'.join(context_parts)


class PromptAugmenter:
    """提示词增强器
    
    将上下文和用户查询组装成增强后的提示词，支持自定义模板。
    """
    
    DEFAULT_TEMPLATE = """## 相关参考资料

{context}

## 用户问题

{query}

请根据以上参考资料回答用户问题。"""
    
    TEMPLATE_WITH_SYSTEM = """{system_prompt}

## 相关参考资料

{context}

## 用户问题

{query}

请根据以上参考资料回答用户问题。如果参考资料中没有相关信息，请基于你的知识库回答。"""
    
    def __init__(self, template: str = None, template_with_system: str = None):
        """
        初始化提示词增强器
        
        Args:
            template: 默认提示词模板
            template_with_system: 包含系统提示词的模板
        """
        self.template = template or self.DEFAULT_TEMPLATE
        self.template_with_system = template_with_system or self.TEMPLATE_WITH_SYSTEM
    
    def augment(
        self,
        query: str,
        context: str,
        system_prompt: str = None
    ) -> str:
        """
        增强提示词
        
        Args:
            query: 用户查询
            context: 上下文
            system_prompt: 系统提示词
            
        Returns:
            增强后的提示词
        """
        if not context:
            return query
        
        if system_prompt:
            return self.template_with_system.format(
                system_prompt=system_prompt,
                context=context,
                query=query
            )
        
        return self.template.format(context=context, query=query)


class IndexManager:
    """索引管理器
    
    负责索引的构建、加载、重载和资源管理，封装索引相关的所有操作。
    """
    
    def __init__(self, config: RAGConfig):
        """
        初始化索引管理器
        
        Args:
            config: RAG 配置对象
        """
        self.config = config
        self.path_manager = IndexPathManager(str(config.get('index_dir')))
        self.chunker = TextChunker(
            chunk_size=config.get('chunk_size'),
            chunk_overlap=config.get('chunk_overlap')
        )
        self.retriever = HybridRetriever(
            semantic_weight=config.get('semantic_weight'),
            keyword_weight=config.get('keyword_weight'),
            top_k=config.get('top_k'),
            cache_size=config.get('cache_size'),
            cache_ttl=config.get('cache_ttl'),
            embedding_model=config.get('embedding_model'),
            reranker_model=config.get('reranker_model'),
            use_rerank=config.get('use_rerank'),
            index_path=str(config.get('index_dir'))
        )
        self.file_reader = FileEncodingReader()
        self._initialized = False
    
    def build_index(self):
        """构建索引"""
        self.path_manager.ensure_dir()
        chunks = []
        raw_dir = Path(self.config.get('data_dir')) / 'raw'
        
        if raw_dir.exists():
            for file_path in raw_dir.glob('*.txt'):
                content = self.file_reader.read(file_path)
                
                if content is None:
                    continue
                
                title = file_path.stem.replace('_', ' ')
                
                file_chunks = self.chunker.chunk_text(
                    content,
                    source=str(file_path),
                    title=title
                )
                
                chunks.extend(file_chunks)
                logger.info(f"分块: {file_path.name} -> {len(file_chunks)} 块")
        
        if chunks:
            self.retriever.build_index(chunks)
            logger.info(f"索引构建完成：{len(chunks)} 个分块")
        else:
            logger.warning("没有找到分块数据")
    
    def load_index(self):
        """加载已有索引"""
        if self.retriever.semantic_retriever is not None:
            self.retriever.semantic_retriever.load_model()
        else:
            logger.info("跳过语义模型加载（已禁用）")
        
        chunks_path = self.path_manager.chunks
        bm25_path = self.path_manager.bm25_docs
        
        if not chunks_path.exists():
            raise RuntimeError(f"索引文件不存在: {chunks_path}")
        
        try:
            with open(chunks_path, 'rb') as f:
                chunks = pickle.load(f)
        except (pickle.UnpicklingError, EOFError, IOError) as e:
            logger.error(f"加载chunks.pkl失败: {e}")
            raise RuntimeError(f"索引文件损坏: {chunks_path}")
        
        if self.retriever.semantic_retriever is not None:
            try:
                self.retriever.semantic_retriever.documents = [c['content'] for c in chunks]
                self.retriever.semantic_retriever.chunk_map = {
                    i: chunks[i] for i in range(len(chunks))
                }
            except (IndexError, KeyError) as e:
                logger.error(f"索引数据结构异常: {e}")
                raise RuntimeError("索引数据结构损坏")
        
        if bm25_path.exists():
            try:
                with open(bm25_path, 'rb') as f:
                    data = pickle.load(f)
                self.retriever.keyword_retriever.documents = data['documents']
                self.retriever.keyword_retriever.doc_map = data['doc_map']
                self.retriever.keyword_retriever._idf = data.get('idf', {})
                self.retriever.keyword_retriever._doc_lengths = data.get('doc_lengths', [])
                self.retriever.keyword_retriever._avg_doc_length = data.get('avg_doc_length', 0)
                self.retriever.keyword_retriever._num_docs = data.get('num_docs', 0)
                self.retriever.keyword_retriever.k1 = data.get('k1', 1.2)
                self.retriever.keyword_retriever.b = data.get('b', 0.75)
                self.retriever.keyword_retriever.bm25_max_score = data.get('bm25_max_score', 10.0)
            except (pickle.UnpicklingError, EOFError, IOError, KeyError) as e:
                logger.warning(f"BM25索引加载失败，将仅使用语义检索: {e}")
                self.retriever.keyword_retriever.documents = []
                self.retriever.keyword_retriever.doc_map = {}
        else:
            logger.warning(f"BM25索引文件不存在: {bm25_path}，将仅使用语义检索")
            self.retriever.keyword_retriever.documents = []
            self.retriever.keyword_retriever.doc_map = {}
        
        self.retriever.index_built = True
        logger.info(f"索引加载完成: {len(chunks)} 个分块")
    
    def reload(self, force_rebuild: bool = False):
        """
        重新加载索引
        
        Args:
            force_rebuild: 是否强制重新构建索引
        """
        logger.info("开始重新加载索引...")
        
        self._clear_cache()
        
        self.retriever.semantic_retriever._index_cache = None
        self.retriever.semantic_retriever._index_path = None
        self.retriever.index_built = False
        self._initialized = False
        
        index_dir = Path(self.config.get('index_dir'))
        if force_rebuild or not index_dir.exists():
            logger.info("强制重新构建索引...")
            self.build_index()
        else:
            logger.info("重新加载已有索引...")
            self.load_index()
        
        logger.info("索引重载完成")
    
    def _clear_cache(self):
        """清空所有缓存"""
        if self.retriever.semantic_retriever is not None:
            self.retriever.semantic_retriever._cache.clear()
        self.retriever._cache.clear()
        logger.info("缓存已清空")
    
    def is_built(self) -> bool:
        """
        检查索引是否已构建
        
        Returns:
            是否已构建
        """
        return self.retriever.index_built
    
    def get_stats(self) -> Dict:
        """
        获取索引统计信息
        
        Returns:
            统计信息字典
        """
        num_docs = self.retriever.keyword_retriever._num_docs
        num_chunks = len(self.retriever.keyword_retriever.doc_map)
        
        return {
            'num_documents': num_docs,
            'num_chunks': num_chunks,
            'index_dir': str(self.config.get('index_dir'))
        }
    
    def close(self):
        """释放资源"""
        if self.retriever.semantic_retriever._index_cache is not None:
            self.retriever.semantic_retriever._index_cache = None
            logger.info("FAISS索引已释放")


class RAGRetriever:
    """RAG 检索器（对外接口）
    
    作为门面模式（Facade Pattern）的实现，提供统一的 RAG 检索接口，
    内部委托给各个专门的组件处理具体职责。
    """
    
    def __init__(
        self,
        config: RAGConfig = None,
        config_path: str = None,
        **kwargs
    ):
        """
        初始化 RAG 检索器
        
        Args:
            config: RAG 配置对象，优先级最高
            config_path: 配置文件路径，当 config 为 None 时使用
            **kwargs: 覆盖配置的参数
        """
        if config is None:
            config = RAGConfig(config_path=config_path, **kwargs)
        
        self.config = config
        
        self.index_manager = IndexManager(config)
        self.context_builder = ContextBuilder(max_chars=config.get('chunk_size') * 5)
        self.prompt_augmenter = PromptAugmenter()
        
        self._initialized = False
        
        if config.get('eager_load'):
            self.initialize()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，释放资源"""
        self.close()
        return False
    
    def close(self):
        """释放资源"""
        self.index_manager.close()
    
    def reload(self, force_rebuild: bool = False):
        """
        重新加载索引
        
        Args:
            force_rebuild: 是否强制重新构建索引
        """
        self.index_manager.reload(force_rebuild=force_rebuild)
        self._initialized = False
    
    def stats(self) -> Dict:
        """
        获取完整统计信息
        
        Returns:
            统计信息字典
        """
        hybrid_stats = self.index_manager.retriever.get_stats()
        semantic_cache = {}
        if self.index_manager.retriever.semantic_retriever:
            semantic_cache = self.index_manager.retriever.semantic_retriever._cache.get_stats()
        
        index_stats = self.index_manager.get_stats()
        
        return {
            'index': index_stats,
            'retrieval': {
                'num_retrievals': hybrid_stats['num_retrievals'],
                'total_time_ms': hybrid_stats['total_time_ms'],
                'avg_time_ms': hybrid_stats['avg_time_ms'],
                'last_query_time_ms': hybrid_stats['last_query_time_ms'],
                'use_fusion': self.config.get('use_fusion'),
                'semantic_weight': self.config.get('semantic_weight'),
                'keyword_weight': self.config.get('keyword_weight')
            },
            'hybrid_cache': hybrid_stats['cache'],
            'semantic_cache': semantic_cache
        }
    
    def get_config(self) -> Dict:
        """
        获取当前配置
        
        Returns:
            配置字典
        """
        return self.config.to_dict()
    
    def initialize(self):
        """初始化"""
        if self._initialized:
            return
        
        index_dir = Path(self.config.get('index_dir'))
        if index_dir.exists():
            logger.info("加载已有索引...")
            self.index_manager.load_index()
        else:
            logger.info("构建新索引...")
            self.index_manager.build_index()
        
        self._initialized = True
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_fusion: bool = None,
        use_cache: bool = None
    ) -> List[Dict]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            use_fusion: 是否使用分数融合，覆盖配置文件
            use_cache: 是否使用缓存，覆盖配置文件
            
        Returns:
            相关文档列表
        """
        self.initialize()
        
        fusion = use_fusion if use_fusion is not None else self.config.get('use_fusion')
        cache = use_cache if use_cache is not None else self.config.get('use_cache')
        
        return self.index_manager.retriever.retrieve(
            query,
            top_k=top_k,
            use_fusion=fusion,
            use_cache=cache
        )
    
    def build_context(
        self,
        query: str,
        top_k: int = None,
        max_chars: int = None
    ) -> str:
        """
        构建上下文
        
        Args:
            query: 查询文本
            top_k: 检索数量
            max_chars: 最大字符数
            
        Returns:
            上下文字符串
        """
        results = self.retrieve(query, top_k=top_k)
        return self.context_builder.build(results, max_chars=max_chars)
    
    def augment_prompt(
        self,
        query: str,
        system_prompt: str = None
    ) -> str:
        """
        增强提示词
        
        Args:
            query: 用户查询
            system_prompt: 系统提示词
            
        Returns:
            增强后的提示词
        """
        context = self.build_context(query)
        return self.prompt_augmenter.augment(query, context, system_prompt)


class RAGService:
    """RAG 服务"""
    
    def __init__(self, config: Dict = None):
        config = config or {}
        
        self.retriever = RAGRetriever(
            data_dir=config.get('data_dir', './data/premium_classics'),
            index_dir=config.get('index_dir', './data/rag_index'),
            chunk_size=config.get('chunk_size', 512),
            top_k=config.get('top_k', 5)
        )
    
    def query(
        self,
        question: str,
        return_context: bool = True,
        max_context_chars: int = 2000
    ) -> Dict:
        """
        查询
        
        Returns:
            {
                "answer": "回答文本",
                "sources": [{"title": "...", "score": 0.9}],
                "context": "检索到的上下文"
            }
        """
        results = self.retriever.retrieve(question, top_k=5)
        
        context = self.retriever.build_context(
            question,
            max_chars=max_context_chars
        )
        
        sources = [
            {
                'title': r.get('title', r.get('source', 'Unknown')),
                'score': r.get('similarity_score', r.get('bm25_score', 0))
            }
            for r in results[:5]
        ]
        
        return {
            'question': question,
            'sources': sources,
            'context': context,
            'augmented_prompt': self.retriever.augment_prompt(question)
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='RAG 检索增强系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 构建索引
    python rag_system.py --build --data "data/premium_classics"
    
    # 检索测试
    python rag_system.py --query "什么是正义？"
    
    # 完整流程
    python rag_system.py --build --query " Plato's view on justice"
        """
    )
    
    parser.add_argument('--build', action='store_true', help='构建索引')
    parser.add_argument('--query', type=str, help='查询文本')
    parser.add_argument('--data', type=str, default='./data/premium_classics', help='数据目录')
    parser.add_argument('--index', type=str, default='./data/rag_index', help='索引目录')
    parser.add_argument('--top_k', type=int, default=5, help='返回数量')
    
    args = parser.parse_args()
    
    if args.build:
        logger.info("=" * 60)
        logger.info("构建 RAG 索引")
        logger.info("=" * 60)
        
        rag = RAGRetriever(
            data_dir=args.data,
            index_dir=args.index,
            chunk_size=512,
            top_k=args.top_k
        )
        
        rag.initialize()
        
        logger.info("索引构建完成")
    
    if args.query:
        logger.info("=" * 60)
        logger.info(f"查询: {args.query}")
        logger.info("=" * 60)
        
        rag = RAGRetriever(
            data_dir=args.data,
            index_dir=args.index,
            chunk_size=512,
            top_k=args.top_k
        )
        
        results = rag.retrieve(args.query, top_k=args.top_k)
        
        logger.info(f"\n找到 {len(results)} 个相关文档:\n")
        
        for i, r in enumerate(results[:5]):
            title = r.get('title', r.get('source', 'Unknown'))
            score = r.get('similarity_score', r.get('bm25_score', 0))
            preview = r.get('preview', '')[:100]
            
            logger.info(f"{i+1}. [{title}] (相似度: {score:.3f})")
            logger.info(f"   预览: {preview}...")
            logger.info("")


if __name__ == '__main__':
    main()
