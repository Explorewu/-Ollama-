"""
API 模块

提供所有 API 路由注册函数
"""

from .chat import register_chat_routes
from .image import register_image_routes
from .memory import register_memory_routes
from .summary import register_summary_routes
from .models import register_models_routes
from .api_key import register_api_key_routes
from .health import register_health_routes
from .asr import register_asr_routes
from .group_chat import register_group_chat_routes
from .search import register_search_routes
from .rag import register_rag_routes
from .vision import register_vision_routes
from .functions import register_functions_routes
from .context import register_context_routes
from .ollama_proxy import register_ollama_proxy_routes
from .greeting import register_greeting_routes

__all__ = [
    'register_chat_routes',
    'register_image_routes',
    'register_memory_routes',
    'register_summary_routes',
    'register_models_routes',
    'register_api_key_routes',
    'register_health_routes',
    'register_asr_routes',
    'register_group_chat_routes',
    'register_search_routes',
    'register_rag_routes',
    'register_vision_routes',
    'register_functions_routes',
    'register_context_routes',
    'register_ollama_proxy_routes',
    'register_greeting_routes',
]
