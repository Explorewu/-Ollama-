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
from .audio_codec import register_audio_codec_routes
from .model_eval import model_eval_bp
from .storage import storage_bp
from .ceee import ceee_bp
from .elpe import elpe_bp
from .lsmpe import lsmpe_bp
from .ciscg import ciscg_bp
from .temg import temg_bp
from .unified_engine import unified_engine_bp
from .knowledge_graph import knowledge_graph_bp
from .v2 import v2_bp, openai_bp
from .proactive import proactive_bp
from .music import music_bp
from .unified_memory import unified_memory_bp
from .knowledge_flywheel import knowledge_flywheel_bp

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
    'register_audio_codec_routes',
    'model_eval_bp',
    'storage_bp',
    'ceee_bp',
    'elpe_bp',
    'lsmpe_bp',
    'ciscg_bp',
    'temg_bp',
    'unified_engine_bp',
    'knowledge_graph_bp',
    'v2_bp',
    'openai_bp',
    'proactive_bp',
    'music_bp',
    'unified_memory_bp',
    'knowledge_flywheel_bp',
]
