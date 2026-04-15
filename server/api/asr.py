"""
语音识别 API 模块

提供 ASR 相关接口
"""

import os
import tempfile
import logging
from flask import request, jsonify

from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

asr_service = None


def init_asr_services():
    """初始化语音识别服务（仅使用 Qwen3-ASR）"""
    global asr_service
    try:
        from asr.factory import create_asr_service, ASREngineType
        asr_service = create_asr_service(ASREngineType.QWEN3_ASR)
        logger.info("语音识别服务初始化成功（Qwen3-ASR）")
    except Exception as e:
        logger.warning(f"语音识别服务初始化失败: {e}")


def register_asr_routes(app):
    """注册语音识别相关路由"""

    def _resolve_audio_upload():
        """兼容不同前端字段名"""
        return request.files.get('file') or request.files.get('audio')

    def _save_uploaded_audio(uploaded_file):
        suffix = os.path.splitext(uploaded_file.filename or "")[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_file = tmp.name
        uploaded_file.save(temp_file)
        return temp_file

    def _transcribe_with_available_service(temp_file, language, preferred_engine='auto'):
        """使用 Qwen3-ASR 进行语音识别"""
        if asr_service:
            result = asr_service.transcribe_with_preprocessing(temp_file, language)
            if result:
                return result, 'qwen3_asr'
        return None, None
    
    @app.route('/api/asr/status', methods=['GET'])
    @app.route('/api/voice/status', methods=['GET'])
    def get_asr_status():
        """获取语音识别服务状态"""
        try:
            primary_status = asr_service.check_status() if asr_service else None

            if primary_status:
                return jsonify(success_response(data={
                    "primary": primary_status,
                    "available": True
                }))
            return jsonify(error_response("ASR 服务未初始化", 503)), 503
        except Exception as e:
            logger.error(f"获取 ASR 状态失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/asr/transcribe', methods=['POST'])
    @app.route('/api/voice/transcribe', methods=['POST'])
    def transcribe_audio():
        """转写音频"""
        try:
            uploaded_file = _resolve_audio_upload()
            if not uploaded_file:
                return jsonify(error_response("没有上传文件", 400)), 400

            if not asr_service:
                return jsonify(error_response("ASR 服务未初始化", 503)), 503

            language = request.form.get('language', 'zh')
            temp_file = _save_uploaded_audio(uploaded_file)

            try:
                result, engine = _transcribe_with_available_service(temp_file, language)
            finally:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
            
            if result:
                payload = result.to_dict()
                payload["engine"] = engine
                return jsonify(success_response(data=payload))
            else:
                return jsonify(error_response("转写失败", 500)), 500
        except Exception as e:
            logger.error(f"转写失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/whisper/model', methods=['GET'])
    def get_whisper_model():
        """获取 ASR 模型状态"""
        return jsonify(success_response(data={
            "current_model": {
                "name": "Qwen/Qwen3-ASR-0.6B",
                "is_downloaded": True
            },
            "message": "使用 Qwen3-ASR"
        }))

    logger.info("✓ 语音识别 API 路由已注册")
