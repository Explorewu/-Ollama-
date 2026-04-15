"""
ASR (Automatic Speech Recognition) 模块
统一的语音识别服务接口
"""
from .base import ASRService, TranscriptionResult, ASREngineType, AudioProcessor
from .factory import create_asr_service, get_available_engines, create_best_available_service, register_engine

from . import whisper_ollama

__all__ = [
    "ASRService",
    "TranscriptionResult",
    "ASREngineType",
    "AudioProcessor",
    "create_asr_service",
    "get_available_engines",
    "create_best_available_service",
    "register_engine",
]
