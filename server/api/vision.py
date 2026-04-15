"""
视觉 API 模块

提供视觉理解、多模态对话相关接口
"""

import logging
import requests
from flask import request, jsonify, Response, stream_with_context

from utils.config import OLLAMA_BASE_URL, VISION_SERVICE_URL
from utils.helpers import success_response, error_response
from api.chat import get_mode_settings

logger = logging.getLogger(__name__)


def register_vision_routes(app):
    """注册视觉相关路由"""
    
    @app.route('/api/vision/load', methods=['POST'])
    def api_vision_load():
        """加载视觉模型"""
        try:
            response = requests.post(f"{VISION_SERVICE_URL}/api/vision/load", timeout=60)
            return jsonify(response.json())
        except requests.exceptions.ConnectionError:
            return jsonify(error_response("视觉服务未启动", 503)), 503
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/vision/analyze', methods=['POST'])
    def api_vision_analyze():
        """分析图片"""
        try:
            data = request.get_json()
            response = requests.post(
                f"{VISION_SERVICE_URL}/api/vision/analyze",
                json=data,
                timeout=120
            )
            return jsonify(response.json())
        except requests.exceptions.ConnectionError:
            return jsonify(error_response("视觉服务未启动", 503)), 503
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/vision/ocr', methods=['POST'])
    def api_vision_ocr():
        """OCR 识别"""
        try:
            data = request.get_json()
            response = requests.post(
                f"{VISION_SERVICE_URL}/api/vision/ocr",
                json=data,
                timeout=120
            )
            return jsonify(response.json())
        except requests.exceptions.ConnectionError:
            return jsonify(error_response("视觉服务未启动", 503)), 503
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/vision/describe', methods=['POST'])
    def api_vision_describe():
        """图片描述"""
        try:
            data = request.get_json()
            response = requests.post(
                f"{VISION_SERVICE_URL}/api/vision/describe",
                json=data,
                timeout=120
            )
            return jsonify(response.json())
        except requests.exceptions.ConnectionError:
            return jsonify(error_response("视觉服务未启动", 503)), 503
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/chat/multimodal', methods=['POST'])
    def multimodal_chat():
        """多模态对话接口"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify(error_response("请求数据为空", 400)), 400
            
            message = data.get('message', '')
            image_data = data.get('image')
            model = data.get('model', 'dasd-4b-thinking')
            stream = data.get('stream', True)
            
            enhanced_message = message
            if image_data:
                try:
                    vision_response = requests.post(
                        f"{VISION_SERVICE_URL}/api/vision/analyze",
                        json={
                            "image": image_data,
                            "prompt": message or "请详细描述这张图片的内容"
                        },
                        timeout=120
                    )
                    
                    if vision_response.status_code == 200:
                        vision_result = vision_response.json()
                        if vision_result.get('success'):
                            image_description = vision_result.get('result', '')
                            enhanced_message = f"[用户上传了一张图片]\n[图片内容分析]: {image_description}\n[用户问题]: {message or '请分析这张图片'}"
                        else:
                            enhanced_message = f"[用户上传了一张图片，但图片分析失败]\n[用户问题]: {message or '请分析这张图片'}"
                    else:
                        enhanced_message = f"[用户上传了一张图片，但视觉服务暂时不可用]\n[用户问题]: {message or '请分析这张图片'}"
                except Exception as e:
                    logger.warning(f"图片分析失败: {e}")
                    enhanced_message = f"[用户上传了一张图片，但分析失败]\n[用户问题]: {message or '请分析这张图片'}"
            
            messages = [{"role": "user", "content": enhanced_message}]
            mode_settings = get_mode_settings()
            
            if stream:
                def generate_response():
                    import json
                    import time
                    ollama_params = {
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "temperature": mode_settings['temperature'],
                        "repeat_penalty": mode_settings['repeat_penalty']
                    }
                    
                    try:
                        response = requests.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json=ollama_params,
                            timeout=120,
                            stream=True
                        )
                        
                        for line in response.iter_lines():
                            if line:
                                chunk = json.loads(line.decode('utf-8'))
                                content = chunk.get('message', {}).get('content', '')
                                payload = {
                                    "content": content,
                                    "done": chunk.get('done', False),
                                    "model": model,
                                    "created": int(time.time())
                                }
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        import json
                        yield f"data: {json.dumps({'error': str(e), 'done': True}, ensure_ascii=False)}\n\n"
                
                return Response(
                    stream_with_context(generate_response()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
                )
            else:
                ollama_params = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "temperature": mode_settings['temperature'],
                    "repeat_penalty": mode_settings['repeat_penalty']
                }
                
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=ollama_params,
                    timeout=120
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return jsonify(success_response(data={
                        "response": result.get('message', {}).get('content', ''),
                        "has_image": bool(image_data)
                    }))
                else:
                    return jsonify(error_response("生成回复失败", 500)), 500
        except Exception as e:
            logger.error(f"多模态对话失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ 视觉 API 路由已注册")
