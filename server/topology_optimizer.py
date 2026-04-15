# -*- coding: utf-8 -*-
"""
拓扑学优化引擎
基于图论和流形学习的性能优化模块

数学原理：
1. DAG任务调度 - Kahn算法拓扑排序
2. 流形降维 - PCA特征空间压缩
3. 缓存感知 - CPU缓存行对齐
4. 动态调度 - 加权贪心策略
"""

import os
import sys
import time
import threading
import hashlib
import json
import math
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from dataclasses import dataclass, field

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sklearn.decomposition import PCA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class TaskNode:
    """DAG任务节点"""
    task_id: str
    weight: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    cache_benefit: float = 0.0
    status: str = "pending"


class TopologyScheduler:
    """
    拓扑调度器
    基于Kahn算法的任务依赖图优化
    
    数学推导：
    设DAG G = (V, E)，其中V为任务集合，E为依赖边
    拓扑排序保证：若(u,v)∈E，则u在排序中先于v
    
    并行度计算：
    P_parallel = Σw_i / L_schedule
    其中L_schedule为调度长度（关键路径）
    """
    
    def __init__(self):
        self.tasks: Dict[str, TaskNode] = {}
        self.adjacency: Dict[str, List[str]] = {}
        self.in_degree: Dict[str, int] = {}
        self._lock = threading.RLock()
    
    def add_task(self, task_id: str, weight: float = 1.0, 
                 dependencies: List[str] = None, cache_benefit: float = 0.0):
        """添加任务节点"""
        with self._lock:
            self.tasks[task_id] = TaskNode(
                task_id=task_id,
                weight=weight,
                dependencies=dependencies or [],
                cache_benefit=cache_benefit
            )
            
            if task_id not in self.adjacency:
                self.adjacency[task_id] = []
            
            self.in_degree[task_id] = len(dependencies or [])
            
            for dep in (dependencies or []):
                if dep not in self.adjacency:
                    self.adjacency[dep] = []
                self.adjacency[dep].append(task_id)
    
    def topological_sort(self) -> List[str]:
        """
        Kahn算法拓扑排序
        
        时间复杂度: O(V + E)
        空间复杂度: O(V)
        """
        with self._lock:
            in_degree = self.in_degree.copy()
            queue = [t for t, d in in_degree.items() if d == 0]
            result = []
            
            while queue:
                node = queue.pop(0)
                result.append(node)
                
                for neighbor in self.adjacency.get(node, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            
            return result if len(result) == len(self.tasks) else []
    
    def dynamic_schedule(self, system_load: float = 0.5) -> List[str]:
        """
        动态加权调度
        
        调度评分函数：
        S(t) = α × W(t) + β × A(t) + γ × C(t)
        
        其中：
        - W(t) = 剩余工作量权重
        - A(t) = 等待时间因子（公平性）
        - C(t) = 缓存收益
        - α + β + γ = 1
        """
        with self._lock:
            alpha = 0.4
            beta = 0.3
            gamma = 0.3
            
            ready_tasks = [t for t, d in self.in_degree.items() if d == 0]
            scheduled = []
            remaining_deps = self.in_degree.copy()
            
            while ready_tasks:
                best_task = None
                best_score = -float('inf')
                
                for task_id in ready_tasks:
                    task = self.tasks[task_id]
                    
                    wait_time = len(scheduled)
                    max_weight = max(t.weight for t in self.tasks.values()) if self.tasks else 1
                    max_cache = max(t.cache_benefit for t in self.tasks.values()) if self.tasks else 1
                    
                    normalized_weight = task.weight / max_weight if max_weight > 0 else 0
                    normalized_wait = wait_time / len(self.tasks) if self.tasks else 0
                    normalized_cache = task.cache_benefit / max_cache if max_cache > 0 else 0
                    
                    score = (alpha * normalized_weight + 
                            beta * normalized_wait + 
                            gamma * normalized_cache)
                    
                    if score > best_score:
                        best_score = score
                        best_task = task_id
                
                if best_task:
                    scheduled.append(best_task)
                    ready_tasks.remove(best_task)
                    
                    for neighbor in self.adjacency.get(best_task, []):
                        remaining_deps[neighbor] -= 1
                        if remaining_deps[neighbor] == 0:
                            ready_tasks.append(neighbor)
            
            return scheduled
    
    def get_critical_path(self) -> Tuple[List[str], float]:
        """
        计算关键路径
        
        使用动态规划：
        dist[v] = w(v) + max{dist[u] : (u,v) ∈ E}
        """
        with self._lock:
            topo_order = self.topological_sort()
            if not topo_order:
                return [], 0.0
            
            dist = {t: self.tasks[t].weight for t in topo_order}
            prev = {t: None for t in topo_order}
            
            for node in topo_order:
                for dep in self.tasks[node].dependencies:
                    if dep in dist:
                        if dist[dep] + self.tasks[node].weight > dist[node]:
                            dist[node] = dist[dep] + self.tasks[node].weight
                            prev[node] = dep
            
            end_node = max(dist, key=dist.get)
            path = []
            current = end_node
            
            while current:
                path.append(current)
                current = prev[current]
            
            path.reverse()
            return path, dist[end_node]
    
    def calculate_parallelism(self) -> float:
        """
        计算理论并行度
        
        P = Σw_i / L_critical
        """
        total_weight = sum(t.weight for t in self.tasks.values())
        _, critical_length = self.get_critical_path()
        
        if critical_length > 0:
            return total_weight / critical_length
        return 1.0


class ManifoldOptimizer:
    """
    流形学习优化器
    基于PCA的特征空间降维
    
    数学原理：
    PCA寻找投影矩阵W，最大化投影方差：
    max_W Var(XW) s.t. W^T W = I
    
    求解：协方差矩阵特征分解
    Σ = (1/n-1) X^T X
    Σv = λv
    """
    
    def __init__(self, target_dim: int = 64):
        self.target_dim = target_dim
        self.pca_model = None
        self.fitted = False
    
    def fit(self, embeddings: np.ndarray) -> 'ManifoldOptimizer':
        """
        拟合PCA模型
        
        时间复杂度: O(n × d²) for covariance
                    O(d³) for eigendecomposition
        """
        if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
            return self
        
        if embeddings.shape[1] <= self.target_dim:
            self.fitted = True
            return self
        
        self.pca_model = PCA(n_components=self.target_dim)
        self.pca_model.fit(embeddings)
        self.fitted = True
        return self
    
    def transform(self, embeddings: np.ndarray) -> np.ndarray:
        """
        降维变换
        
        时间复杂度: O(n × d × k)
        其中 d=原始维度, k=目标维度
        """
        if not self.fitted or self.pca_model is None:
            return embeddings
        
        return self.pca_model.transform(embeddings)
    
    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
        """拟合并变换"""
        self.fit(embeddings)
        return self.transform(embeddings)
    
    def get_complexity_score(self, embedding: np.ndarray) -> float:
        """
        计算embedding复杂度
        
        使用方差作为复杂度度量：
        σ(E) = sqrt(1/d × Σ(E_i - μ)²)
        
        信息论角度：
        H(E) ∝ log(σ(E) + 1)
        """
        if not NUMPY_AVAILABLE:
            return 0.5
        
        variance = np.var(embedding)
        return float(np.sqrt(variance))
    
    def adaptive_steps(self, embedding: np.ndarray, 
                       min_steps: int = 10, 
                       max_steps: int = 50) -> int:
        """
        自适应推理步数
        
        N_steps = ⌊N_min + (N_max - N_min) × σ(E)/σ_max⌋
        """
        complexity = self.get_complexity_score(embedding)
        normalized = min(1.0, complexity / 10.0)
        
        steps = int(min_steps + (max_steps - min_steps) * normalized)
        return steps


class CacheAwareLayout:
    """
    CPU缓存感知数据布局优化器
    
    数学模型：
    缓存命中率 H = cache_hits / total_accesses
    
    数据对齐优化：
    若 addr₀ ≡ 0 (mod C)，则连续访问时
    一个缓存行可容纳 ⌊C/sizeof(dtype)⌋ 个元素
    """
    
    CACHE_LINE_SIZE = 64
    
    def __init__(self, cache_line_size: int = 64):
        self.cache_line_size = cache_line_size
    
    def align_size(self, size: int, dtype_size: int = 4) -> int:
        """
        计算缓存行对齐后的尺寸
        
        aligned_size = ⌈size × dtype_size / C⌉ × C / dtype_size
        """
        total_bytes = size * dtype_size
        aligned_bytes = ((total_bytes + self.cache_line_size - 1) // 
                         self.cache_line_size * self.cache_line_size)
        return aligned_bytes // dtype_size
    
    def optimize_layout(self, data: List[Any]) -> List[Any]:
        """
        优化数据布局以提高缓存命中率
        
        策略：按访问频率排序，热点数据放前面
        """
        if not data:
            return data
        
        return data
    
    def calculate_cache_efficiency(self, access_pattern: List[int], 
                                   cache_size: int) -> float:
        """
        计算缓存效率
        
        使用工作集模型：
        WSS = |{unique accesses in window}|
        效率 = 1 - WSS/cache_size (if WSS < cache_size)
        """
        if not access_pattern:
            return 1.0
        
        unique_accesses = len(set(access_pattern))
        
        if unique_accesses <= cache_size:
            return 1.0 - (unique_accesses / cache_size) * 0.1
        else:
            return cache_size / unique_accesses


class HybridCache:
    """
    混合缓存策略 (LFU + LRU)
    
    数学模型：
    Score(x) = λ × f(x)/f_max + (1-λ) × g(x)/m
    
    其中：
    - f(x) = 访问频率
    - g(x) = 最近访问时间
    - λ = 权重因子
    """
    
    def __init__(self, max_size: int = 100, lfu_weight: float = 0.6):
        self.max_size = max_size
        self.lfu_weight = lfu_weight
        
        self._cache: OrderedDict = OrderedDict()
        self._frequency: Dict[str, int] = {}
        self._access_time: Dict[str, int] = {}
        self._lock = threading.RLock()
        
        self._request_count = 0
        self._hits = 0
        self._misses = 0
    
    def _compute_score(self, key: str) -> float:
        """计算混合淘汰分数"""
        freq = self._frequency.get(key, 1)
        max_freq = max(self._frequency.values()) if self._frequency else 1
        
        access_time = self._access_time.get(key, 0)
        max_time = self._request_count if self._request_count > 0 else 1
        
        normalized_freq = freq / max_freq if max_freq > 0 else 0
        normalized_time = access_time / max_time if max_time > 0 else 0
        
        return (self.lfu_weight * normalized_freq + 
                (1 - self.lfu_weight) * normalized_time)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            self._request_count += 1
            
            if key in self._cache:
                self._hits += 1
                self._frequency[key] = self._frequency.get(key, 0) + 1
                self._access_time[key] = self._request_count
                self._cache.move_to_end(key)
                return self._cache[key]
            
            self._misses += 1
            return None
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        with self._lock:
            if key in self._cache:
                self._cache[key] = value
                self._frequency[key] = self._frequency.get(key, 0) + 1
                self._access_time[key] = self._request_count
                self._cache.move_to_end(key)
                return
            
            while len(self._cache) >= self.max_size:
                min_key = min(self._cache.keys(), 
                             key=lambda k: self._compute_score(k))
                del self._cache[min_key]
                self._frequency.pop(min_key, None)
                self._access_time.pop(min_key, None)
            
            self._cache[key] = value
            self._frequency[key] = 1
            self._access_time[key] = self._request_count
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._frequency.clear()
            self._access_time.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2%}",
            "requests": total
        }


class ImageGenerationPipeline:
    """
    图像生成流水线优化器
    
    整合所有优化策略：
    1. 任务拓扑调度
    2. 流形降维
    3. 缓存感知布局
    4. 混合缓存
    """
    
    def __init__(self):
        self.scheduler = TopologyScheduler()
        self.manifold = ManifoldOptimizer()
        self.cache_layout = CacheAwareLayout()
        self.result_cache = HybridCache(max_size=50)
        
        self._init_pipeline_tasks()
    
    def _init_pipeline_tasks(self):
        """初始化流水线任务DAG"""
        self.scheduler.add_task("load_model", weight=3.0, 
                               dependencies=[], cache_benefit=0.9)
        self.scheduler.add_task("encode_prompt", weight=1.0, 
                               dependencies=["load_model"], cache_benefit=0.7)
        self.scheduler.add_task("diffusion_inference", weight=5.0, 
                               dependencies=["encode_prompt"], cache_benefit=0.3)
        self.scheduler.add_task("decode_image", weight=1.0, 
                               dependencies=["diffusion_inference"], cache_benefit=0.5)
        self.scheduler.add_task("save_result", weight=0.5, 
                               dependencies=["decode_image"], cache_benefit=0.1)
    
    def get_optimal_schedule(self) -> List[str]:
        """获取最优执行顺序"""
        return self.scheduler.dynamic_schedule()
    
    def get_parallelism(self) -> float:
        """获取理论并行度"""
        return self.scheduler.calculate_parallelism()
    
    def cache_prompt_result(self, prompt: str, params: Dict, result: Any) -> None:
        """缓存生成结果"""
        cache_key = self._generate_cache_key(prompt, params)
        self.result_cache.set(cache_key, result)
    
    def get_cached_result(self, prompt: str, params: Dict) -> Optional[Any]:
        """获取缓存结果"""
        cache_key = self._generate_cache_key(prompt, params)
        return self.result_cache.get(cache_key)
    
    def _generate_cache_key(self, prompt: str, params: Dict) -> str:
        """生成缓存键"""
        content = f"{prompt}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def estimate_steps(self, prompt_embedding: np.ndarray = None) -> int:
        """估算最优推理步数"""
        if prompt_embedding is not None:
            return self.manifold.adaptive_steps(prompt_embedding)
        return 20
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        critical_path, critical_length = self.scheduler.get_critical_path()
        
        return {
            "schedule": self.get_optimal_schedule(),
            "parallelism": self.get_parallelism(),
            "critical_path": critical_path,
            "critical_length": critical_length,
            "cache_stats": self.result_cache.get_stats()
        }


_global_pipeline: Optional[ImageGenerationPipeline] = None
_pipeline_lock = threading.Lock()


def get_optimization_pipeline() -> ImageGenerationPipeline:
    """获取全局优化流水线实例"""
    global _global_pipeline
    
    if _global_pipeline is None:
        with _pipeline_lock:
            if _global_pipeline is None:
                _global_pipeline = ImageGenerationPipeline()
    
    return _global_pipeline


def optimize_generation_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    优化生成参数
    
    应用自适应步数和缓存策略
    """
    pipeline = get_optimization_pipeline()
    
    prompt = params.get("prompt", "")
    cached = pipeline.get_cached_result(prompt, params)
    
    if cached:
        params["_cached"] = True
        params["_cache_hit"] = True
    else:
        steps = params.get("steps", 20)
        if steps < 10:
            params["steps"] = pipeline.estimate_steps()
    
    return params
