"""
Group chat API routes.
"""

import logging
import base64
from flask import request, jsonify

from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

group_controller = None
tts_service = None


def init_group_chat_services():
    """Initialize group chat services without hard failing on TTS."""
    global group_controller, tts_service

    if group_controller is None:
        try:
            from hybrid_group_chat_controller import get_group_chat_controller
            group_controller = get_group_chat_controller()
            try:
                group_controller.load_state()
            except Exception as e:
                logger.warning(f"group_chat load_state failed: {e}")
        except Exception as e:
            logger.warning(f"group_chat controller init failed: {e}")

    if tts_service is None:
        try:
            from silero_tts_service import get_tts_service
            tts_service = get_tts_service()
        except Exception as e:
            logger.warning(f"group_chat tts init failed: {e}")

    if group_controller is not None:
        logger.info("group_chat services initialized")


def ensure_group_controller():
    global group_controller
    if group_controller is None:
        try:
            from hybrid_group_chat_controller import get_group_chat_controller
            group_controller = get_group_chat_controller()
            try:
                group_controller.load_state()
            except Exception as e:
                logger.warning(f"group_chat load_state failed: {e}")
        except Exception as e:
            logger.warning(f"group_chat controller init failed: {e}")
    if group_controller is not None:
        try:
            group_controller.ensure_default_characters()
        except Exception as e:
            logger.warning(f"group_chat default characters init failed: {e}")
    return group_controller


def ensure_tts_service():
    global tts_service
    if tts_service is None:
        try:
            from silero_tts_service import get_tts_service
            tts_service = get_tts_service()
        except Exception as e:
            logger.warning(f"group_chat tts init failed: {e}")
    return tts_service


def register_group_chat_routes(app):
    """Register group chat routes."""

    @app.route('/api/group_chat/stream', methods=['GET'])
    def group_chat_stream():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        from flask import Response, stream_with_context
        import json
        import time

        def generate():
            last_idx = len(group_controller.messages)
            last_state = None
            heartbeat_ts = time.time()

            yield f": connected {int(time.time())}\n\n"

            while True:
                try:
                    msgs = group_controller.get_messages(10_000)
                    current_len = len(msgs)

                    if current_len > last_idx:
                        for m in msgs[last_idx:]:
                            payload = {
                                "content": m.get("content", ""),
                                "done": False,
                                "model": m.get("model_name", ""),
                                "character": m.get("character_name", ""),
                                "created": int(time.time())
                            }
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        last_idx = current_len

                    cur_state = group_controller.state.value
                    if cur_state != last_state:
                        last_state = cur_state
                        state_payload = {
                            "type": "state_change",
                            "state": cur_state,
                            "created": int(time.time())
                        }
                        yield f"data: {json.dumps(state_payload, ensure_ascii=False)}\n\n"

                    now = time.time()
                    if now - heartbeat_ts >= 15:
                        yield f": ping {int(now)}\n\n"
                        heartbeat_ts = now

                    time.sleep(1.0)
                except GeneratorExit:
                    break
                except Exception as e:
                    err = {"error": str(e), "done": True}
                    yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
                    break

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    @app.route('/api/group_chat/health', methods=['GET'])
    def group_chat_health():
        if ensure_group_controller():
            return jsonify(success_response(
                data={
                    "status": "ok",
                    "controller_state": group_controller.state.value,
                    "message_count": len(group_controller.messages)
                },
                message="group_chat service healthy"
            ))
        return jsonify(error_response("group_chat service not initialized", 503)), 503

    @app.route('/api/group_chat/status', methods=['GET'])
    def group_chat_status():
        if ensure_group_controller():
            return jsonify(success_response(data=group_controller.get_status()))
        return jsonify(error_response("group_chat service not initialized", 503)), 503

    @app.route('/api/group_chat/characters', methods=['GET', 'POST'])
    def list_group_characters():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        if request.method == 'GET':
            return jsonify(success_response(data=[
                {
                    "model_name": k,
                    "name": v.name,
                    "avatar": v.avatar,
                    "personality": v.personality
                }
                for k, v in group_controller.characters.items()
            ]))

        data = request.json or {}
        try:
            from hybrid_group_chat_controller import CharacterConfig
            character = CharacterConfig(
                model_name=data["model_name"],
                name=data["name"],
                avatar=data.get("avatar", "assistant"),
                personality=data.get("personality", ""),
                style=data.get("style", ""),
                expertise=data.get("expertise", []),
                speaking_style=data.get("speaking_style", "balanced")
            )
            group_controller.add_character(character)
            return jsonify(success_response(message=f"character {character.name} added"))
        except Exception as e:
            return jsonify(error_response(str(e), 400)), 400

    @app.route('/api/group_chat/auto_chat/start', methods=['POST'])
    def start_group_auto_chat():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        data = request.json or {}
        success = group_controller.start_auto_chat(data.get("topic"))
        if success:
            return jsonify(success_response(
                message="auto chat started",
                data={
                    "topic": data.get("topic"),
                    "participants": list(group_controller.characters.keys())
                }
            ))
        participants = list(group_controller.characters.keys())
        if not participants:
            return jsonify(error_response("group chat has no available participants", 400)), 400
        return jsonify(error_response("failed to start auto chat", 400, data={"participants": participants})), 400

    @app.route('/api/group_chat/auto_chat/pause', methods=['POST'])
    def pause_group_auto_chat():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        success = group_controller.pause_auto_chat()
        if success:
            return jsonify(success_response(message="auto chat paused", data={"paused": True}))
        return jsonify(error_response("failed to pause auto chat", 400, data={"paused": False})), 400

    @app.route('/api/group_chat/auto_chat/resume', methods=['POST'])
    def resume_group_auto_chat():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        success = group_controller.resume_auto_chat()
        if success:
            return jsonify(success_response(message="auto chat resumed", data={"running": True}))
        return jsonify(error_response("failed to resume auto chat", 400, data={"running": False})), 400

    @app.route('/api/group_chat/auto_chat/stop', methods=['POST'])
    def stop_group_auto_chat():
        if ensure_group_controller():
            reason = (request.json or {}).get("reason", "manual stop") if request.is_json else "manual stop"
            group_controller.stop_auto_chat(reason)
        return jsonify(success_response(message="auto chat stopped"))

    @app.route('/api/group_chat/messages', methods=['GET'])
    def get_group_messages():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        limit = request.args.get('limit', 50, type=int)
        return jsonify(success_response(data=group_controller.get_messages(limit)))

    @app.route('/api/group_chat/emotions', methods=['GET'])
    def group_chat_emotions():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        history = group_controller.get_emotion_history()
        return jsonify(success_response(data=history))

    @app.route('/api/group_chat/viewpoints', methods=['GET'])
    def group_chat_viewpoints():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        clusters = group_controller.get_viewpoint_clusters()
        return jsonify(success_response(data=clusters))

    @app.route('/api/group_chat/config', methods=['POST'])
    def update_group_config():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        try:
            data = request.json or {}
            if "max_turns" in data:
                group_controller.set_max_turns(data["max_turns"])
            if "auto_stop" in data:
                group_controller.set_auto_stop(data["auto_stop"])
            group_controller.update_generation_config(data)
            return jsonify(success_response(message="config updated", data=group_controller.get_status().get("config")))
        except Exception as e:
            logger.error(f"group_chat config update failed: {e}")
            return jsonify(error_response(str(e), 400)), 400

    @app.route('/api/group_chat/world_setting', methods=['GET'])
    def get_world_setting():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        setting = group_controller.world_setting
        return jsonify(success_response(data={
            "title": setting.title,
            "description": setting.description,
            "background": setting.background,
            "rules": setting.rules,
            "culture": setting.culture,
            "technology_level": setting.technology_level,
            "main_topics": setting.main_topics
        }))

    @app.route('/api/group_chat/world_setting', methods=['POST'])
    def set_world_setting():
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503
        try:
            data = request.json or {}
            from hybrid_group_chat_controller import WorldSetting
            setting = WorldSetting(
                title=data.get("title", ""),
                description=data.get("description", ""),
                background=data.get("background", ""),
                rules=data.get("rules", []),
                culture=data.get("culture", ""),
                technology_level=data.get("technology_level", ""),
                main_topics=data.get("main_topics", []),
                discussion_templates=data.get("discussion_templates", [])
            )
            group_controller.set_world_setting(setting)
            return jsonify(success_response(message="world setting updated"))
        except Exception as e:
            logger.error(f"group_chat world_setting update failed: {e}")
            return jsonify(error_response(str(e), 400)), 400

    @app.route('/api/group_chat/clear', methods=['POST'])
    def clear_group_history():
        if ensure_group_controller():
            group_controller.clear_history()
        return jsonify(success_response(message="history cleared"))

    @app.route('/api/group_chat/tts/synthesize', methods=['POST'])
    def group_tts_synthesize():
        if not ensure_tts_service():
            return jsonify(error_response("tts service not initialized", 503)), 503

        data = request.json or {}
        text = data.get("text", "")
        character = data.get("character", "default")

        if not text:
            return jsonify(error_response("text must not be empty", 400)), 400

        try:
            result = tts_service.synthesize_to_result(text, character)
            if result is None:
                return jsonify(error_response("tts synthesis failed", 500)), 500

            import wave
            import io

            audio_io = io.BytesIO()
            with wave.open(audio_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(result.sample_rate)
                wf.writeframes(result.audio_bytes)

            audio_io.seek(0)
            audio_b64 = base64.b64encode(audio_io.read()).decode('utf-8')

            return jsonify(success_response(data={
                "audio": audio_b64,
                "format": "wav",
                "sample_rate": result.sample_rate
            }))
        except Exception as e:
            logger.error(f"tts synthesis failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/group_chat/tts/voices', methods=['GET'])
    def group_tts_voices():
        """获取可用音色列表"""
        if not ensure_tts_service():
            return jsonify(error_response("tts service not initialized", 503)), 503
        return jsonify({
            "success": True,
            "data": {
                "speakers": tts_service.get_available_speakers(),
                "profiles": tts_service.get_character_profiles()
            }
        })

    @app.route('/api/group_chat/message', methods=['POST'])
    def send_group_message():
        """用户发送消息到群聊"""
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        data = request.json or {}
        content = data.get("content", "").strip()
        target_model = data.get("target_model")

        if not content:
            return jsonify(error_response("content is required", 400)), 400

        try:
            msg = group_controller.send_user_message(content, target_model)
            return jsonify(success_response(data={
                "id": msg.id,
                "content": msg.content,
                "timestamp": msg.timestamp
            }, message="message sent"))
        except Exception as e:
            logger.error(f"send message failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/group_chat/ask', methods=['POST'])
    def ask_model():
        """指定模型回答问题"""
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        data = request.json or {}
        model_name = data.get("model")
        question = data.get("question")

        if not model_name:
            return jsonify(error_response("model is required", 400)), 400

        try:
            group_controller.ask_model(model_name, question)
            return jsonify(success_response(message=f"request sent to {model_name}"))
        except Exception as e:
            logger.error(f"ask model failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/group_chat/summarize', methods=['POST'])
    def request_summary():
        """手动请求总结"""
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        data = request.json or {}
        summary_type = data.get("type", "full")

        try:
            summary = group_controller.request_summary(summary_type)
            return jsonify(success_response(data={"summary": summary}))
        except Exception as e:
            logger.error(f"request summary failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/group_chat/models', methods=['GET'])
    def get_available_models():
        """获取可用模型列表"""
        if not ensure_group_controller():
            return jsonify(error_response("group_chat service not initialized", 503)), 503

        try:
            models = group_controller.get_available_models()
            return jsonify(success_response(data=models))
        except Exception as e:
            logger.error(f"get models failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("Group chat API routes registered")
