"""
本地 Whisper 语音识别服务模块

基于 OpenAI Whisper 的 PyTorch 模型
使用本地下载的 base.pt 模型文件
"""

import os
import sys
import time
import logging
import tempfile
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from model_paths import WHISPER_CACHE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WhisperResult:
    """Whisper 识别结果"""
    text: str
    language: str
    confidence: float
    duration: float
    model: str = "whisper-base"
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "duration": self.duration,
            "model": self.model,
            "timestamp": self.timestamp
        }


class LocalWhisperService:
    """
    本地 Whisper 语音识别服务
    
    使用本地下载的 Whisper base.pt 模型
    模型文件位置: <models>/whisper/base.pt
    """
    
    DEFAULT_MODEL_PATH = os.path.join(WHISPER_CACHE_DIR, "base.pt")
    
    def __init__(self, model_path: str = None):
        """
        初始化本地 Whisper 服务
        
        Args:
            model_path: 模型文件路径，默认使用 <models>/whisper/base.pt
        """
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self.model = None
        self.device = "cpu"
        self._is_loaded = False
        self._load_lock = threading.Lock()
    
    def check_status(self) -> Dict[str, Any]:
        """
        检查服务状态
        
        Returns:
            状态信息字典
        """
        return {
            "is_loaded": self._is_loaded,
            "model_path": self.model_path,
            "device": self.device,
            "model_size": "base",
            "memory_usage": "~1GB",
            "speed": "快"
        }
    
    def load_model(self) -> bool:
        """
        加载 Whisper 模型
        
        Returns:
            是否加载成功
        """
        with self._load_lock:
            if self._is_loaded:
                return True
                
            try:
                if not os.path.exists(self.model_path):
                    logger.error(f"模型文件不存在: {self.model_path}")
                    return False
                
                logger.info(f"正在加载 Whisper 模型: {self.model_path}")
                
                import torch
                import whisper
                
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"使用设备: {self.device}")
                
                self.model = whisper.load_model(
                    "base",
                    device=self.device,
                    download_root=os.path.dirname(self.model_path)
                )
                
                self._is_loaded = True
                logger.info("✅ Whisper base 模型加载成功")
                return True
                
            except Exception as e:
                logger.error(f"加载 Whisper 模型失败: {e}")
                return False
    
    def transcribe(self, audio_path: str, 
                   language: str = "zh",
                   verbose: bool = False) -> Optional[WhisperResult]:
        """
        转写音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言，默认中文
            verbose: 是否输出详细日志
            
        Returns:
            WhisperResult 对象，失败返回 None
        """
        try:
            if not self._is_loaded:
                if not self.load_model():
                    logger.error("模型加载失败，无法进行转写")
                    return None
            
            if not os.path.exists(audio_path):
                logger.error(f"音频文件不存在: {audio_path}")
                return None
            
            logger.info(f"开始转写音频: {audio_path}")
            
            import whisper
            import torch
            
            start_time = time.time()
            
            result = self.model.transcribe(
                audio_path,
                language=language,
                verbose=verbose,
                device=self.device
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            text = result.get("text", "").strip()
            detected_language = result.get("language", language)
            
            confidence = 0.85
            if "segments" in result and result["segments"]:
                try:
                    avg_confidence = sum(
                        seg.get("avg_logprob", 0) 
                        for seg in result["segments"]
                    ) / len(result["segments"])
                    confidence = max(0, min(1, (avg_confidence + 1) / 2))
                except:
                    pass
            
            whisper_result = WhisperResult(
                text=text,
                language=detected_language,
                confidence=confidence,
                duration=duration,
                model="whisper-base"
            )
            
            logger.info(f"✅ 转写完成: {text[:50]}... (置信度: {confidence:.2f})")
            return whisper_result
            
        except Exception as e:
            logger.error(f"转写失败: {e}")
            return None
    
    def transcribe_with_preprocessing(self, audio_path: str,
                                       language: str = "zh",
                                       preprocess: bool = True) -> Optional[WhisperResult]:
        """
        带预处理的转写
        
        Args:
            audio_path: 音频文件路径
            language: 语言
            preprocess: 是否预处理
            
        Returns:
            WhisperResult 对象
        """
        try:
            import subprocess
            
            temp_file = None
            
            if preprocess:
                temp_file = tempfile.mktemp(suffix=".wav")
                
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-ar", "16000",
                    "-ac", "1",
                    "-acodec", "pcm_s16le",
                    temp_file
                ]
                
                try:
                    subprocess.run(
                        ffmpeg_cmd,
                        capture_output=True,
                        timeout=60
                    )
                    audio_path = temp_file
                except Exception as e:
                    logger.warning(f"音频预处理失败，使用原文件: {e}")
            
            result = self.transcribe(audio_path, language)
            
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            return result
            
        except Exception as e:
            logger.error(f"预处理转写失败: {e}")
            return None
    
    def transcribe_audio_data(self, audio_data: bytes,
                               language: str = "zh") -> Optional[WhisperResult]:
        """
        转写音频数据
        
        Args:
            audio_data: 音频字节数据
            language: 语言
            
        Returns:
            WhisperResult 对象
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            try:
                result = self.transcribe(temp_path, language)
                return result
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            logger.error(f"转写音频数据失败: {e}")
            return None
    
    def unload_model(self):
        """卸载模型，释放内存"""
        try:
            if self.model is not None:
                del self.model
                self.model = None
                self._is_loaded = False
                
                import torch
                torch.cuda.empty_cache() if torch.cuda.is_available() else None
                
                logger.info("✅ Whisper 模型已卸载")
        except Exception as e:
            logger.error(f"卸载模型失败: {e}")


_local_whisper_service: Optional[LocalWhisperService] = None


def get_local_whisper_service() -> LocalWhisperService:
    """获取全局 Whisper 服务实例（单例模式）"""
    global _local_whisper_service
    if _local_whisper_service is None:
        _local_whisper_service = LocalWhisperService()
    return _local_whisper_service


def transcribe_audio(audio_path: str, language: str = "zh") -> Optional[WhisperResult]:
    """
    便捷的音频转写函数
    
    Args:
        audio_path: 音频文件路径
        language: 语言
        
    Returns:
        WhisperResult 对象
    """
    service = get_local_whisper_service()
    return service.transcribe(audio_path, language)
