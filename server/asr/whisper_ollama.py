"""
基于 Ollama Whisper 的 ASR 引擎实现
"""
import os
import time
import json
import logging
from typing import Optional, Callable, List
from enum import Enum

from .base import ASRService, TranscriptionResult, ASREngineType, EngineInfo, AudioProcessor
from .factory import register_engine

logger = logging.getLogger(__name__)


class WhisperModelSize(Enum):
    """Whisper 模型大小"""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class WhisperOllamaService(ASRService):
    """
    基于 Ollama Whisper 的 ASR 服务
    """
    
    DEFAULT_MODEL = WhisperModelSize.BASE
    SUPPORTED_LANGUAGES = ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'ru']
    
    def __init__(self, base_url: str = None, model_size: WhisperModelSize = None):
        super().__init__()
        self.base_url = base_url or "http://localhost:11434"
        self.model_size = model_size or WhisperModelSize.BASE
        self.model_name = f"whisper:{self.model_size.value}"
        self._is_model_loaded = False
    
    def initialize(self) -> bool:
        """初始化服务"""
        try:
            is_available = self._check_ollama_available()
            if is_available:
                self._is_initialized = True
                logger.info(f"Whisper Ollama 服务初始化成功 (模型: {self.model_name})")
            return is_available
        except Exception as e:
            logger.error(f"初始化 Whisper Ollama 服务失败: {e}")
            return False
    
    def _check_ollama_available(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    @staticmethod
    def get_engine_info() -> EngineInfo:
        """获取引擎信息"""
        return EngineInfo(
            name="Whisper (Ollama)",
            engine_type=ASREngineType.WHISPER_OLLAMA,
            is_available=True,
            description="基于 Ollama 的 OpenAI Whisper 语音识别服务，支持多种模型大小",
            version="1.0"
        )
    
    def get_engine_info(self) -> EngineInfo:
        """获取引擎信息（实例方法）"""
        return self.__class__.get_engine_info()
    
    def _check_model_exists(self) -> bool:
        """检查模型是否已下载"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                for model in models:
                    if self.model_name in model or model == self.model_name:
                        self._is_model_loaded = True
                        return True
            return False
        except Exception as e:
            logger.error(f"检查模型状态失败: {e}")
            return False
    
    def download_model(self, progress_callback: Callable[[float], None] = None) -> bool:
        """下载模型"""
        try:
            import requests
            logger.info(f"开始下载模型: {self.model_name}")
            
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model_name, "stream": True},
                timeout=300,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode('utf-8'))
                        if 'progress' in data and progress_callback:
                            progress_callback(data['progress'])
                        if data.get('status') == 'success':
                            self._is_model_loaded = True
                            return True
                return True
            else:
                logger.error(f"下载失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            return False
    
    def transcribe(
        self,
        audio_path: str,
        language: str = 'zh',
        progress_callback: Callable[[float], None] = None
    ) -> Optional[TranscriptionResult]:
        """转写音频"""
        with self._transcribe_lock:
            try:
                import requests
                import time as time_module
                
                valid, error_msg = AudioProcessor.validate_audio(audio_path)
                if not valid:
                    logger.error(f"音频验证失败: {error_msg}")
                    return None
                
                start_time = time_module.time()
                logger.info(f"开始转写: {audio_path}")
                
                with open(audio_path, 'rb') as audio_file:
                    files = {'file': ('audio.wav', audio_file, 'audio/wav')}
                    data = {'language': language, 'model': self.model_name}
                    
                    response = requests.post(
                        f"{self.base_url}/api/transcribe",
                        files=files,
                        data=data,
                        timeout=120
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    duration = time_module.time() - start_time
                    
                    text = result.get('text', '')
                    confidence = result.get('confidence', 0.8)
                    
                    transcribed = TranscriptionResult(
                        text=text.strip(),
                        language=language,
                        confidence=confidence,
                        duration=duration,
                        model=self.model_name,
                        engine=ASREngineType.WHISPER_OLLAMA
                    )
                    
                    logger.info(f"转写完成: {duration:.1f}秒, {len(text)}字符")
                    return transcribed
                else:
                    logger.error(f"转写失败: {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"转写过程出错: {e}")
                return None


register_engine(ASREngineType.WHISPER_OLLAMA, WhisperOllamaService)
