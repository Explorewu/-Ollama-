"""
ASR (Automatic Speech Recognition) 基类
定义统一的语音识别服务接口
"""
import os
import time
import logging
import tempfile
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, Tuple, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ASREngineType(Enum):
    """ASR 引擎类型"""
    WHISPER_OLLAMA = "whisper_ollama"
    WHISPER_LOCAL = "whisper_local"
    QWEN3_ASR = "qwen3_asr"


@dataclass
class TranscriptionResult:
    """转写结果"""
    text: str
    language: str
    confidence: float
    duration: float
    model: str
    engine: ASREngineType
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "engine": self.engine.value
        }


@dataclass
class EngineInfo:
    """引擎信息"""
    name: str
    engine_type: ASREngineType
    is_available: bool
    description: str = ""
    version: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "engine_type": self.engine_type.value,
            "is_available": self.is_available,
            "description": self.description,
            "version": self.version
        }


class AudioProcessor:
    """
    音频处理器（通用）
    
    负责音频文件的格式转换和预处理
    """
    
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm'}
    
    @staticmethod
    def validate_audio(file_path: str) -> Tuple[bool, str]:
        """
        验证音频文件
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            (是否有效, 错误信息)
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        ext = Path(file_path).suffix.lower()
        if ext not in AudioProcessor.SUPPORTED_FORMATS:
            return False, f"不支持的格式: {ext}，支持的格式: {', '.join(AudioProcessor.SUPPORTED_FORMATS)}"
        
        return True, ""
    
    @staticmethod
    def get_audio_duration(file_path: str) -> float:
        """
        获取音频时长
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            时长（秒）
        """
        try:
            import subprocess
            
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return float(result.stdout.strip())
        except Exception:
            return 0.0
    
    @staticmethod
    def convert_to_wav(input_path: str, output_path: str = None) -> str:
        """
        转换音频为 WAV 格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            
        Returns:
            输出文件路径
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix='.wav')
        
        try:
            import subprocess
            
            subprocess.run([
                'ffmpeg', '-y', '-i', input_path, 
                '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                output_path
            ], check=True, capture_output=True, timeout=60)
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"音频转换失败: {e}")
            raise ValueError(f"音频转换失败: {e}")
        except FileNotFoundError:
            raise RuntimeError("ffmpeg 未安装，无法进行音频转换")
    
    @staticmethod
    def remove_silence(file_path: str, output_path: str = None) -> str:
        """
        移除音频静音部分
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            处理后的文件路径
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix='.wav')
        
        try:
            import subprocess
            
            subprocess.run([
                'ffmpeg', '-y', '-i', file_path,
                '-af', 'silenceremove=1:0:-50dB',
                output_path
            ], check=True, capture_output=True, timeout=60)
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"移除静音失败: {e}")
            return file_path


class ASRService(ABC):
    """
    ASR 服务抽象基类
    
    所有 ASR 引擎都应该继承此类并实现抽象方法
    """
    
    def __init__(self):
        self._transcribe_lock = threading.Lock()
        self._is_initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化 ASR 服务
        
        Returns:
            是否初始化成功
        """
        pass
    
    @abstractmethod
    def get_engine_info(self) -> EngineInfo:
        """
        获取引擎信息
        
        Returns:
            引擎信息
        """
        pass
    
    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: str = 'zh',
        progress_callback: Callable[[float], None] = None
    ) -> Optional[TranscriptionResult]:
        """
        转写音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码
            progress_callback: 进度回调
            
        Returns:
            转写结果，失败返回 None
        """
        pass
    
    def transcribe_with_preprocessing(
        self,
        audio_path: str,
        language: str = 'zh',
        remove_silence: bool = True,
        progress_callback: Callable[[float], None] = None
    ) -> Optional[TranscriptionResult]:
        """
        带预处理的转写
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码
            remove_silence: 是否移除静音
            progress_callback: 进度回调
            
        Returns:
            转写结果
        """
        try:
            temp_files = []
            
            try:
                if remove_silence:
                    processed_path = AudioProcessor.remove_silence(audio_path)
                    temp_files.append(processed_path)
                else:
                    if not audio_path.endswith('.wav'):
                        processed_path = AudioProcessor.convert_to_wav(audio_path)
                        temp_files.append(processed_path)
                        audio_path = processed_path
                
                result = self.transcribe(audio_path, language, progress_callback)
                return result
                
            finally:
                for f in temp_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.error(f"预处理转写失败: {e}")
            return None
    
    def cleanup(self) -> None:
        """清理资源"""
        pass
