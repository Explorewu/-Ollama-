"""
Smart Greeting API - 智能问候语生成

模型空闲时生成个性化问候语，支持上下文感知和定时弹出
"""

import json
import logging
import time
import uuid
from datetime import datetime

import requests
from flask import jsonify, request

from utils.config import OLLAMA_BASE_URL, DEFAULT_CHAT_MODEL

logger = logging.getLogger(__name__)

GREETING_CACHE = {}
GREETING_PROMPTS = {
    "morning": "现在是早晨，生成一句简短的个性化问候语（15字以内），要温暖有活力，不要带emoji，不要重复常见套话。只输出问候语本身。",
    "afternoon": "现在是下午，生成一句简短的个性化问候语（15字以内），要轻松有趣，不要带emoji，不要重复常见套话。只输出问候语本身。",
    "evening": "现在是晚上，生成一句简短的个性化问候语（15字以内），要温馨放松，不要带emoji，不要重复常见套话。只输出问候语本身。",
    "night": "现在是深夜，生成一句简短的个性化问候语（15字以内），要关心体贴，不要带emoji，不要重复常见套话。只输出问候语本身。",
    "idle": "用户已经一段时间没有操作了，生成一句简短的关心问候（15字以内），要自然不突兀，不要带emoji。只输出问候语本身。",
    "context": "根据以下上下文，生成一句简短的相关问候或提醒（15字以内），要自然有用，不要带emoji。只输出问候语本身。上下文：{context}",
}


def _get_time_period():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


def _generate_greeting_via_ollama(prompt, model=None):
    try:
        model = model or DEFAULT_CHAT_MODEL
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.9,
                "num_predict": 50,
            }
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = (data.get("response") or "").strip()
            if len(text) > 30:
                text = text[:30].rstrip("，。！？、") + "…"
            return text if text else None
    except Exception as e:
        logger.warning(f"生成问候语失败: {e}")
    return None


def _generate_greeting_via_local(model=None):
    try:
        from local_model_loader import generate_chat_response
        period = _get_time_period()
        prompt = GREETING_PROMPTS.get(period, GREETING_PROMPTS["default"])
        result = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            model_name=model,
        )
        if result and isinstance(result, str):
            text = result.strip()
            if len(text) > 30:
                text = text[:30].rstrip("，。！？、") + "…"
            return text
    except Exception as e:
        logger.warning(f"本地模型生成问候语失败: {e}")
    return None


def generate_greeting(greeting_type="time", context=None, model=None):
    period = _get_time_period() if greeting_type == "time" else greeting_type
    prompt = GREETING_PROMPTS.get(period, GREETING_PROMPTS["idle"])

    if greeting_type == "context" and context:
        prompt = GREETING_PROMPTS["context"].format(context=context[:100])

    greeting_text = _generate_greeting_via_ollama(prompt, model)

    if not greeting_text:
        greeting_text = _generate_greeting_via_local(model)

    if not greeting_text:
        fallback = {
            "morning": "新的一天，新的开始~",
            "afternoon": "下午好，继续加油！",
            "evening": "晚上好，辛苦了~",
            "night": "夜深了，早点休息吧",
            "idle": "还在吗？需要帮忙随时说~",
        }
        greeting_text = fallback.get(period, "你好呀~")

    greeting_id = str(uuid.uuid4())[:8]
    now = time.time()

    greeting_data = {
        "id": greeting_id,
        "content": greeting_text,
        "type": greeting_type,
        "period": period,
        "generated_at": now,
        "scheduled_at": now + 60,
        "displayed": False,
        "expires_at": now + 3600,
    }

    GREETING_CACHE[greeting_id] = greeting_data

    _cleanup_expired()

    return greeting_data


def _cleanup_expired():
    now = time.time()
    expired = [k for k, v in GREETING_CACHE.items() if v.get("expires_at", 0) < now]
    for k in expired:
        del GREETING_CACHE[k]


def register_greeting_routes(app):
    @app.route("/api/greeting/generate", methods=["POST"])
    def api_generate_greeting():
        data = request.get_json(silent=True) or {}
        greeting_type = data.get("type", "time")
        context = data.get("context")
        model = data.get("model")

        result = generate_greeting(greeting_type, context, model)
        return jsonify({"success": True, "data": result})

    @app.route("/api/greeting/list", methods=["GET"])
    def api_list_greetings():
        _cleanup_expired()
        greetings = list(GREETING_CACHE.values())
        return jsonify({"success": True, "data": greetings})

    @app.route("/api/greeting/mark_displayed", methods=["POST"])
    def api_mark_greeting_displayed():
        data = request.get_json(silent=True) or {}
        greeting_id = data.get("id")
        if greeting_id and greeting_id in GREETING_CACHE:
            GREETING_CACHE[greeting_id]["displayed"] = True
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "未找到该问候语"}), 404

    @app.route("/api/greeting/cleanup", methods=["POST"])
    def api_cleanup_greetings():
        _cleanup_expired()
        return jsonify({"success": True, "remaining": len(GREETING_CACHE)})
