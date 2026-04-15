"""
RAG 服务模块

为 Flask API 提供 RAG 检索功能

功能：
- 单次检索
- 带统计信息的检索
- 系统状态查询
- 索引管理（重载、重建）
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system import RAGRetriever

logger = logging.getLogger(__name__)

_rag_instance: Optional[RAGRetriever] = None


def get_rag_service(config_path: str = None) -> 'RAGService':
    """
    获取 RAG 服务实例（单例模式）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        RAGService 实例
    """
    global _rag_instance
    
    if _rag_instance is None:
        _rag_instance = RAGService(config_path)
    
    return _rag_instance


class RAGService:
    """RAG 服务类"""
    
    def __init__(self, config_path: str = None):
        """
        初始化 RAG 服务
        
        Args:
            config_path: 配置文件路径
        """
        self.retriever = RAGRetriever(config_path=config_path)
        logger.info("RAG 服务已初始化")
    
    def retrieve(self, query: str, top_k: int = None, use_fusion: bool = None) -> Dict[str, Any]:
        """
        执行检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            use_fusion: 是否使用混合检索
            
        Returns:
            检索结果和统计信息
        """
        import time
        start_time = time.time()
        
        try:
            config = self.retriever.get_config()
            use_fusion_val = use_fusion if use_fusion is not None else config.get('use_fusion', True)
            score_threshold = config.get('score_threshold', 0.25)
            use_cache = config.get('use_cache', True)
            
            results = self.retriever.retrieve(
                query=query,
                top_k=top_k,
                use_fusion=use_fusion_val,
                use_cache=use_cache
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'data': {
                    'query': query,
                    'results': results,
                    'count': len(results),
                    'elapsed_ms': round(elapsed_ms, 2),
                    'use_fusion': use_fusion_val
                }
            }
        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def retrieve_with_stats(self, query: str, top_k: int = None) -> Dict[str, Any]:
        """
        执行检索并返回详细统计
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            检索结果和完整统计信息
        """
        import time
        start_time = time.time()
        
        try:
            config = self.retriever.get_config()
            use_fusion = config.get('use_fusion', True)
            use_cache = config.get('use_cache', True)
            
            results = self.retriever.retrieve(
                query=query,
                top_k=top_k,
                use_fusion=use_fusion,
                use_cache=use_cache
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            stats = self.retriever.stats()
            config = self.retriever.get_config()
            
            return {
                'success': True,
                'data': {
                    'query': query,
                    'results': results,
                    'count': len(results),
                    'timing': {
                        'elapsed_ms': round(elapsed_ms, 2)
                    },
                    'stats': stats,
                    'config': config
                }
            }
        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取 RAG 系统状态
        
        Returns:
            系统状态信息
        """
        try:
            stats = self.retriever.stats()
            config = self.retriever.get_config()
            
            index_dir = self.retriever.config.get('index_dir', 'unknown')
            index_exists = False
            if hasattr(self.retriever.index_manager, 'index_dir'):
                index_dir = str(self.retriever.index_manager.index_dir)
                index_exists = self.retriever.index_manager.index_dir.exists()
            elif hasattr(self.retriever.config, 'index_dir'):
                from pathlib import Path
                index_path = Path(self.retriever.config.get('index_dir', ''))
                index_exists = index_path.exists()
            
            return {
                'success': True,
                'data': {
                    'initialized': self.retriever._initialized,
                    'index_exists': index_exists,
                    'index_dir': str(index_dir),
                    'config': config,
                    'stats': stats
                }
            }
        except Exception as e:
            logger.error(f"获取 RAG 状态失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reload(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        重新加载索引
        
        Args:
            force_rebuild: 是否强制重新构建
            
        Returns:
            操作结果
        """
        try:
            import time
            start_time = time.time()
            
            self.retriever.reload(force_rebuild=force_rebuild)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'data': {
                    'message': '索引重载完成',
                    'force_rebuild': force_rebuild,
                    'elapsed_ms': round(elapsed_ms, 2),
                    'stats': self.retriever.stats()
                }
            }
        except Exception as e:
            logger.error(f"索引重载失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def clear_cache(self) -> Dict[str, Any]:
        """
        清空缓存
        
        Returns:
            操作结果
        """
        try:
            cleared = False
            
            if hasattr(self.retriever, 'index_manager') and hasattr(self.retriever.index_manager, 'retriever'):
                retriever = self.retriever.index_manager.retriever
                if hasattr(retriever, '_cache'):
                    retriever._cache.clear()
                    cleared = True
                if hasattr(retriever, 'semantic_retriever') and retriever.semantic_retriever:
                    if hasattr(retriever.semantic_retriever, '_cache'):
                        retriever.semantic_retriever._cache.clear()
                        cleared = True
            
            if hasattr(self.retriever, '_clear_cache'):
                self.retriever._clear_cache()
                cleared = True
            
            if not cleared:
                logger.warning("RAG 检索器没有可清空的缓存")
            
            return {
                'success': True,
                'data': {
                    'message': '缓存已清空'
                }
            }
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态
        """
        try:
            stats = self.retriever.stats()
            
            index_stats = stats.get('index', {})
            num_docs = index_stats.get('num_documents', 0)
            num_chunks = index_stats.get('num_chunks', 0)
            
            if num_docs > 0 and num_chunks > 0:
                return {
                    'success': True,
                    'healthy': True,
                    'message': 'RAG 系统正常'
                }
            else:
                return {
                    'success': True,
                    'healthy': False,
                    'message': '索引为空，请先构建索引'
                }
        except Exception as e:
            logger.error(f"RAG 健康检查失败: {e}")
            return {
                'success': False,
                'healthy': False,
                'error': str(e)
            }
