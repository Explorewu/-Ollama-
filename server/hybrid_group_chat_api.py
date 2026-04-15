"""
混合群聊API服务

整合以下服务提供统一API接口：
- 混合智能群聊控制器 (hybrid_group_chat_controller)
- Silero TTS语音合成 (silero_tts_service)
- 情感分析与可视化
- 观点聚类分析

提供RESTful API接口，支持群聊控制、语音合成等功能
"""

import os
import sys
import json
import time
import logging
import threading
import base64
import io
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid_group_chat_controller import (
    get_group_chat_controller, 
    HybridGroupChatController,
    DiscussionState,
    CharacterConfig,
    WorldSetting
)
from silero_tts_service import get_tts_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:8080", "http://127.0.0.1:8080"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

controller = get_group_chat_controller()
tts_service = get_tts_service()

controller.register_callback("message_generated", lambda data: logger.info(f"新消息: {data.get('character', 'Unknown')}"))
controller.register_callback("auto_chat_started", lambda data: logger.info(f"自动讨论开始: {data}"))
controller.register_callback("auto_chat_stopped", lambda data: logger.info(f"自动讨论停止: {data}"))

DEFAULT_CHARACTERS = {
    "qwen2.5:3b": {
        "name": "Qwen助手",
        "avatar": "🌟",
        "personality": "高效、实用、反应迅速",
        "style": "简洁有力，侧重实际应用",
        "expertise": ["通用知识", "实用建议"]
    },
    "gemma2:2b": {
        "name": "Gemma",
        "avatar": "🔬",
        "personality": "理性、严谨、善于分析",
        "style": "简洁、准确、有条理",
        "expertise": ["科学研究", "数据分析"]
    },
    "llama3.2:3b": {
        "name": "Llama学者",
        "avatar": "🦁",
        "personality": "开放、知识渊博、友好",
        "style": "详细且易于理解",
        "expertise": ["技术", "科学", "教育"]
    },
    "llama3:8b": {
        "name": "Llama专家",
        "avatar": "🦁",
        "personality": "深度思考、知识渊博",
        "style": "详尽深入",
        "expertise": ["复杂问题", "技术深度"]
    },
    "mistral:7b": {
        "name": "Mistral",
        "avatar": "💨",
        "personality": "敏捷、创意十足、灵活",
        "style": "灵活多变",
        "expertise": ["创意", "快速响应"]
    },
    "deepseek-r1:1.5b": {
        "name": "DeepSeek",
        "avatar": "🧠",
        "personality": "深度思考、逻辑推理强大",
        "style": "分析深入、步骤清晰",
        "expertise": ["推理", "数学", "编程"]
    }
}


def init_default_characters():
    """初始化默认角色配置"""
    for model_name, char_data in DEFAULT_CHARACTERS.items():
        character = CharacterConfig(
            model_name=model_name,
            name=char_data["name"],
            avatar=char_data["avatar"],
            personality=char_data["personality"],
            style=char_data["style"],
            expertise=char_data.get("expertise", []),
            speaking_style="balanced",
            emotional_range=["neutral", "thoughtful"],
            voice_profile=char_data["name"]
        )
        controller.add_character(character)
    logger.info(f"✓ 已初始化 {len(DEFAULT_CHARACTERS)} 个默认角色")


init_default_characters()


@app.route('/api/group_chat/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "controller_state": controller.state.value,
        "auto_chat": controller.auto_chat_enabled,
        "message_count": len(controller.messages),
        "character_count": len(controller.characters)
    })


@app.route('/api/health', methods=['GET', 'OPTIONS'])
def api_health():
    if request.method == 'OPTIONS':
        return Response(status=200)
    return jsonify({"status": "ok"})


@app.route('/api/group_chat/status', methods=['GET'])
def get_status():
    """获取群聊状态"""
    return jsonify({
        "success": True,
        "data": controller.get_status()
    })


@app.route('/api/group_chat/characters', methods=['GET'])
def list_characters():
    """列出所有角色配置"""
    return jsonify({
        "success": True,
        "data": [
            {
                "model_name": k,
                "name": v.name,
                "avatar": v.avatar,
                "personality": v.personality,
                "style": v.style,
                "expertise": v.expertise
            }
            for k, v in controller.characters.items()
        ]
    })


@app.route('/api/group_chat/characters', methods=['POST'])
def add_character():
    """添加角色配置"""
    try:
        data = request.json
        
        character = CharacterConfig(
            model_name=data["model_name"],
            name=data["name"],
            avatar=data.get("avatar", "🤖"),
            personality=data.get("personality", ""),
            style=data.get("style", ""),
            expertise=data.get("expertise", []),
            speaking_style=data.get("speaking_style", "balanced"),
            emotional_range=data.get("emotional_range", ["neutral"]),
            voice_profile=data.get("voice_profile", data["name"])
        )
        
        controller.add_character(character)
        
        return jsonify({
            "success": True,
            "message": f"角色 {character.name} 已添加"
        })
    except Exception as e:
        logger.error(f"添加角色失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/group_chat/world_setting', methods=['GET'])
def get_world_setting():
    """获取世界设定"""
    setting = controller.world_setting
    return jsonify({
        "success": True,
        "data": {
            "title": setting.title,
            "description": setting.description,
            "background": setting.background,
            "rules": setting.rules,
            "culture": setting.culture,
            "technology_level": setting.technology_level,
            "main_topics": setting.main_topics
        }
    })


@app.route('/api/group_chat/world_setting', methods=['POST'])
def set_world_setting():
    """设置世界设定"""
    try:
        data = request.json
        
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
        
        controller.set_world_setting(setting)
        
        return jsonify({
            "success": True,
            "message": "世界设定已更新"
        })
    except Exception as e:
        logger.error(f"设置世界设定失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/group_chat/auto_chat/start', methods=['POST'])
def start_auto_chat():
    """开始自动聊天"""
    try:
        data = request.json or {}
        initial_topic = data.get("topic")
        
        success = controller.start_auto_chat(initial_topic)
        
        if success:
            return jsonify({
                "success": True,
                "message": "自动讨论已开始",
                "data": {
                    "topic": controller.discussion_turns[-1].topic if controller.discussion_turns else None
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "无法开始自动讨论"
            }), 400
    except Exception as e:
        logger.error(f"开始自动聊天失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/group_chat/auto_chat/pause', methods=['POST'])
def pause_auto_chat():
    """暂停自动聊天"""
    success = controller.pause_auto_chat()
    
    return jsonify({
        "success": success,
        "message": "已暂停" if success else "无法暂停"
    })


@app.route('/api/group_chat/auto_chat/resume', methods=['POST'])
def resume_auto_chat():
    """继续自动聊天"""
    success = controller.resume_auto_chat()
    
    return jsonify({
        "success": success,
        "message": "已继续" if success else "无法继续"
    })


@app.route('/api/group_chat/auto_chat/stop', methods=['POST'])
def stop_auto_chat():
    """停止自动聊天"""
    try:
        data = request.json or {}
        reason = data.get("reason", "手动停止")
        
        success = controller.stop_auto_chat(reason)
        
        return jsonify({
            "success": True,
            "message": "自动讨论已停止"
        })
    except Exception as e:
        logger.error(f"停止自动聊天失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/group_chat/messages', methods=['GET'])
def get_messages():
    """获取消息列表"""
    limit = request.args.get('limit', 50, type=int)
    messages = controller.get_messages(limit)
    
    return jsonify({
        "success": True,
        "data": messages,
        "total": len(controller.messages)
    })


@app.route('/api/group_chat/messages', methods=['POST'])
def add_message():
    """添加用户消息并触发讨论"""
    try:
        data = request.json
        content = data.get("content", "")
        
        if not content:
            return jsonify({"success": False, "error": "消息内容不能为空"}), 400
        
        from hybrid_group_chat_controller import Message
        
        user_msg = Message(
            id=f"user_{int(time.time() * 1000)}",
            role="user",
            content=content,
            timestamp=int(time.time() * 1000)
        )
        
        with controller._lock:
            controller.messages.append(user_msg)
        
        if controller.auto_chat_enabled:
            return jsonify({
                "success": True,
                "message": "消息已添加，讨论将继续",
                "message_id": user_msg.id
            })
        
        return jsonify({
            "success": True,
            "message": "消息已添加",
            "message_id": user_msg.id
        })
    except Exception as e:
        logger.error(f"添加消息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/group_chat/emotions', methods=['GET'])
def get_emotions():
    """获取情感历史"""
    history = controller.get_emotion_history()
    
    return jsonify({
        "success": True,
        "data": history
    })


@app.route('/api/group_chat/viewpoints', methods=['GET'])
def get_viewpoints():
    """获取观点聚类"""
    result = controller.get_viewpoint_clusters()
    
    return jsonify({
        "success": True,
        "data": result
    })


@app.route('/api/group_chat/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        data = request.json
        
        if "max_turns" in data:
            controller.set_max_turns(data["max_turns"])
        
        if "auto_stop" in data:
            controller.set_auto_stop(data["auto_stop"])
        
        return jsonify({
            "success": True,
            "message": "配置已更新"
        })
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/group_chat/clear', methods=['POST'])
def clear_history():
    """清空历史"""
    controller.clear_history()
    
    return jsonify({
        "success": True,
        "message": "历史记录已清空"
    })


@app.route('/api/group_chat/tts/synthesize', methods=['POST'])
def synthesize_speech():
    """语音合成"""
    try:
        data = request.json
        text = data.get("text", "")
        character_name = data.get("character", "default")
        
        if not text:
            return jsonify({"success": False, "error": "文本内容不能为空"}), 400
        
        audio_data = tts_service.synthesize(text, character_name)
        
        if audio_data is None:
            return jsonify({"success": False, "error": "语音合成失败"}), 500
        
        import numpy as np
        
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        audio_io = io.BytesIO()
        import wave
        with wave.open(audio_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(audio_int16.tobytes())
        
        audio_io.seek(0)
        audio_base64 = base64.b64encode(audio_io.read()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "data": {
                "audio": audio_base64,
                "format": "wav",
                "sample_rate": 48000
            }
        })
    except Exception as e:
        logger.error(f"语音合成失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/group_chat/tts/voices', methods=['GET'])
def list_voices():
    """获取可用音色列表"""
    return jsonify({
        "success": True,
        "data": {
            "speakers": tts_service.get_available_speakers(),
            "profiles": tts_service.get_character_profiles()
        }
    })


@app.route('/api/group_chat/stream', methods=['POST'])
def stream_chat():
    """\n    流式生成消息（用于实时显示）
    支持按句子输出，实现更自然的对话体验
    """
    try:
        data = request.json
        model_name = data.get("model", "")
        content = data.get("content", "")
        sentence_stream = data.get("sentence_stream", True)  # 默认按句子输出
        
        if not model_name or not content:
            return jsonify({"success": False, "error": "参数不完整"}), 400
        
        def generate():
            try:
                import requests
                import json
                
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": content}],
                        "stream": True
                    },
                    stream=True,
                    timeout=120
                )
                
                if sentence_stream:
                    # 按句子流式输出
                    sentence_buffer = ""
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                data_chunk = json.loads(line.decode('utf-8'))
                                chunk_content = data_chunk.get("message", {}).get("content", "")
                                if chunk_content:
                                    sentence_buffer += chunk_content
                                    
                                    # 检测句子边界
                                    while True:
                                        sentence_end = -1
                                        for i, char in enumerate(sentence_buffer):
                                            if char in '。！？.!?':
                                                sentence_end = i + 1
                                                break
                                        
                                        if sentence_end > 0:
                                            sentence = sentence_buffer[:sentence_end]
                                            sentence_buffer = sentence_buffer[sentence_end:]
                                            yield f"data: {json.dumps({'chunk': sentence, 'is_sentence': True})}\n\n"
                                        else:
                                            # 没有完整句子，检查是否积累了足够多的内容
                                            if len(sentence_buffer) >= 30:
                                                yield f"data: {json.dumps({'chunk': sentence_buffer, 'is_sentence': False})}\n\n"
                                                sentence_buffer = ""
                                            break
                            except json.JSONDecodeError:
                                continue
                    
                    # 处理剩余内容
                    if sentence_buffer.strip():
                        yield f"data: {json.dumps({'chunk': sentence_buffer.strip(), 'is_sentence': True})}\n\n"
                else:
                    # 原有逻辑：逐token输出
                    for line in response.iter_lines():
                        if line:
                            try:
                                data_chunk = json.loads(line.decode('utf-8'))
                                if data_chunk.get("message", {}).get("content"):
                                    yield f"data: {json.dumps({'chunk': data_chunk['message']['content'], 'is_sentence': False})}\n\n"
                            except:
                                pass
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    except Exception as e:
        logger.error(f"流式聊天失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/group_chat/load_state', methods=['POST'])
def load_state():
    """加载保存的状态"""
    success = controller.load_state()
    
    return jsonify({
        "success": success,
        "message": "状态已加载" if success else "无法加载状态"
    })


@app.route('/api/group_chat/save_state', methods=['POST'])
def save_state():
    """手动保存状态"""
    controller._save_state()
    
    return jsonify({
        "success": True,
        "message": "状态已保存"
    })


if __name__ == '__main__':
    print("=== 混合群聊API服务 ===")
    print(f"健康检查: http://localhost:5001/api/group_chat/health")
    print(f"群聊状态: http://localhost:5001/api/group_chat/status")
    print(f"开始自动讨论: POST /api/group_chat/auto_chat/start")
    print(f"语音合成: POST /api/group_chat/tts/synthesize")
    
    app.run(host='::', port=5001, debug=False, threaded=True)
