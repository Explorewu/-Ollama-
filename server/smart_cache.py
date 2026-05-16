"""
智能缓存系统 - 后端性能优化核心模块

数学模型：
1. LRU (Least Recently Used) 缓存淘汰算法
2. 自适应TTL：基于访问频率动态调整过期时间
3. 内存压力感知：根据系统内存使用情况自动调整缓存大小
4. 预测性缓存：基于历史访问模式预加载

性能指标：
- 缓存命中率目标：> 80%
- 响应时间降低：> 50%
- 内存占用可控：< 100MB
"""

import time
import threading
import hashlib
import json
import logging
import os
import sqlite3
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from functools import wraps
from pathlib import Path
import weakref

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    last_access: float
    access_count: int
    ttl: float
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl
    
    def update_access(self):
        self.last_access = time.time()
        self.access_count += 1


class AdaptiveTTL:
    TTL_MIN = 10
    TTL_MAX = 3600
    TTL_DEFAULT = 300
    
    @classmethod
    def calculate(cls, access_count: int, time_since_creation: float) -> float:
        if access_count <= 1:
            return cls.TTL_MIN
        
        frequency = access_count / max(time_since_creation, 1)
        
        if frequency > 0.1:
            return min(cls.TTL_MAX, cls.TTL_DEFAULT * 4)
        elif frequency > 0.01:
            return cls.TTL_DEFAULT * 2
        elif frequency > 0.001:
            return cls.TTL_DEFAULT
        else:
            return cls.TTL_MIN


class MemoryAwareCache:
    MAX_MEMORY_MB = 100
    CLEANUP_THRESHOLD = 0.8
    
    def __init__(self, max_size: int = 1000, max_memory_mb: float = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_evictions': 0
        }
        self._start_cleanup_thread()
    
    def _generate_key(self, key: str, namespace: str = '') -> str:
        if namespace:
            return f"{namespace}:{key}"
        return key
    
    def _estimate_size(self, value: Any) -> int:
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (dict, list)):
                return len(json.dumps(value, ensure_ascii=False))
            else:
                return len(str(value))
        except:
            return 1024
    
    def _current_memory_usage(self) -> int:
        return sum(entry.size_bytes for entry in self._cache.values())
    
    def get(self, key: str, namespace: str = '') -> Optional[Any]:
        full_key = self._generate_key(key, namespace)
        
        with self._lock:
            if full_key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[full_key]
            
            if entry.is_expired():
                del self._cache[full_key]
                self._stats['misses'] += 1
                self._stats['evictions'] += 1
                return None
            
            entry.update_access()
            self._cache.move_to_end(full_key)
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: float = None, 
            namespace: str = '', tags: List[str] = None) -> bool:
        full_key = self._generate_key(key, namespace)
        
        if ttl is None:
            ttl = AdaptiveTTL.TTL_DEFAULT
        
        size_bytes = self._estimate_size(value)
        
        with self._lock:
            current_memory = self._current_memory_usage()
            
            while (len(self._cache) >= self.max_size or 
                   current_memory + size_bytes > self.max_memory_bytes):
                if not self._cache:
                    break
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                current_memory -= oldest_entry.size_bytes
                self._stats['evictions'] += 1
                self._stats['memory_evictions'] += 1
            
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                last_access=time.time(),
                access_count=1,
                ttl=ttl,
                size_bytes=size_bytes,
                tags=tags or []
            )
            
            self._cache[full_key] = entry
            return True
    
    def delete(self, key: str, namespace: str = '') -> bool:
        full_key = self._generate_key(key, namespace)
        
        with self._lock:
            if full_key in self._cache:
                del self._cache[full_key]
                return True
            return False
    
    def clear(self, namespace: str = None):
        with self._lock:
            if namespace:
                prefix = f"{namespace}:"
                keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
                for k in keys_to_delete:
                    del self._cache[k]
            else:
                self._cache.clear()
    
    def invalidate_tags(self, tags: List[str]):
        with self._lock:
            keys_to_delete = []
            for key, entry in self._cache.items():
                if any(tag in entry.tags for tag in tags):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
    
    def get_stats(self) -> Dict:
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'memory_usage_mb': self._current_memory_usage() / (1024 * 1024),
            'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': f"{hit_rate:.2f}%",
            'evictions': self._stats['evictions'],
            'memory_evictions': self._stats['memory_evictions']
        }
    
    def _start_cleanup_thread(self):
        def cleanup():
            while True:
                time.sleep(60)
                with self._lock:
                    expired_keys = [
                        k for k, v in self._cache.items() 
                        if v.is_expired()
                    ]
                    for k in expired_keys:
                        del self._cache[k]
                        self._stats['evictions'] += 1
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()


class CachedAPI:
    _instance = None
    _cache = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._cache = MemoryAwareCache()
        return cls._instance
    
    @classmethod
    def get_cache(cls):
        if cls._cache is None:
            cls._cache = MemoryAwareCache()
        return cls._cache
    
    @classmethod
    def cached(cls, ttl: float = 300, namespace: str = '', tags: List[str] = None):
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache = cls.get_cache()
                
                key_parts = [func.__name__, str(args), str(sorted(kwargs.items()))]
                key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
                
                cached_result = cache.get(key, namespace)
                if cached_result is not None:
                    logger.debug(f"[Cache] 命中: {func.__name__}")
                    return cached_result
                
                result = func(*args, **kwargs)
                
                cache.set(key, result, ttl=ttl, namespace=namespace, tags=tags)
                logger.debug(f"[Cache] 存储: {func.__name__}")
                
                return result
            
            return wrapper
        return decorator


class TokenEstimatorOptimized:
    """
    优化的 Token 估算器
    
    使用更精确的算法：
    - 英文：约 4 字符 = 1 token
    - 中文：约 1.5 字符 = 1 token
    - 代码：约 3 字符 = 1 token
    - 混合内容：加权平均
    """
    
    CHINESE_PATTERN = None
    CODE_PATTERN = None
    
    @classmethod
    def _init_patterns(cls):
        if cls.CHINESE_PATTERN is None:
            import re
            cls.CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')
            cls.CODE_PATTERN = re.compile(r'[{}()\[\];:=<>]')
    
    @classmethod
    def estimate(cls, text: str) -> int:
        if not text:
            return 0
        
        cls._init_patterns()
        
        total_chars = len(text)
        chinese_chars = len(cls.CHINESE_PATTERN.findall(text))
        code_chars = len(cls.CODE_PATTERN.findall(text))
        other_chars = total_chars - chinese_chars - code_chars
        
        chinese_tokens = chinese_chars / 1.5
        code_tokens = code_chars / 3
        other_tokens = other_chars / 4
        
        base_estimate = chinese_tokens + code_tokens + other_tokens
        
        adjusted = base_estimate * 1.1
        
        return max(1, int(adjusted))
    
    @classmethod
    def estimate_messages(cls, messages: List[Dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role', '')
            total += cls.estimate(content)
            total += 4
        return total


global_cache = MemoryAwareCache()

def get_smart_cache() -> MemoryAwareCache:
    return global_cache

def cached_api(ttl: float = 300, namespace: str = ''):
    return CachedAPI.cached(ttl=ttl, namespace=namespace)


class ThreeLevelCache:
    """
    三级缓存: L1内存 → L2SQLite → L3远程(Ollama)
    
    快路径: L1/L2命中直接返回 (0-5ms)
    慢路径: L3 Ollama推理 (1-10s), 结果回填L1/L2
    """

    L1_TTL = 300
    L2_TTL = 3600

    def __init__(self, db_path: str = None):
        self._l1 = MemoryAwareCache(max_size=2000, max_memory_mb=50)
        self._l2_path = db_path
        self._l2_conn = None
        self._lock = threading.Lock()
        self._stats = {"l1_hits": 0, "l2_hits": 0, "l3_hits": 0, "misses": 0, "total": 0}

        if db_path:
            self._init_l2(db_path)

    def _init_l2(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._l2_conn = sqlite3.connect(db_path, timeout=10)
        self._l2_conn.execute("PRAGMA journal_mode=WAL")
        self._l2_conn.execute("PRAGMA synchronous=NORMAL")
        self._l2_conn.execute("""CREATE TABLE IF NOT EXISTS cache_entries (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, created_at REAL NOT NULL,
            ttl REAL NOT NULL, access_count INTEGER DEFAULT 1)""")
        self._l2_conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_created ON cache_entries(created_at)")
        self._l2_conn.commit()

    def get(self, key: str) -> Optional[Any]:
        self._stats["total"] += 1

        result = self._l1.get(key, namespace="tlc")
        if result is not None:
            self._stats["l1_hits"] += 1
            return result

        if self._l2_conn:
            result = self._l2_get(key)
            if result is not None:
                self._stats["l2_hits"] += 1
                self._l1.set(key, result, ttl=self.L1_TTL, namespace="tlc")
                return result

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: float = None) -> None:
        ttl = ttl or self.L1_TTL
        self._l1.set(key, value, ttl=ttl, namespace="tlc")
        if self._l2_conn:
            self._l2_set(key, value, ttl)

    def _l2_get(self, key: str) -> Optional[Any]:
        try:
            cur = self._l2_conn.cursor()
            cur.execute("SELECT value, created_at, ttl FROM cache_entries WHERE key=?", (key,))
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            if time.time() - row[1] > row[2]:
                self._l2_delete(key)
                return None
            self._l2_conn.execute("UPDATE cache_entries SET access_count=access_count+1 WHERE key=?", (key,))
            self._l2_conn.commit()
            return json.loads(row[0])
        except Exception:
            return None

    def _l2_set(self, key: str, value: Any, ttl: float) -> None:
        try:
            data = json.dumps(value, ensure_ascii=False)
            self._l2_conn.execute(
                "INSERT OR REPLACE INTO cache_entries (key, value, created_at, ttl) VALUES (?, ?, ?, ?)",
                (key, data, time.time(), ttl),
            )
            self._l2_conn.commit()
        except Exception:
            pass

    def _l2_delete(self, key: str) -> None:
        try:
            self._l2_conn.execute("DELETE FROM cache_entries WHERE key=?", (key,))
            self._l2_conn.commit()
        except Exception:
            pass

    def cleanup(self) -> int:
        count = 0
        if self._l2_conn:
            try:
                cur = self._l2_conn.execute("DELETE FROM cache_entries WHERE created_at + ttl < ?", (time.time(),))
                count = cur.rowcount
                self._l2_conn.commit()
            except Exception:
                pass
        return count

    def get_stats(self) -> Dict:
        total = self._stats["total"] or 1
        return {
            "total_requests": self._stats["total"],
            "l1_hits": self._stats["l1_hits"],
            "l2_hits": self._stats["l2_hits"],
            "l3_hits": self._stats["l3_hits"],
            "misses": self._stats["misses"],
            "l1_hit_rate": round(self._stats["l1_hits"] / total * 100, 1),
            "l2_hit_rate": round(self._stats["l2_hits"] / total * 100, 1),
            "overall_hit_rate": round((self._stats["l1_hits"] + self._stats["l2_hits"]) / total * 100, 1),
        }


class FastPathRouter:
    """
    快慢路径路由器
    
    快路径: CASC意图识别 + 缓存命中 → 0-5ms
    慢路径: Ollama推理 → 1-10s, 限流保护
    """

    def __init__(self, cache: ThreeLevelCache = None, max_concurrent_slow: int = 4):
        self._cache = cache or ThreeLevelCache()
        self._max_concurrent = max_concurrent_slow
        self._current_slow = 0
        self._lock = threading.Lock()
        self._stats = {"fast_path": 0, "slow_path": 0, "slow_rejected": 0}

    def route(self, text: str, intent_result: Dict = None) -> Dict:
        cache_key = hashlib.md5(text.encode()).hexdigest()

        cached = self._cache.get(cache_key)
        if cached is not None:
            self._stats["fast_path"] += 1
            result = dict(cached)
            result["_path"] = "fast_cache"
            return result

        if intent_result:
            self._cache.set(cache_key, intent_result, ttl=ThreeLevelCache.L1_TTL)
            self._stats["fast_path"] += 1
            result = dict(intent_result)
            result["_path"] = "fast_casc"
            return result

        can_slow = self._try_acquire_slow()
        if can_slow:
            self._stats["slow_path"] += 1
            return {"_path": "slow", "_needs_inference": True}
        else:
            self._stats["slow_rejected"] += 1
            return {"_path": "rejected", "_needs_inference": False, "_reason": "concurrency_limit"}

    def _try_acquire_slow(self) -> bool:
        with self._lock:
            if self._current_slow < self._max_concurrent:
                self._current_slow += 1
                return True
            return False

    def release_slow(self):
        with self._lock:
            self._current_slow = max(0, self._current_slow - 1)

    def store_slow_result(self, text: str, result: Dict, ttl: float = None):
        cache_key = hashlib.md5(text.encode()).hexdigest()
        self._cache.set(cache_key, result, ttl=ttl or ThreeLevelCache.L2_TTL)
        self.release_slow()

    def get_stats(self) -> Dict:
        total = sum(self._stats.values()) or 1
        return {
            **self._stats,
            "fast_path_pct": round(self._stats["fast_path"] / total * 100, 1),
            "current_slow": self._current_slow,
            "max_concurrent_slow": self._max_concurrent,
            "cache_stats": self._cache.get_stats(),
        }


def get_three_level_cache(db_path: str = None) -> ThreeLevelCache:
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return ThreeLevelCache(db_path or str(data_dir / "response_cache.db"))
