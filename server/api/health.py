"""
健康检查 API 模块

提供健康检查、状态监控接口
"""

import time
import logging
import requests
from flask import request, jsonify

from utils.config import OLLAMA_BASE_URL
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)


def register_health_routes(app, services=None):
    """注册健康检查相关路由    
    Args:
        app: Flask 应用
        services: 服务实例字典，包含 memory_service, summary_service 等
    """
    services = services or {}
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """健康检查"""
        services_status = {}
        memory_service = services.get('memory_service')
        summary_service = services.get('summary_service')
        context_manager = services.get('context_manager')
        asr_service = services.get('asr_service')
        
        services_status["memory"] = "ready" if memory_service else "not_loaded"
        services_status["summary"] = "ready" if summary_service else "not_loaded"
        services_status["context"] = "ready" if context_manager else "not_loaded"
        services_status["asr"] = asr_service.check_status() if asr_service else "not_loaded"
        
        ollama_connected = False
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            ollama_connected = resp.status_code == 200
        except Exception:
            ollama_connected = False
        services_status["ollama"] = {"connected": ollama_connected}
        services_status["api"] = {"healthy": True}
        
        payload = {
            "status": "healthy",
            "timestamp": int(time.time() * 1000),
            "services": services_status
        }
        response_body = success_response(data=payload)
        response_body["status"] = "healthy"
        return jsonify(response_body)

    @app.route('/api/health/detailed', methods=['GET'])
    def health_check_detailed():
        """更优化的健康检查 (格式合作率得)"""
        return health_check()

    @app.route('/api/stats', methods=['GET'])
    def get_all_stats():
        """获取所有服务统计信息"""
        try:
            stats = {}
            
            memory_service = services.get('memory_service')
            context_manager = services.get('context_manager')
            asr_service = services.get('asr_service')
            
            if memory_service:
                stats["memory"] = memory_service.get_statistics()
            if context_manager:
                stats["context"] = context_manager.get_context_statistics()
            if asr_service:
                stats["asr"] = asr_service.check_status()
            
            return jsonify(success_response(data=stats))
        except Exception as e:
            logger.error(f"获取统计信息失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/ollama/status', methods=['GET'])
    def check_ollama_status():
        """检查 Ollama 服务状态"""
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if response.status_code == 200:
                return jsonify(success_response(data={
                    "running": True,
                    "message": "Ollama 服务正在运行"
                }))
            else:
                return jsonify(success_response(data={
                    "running": False,
                    "message": "Ollama 服务无响应"
                }))
        except requests.exceptions.ConnectionError:
            return jsonify(success_response(data={
                "running": False,
                "message": "无法连接到 Ollama 服务"
            }))
        except Exception as e:
            logger.error(f"检查 Ollama 状态失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/ollama/start', methods=['POST'])
    def start_ollama_service():
        """启动 Ollama 服务（仅返回提示，不实际启动）"""
        try:
            import subprocess
            import platform
            
            if platform.system() == 'Windows':
                try:
                    CREATE_NEW_PROCESS_GROUP = 0x00000200
                    DETACHED_PROCESS = 0x00000008
                    subprocess.Popen(
                        ['ollama', 'serve'],
                        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return jsonify(success_response(data={
                        "started": True,
                        "message": "Ollama 服务启动命令已发送"
                    }))
                except FileNotFoundError:
                    return jsonify(error_response("Ollama 未安装或不在 PATH 中", 404)), 404
            else:
                try:
                    subprocess.Popen(['ollama', 'serve'], 
                                    stdout=subprocess.DEVNULL, 
                                    stderr=subprocess.DEVNULL)
                    return jsonify(success_response(data={
                        "started": True,
                        "message": "Ollama 服务启动命令已发送"
                    }))
                except FileNotFoundError:
                    return jsonify(error_response("Ollama 未安装或不在 PATH 中", 404)), 404
        except Exception as e:
            logger.error(f"启动 Ollama 服务失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/cache/stats', methods=['GET'])
    def cache_stats():
        """获取缓存统计"""
        try:
            smart_cache = services.get('smart_cache')
            if smart_cache:
                return jsonify(success_response(data=smart_cache.get_stats()))
            return jsonify(success_response(data={}))
        except Exception as e:
            logger.error(f"获取缓存统计失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/summary/health', methods=['GET'])
    def summary_health():
        """摘要服务健康检查（兼容旧版前端）"""
        summary_service = services.get('summary_service')
        if summary_service:
            return jsonify(success_response(data={
                "status": "healthy",
                "service": "summary",
                "loaded": True
            }))
        else:
            return jsonify(success_response(data={
                "status": "unhealthy",
                "service": "summary",
                "loaded": False,
                "error": "服务未加载"
            })), 503
    
    @app.route('/api/vision/status', methods=['GET'])
    def vision_status():
        """视觉服务状态检查（兼容旧版前端）"""
        vision_service = services.get('vision_service')
        if vision_service:
            return jsonify(success_response(data={
                "status": "healthy",
                "service": "vision",
                "loaded": True
            }))
        else:
            return jsonify(success_response(data={
                "status": "unhealthy",
                "service": "vision",
                "loaded": False,
                "error": "服务未加载"
            })), 503
    
    @app.route('/api/native_llama_cpp_image/health', methods=['GET'])
    def native_image_health():
        """原生图像服务健康检查（兼容旧版前端）"""
        image_service = services.get('image_service')
        if image_service:
            return jsonify(success_response(data={
                "status": "healthy",
                "service": "nativeImage",
                "loaded": True
            }))
        else:
            return jsonify(success_response(data={
                "status": "unhealthy",
                "service": "nativeImage",
                "loaded": False,
                "error": "服务未加载"
            })), 503
    
    @app.route('/api/cache/clear', methods=['POST'])
    def cache_clear():
        """清空缓存"""
        try:
            smart_cache = services.get('smart_cache')
            if smart_cache:
                smart_cache.clear()
            return jsonify(success_response(message="缓存已清空"))
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/connection/status', methods=['GET'])
    def connection_status():
        """连接状态检查"""
        try:
            status = {
                "backend": "connected",
                "backend_url": "http://localhost:5001",
                "timestamp": int(time.time() * 1000),
                "services": {}
            }
            
            # 检查 Ollama 连接
            try:
                response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
                status["services"]["ollama"] = {
                    "connected": response.status_code == 200,
                    "url": OLLAMA_BASE_URL,
                    "latency_ms": int(response.elapsed.total_seconds() * 1000)
                }
            except Exception as e:
                status["services"]["ollama"] = {
                    "connected": False,
                    "url": OLLAMA_BASE_URL,
                    "error": str(e)
                }
            
            # 检查其他服务
            for service_name in ['memory_service', 'summary_service', 'context_manager', 'asr_service']:
                service = services.get(service_name)
                status["services"][service_name] = {
                    "loaded": service is not None,
                    "status": "ready" if service else "not_loaded"
                }
            
            return jsonify(success_response(data=status))
        except Exception as e:
            logger.error(f"连接状态检查失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/connection/reset', methods=['POST'])
    def reset_connection():
        """重置连接"""
        try:
            reset_result = {
                "timestamp": int(time.time() * 1000),
                "actions": []
            }
            
            # 清空缓存
            smart_cache = services.get('smart_cache')
            if smart_cache:
                smart_cache.clear()
                reset_result["actions"].append("cache_cleared")
            
            # 重置上下文管理器
            context_manager = services.get('context_manager')
            if context_manager:
                try:
                    context_manager.clear_all()
                    reset_result["actions"].append("context_reset")
                except Exception as e:
                    logger.warning(f"重置上下文失败：{e}")
            
            # 重置记忆服务
            memory_service = services.get('memory_service')
            if memory_service:
                try:
                    memory_service.clear_session()
                    reset_result["actions"].append("memory_reset")
                except Exception as e:
                    logger.warning(f"重置记忆失败：{e}")
            
            logger.info(f"连接重置完成：{reset_result['actions']}")
            return jsonify(success_response(data=reset_result, message="连接已重置"))
        except Exception as e:
            logger.error(f"连接重置失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("Health API routes registered")
