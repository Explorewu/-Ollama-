"""
RAG API 模块

提供 RAG 检索相关接口
"""

import logging
from flask import request, jsonify

from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

RAG_AVAILABLE = False
rag_service = None


def init_rag_service():
    """初始化 RAG 服务"""
    global RAG_AVAILABLE, rag_service
    try:
        from rag_service import get_rag_service
        rag_service = get_rag_service()
        RAG_AVAILABLE = True
        logger.info("RAG 服务初始化成功")
    except ImportError as e:
        logger.warning(f"RAG 服务不可用: {e}")


def register_rag_routes(app):
    """注册 RAG 相关路由"""
    
    if rag_service is None:
        logger.warning("RAG 服务不可用，跳过路由注册")
        return
    
    @app.route('/api/rag/retrieve', methods=['POST'])
    def rag_retrieve_api():
        """RAG 检索接口"""
        try:
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify(error_response("缺少 query 参数", 400)), 400
            
            query = data['query']
            top_k = data.get('top_k')
            
            result = rag_service.retrieve(query=query, top_k=top_k)
            
            if result.get('success'):
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '检索成功')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '检索失败')),
                    code=500
                )), 500
        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/rag/status', methods=['GET'])
    def rag_status_api():
        """获取 RAG 系统状态"""
        try:
            result = rag_service.get_status()
            return jsonify(success_response(data=result, message="获取状态成功"))
        except Exception as e:
            logger.error(f"获取 RAG 状态失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/rag/health', methods=['GET'])
    def rag_health_api():
        """RAG 健康检查"""
        try:
            result = rag_service.health_check()
            return jsonify(success_response(data=result, message="健康检查完成"))
        except Exception as e:
            logger.error(f"RAG 健康检查失败: {e}")
            return jsonify(error_response(message=str(e), code=500, data={"healthy": False})), 500
    
    @app.route('/api/rag/reload', methods=['POST'])
    def rag_reload_api():
        """重新加载 RAG 索引"""
        try:
            force_rebuild = request.args.get('force_rebuild', 'false').lower() == 'true'
            result = rag_service.reload(force_rebuild=force_rebuild)
            if result.get('success'):
                return jsonify(success_response(data=result.get('data'), message=result.get('message', '重载成功')))
            else:
                return jsonify(error_response(message=result.get('message', result.get('error', '重载失败')), code=500)), 500
        except Exception as e:
            logger.error(f"RAG 重载失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/rag/clear-cache', methods=['POST'])
    def rag_clear_cache_api():
        """清空 RAG 缓存"""
        try:
            result = rag_service.clear_cache()
            if result.get('success'):
                return jsonify(success_response(data=result.get('data'), message=result.get('message', '缓存已清空')))
            else:
                return jsonify(error_response(message=result.get('message', result.get('error', '清空缓存失败')), code=500)), 500
        except Exception as e:
            logger.error(f"RAG 清空缓存失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/rag/stats', methods=['GET'])
    def rag_stats_api():
        """获取 RAG 统计信息"""
        try:
            stats = {
                "documents": 0,
                "chunks": 0,
                "cache_size": 0,
                "index_size": 0,
                "last_updated": None
            }
            
            # 尝试获取详细统计
            try:
                status = rag_service.get_status()
                if status and isinstance(status, dict):
                    stats["documents"] = status.get("documents_count", 0)
                    stats["chunks"] = status.get("chunks_count", 0)
                    stats["index_size"] = status.get("index_size", 0)
                    stats["last_updated"] = status.get("last_updated")
            except Exception as e:
                logger.warning(f"获取RAG详细统计失败: {e}")
            
            # 尝试获取缓存大小
            try:
                cache_info = rag_service.get_cache_info()
                if cache_info and isinstance(cache_info, dict):
                    stats["cache_size"] = cache_info.get("size", 0)
            except Exception as e:
                logger.warning(f"获取RAG缓存信息失败: {e}")
            
            return jsonify(success_response(data=stats, message="获取统计信息成功"))
        except Exception as e:
            logger.error(f"获取 RAG 统计信息失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ RAG API 路由已注册")
