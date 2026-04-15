"""
Chat API routes.
"""

import json
import logging
import time
import uuid

import requests
from flask import Response, jsonify, request, stream_with_context

from utils.auth import require_api_key
from utils.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_CHAT_RUNTIME_CONFIG,
    DEFAULT_OPENAI_COMPAT_MODEL,
    OLLAMA_BASE_URL,
    REPETITION_DETECTION_CONFIG,
    SAFETY_POLICY_BLOCKS,
    SYSTEM_PROMPT_TEMPLATES,
    build_ollama_options,
)
from utils.helpers import error_response, success_response
from utils.repetition_detector import create_detector

try:
    from local_model_loader import generate_chat_response
    LOCAL_MODEL_AVAILABLE = True
except ImportError:
    LOCAL_MODEL_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_mode_settings():
    """Compatibility helper for older routes that expect chat defaults."""
    return {
        "temperature": DEFAULT_CHAT_RUNTIME_CONFIG["temperature"],
        "repeat_penalty": DEFAULT_CHAT_RUNTIME_CONFIG["repeat_penalty"],
        "top_k": DEFAULT_CHAT_RUNTIME_CONFIG["top_k"],
        "top_p": DEFAULT_CHAT_RUNTIME_CONFIG["top_p"],
        "max_response_tokens": DEFAULT_CHAT_RUNTIME_CONFIG["max_response_tokens"],
    }


def _normalize_message_input(data):
    message = (data.get("message") or "").strip()
    messages = data.get("messages") or []
    if message:
        return message
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user" and item.get("content"):
                return str(item["content"]).strip()
    return ""


def _compose_response_style_block(response_depth):
    mapping = {
        "brief": "Answer briefly. Give the answer first and keep only the most useful details.",
        "standard": "Answer clearly. Lead with the answer, then add key supporting details.",
        "deep": "Answer with steps, tradeoffs, and risks only when that helps the user decide.",
    }
    return mapping.get(response_depth, mapping["brief"])


def _compose_persona_block(persona, strength):
    if not isinstance(persona, dict):
        return ""

    name = persona.get("name", "assistant")
    tone = persona.get("tone", "clear and direct")
    worldview = persona.get("worldview", "")
    signature_style = persona.get("signature_style", "")
    taboo = persona.get("taboo", persona.get("taboos", []))
    taboo_text = ", ".join(taboo) if isinstance(taboo, list) else str(taboo or "")

    return (
        f"Persona: {name}\n"
        f"Strength: {strength}/100\n"
        f"Tone: {tone}\n"
        f"Worldview: {worldview or 'fact-based and practical'}\n"
        f"Style: {signature_style or 'succinct and useful'}\n"
        f"Avoid: {taboo_text or 'nothing special'}"
    )


def _compose_output_contract(show_reasoning_summary, level):
    if not show_reasoning_summary or level == "off":
        return "Do not reveal detailed chain-of-thought. Return only the final answer."
    if level == "brief":
        return "Optionally include a one-sentence reasoning summary, then the final answer."
    return "Include a short high-level reasoning summary, then the final answer."


def build_system_prompt(runtime_cfg, persona=None):
    template_key = runtime_cfg.get("system_prompt_template", "assistant_brief")
    template_text = SYSTEM_PROMPT_TEMPLATES.get(template_key, SYSTEM_PROMPT_TEMPLATES["assistant_brief"])
    if runtime_cfg.get("system_prompt_mode") == "custom" and runtime_cfg.get("system_prompt_custom", "").strip():
        template_text = runtime_cfg["system_prompt_custom"].strip()

    parts = [
        template_text,
        SAFETY_POLICY_BLOCKS.get(runtime_cfg.get("safety_mode", "balanced"), SAFETY_POLICY_BLOCKS["balanced"]),
        _compose_response_style_block(runtime_cfg.get("response_depth", "brief")),
        _compose_persona_block(persona, int(runtime_cfg.get("persona_strength", 40))),
        _compose_output_contract(
            bool(runtime_cfg.get("show_reasoning_summary", False)),
            runtime_cfg.get("reasoning_summary_level", "off"),
        ),
    ]
    return "\n\n".join(part for part in parts if part)


def _summarize_reasoning(message, level):
    if level == "off":
        return ""
    if level == "brief":
        return f"Focused on the core request: {message[:32]}"
    return f"Focused on the goal, constraints, and the shortest workable answer for: {message[:48]}"


def _should_search(message):
    lowered = message.lower()
    search_keywords = ["search", "look up", "latest", "current", "news", "查一下", "搜索", "最新"]
    return any(keyword in lowered for keyword in search_keywords)


def _extract_search_query(message):
    query = message
    for trigger in ["search", "look up", "查一下", "搜索", "最新", "current", "latest"]:
        query = query.replace(trigger, "")
    return " ".join(query.split()).strip()


def _perform_web_search(query):
    if not query:
        return []
    try:
        from web_search_service import WebSearchService

        result = WebSearchService().search(query, max_results=2)
        data = result.get("data") or {}
        return data.get("results") or result.get("results") or []
    except Exception as e:
        logger.warning(f"search context unavailable: {e}")
        return []


def _format_search_results(results):
    if not results:
        return ""
    lines = ["Web search context:"]
    for item in results[:2]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")[:120]
        if title or snippet:
            lines.append(f"- {title}: {snippet}")
    return "\n".join(lines)


def _build_runtime_config(conversation_id, incoming_cfg):
    from api.context import get_effective_context_config

    runtime_cfg = get_effective_context_config(conversation_id)
    if isinstance(incoming_cfg, dict):
        runtime_cfg = {**runtime_cfg, **incoming_cfg}
    return {**DEFAULT_CHAT_RUNTIME_CONFIG, **runtime_cfg}


def _build_chat_messages(user_message, runtime_cfg, persona=None, existing_messages=None):
    """构建对话消息（支持历史消息）

    Args:
        user_message: 当前用户消息
        runtime_cfg: 运行配置
        persona: 人设
        existing_messages: 已有的历史消息数组
    """
    system_prompt = build_system_prompt(runtime_cfg, persona)
    search_context = ""
    if _should_search(user_message):
        search_query = _extract_search_query(user_message)
        search_results = _perform_web_search(search_query)
        search_context = _format_search_results(search_results)

    messages = []
    if existing_messages and isinstance(existing_messages, list):
        for msg in existing_messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)

    if messages and messages[0]["role"] == "system":
        existing_system = messages.pop(0)
        if search_context:
            system_prompt = f"{search_context}\n\n{system_prompt}"
        system_prompt = f"{existing_system['content']}\n\n{system_prompt}"
    else:
        if search_context:
            system_prompt = f"{search_context}\n\n{system_prompt}"

    messages.insert(0, {"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_ollama_payload(model, messages, runtime_cfg, stream):
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": build_ollama_options(runtime_cfg),
        "keep_alive": runtime_cfg.get("keep_alive", "10m"),
        "think": bool(runtime_cfg.get("thinking", False)),
    }
    return payload


def _extract_ollama_message(result):
    message = result.get("message") or {}
    return (
        message.get("content") or "",
        message.get("thinking") or "",
        result.get("done_reason") or "",
    )


def _should_retry_without_thinking(payload, result, allow_retry=True):
    if not allow_retry:
        return False

    if payload.get("think") is False:
        return False

    content, thinking, _ = _extract_ollama_message(result)
    return not content and bool(thinking)


def _send_ollama_chat(payload, timeout=120, allow_thinking_retry=True):
    response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()
    result = response.json()

    if not _should_retry_without_thinking(payload, result, allow_retry=allow_thinking_retry):
        return result, payload

    retry_payload = dict(payload)
    retry_payload["think"] = False
    logger.warning("Ollama returned thinking without final content; retrying with think=false")

    retry_response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=retry_payload, timeout=timeout)
    retry_response.raise_for_status()
    return retry_response.json(), retry_payload


def _check_ollama_available():
    """检查 Ollama 服务是否可用"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def _try_local_model_chat(
    model,
    messages,
    stream=False,
    temperature=0.7,
    max_tokens=2048,
    repeat_penalty=1.1,
    top_k=40,
    top_p=0.9
):
    """尝试使用本地模型进行对话（自动检测 GGUF / safetensors）"""
    if not LOCAL_MODEL_AVAILABLE:
        return None

    logger.info(f"尝试本地模型: {model}, temperature={temperature}, repeat_penalty={repeat_penalty}")

    if stream:
        def generate_local():
            try:
                for chunk in generate_chat_response(
                    model_name=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    repeat_penalty=repeat_penalty,
                    top_k=top_k,
                    top_p=top_p
                ):
                    if "error" in chunk:
                        yield f"data: {json.dumps({'error': chunk['error'], 'done': True}, ensure_ascii=False)}\n\n"
                        return

                    content = chunk.get("message", {}).get("content", "")
                    done = chunk.get("done", False)
                    repeat_detected = chunk.get("repeat_detected", False)
                    suggested_temp = chunk.get("suggested_temperature", None)

                    payload = {
                        "event": "answer_chunk",
                        "content": content,
                        "done": done,
                        "model": model,
                        "created": int(time.time()),
                        "repeat_detected": repeat_detected,
                        "suggested_temperature": suggested_temp,
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    if done:
                        break
            except Exception as e:
                logger.error(f"本地模型生成失败: {e}")
                yield f"data: {json.dumps({'error': str(e), 'done': True}, ensure_ascii=False)}\n\n"

        return generate_local()
    else:
        result = None
        for chunk in generate_chat_response(
            model_name=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            repeat_penalty=repeat_penalty,
            top_k=top_k,
            top_p=top_p
        ):
            if "error" in chunk:
                return {"error": chunk["error"]}
            result = chunk

        return result


def register_chat_routes(app):
    @app.route("/api/chat", methods=["POST"])
    @require_api_key
    def chat_with_context():
        try:
            data = request.json or {}
            message = _normalize_message_input(data)
            if not message:
                return jsonify(error_response("message is required", 400)), 400

            stream = bool(data.get("stream", False))
            model = data.get("model") or DEFAULT_CHAT_MODEL
            conversation_id = data.get("conversation_id") or str(uuid.uuid4())
            persona = data.get("persona") if isinstance(data.get("persona"), dict) else None
            incoming_chat_settings = data.get("chat_settings", {})
            runtime_cfg = _build_runtime_config(conversation_id, incoming_chat_settings)
            thinking_requested = isinstance(incoming_chat_settings, dict) and bool(incoming_chat_settings.get("thinking"))
            messages = _build_chat_messages(message, runtime_cfg, persona, data.get("messages"))
            ollama_payload = _build_ollama_payload(model, messages, runtime_cfg, stream)
            
            ollama_available = _check_ollama_available()

            if stream:
                def generate_response():
                    level = runtime_cfg.get("reasoning_summary_level", "off")
                    if runtime_cfg.get("show_reasoning_summary", False) and level != "off":
                        summary = _summarize_reasoning(message, level)
                        yield f"data: {json.dumps({'event': 'reasoning_summary_chunk', 'content': summary, 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                    repetition_detector = create_detector(REPETITION_DETECTION_CONFIG)
                    full_content = ""

                    if ollama_available:
                        try:
                            with requests.post(
                                f"{OLLAMA_BASE_URL}/api/chat",
                                json=ollama_payload,
                                timeout=120,
                                stream=True,
                            ) as response:
                                response.raise_for_status()
                                for line in response.iter_lines():
                                    if not line:
                                        continue
                                    try:
                                        chunk = json.loads(line.decode("utf-8"))
                                    except json.JSONDecodeError:
                                        continue

                                    content = chunk.get("message", {}).get("content", "")
                                    full_content += content
                                    
                                    should_stop, reason = repetition_detector.process_token(content)
                                    
                                    if should_stop:
                                        logger.warning(f"重复检测触发截断: {reason}")
                                        payload = {
                                            "event": "answer_chunk",
                                            "content": content,
                                            "done": True,
                                            "model": model,
                                            "created": int(time.time()),
                                            "truncated": True,
                                            "truncation_reason": reason,
                                            "suggested_params": repetition_detector.get_suggested_params(),
                                        }
                                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                        break
                                    
                                    payload = {
                                        "event": "answer_chunk",
                                        "content": content,
                                        "done": chunk.get("done", False),
                                        "model": model,
                                        "created": int(time.time()),
                                    }
                                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                    if payload["done"]:
                                        break
                        except Exception as e:
                            logger.error(f"Ollama stream chat failed: {e}")
                            local_result = _try_local_model_chat(
                                model, messages, stream=True,
                                temperature=runtime_cfg.get("temperature", 0.7),
                                max_tokens=runtime_cfg.get("max_response_tokens", 2048),
                                repeat_penalty=runtime_cfg.get("repeat_penalty", 1.1),
                                top_k=runtime_cfg.get("top_k", 40),
                                top_p=runtime_cfg.get("top_p", 0.9)
                            )
                            if local_result:
                                for chunk in local_result:
                                    yield chunk
                            else:
                                yield f"data: {json.dumps({'error': str(e), 'done': True}, ensure_ascii=False)}\n\n"
                    else:
                        logger.info("Ollama 不可用，尝试使用本地模型")
                        local_result = _try_local_model_chat(
                            model, messages, stream=True,
                            temperature=runtime_cfg.get("temperature", 0.7),
                            max_tokens=runtime_cfg.get("max_response_tokens", 2048),
                            repeat_penalty=runtime_cfg.get("repeat_penalty", 1.1),
                            top_k=runtime_cfg.get("top_k", 40),
                            top_p=runtime_cfg.get("top_p", 0.9)
                        )
                        if local_result:
                            for chunk in local_result:
                                yield chunk
                        else:
                            yield f"data: {json.dumps({'error': 'Ollama 服务不可用且本地模型不存在', 'done': True}, ensure_ascii=False)}\n\n"

                return Response(
                    stream_with_context(generate_response()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            logger.info(f"[DEBUG] ollama_available={ollama_available}, model={model}")
            if ollama_available:
                try:
                    logger.info(f"[DEBUG] Calling Ollama /api/chat with payload: model={ollama_payload.get('model')}")
                    result, used_payload = _send_ollama_chat(
                        ollama_payload,
                        timeout=120,
                        allow_thinking_retry=not thinking_requested,
                    )
                    response_text, thinking_text, done_reason = _extract_ollama_message(result)
                    logger.info(
                        "[DEBUG] Ollama response content length: %s, thinking length: %s, done_reason=%s",
                        len(response_text),
                        len(thinking_text),
                        done_reason or "unknown",
                    )
                    reasoning_summary = ""
                    if runtime_cfg.get("show_reasoning_summary", False):
                        reasoning_summary = _summarize_reasoning(message, runtime_cfg.get("reasoning_summary_level", "off"))

                    return jsonify(
                        success_response(
                            data={
                                "response": response_text,
                                "reasoning_summary": reasoning_summary,
                                "conversation_id": conversation_id,
                                "model": model,
                                "options": used_payload["options"],
                            }
                        )
                    )
                except Exception as e:
                    logger.error(f"Ollama chat failed: {e}")
            
            logger.info("Ollama 不可用或失败，尝试使用本地模型")
            local_result = _try_local_model_chat(
                model, messages, stream=False,
                temperature=runtime_cfg.get("temperature", 0.7),
                max_tokens=runtime_cfg.get("max_response_tokens", 2048),
                repeat_penalty=runtime_cfg.get("repeat_penalty", 1.1),
                top_k=runtime_cfg.get("top_k", 40),
                top_p=runtime_cfg.get("top_p", 0.9)
            )
            
            if local_result and "error" not in local_result:
                response_text = local_result.get("message", {}).get("content", "")
                reasoning_summary = ""
                if runtime_cfg.get("show_reasoning_summary", False):
                    reasoning_summary = _summarize_reasoning(message, runtime_cfg.get("reasoning_summary_level", "off"))
                
                return jsonify(
                    success_response(
                        data={
                            "response": response_text,
                            "reasoning_summary": reasoning_summary,
                            "conversation_id": conversation_id,
                            "model": model,
                            "options": {},
                        }
                    )
                )
            
            error_msg = local_result.get("error", "Ollama 服务不可用且本地模型不存在") if local_result else "Ollama 服务不可用且本地模型不存在"
            return jsonify(error_response(error_msg, 500)), 500
            
        except Exception as e:
            logger.error(f"chat failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/v1/chat/completions", methods=["POST"])
    @app.route("/v1/completions", methods=["POST"])
    @require_api_key
    def openai_chat_completion():
        try:
            data = request.json or {}
            messages = data.get("messages") or []
            prompt = data.get("prompt", "")
            if not messages and prompt:
                messages = [{"role": "user", "content": prompt}]
            if not messages:
                return jsonify(error_response("messages is required", 400)), 400

            model = data.get("model") or DEFAULT_OPENAI_COMPAT_MODEL
            temperature = float(data.get("temperature", DEFAULT_CHAT_RUNTIME_CONFIG["temperature"]))
            max_tokens = int(data.get("max_tokens", DEFAULT_CHAT_RUNTIME_CONFIG["max_response_tokens"]))
            stream = bool(data.get("stream", False))
            request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

            runtime_cfg = {
                **DEFAULT_CHAT_RUNTIME_CONFIG,
                "temperature": temperature,
                "max_response_tokens": max_tokens,
            }
            payload = _build_ollama_payload(model, messages, runtime_cfg, stream)

            if stream:
                def generate_stream():
                    try:
                        with requests.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json=payload,
                            timeout=120,
                            stream=True,
                        ) as response:
                            response.raise_for_status()
                            for line in response.iter_lines():
                                if not line:
                                    continue
                                try:
                                    chunk = json.loads(line.decode("utf-8"))
                                except json.JSONDecodeError:
                                    continue
                                content = chunk.get("message", {}).get("content", "")
                                done = chunk.get("done", False)
                                openai_chunk = {
                                    "id": request_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": "stop" if done else None,
                                    }],
                                }
                                yield f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"
                                if done:
                                    break
                            yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"openai stream failed: {e}")
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"

                return Response(stream_with_context(generate_stream()), mimetype="text/event-stream")

            result, _ = _send_ollama_chat(payload, timeout=120)
            content, _, _ = _extract_ollama_message(result)
            return jsonify(
                {
                    "id": request_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                    },
                }
            )
        except Exception as e:
            logger.error(f"openai compatible chat failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("Chat API routes registered")
