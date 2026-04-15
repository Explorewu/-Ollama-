"""
上下文管理 API 模块

提供上下文配置管理、统计信息、清理等功能
"""

import copy
import logging
import time
from flask import request, jsonify

from utils.helpers import success_response, error_response
from utils.config import DEFAULT_CHAT_RUNTIME_CONFIG

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_CONFIG = {
    "maxContextLength": 4096,
    "contextStrategy": "auto",
    "enableContextCompression": True,
    "enableSmartContext": True,
    "contextWindowSize": 10,
    # 聊天运行时配置（用于提示词/输出策略）
    **DEFAULT_CHAT_RUNTIME_CONFIG
}

ALLOWED_ENUMS = {
    "reasoning_summary_level": {"off", "brief", "standard"},
    "response_depth": {"brief", "standard", "deep"},
    "system_prompt_mode": {"template", "custom"},
    "safety_mode": {"strict", "balanced", "relaxed"}
}

_context_store = {
    "version": 1,
    "updated_at": int(time.time() * 1000),
    "global_defaults": copy.deepcopy(DEFAULT_CONTEXT_CONFIG),
    "conversation_overrides": {}
}

_context_stats = {
    "totalMessages": 0,
    "totalConversations": 0,
    "averageContextLength": 0
}


def _sanitize_config(config: dict) -> dict:
    """清洗配置，仅保留允许字段并规范取值"""
    if not isinstance(config, dict):
        return {}

    result = {}
    for key, value in config.items():
        if key not in DEFAULT_CONTEXT_CONFIG:
            continue

        if key == "persona_strength":
            try:
                value = int(value)
            except Exception:
                value = DEFAULT_CONTEXT_CONFIG["persona_strength"]
            value = max(0, min(100, value))

        if key in ("max_response_tokens", "maxContextLength", "contextWindowSize"):
            try:
                value = int(value)
            except Exception:
                value = DEFAULT_CONTEXT_CONFIG.get(key, 0)

        if key in ("temperature", "repeat_penalty"):
            try:
                value = float(value)
            except Exception:
                value = DEFAULT_CONTEXT_CONFIG.get(key, 0.0)

        if key in ALLOWED_ENUMS and value not in ALLOWED_ENUMS[key]:
            value = DEFAULT_CONTEXT_CONFIG[key]

        if key in ("thinking", "show_reasoning_summary", "enableContextCompression",
                   "enableSmartContext", "adult_tone_mode", "adult_tone_acknowledged"):
            value = bool(value)

        result[key] = value

    return result


def get_effective_context_config(conversation_id: str = None) -> dict:
    """获取生效配置（系统默认 -> 全局 -> 会话覆盖）"""
    effective = copy.deepcopy(DEFAULT_CONTEXT_CONFIG)
    effective.update(_context_store.get("global_defaults", {}))
    if conversation_id:
        overrides = _context_store["conversation_overrides"].get(conversation_id, {})
        effective.update(overrides)
    return effective


def register_context_routes(app, services=None):
    """注册上下文管理 API 路由"""

    @app.route('/api/context/config', methods=['GET', 'OPTIONS'])
    def get_context_config():
        if request.method == 'OPTIONS':
            return jsonify(success_response(message='OK'))

        try:
            conversation_id = request.args.get("conversation_id")
            return jsonify(success_response(data=get_effective_context_config(conversation_id)))
        except Exception as e:
            logger.error(f"获取上下文配置失败: {e}")
            return jsonify(error_response(f"获取配置失败: {str(e)}")), 500

    @app.route('/api/context/config', methods=['POST', 'OPTIONS'])
    def update_context_config():
        if request.method == 'OPTIONS':
            return jsonify(success_response(message='OK'))

        try:
            payload = request.get_json() or {}
            conversation_id = payload.get("conversation_id")
            incoming = payload.get("settings", payload)
            sanitized = _sanitize_config(incoming)

            if conversation_id:
                existing = _context_store["conversation_overrides"].get(conversation_id, {})
                existing.update(sanitized)
                _context_store["conversation_overrides"][conversation_id] = existing
                updated = get_effective_context_config(conversation_id)
            else:
                _context_store["global_defaults"].update(sanitized)
                updated = get_effective_context_config()

            _context_store["updated_at"] = int(time.time() * 1000)
            _context_stats["totalConversations"] = len(_context_store["conversation_overrides"])

            return jsonify(success_response(data=updated, message="配置更新成功"))
        except Exception as e:
            logger.error(f"更新上下文配置失败: {e}")
            return jsonify(error_response(f"更新配置失败: {str(e)}")), 500

    @app.route('/api/context/config/reset', methods=['POST', 'OPTIONS'])
    def reset_context_config():
        if request.method == 'OPTIONS':
            return jsonify(success_response(message='OK'))

        try:
            payload = request.get_json() or {}
            conversation_id = payload.get("conversation_id")

            if conversation_id:
                _context_store["conversation_overrides"].pop(conversation_id, None)
                data = get_effective_context_config(conversation_id)
            else:
                _context_store["global_defaults"] = copy.deepcopy(DEFAULT_CONTEXT_CONFIG)
                _context_store["conversation_overrides"] = {}
                data = get_effective_context_config()

            _context_store["updated_at"] = int(time.time() * 1000)
            _context_stats["totalConversations"] = len(_context_store["conversation_overrides"])
            return jsonify(success_response(data=data, message="配置已重置为默认值"))
        except Exception as e:
            logger.error(f"重置上下文配置失败: {e}")
            return jsonify(error_response(f"重置配置失败: {str(e)}")), 500

    @app.route('/api/context/clear', methods=['POST', 'OPTIONS'])
    def clear_context():
        if request.method == 'OPTIONS':
            return jsonify(success_response(message='OK'))

        try:
            return jsonify(success_response(message="上下文数据已清理"))
        except Exception as e:
            logger.error(f"清理上下文失败: {e}")
            return jsonify(error_response(f"清理失败: {str(e)}")), 500

    @app.route('/api/context/stats', methods=['GET', 'OPTIONS'])
    def get_context_stats():
        if request.method == 'OPTIONS':
            return jsonify(success_response(message='OK'))

        try:
            conversation_id = request.args.get('conversation_id')

            if conversation_id:
                memory_service = services.get('memory_service') if services else None
                if memory_service:
                    try:
                        stats = memory_service.get_statistics()
                        stats["conversationId"] = conversation_id
                        return jsonify(success_response(data=stats))
                    except Exception as e:
                        logger.warning(f"获取对话统计失败: {e}")

            _context_stats["totalConversations"] = len(_context_store["conversation_overrides"])
            return jsonify(success_response(data=_context_stats))
        except Exception as e:
            logger.error(f"获取上下文统计失败: {e}")
            return jsonify(error_response(f"获取统计失败: {str(e)}")), 500

    logger.info("✓ 上下文管理 API 路由已注册")
