"""
Smart Greeting API - 智能问候语生成

使用小模型(qwen3.5:0.8b)生成个性化问候语，降低资源占用
支持上下文感知和定时弹出，模型不可用时自动降级
"""

import json
import logging
import time
import uuid
from datetime import datetime

import requests
from flask import jsonify, request

from utils.config import OLLAMA_BASE_URL, GREETING_MODEL

logger = logging.getLogger(__name__)

GREETING_CACHE = {}
_MODEL_AVAILABLE = None

GREETING_PROMPTS = {
    "morning": "生成一句早晨问候语，15字以内，温暖有活力，无emoji，无套话。只输出问候语：",
    "afternoon": "生成一句下午问候语，15字以内，轻松有趣，无emoji，无套话。只输出问候语：",
    "evening": "生成一句晚上问候语，15字以内，温馨放松，无emoji，无套话。只输出问候语：",
    "night": "生成一句深夜问候语，15字以内，关心体贴，无emoji，无套话。只输出问候语：",
    "idle": "生成一句关心问候，15字以内，自然不突兀，无emoji。只输出问候语：",
    "context": "根据上下文生成一句简短问候或提醒，15字以内，自然有用，无emoji。上下文：{context}。只输出问候语：",
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


def _check_model_available(model_name=None):
    global _MODEL_AVAILABLE
    if _MODEL_AVAILABLE is not None:
        return _MODEL_AVAILABLE
    try:
        target = model_name or GREETING_MODEL
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            _MODEL_AVAILABLE = any(m.get("name", "") == target for m in models)
            if not _MODEL_AVAILABLE:
                logger.info(f"问候模型 {target} 未安装，将使用降级方案")
    except Exception as e:
        logger.warning(f"检测模型可用性失败: {e}")
        _MODEL_AVAILABLE = False
    return _MODEL_AVAILABLE


def _generate_greeting_via_ollama(prompt, model=None):
    target_model = model or GREETING_MODEL
    if not _check_model_available(target_model):
        return None
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.9,
                "num_predict": 40,
                "top_k": 20,
                "top_p": 0.85,
            }
        }
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            text = (data.get("response") or "").strip()
            text = _clean_greeting_text(text)
            return text if text else None
        else:
            logger.warning(f"问候语生成失败 HTTP {resp.status_code}，标记模型不可用")
            global _MODEL_AVAILABLE
            _MODEL_AVAILABLE = None
    except requests.Timeout:
        logger.warning("问候语生成超时")
        _MODEL_AVAILABLE = None
    except Exception as e:
        logger.warning(f"生成问候语失败: {e}")
    return None


def _clean_greeting_text(text):
    if not text:
        return None
    for prefix in ["问候语：", "问候语:", "输出：", "输出:"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    if len(text) > 30:
        text = text[:30].rstrip("，。！？、：:…")
    if text.startswith(("「", '"', "'", "《")):
        text = text[1:]
    if text.endswith(("」", '"', "'", "》")):
        text = text[:-1]
    return text.strip() if text.strip() else None


def _generate_greeting_via_local(model=None):
    try:
        from local_model_loader import generate_chat_response
        period = _get_time_period()
        prompt = GREETING_PROMPTS.get(period, GREETING_PROMPTS["idle"])
        result = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            model_name=model or GREETING_MODEL,
        )
        if result and isinstance(result, str):
            text = _clean_greeting_text(result)
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

    @app.route("/api/greeting/cleanup", methods=["POST"])
    def api_cleanup_greetings():
        _cleanup_expired()
        return jsonify({"success": True, "remaining": len(GREETING_CACHE)})
