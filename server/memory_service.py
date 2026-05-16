"""
长期记忆服务模块 v2

严格遵循架构文档设计：
  内存分类：Fact / Preference / Goal / Relation
  两阶段召回：清单扫描 + 相关性选择
  内存注入格式：<memory content="..." age="3天前"/>
  新鲜度警告：超7天加 <caution> 标签
  过期纠正：用户纠正时标记旧内存为过期
  后台异步写入：每次回答后判断是否保存
"""

import json
import os
import re
import time
import hashlib
import logging
import threading
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MEMORY_CATEGORIES = {
    'fact': '用户事实',
    'preference': '长期偏好',
    'goal': '项目/目标',
    'relation': '关系记忆',
}

FRESHNESS_WARNING_DAYS = 7


def clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(value, max_val))


def format_age(timestamp: float) -> str:
    if timestamp <= 0:
        return '未知'
    delta = time.time() - timestamp
    if delta < 3600:
        return f'{int(delta / 60)}分钟前'
    elif delta < 86400:
        return f'{int(delta / 3600)}小时前'
    elif delta < 604800:
        return f'{int(delta / 86400)}天前'
    elif delta < 2592000:
        return f'{int(delta / 604800)}周前'
    else:
        return f'{int(delta / 2592000)}个月前'


@dataclass
class Memory:
    id: str
    content: str
    category: str
    tags: List[str]
    importance: int
    created_at: float
    updated_at: float
    usage_count: int
    last_used_at: float
    is_expired: bool = False
    expired_by: str = ''
    source_summary: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @property
    def age_description(self) -> str:
        return format_age(self.created_at)

    @property
    def needs_freshness_warning(self) -> bool:
        if self.is_expired:
            return False
        age_days = (time.time() - self.created_at) / 86400
        return age_days > FRESHNESS_WARNING_DAYS

    def to_injection_xml(self) -> str:
        age = self.age_description
        category_label = MEMORY_CATEGORIES.get(self.category, self.category)
        parts = [f'<memory type="{category_label}" content="{self.content}" age="{age}"']

        if self.needs_freshness_warning:
            parts.append(' stale="true"')

        if self.is_expired:
            parts.append(f' expired="true" replaced_by="{self.expired_by}"')

        parts.append('/>')

        xml = ''.join(parts)

        if self.needs_freshness_warning and not self.is_expired:
            xml += '\n<caution>以下信息记录于很久以前，可能已变化，请先确认。</caution>'

        return xml


@dataclass
class MemorySearchResult:
    memory: Memory
    similarity: float


class MemoryStore:
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_path = os.path.join(base_dir, 'data', 'memories.json')

        self.storage_path = storage_path
        self._lock_file = storage_path + '.lock'
        self._memory_lock = threading.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        storage_dir = os.path.dirname(self.storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        if not os.path.exists(self.storage_path):
            self._save_all({})

    def _acquire_lock(self) -> bool:
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
        try:
            self._acquire_lock()
            with self._memory_lock:
                with open(self.storage_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆数据失败: {e}")
            raise
        finally:
            self._release_lock()

    def _load_all(self) -> Dict[str, Any]:
        try:
            with self._memory_lock:
                if os.path.exists(self.storage_path):
                    with open(self.storage_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                return {}
        except Exception as e:
            logger.error(f"加载记忆数据失败: {e}")
            return {}

    def create(self, content: str, category: str = "fact",
               tags: List[str] = None, importance: int = 5,
               source_summary: str = '') -> Memory:
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
            last_used_at=0,
            is_expired=False,
            expired_by='',
            source_summary=source_summary,
        )

        data = self._load_all()
        data[memory_id] = memory.to_dict()
        self._save_all(data)

        logger.info(f"创建记忆成功: {memory_id} [{category}] {content[:30]}")
        return memory

    def get(self, memory_id: str) -> Optional[Memory]:
        data = self._load_all()
        if memory_id in data:
            return Memory.from_dict(data[memory_id])
        return None

    def list_all(self, category: str = None, include_expired: bool = False, limit: int = 100) -> List[Memory]:
        data = self._load_all()
        memories = []

        for item in data.values():
            memory = Memory.from_dict(item)
            if not include_expired and memory.is_expired:
                continue
            if category is None or memory.category == category:
                memories.append(memory)

        memories.sort(key=lambda x: x.created_at, reverse=True)
        return memories[:limit]

    def update(self, memory_id: str, content: str = None,
               category: str = None, tags: List[str] = None,
               importance: int = None) -> Optional[Memory]:
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
        data = self._load_all()

        if memory_id not in data:
            return False

        del data[memory_id]
        self._save_all(data)
        logger.info(f"删除记忆: {memory_id}")
        return True

    def mark_expired(self, memory_id: str, replaced_by: str = '') -> bool:
        data = self._load_all()

        if memory_id not in data:
            return False

        memory = Memory.from_dict(data[memory_id])
        memory.is_expired = True
        memory.expired_by = replaced_by
        memory.updated_at = time.time()
        data[memory_id] = memory.to_dict()
        self._save_all(data)

        logger.info(f"标记记忆过期: {memory_id}, 替代: {replaced_by[:30]}")
        return True

    def record_usage(self, memory_id: str) -> None:
        data = self._load_all()

        if memory_id in data:
            memory = Memory.from_dict(data[memory_id])
            memory.usage_count += 1
            memory.last_used_at = time.time()
            data[memory_id] = memory.to_dict()
            self._save_all(data)

    def get_stats(self) -> Dict[str, Any]:
        data = self._load_all()
        memories = [Memory.from_dict(item) for item in data.values()]

        categories = {}
        for mem in memories:
            categories[mem.category] = categories.get(mem.category, 0) + 1

        active = sum(1 for m in memories if not m.is_expired)
        expired = sum(1 for m in memories if m.is_expired)
        stale = sum(1 for m in memories if m.needs_freshness_warning and not m.is_expired)

        return {
            "total_count": len(memories),
            "active_count": active,
            "expired_count": expired,
            "stale_count": stale,
            "categories": categories,
            "total_usage": sum(m.usage_count for m in memories),
        }


class EmbeddingService:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or "http://localhost:11434"
        self.model = model or "nomic-embed-text"

    def embed(self, text: str) -> Optional[List[float]]:
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


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


class MemoryService:
    """长期记忆服务 v2 — 严格遵循架构文档"""

    def __init__(self, base_url: str = None, embedding_model: str = None):
        self.store = MemoryStore()
        self.embedding = EmbeddingService(base_url, embedding_model)
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_max_size = 100

    def add_memory(self, content: str, category: str = "fact",
                   tags: List[str] = None, importance: int = 5,
                   source_summary: str = '') -> Memory:
        # 检查是否与已有记忆冲突（过期纠正）
        self._check_and_expire_conflicts(content, category)

        memory = self.store.create(content, category, tags, importance, source_summary)
        self._cache_embedding(memory)
        return memory

    def _check_and_expire_conflicts(self, new_content: str, category: str) -> None:
        """过期纠正：用户纠正时标记旧内存为过期"""
        correction_patterns = [
            r'我(?:不再|已经不|现在不)(.+)',
            r'我(?:改|换|更新)(?:了|为|成)(.+)',
            r'其实我(?:是|喜欢|想要)(.+)',
            r'之前说的(.+)不对',
        ]

        is_correction = False
        corrected_topic = ''
        for pattern in correction_patterns:
            match = re.search(pattern, new_content)
            if match:
                is_correction = True
                corrected_topic = match.group(1)
                break

        if not is_correction:
            return

        existing = self.store.list_all(category=category, include_expired=False)
        for mem in existing:
            if any(w in mem.content for w in corrected_topic.split() if len(w) > 1):
                self.store.mark_expired(mem.id, replaced_by=new_content)
                logger.info(f"过期纠正: 旧记忆 '{mem.content[:30]}' 被新内容替代")

    def get_relevant_memories(self, query: str, top_k: int = 5,
                               min_similarity: float = 0.5) -> List[MemorySearchResult]:
        """两阶段召回：阶段一清单扫描 + 阶段二相关性选择"""

        # 阶段一：清单扫描 — 获取所有非过期记忆的摘要
        all_memories = self.store.list_all(include_expired=False)
        if not all_memories:
            return []

        # 阶段二：相关性选择
        query_embedding = self._get_cached_embedding(query)
        if query_embedding is None:
            query_embedding = self.embedding.embed(query)
            if query_embedding is None:
                # 降级：关键词匹配
                return self._keyword_fallback(query, all_memories, top_k)

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
                # 时间衰减：越近的记忆权重越高
                age_days = (time.time() - memory.created_at) / 86400
                time_decay = max(0.5, 1.0 - age_days / 60.0)
                adjusted_similarity = similarity * time_decay

                if adjusted_similarity >= min_similarity:
                    results.append(MemorySearchResult(memory, adjusted_similarity))

        results.sort(key=lambda x: x.similarity, reverse=True)
        selected = results[:top_k]

        for result in selected:
            self.store.record_usage(result.memory.id)

        return selected

    def _keyword_fallback(self, query: str, memories: List[Memory],
                           top_k: int) -> List[MemorySearchResult]:
        """关键词降级召回（嵌入服务不可用时）"""
        query_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', query))
        if not query_words:
            return []

        results = []
        for memory in memories:
            mem_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', memory.content))
            overlap = len(query_words & mem_words)
            if overlap > 0:
                similarity = overlap / max(len(query_words), 1)
                results.append(MemorySearchResult(memory, similarity))

        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]

    def get_memories_for_context(self, conversation_text: str,
                                  max_memories: int = 3) -> List[str]:
        """获取适合注入上下文的记忆内容（架构文档格式）"""
        results = self.get_relevant_memories(
            conversation_text,
            top_k=max_memories,
            min_similarity=0.4
        )

        return [result.memory.to_injection_xml() for result in results]

    def async_write_from_conversation(self, user_msg: str, assistant_msg: str) -> None:
        """后台异步写入：每次回答后判断是否保存新记忆"""
        def _write():
            try:
                self._extract_and_save_memories(user_msg, assistant_msg)
            except Exception as e:
                logger.error(f"异步记忆写入失败: {e}")

        thread = threading.Thread(target=_write, daemon=True)
        thread.start()

    def _extract_and_save_memories(self, user_msg: str, assistant_msg: str) -> None:
        """从对话中提取并保存记忆"""
        # 偏好提取
        preference_patterns = [
            r'我(?:喜欢|偏好|偏爱|习惯|倾向于)(.+)',
            r'我(?:不喜欢|讨厌|反感|不想|不要)(.+)',
            r'请(?:用|以|按)(.+)(?:方式|风格|格式)',
        ]

        for pattern in preference_patterns:
            match = re.search(pattern, user_msg)
            if match:
                content = match.group(0)
                existing = self.store.list_all(category='preference', include_expired=False)
                is_duplicate = any(e.content == content for e in existing)
                if not is_duplicate:
                    self.store.create(content, 'preference', importance=7,
                                      source_summary=f'用户在对话中表达偏好')

        # 事实提取
        fact_patterns = [
            r'我(?:叫|是|在|从事|工作于|住在)(.+)',
            r'我的(?:名字|职业|公司|城市|专业)(?:是|叫|在)(.+)',
        ]

        for pattern in fact_patterns:
            match = re.search(pattern, user_msg)
            if match:
                content = match.group(0)
                existing = self.store.list_all(category='fact', include_expired=False)
                is_duplicate = any(e.content == content for e in existing)
                if not is_duplicate:
                    self.store.create(content, 'fact', importance=8,
                                      source_summary=f'用户在对话中陈述事实')

        # 目标提取
        goal_patterns = [
            r'我(?:正在|打算|计划|准备|想要)(?:学|做|开发|完成|实现)(.+)',
            r'我的(?:目标|计划|项目)(?:是|叫)(.+)',
        ]

        for pattern in goal_patterns:
            match = re.search(pattern, user_msg)
            if match:
                content = match.group(0)
                existing = self.store.list_all(category='goal', include_expired=False)
                is_duplicate = any(e.content == content for e in existing)
                if not is_duplicate:
                    self.store.create(content, 'goal', importance=6,
                                      source_summary=f'用户在对话中提及目标')

    def update_memory(self, memory_id: str, **kwargs) -> Optional[Memory]:
        memory = self.store.update(memory_id, **kwargs)
        if memory:
            self._invalidate_cache(memory_id)
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        self._invalidate_cache(memory_id)
        return self.store.delete(memory_id)

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        return self.store.get(memory_id)

    def search_memories(self, query: str, top_k: int = 5, min_similarity: float = 0.4) -> List[Memory]:
        results = self.get_relevant_memories(query, top_k=top_k, min_similarity=min_similarity)
        return [r.memory for r in results]

    def list_memories(self, category: str = None) -> List[Memory]:
        return self.store.list_all(category)

    def get_statistics(self) -> Dict[str, Any]:
        return self.store.get_stats()

    def clear_all(self) -> None:
        self.store._save_all({})
        self.clear_cache()

    def _cache_embedding(self, memory: Memory, embedding: List[float] = None) -> None:
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
        return self._embedding_cache.get(key)

    def _invalidate_cache(self, memory_id: str) -> None:
        key = f"mem_{memory_id}"
        if key in self._embedding_cache:
            del self._embedding_cache[key]

    def clear_cache(self) -> None:
        self._embedding_cache.clear()


_memory_service_instance: Optional[MemoryService] = None


def get_memory_service(base_url: str = None, embedding_model: str = None) -> MemoryService:
    global _memory_service_instance

    if _memory_service_instance is None:
        _memory_service_instance = MemoryService(base_url, embedding_model)

    return _memory_service_instance


if __name__ == "__main__":
    service = get_memory_service()

    print("=" * 50)
    print("长期记忆服务 v2 测试")
    print("=" * 50)

    print("\n1. 添加测试记忆...")
    service.add_memory("我叫张三，是程序员", category="fact", importance=9)
    service.add_memory("我喜欢简洁的回答，不要铺陈", category="preference", importance=7)
    service.add_memory("我正在学习日语，目标是考N2", category="goal", importance=8)
    service.add_memory("上次你推荐过一本小说，我很喜欢", category="relation", importance=6)

    print("\n2. 获取注入上下文的记忆（架构文档格式）...")
    context_memories = service.get_memories_for_context("帮我推荐一些日语学习资料", max_memories=3)
    for mem in context_memories:
        print(f"  {mem}")

    print("\n3. 测试过期纠正...")
    service.add_memory("我不再学习日语了", category="fact", importance=9)

    print("\n4. 统计信息...")
    stats = service.get_statistics()
    print(f"  总记忆数: {stats['total_count']}")
    print(f"  活跃记忆: {stats['active_count']}")
    print(f"  过期记忆: {stats['expired_count']}")
    print(f"  陈旧记忆: {stats['stale_count']}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
