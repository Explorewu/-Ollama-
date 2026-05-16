"""
健康检查 API 模块

提供健康检查、状态监控、自动修复接口
"""

import os
import time
import logging
import requests
from flask import request, jsonify

from utils.config import OLLAMA_BASE_URL
from utils.helpers import success_response, error_response
from utils.auth import require_api_key

try:
    from auto_heal import auto_heal
    AUTO_HEAL_AVAILABLE = True
except ImportError:
    AUTO_HEAL_AVAILABLE = False

try:
    from auto_service_recovery import get_auto_recovery
    AUTO_RECOVERY_AVAILABLE = True
except ImportError:
    AUTO_RECOVERY_AVAILABLE = False

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
        try:
            detailed = {
                "timestamp": int(time.time() * 1000),
                "services": {},
                "system": {},
            }

            for service_name in ['memory_service', 'summary_service', 'context_manager', 'asr_service', 'smart_cache']:
                service = services.get(service_name)
                detailed["services"][service_name] = {
                    "loaded": service is not None,
                    "status": "ready" if service else "not_loaded",
                }
                if service and hasattr(service, 'get_statistics'):
                    try:
                        detailed["services"][service_name]["statistics"] = service.get_statistics()
                    except Exception:
                        pass

            try:
                resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
                if resp.ok:
                    models = resp.json().get("models", [])
                    detailed["services"]["ollama"] = {
                        "connected": True,
                        "model_count": len(models),
                        "models": [m.get("name", "") for m in models],
                    }
                else:
                    detailed["services"]["ollama"] = {"connected": False, "status_code": resp.status_code}
            except Exception as e:
                detailed["services"]["ollama"] = {"connected": False, "error": str(e)}

            try:
                import psutil
                detailed["system"] = {
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent,
                }
            except ImportError:
                detailed["system"] = {"note": "psutil not installed"}

            detailed["status"] = "healthy"
            return jsonify(success_response(data=detailed))
        except Exception as e:
            logger.error(f"detailed health check failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

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
    @require_api_key
    def start_ollama_service():
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
                "status": "not_loaded",
                "service": "summary",
                "loaded": False,
                "message": "摘要服务未加载，按需启动"
            }))
    
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
                "status": "not_loaded",
                "service": "vision",
                "loaded": False,
                "message": "视觉服务未加载，按需启动"
            }))
    
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
                "status": "not_loaded",
                "service": "nativeImage",
                "loaded": False,
                "message": "图像服务未加载，按需启动"
            }))
    
    @app.route('/api/cache/clear', methods=['POST'])
    @require_api_key
    def cache_clear():
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
    @require_api_key
    def reset_connection():
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

    @app.route('/api/health/auto_heal', methods=['POST'])
    @require_api_key
    def auto_heal_endpoint():
        if not AUTO_HEAL_AVAILABLE:
            return jsonify(error_response("auto_heal模块未加载", 503)), 503
        try:
            data = request.json or {}
            error_message = data.get("error_message", "")
            source = data.get("source", "manual")
            response_data = data.get("response_data")
            extra = data.get("extra")
            if not error_message:
                return jsonify(error_response("error_message is required", 400)), 400
            result = auto_heal.diagnose_and_repair(
                error_message=error_message,
                source=source,
                response_data=response_data,
                extra=extra,
            )
            return jsonify(success_response(data=result))
        except Exception as e:
            logger.error(f"自动修复失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/health/auto_heal/status', methods=['GET'])
    def auto_heal_status():
        """获取自动修复状态"""
        if not AUTO_HEAL_AVAILABLE:
            return jsonify(success_response(data={"available": False}))
        return jsonify(success_response(data={
            "available": True,
            **auto_heal.get_status(),
        }))

    @app.route('/api/health/inspect', methods=['POST'])
    def inspect_response_endpoint():
        """检查API响应是否存在状态矛盾"""
        if not AUTO_HEAL_AVAILABLE:
            return jsonify(success_response(data={"available": False}))
        try:
            data = request.json or {}
            result = auto_heal.inspect_response(data, source="manual_inspect")
            return jsonify(success_response(data=result))
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/services/status', methods=['GET'])
    def services_status():
        """获取所有服务状态"""
        try:
            if AUTO_RECOVERY_AVAILABLE:
                recovery = get_auto_recovery()
                report = recovery.get_status_report()
                return jsonify(success_response(data=report))
            else:
                # 基础状态检查
                status = {
                    'timestamp': time.time(),
                    'services': {},
                    'summary': {'total': 0, 'running': 0, 'stopped': 0, 'failed': 0, 'starting': 0}
                }
                return jsonify(success_response(data=status))
        except Exception as e:
            logger.error(f"获取服务状态失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/services/recover', methods=['POST'])
    def services_recover():
        """手动触发服务恢复"""
        try:
            if not AUTO_RECOVERY_AVAILABLE:
                return jsonify(error_response("自动恢复模块未加载", 503)), 503
            
            data = request.json or {}
            service_name = data.get('service')
            
            recovery = get_auto_recovery()
            
            if service_name:
                # 恢复指定服务
                success = recovery.recover_service(service_name)
                return jsonify(success_response(data={
                    'service': service_name,
                    'success': success,
                    'state': recovery.service_states.get(service_name, 'unknown').value if hasattr(recovery.service_states.get(service_name), 'value') else str(recovery.service_states.get(service_name))
                }))
            else:
                # 恢复所有离线服务
                results = recovery.check_and_recover()
                return jsonify(success_response(data={
                    'results': results,
                    'message': '恢复命令已执行'
                }))
        except Exception as e:
            logger.error(f"服务恢复失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/services/start', methods=['POST'])
    def services_start():
        """启动指定服务"""
        try:
            if not AUTO_RECOVERY_AVAILABLE:
                return jsonify(error_response("自动恢复模块未加载", 503)), 503
            
            data = request.json or {}
            service_name = data.get('service')
            
            if not service_name:
                return jsonify(error_response("缺少 service 参数", 400)), 400
            
            recovery = get_auto_recovery()
            success = recovery.start_service(service_name)
            
            return jsonify(success_response(data={
                'service': service_name,
                'success': success,
                'state': recovery.service_states.get(service_name, 'unknown').value if hasattr(recovery.service_states.get(service_name), 'value') else str(recovery.service_states.get(service_name))
            }))
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("Health API routes registered")
