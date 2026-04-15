"""
智能交互 API 服务 (重构版 v2)

主入口文件，负责初始化服务和注册路由
所有业务逻辑已拆分到 api/ 和 utils/ 子模块

修复:
- 应用工厂模式，避免模块级副作用
- CORS 安全配置
- 环境变量支持
- 服务失败处理
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from flask import Flask, jsonify, request
from flask_cors import CORS

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

from utils.helpers import error_response, success_response

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REQUIRED_SERVICES = ['memory_service', 'context_manager']
OPTIONAL_SERVICES = ['summary_service', 'asr_service', 'smart_cache']


def get_allowed_origins() -> list:
    """获取允许的 CORS 来源"""
    origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080")
    return [origin.strip() for origin in origins_str.split(",") if origin.strip()]


def get_debug_mode() -> bool:
    """获取调试模式配置"""
    return os.getenv("FLASK_ENV", "production") == "development"


def init_services() -> Dict[str, Any]:
    """初始化所有服务"""
    from utils.config import OLLAMA_BASE_URL
    
    services = {}
    failed_required = []
    
    service_configs = [
        ('memory_service', 'memory_service', 'get_memory_service', True),
        ('summary_service', 'summary_service', 'get_summary_service', False),
        ('context_manager', 'context_manager', 'get_context_manager', True),
        ('asr_service', 'asr.factory', 'create_asr_service', False),
        ('smart_cache', 'smart_cache', 'get_smart_cache', False),
    ]
    
    for service_key, module_name, func_name, is_required in service_configs:
        try:
            if service_key == 'asr_service':
                from asr.factory import create_asr_service, ASREngineType
                services[service_key] = create_asr_service(ASREngineType.QWEN3_ASR)
            elif service_key == 'memory_service':
                from memory_service import get_memory_service
                services[service_key] = get_memory_service(OLLAMA_BASE_URL)
            elif service_key == 'summary_service':
                from summary_service import get_summary_service
                services[service_key] = get_summary_service(OLLAMA_BASE_URL)
            elif service_key == 'context_manager':
                from context_manager import get_context_manager
                services[service_key] = get_context_manager()
            elif service_key == 'smart_cache':
                from smart_cache import get_smart_cache
                services[service_key] = get_smart_cache()
            
            logger.info(f"✓ {service_key} 已加载")
            
        except Exception as e:
            logger.warning(f"⚠ {service_key} 加载失败: {e}")
            if is_required:
                failed_required.append(service_key)
    
    if failed_required:
        error_msg = f"必需服务加载失败: {', '.join(failed_required)}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    
    return services


def init_api_services(services: Dict[str, Any]):
    """初始化 API 模块所需的服务"""
    from utils.config import OLLAMA_BASE_URL
    
    try:
        from api.memory import init_memory_service
        init_memory_service(OLLAMA_BASE_URL)
    except Exception as e:
        logger.warning(f"⚠ memory API 初始化失败: {e}")
    
    try:
        from api.summary import init_summary_service
        init_summary_service(OLLAMA_BASE_URL)
    except Exception as e:
        logger.warning(f"⚠ summary API 初始化失败: {e}")
    
    try:
        from api.api_key import init_api_key_service
        init_api_key_service()
    except Exception as e:
        logger.warning(f"⚠ api_key API 初始化失败: {e}")
    
    try:
        from api.asr import init_asr_services
        init_asr_services()
    except Exception as e:
        logger.warning(f"⚠ asr API 初始化失败: {e}")
    
    try:
        from api.group_chat import init_group_chat_services
        init_group_chat_services()
    except Exception as e:
        logger.warning(f"⚠ group_chat API 初始化失败: {e}")
    
    try:
        from api.rag import init_rag_service
        init_rag_service()
    except Exception as e:
        logger.warning(f"⚠ rag API 初始化失败: {e}")
    
    try:
        from api.functions import init_functions_service
        init_functions_service()
    except Exception as e:
        logger.warning(f"⚠ functions API 初始化失败: {e}")


def register_routes(app: Flask, services: Dict[str, Any]):
    """注册所有 API 路由（仅注册路由，不初始化）"""
    from api import (
        register_chat_routes,
        register_image_routes,
        register_memory_routes,
        register_summary_routes,
        register_models_routes,
        register_api_key_routes,
        register_health_routes,
        register_asr_routes,
        register_group_chat_routes,
        register_search_routes,
        register_rag_routes,
        register_vision_routes,
        register_functions_routes,
        register_context_routes,
        register_ollama_proxy_routes,
        register_greeting_routes,
    )
    
    register_health_routes(app, services)
    register_chat_routes(app)
    register_image_routes(app)
    register_memory_routes(app)
    register_summary_routes(app)
    register_ollama_proxy_routes(app)
    register_models_routes(app)
    register_api_key_routes(app)
    register_asr_routes(app)
    register_group_chat_routes(app)
    register_search_routes(app)
    register_rag_routes(app)
    register_vision_routes(app)
    register_functions_routes(app)
    register_context_routes(app, services)
    register_greeting_routes(app)
    
    logger.info("✓ 所有 API 路由已注册")


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """
    创建 Flask 应用（应用工厂模式）
    
    Args:
        config: 可选的配置字典
    
    Returns:
        Flask 应用实例
    """
    from utils.config import OLLAMA_BASE_URL, PORT_API
    
    app = Flask(__name__)
    
    if config:
        app.config.update(config)
    
    allowed_origins = get_allowed_origins()
    cors_resources = {
        r"/api/*": {
            "origins": allowed_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "supports_credentials": True,
            "max_age": 3600
        }
    }
    CORS(app, resources=cors_resources)
    
    services = init_services()
    
    init_api_services(services)
    
    register_routes(app, services)
    
    # 推理模式控制路由（直接在这里注册，确保能找到）
    @app.route("/api/reasoning", methods=["GET", "POST"])
    def reasoning_control():
        """获取或设置推理模式（前端直接调用，无需认证）"""
        try:
            from local_model_loader import get_reasoning_mode, set_reasoning_mode
            if request.method == "GET":
                return jsonify(success_response({
                    "reasoning_enabled": get_reasoning_mode()
                }))
            else:
                data = request.json or {}
                enabled = data.get("enabled", False)
                if not isinstance(enabled, bool):
                    return jsonify(error_response("enabled must be boolean", 400)), 400
                set_reasoning_mode(enabled)
                logger.info(f"推理模式已设置为: {'开启' if enabled else '关闭'}")
                return jsonify(success_response({
                    "reasoning_enabled": enabled,
                    "message": f"推理模式已{'开启' if enabled else '关闭'}（重启模型后生效）"
                }))
        except Exception as e:
            logger.error(f"reasoning control failed: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    app.services = services
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error", "message": str(error)}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": str(error)}), 404
    
    logger.info(f"✓ Flask 应用创建完成，CORS 允许来源: {allowed_origins}")
    
    return app


app: Optional[Flask] = None


def get_app() -> Flask:
    """获取应用实例（延迟初始化）"""
    global app
    if app is None:
        app = create_app()
    return app


if __name__ == '__main__':
    from utils.config import OLLAMA_BASE_URL, PORT_API
    import threading
    import asyncio

    logger.info("=" * 50)
    logger.info("启动智能交互 API 服务 (重构版 v2)")
    logger.info(f"Ollama 地址: {OLLAMA_BASE_URL}")
    logger.info(f"API 端口: {PORT_API}")
    logger.info(f"调试模式: {get_debug_mode()}")
    logger.info(f"CORS 来源: {get_allowed_origins()}")
    logger.info("=" * 50)

    def start_websocket_service():
        try:
            from voice_call_service import main as ws_main
            asyncio.run(ws_main())
        except Exception as e:
            logger.error(f"WebSocket 服务启动失败: {e}")

    ws_thread = threading.Thread(target=start_websocket_service, daemon=True, name="WebSocket-5005")
    ws_thread.start()
    logger.info("✓ WebSocket 服务已在后台启动 (端口 5005)")

    flask_app = create_app()

    flask_app.run(
        host='0.0.0.0',
        port=PORT_API,
        debug=get_debug_mode(),
        threaded=True
    )
