"""
长期记忆服务模块

提供语义化记忆存储和检索功能，支持：
- 记忆的增删改查操作
- 基于 Ollama 嵌入模型的语义搜索
- 自动检索相关记忆注入对话上下文
- 记忆标签分类管理
"""

import json
import os
import time
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clamp(value: int, min_val: int, max_val: int) -> int:
    """将值限制在指定范围内"""
    return max(min_val, min(value, max_val))


@dataclass
class Memory:
    """记忆数据结构"""
    id: str
    content: str
    category: str
    tags: List[str]
    importance: int
    created_at: float
    updated_at: float
    usage_count: int
    last_used_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        return cls(**data)


@dataclass  
class MemorySearchResult:
    """记忆搜索结果"""
    memory: Memory
    similarity: float


class MemoryStore:
    """
    记忆存储管理器
    
    负责记忆数据的持久化和基础CRUD操作
    """
    
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_path = os.path.join(base_dir, 'data', 'memories.json')
        
        self.storage_path = storage_path
        self._lock_file = storage_path + '.lock'
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
            logger.info(f"创建记忆存储目录: {storage_dir}")
        
        if not os.path.exists(self.storage_path):
            self._save_all({})
    
    def _acquire_lock(self) -> bool:
        """简单文件锁实现"""
        try:
            with open(self._lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False
    
    def _release_lock(self) -> None:
        try:
            if os.path.exists(self._lock_file):
                os.remove(self._lock_file)
        except Exception:
            pass
    
    def _save_all(self, data: Dict[str, Any]) -> None:
        """保存所有记忆数据"""
        try:
            self._acquire_lock()
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆数据失败: {e}")
            raise
        finally:
            self._release_lock()
    
    def _load_all(self) -> Dict[str, Any]:
        """加载所有记忆数据"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载记忆数据失败: {e}")
            return {}
    
    def create(self, content: str, category: str = "general", 
               tags: List[str] = None, importance: int = 5) -> Memory:
        """创建新记忆"""
        timestamp = time.time()
        memory_id = hashlib.md5(f"{content}{timestamp}".encode()).hexdigest()[:12]
        
        memory = Memory(
            id=memory_id,
            content=content,
            category=category,
            tags=tags or [],
            importance=clamp(importance, 1, 10),
            created_at=timestamp,
            updated_at=timestamp,
            usage_count=0,
            last_used_at=0
        )
        
        data = self._load_all()
        data[memory_id] = memory.to_dict()
        self._save_all(data)
        
        logger.info(f"创建记忆成功: {memory_id}")
        return memory
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """获取单个记忆"""
        data = self._load_all()
        if memory_id in data:
            return Memory.from_dict(data[memory_id])
        return None
    
    def list_all(self, category: str = None, limit: int = 100) -> List[Memory]:
        """列出所有记忆，可按分类筛选"""
        data = self._load_all()
        memories = []
        
        for item in data.values():
            memory = Memory.from_dict(item)
            if category is None or memory.category == category:
                memories.append(memory)
        
        memories.sort(key=lambda x: x.created_at, reverse=True)
        return memories[:limit]
    
    def update(self, memory_id: str, content: str = None, 
               category: str = None, tags: List[str] = None,
               importance: int = None) -> Optional[Memory]:
        """更新记忆"""
        data = self._load_all()
        
        if memory_id not in data:
            return None
        
        memory = Memory.from_dict(data[memory_id])
        
        if content is not None:
            memory.content = content
        if category is not None:
            memory.category = category
        if tags is not None:
            memory.tags = tags
        if importance is not None:
            memory.importance = clamp(importance, 1, 10)
        
        memory.updated_at = time.time()
        data[memory_id] = memory.to_dict()
        self._save_all(data)
        
        return memory
    
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        data = self._load_all()
        
        if memory_id not in data:
            return False
        
        del data[memory_id]
        self._save_all(data)
        logger.info(f"删除记忆: {memory_id}")
        return True
    
    def record_usage(self, memory_id: str) -> None:
        """记录记忆使用"""
        data = self._load_all()
        
        if memory_id in data:
            memory = Memory.from_dict(data[memory_id])
            memory.usage_count += 1
            memory.last_used_at = time.time()
            data[memory_id] = memory.to_dict()
            self._save_all(data)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        data = self._load_all()
        memories = [Memory.from_dict(item) for item in data.values()]
        
        categories = {}
        for mem in memories:
            categories[mem.category] = categories.get(mem.category, 0) + 1
        
        return {
            "total_count": len(memories),
            "categories": categories,
            "total_usage": sum(m.usage_count for m in memories)
        }


class EmbeddingService:
    """
    嵌入服务
    
    负责调用 Ollama API 生成文本嵌入向量
    """
    
    def __init__(self, base_url: str = None, model: str = None):
        if base_url is None:
            self.base_url = "http://localhost:11434"
        else:
            self.base_url = base_url
        
        self.model = model or "nomic-embed-text"
    
    def embed(self, text: str) -> Optional[List[float]]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量列表，失败返回 None
        """
        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("embeddings", [None])[0]
            else:
                logger.warning(f"嵌入API返回错误: {response.status_code}")
                return None
                
        except ImportError:
            logger.error("requests 库未安装")
            return None
        except Exception as e:
            logger.error(f"生成嵌入失败: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量生成嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        results = []
        for text in texts:
            embedding = self.embed(text)
            results.append(embedding)
        return results


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算余弦相似度
    
    Args:
        vec1: 向量1
        vec2: 向量2
        
    Returns:
        相似度分数 [-1, 1]
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


class MemoryService:
    """
    长期记忆服务主类
    
    整合记忆存储和嵌入检索功能，提供：
    - 记忆的语义化存储和检索
    - 基于相似度的记忆召回
    - 自动记忆管理
    """
    
    def __init__(self, base_url: str = None, embedding_model: str = None):
        self.store = MemoryStore()
        self.embedding = EmbeddingService(base_url, embedding_model)
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_max_size = 100
    
    def add_memory(self, content: str, category: str = "user_preference",
                   tags: List[str] = None, importance: int = 5) -> Memory:
        """
        添加新记忆
        
        Args:
            content: 记忆内容
            category: 记忆分类
            tags: 标签列表
            importance: 重要性等级 (1-10)
            
        Returns:
            创建的记忆对象
        """
        memory = self.store.create(content, category, tags, importance)
        self._cache_embedding(memory)
        return memory
    
    def get_relevant_memories(self, query: str, top_k: int = 5,
                               min_similarity: float = 0.5) -> List[MemorySearchResult]:
        """
        检索与查询相关的记忆
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            min_similarity: 最小相似度阈值
            
        Returns:
            按相似度排序的记忆列表
        """
        query_embedding = self._get_cached_embedding(query)
        if query_embedding is None:
            query_embedding = self.embedding.embed(query)
            if query_embedding is None:
                logger.warning("无法生成查询嵌入，返回空结果")
                return []
        
        all_memories = self.store.list_all()
        results = []
        
        for memory in all_memories:
            mem_embedding = self._get_cached_embedding(f"mem_{memory.id}")
            if mem_embedding is None:
                mem_embedding = self._get_cached_embedding(memory.content)
                if mem_embedding is None:
                    mem_embedding = self.embedding.embed(memory.content)
                    if mem_embedding:
                        self._cache_embedding(memory, mem_embedding)
            
            if mem_embedding:
                similarity = cosine_similarity(query_embedding, mem_embedding)
                if similarity >= min_similarity:
                    results.append(MemorySearchResult(memory, similarity))
                    self.store.record_usage(memory.id)
        
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]
    
    def get_memories_for_context(self, conversation_text: str, 
                                  max_memories: int = 3) -> List[str]:
        """
        获取适合注入上下文的记忆内容
        
        Args:
            conversation_text: 对话内容
            max_memories: 最大返回数量
            
        Returns:
            记忆内容列表
        """
        results = self.get_relevant_memories(
            conversation_text, 
            top_k=max_memories,
            min_similarity=0.4
        )
        
        memories = []
        for result in results:
            prefix = f"[相关记忆 - {result.memory.category}]"
            memories.append(f"{prefix} {result.memory.content}")
        
        return memories
    
    def update_memory(self, memory_id: str, **kwargs) -> Optional[Memory]:
        """更新记忆"""
        memory = self.store.update(memory_id, **kwargs)
        if memory:
            self._invalidate_cache(memory_id)
        return memory
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        self._invalidate_cache(memory_id)
        return self.store.delete(memory_id)
    
    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a single memory."""
        return self.store.get(memory_id)

    def search_memories(self, query: str, top_k: int = 5, min_similarity: float = 0.4) -> List[Memory]:
        """Search memories and return Memory objects."""
        results = self.get_relevant_memories(query, top_k=top_k, min_similarity=min_similarity)
        return [r.memory for r in results]

    def list_memories(self, category: str = None) -> List[Memory]:
        """List memories."""
        return self.store.list_all(category)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.store.get_stats()

    def clear_all(self) -> None:
        """Remove all persisted memories and reset the embedding cache."""
        self.store._save_all({})
        self.clear_cache()
    
    def _cache_embedding(self, memory: Memory, embedding: List[float] = None) -> None:
        """缓存记忆嵌入向量"""
        key = f"mem_{memory.id}"
        if embedding is None:
            embedding = self.embedding.embed(memory.content)
        
        if embedding:
            self._embedding_cache[key] = embedding
            
            if len(self._embedding_cache) > self._cache_max_size:
                oldest_keys = list(self._embedding_cache.keys())[:10]
                for k in oldest_keys:
                    del self._embedding_cache[k]
    
    def _get_cached_embedding(self, key: str) -> Optional[List[float]]:
        """获取缓存的嵌入向量"""
        return self._embedding_cache.get(key)
    
    def _invalidate_cache(self, memory_id: str) -> None:
        """使缓存失效"""
        key = f"mem_{memory_id}"
        if key in self._embedding_cache:
            del self._embedding_cache[key]
    
    def clear_cache(self) -> None:
        """清空嵌入缓存"""
        self._embedding_cache.clear()


# 单例实例
_memory_service_instance: Optional[MemoryService] = None


def get_memory_service(base_url: str = None, embedding_model: str = None) -> MemoryService:
    """
    获取记忆服务单例
    
    Args:
        base_url: Ollama API 地址
        embedding_model: 嵌入模型名称
        
    Returns:
        MemoryService 实例
    """
    global _memory_service_instance
    
    if _memory_service_instance is None:
        _memory_service_instance = MemoryService(base_url, embedding_model)
    
    return _memory_service_instance


if __name__ == "__main__":
    service = get_memory_service()
    
    print("=" * 50)
    print("长期记忆服务测试")
    print("=" * 50)
    
    print("\n1. 添加测试记忆...")
    service.add_memory(
        "用户喜欢简洁的代码风格，偏爱使用箭头函数",
        category="coding_style",
        tags=["代码", "偏好", "简洁"],
        importance=8
    )
    service.add_memory(
        "用户正在开发一个名为Ollma的AI聊天项目",
        category="project",
        tags=["项目", "AI", "开发"],
        importance=10
    )
    service.add_memory(
        "用户使用Windows系统，主要开发语言是Python和JavaScript",
        category="environment",
        tags=["系统", "开发环境", "Python", "JavaScript"],
        importance=7
    )
    
    print("\n2. 检索相关记忆...")
    results = service.get_relevant_memories("用户在做什么项目？需要什么编程技能？")
    for result in results:
        print(f"  - [{result.memory.category}] {result.memory.content}")
        print(f"    相似度: {result.similarity:.3f}")
    
    print("\n3. 获取注入上下文的记忆...")
    context_memories = service.get_memories_for_context(
        "用户问这个项目用的是什么技术栈？", 
        max_memories=2
    )
    for mem in context_memories:
        print(f"  {mem}")
    
    print("\n4. 统计信息...")
    stats = service.get_statistics()
    print(f"  总记忆数: {stats['total_count']}")
    print(f"  分类统计: {stats['categories']}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
