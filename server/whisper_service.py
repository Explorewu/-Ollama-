"""
语音识别服务模块

提供基于 Ollama Whisper 模型的语音识别功能，支持：
- 多种 Whisper 模型（tiny/base/small/medium/large）
- 中文语音识别优化
- 音频录制和处理
- 识别进度跟踪
- 实时转写支持
"""

import os
import time
import json
import logging
import tempfile
import threading
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WhisperModelSize(Enum):
    """Whisper 模型大小"""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    
    @property
    def memory_estimate(self) -> str:
        """内存需求估计"""
        sizes = {
            WhisperModelSize.TINY: "~1 GB",
            WhisperModelSize.BASE: "~1 GB",
            WhisperModelSize.SMALL: "~2 GB",
            WhisperModelSize.MEDIUM: "~5 GB",
            WhisperModelSize.LARGE: "~10 GB"
        }
        return sizes.get(self, "~2 GB")
    
    @property
    def speed_estimate(self) -> str:
        """速度估计"""
        speeds = {
            WhisperModelSize.TINY: "最快",
            WhisperModelSize.BASE: "快",
            WhisperModelSize.SMALL: "中等",
            WhisperModelSize.MEDIUM: "慢",
            WhisperModelSize.LARGE: "最慢"
        }
        return speeds.get(self, "中等")


@dataclass
class TranscriptionResult:
    """转写结果"""
    text: str
    language: str
    confidence: float
    duration: float
    model: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size: WhisperModelSize
    is_downloaded: bool
    download_progress: float = 0.0
    memory_usage: str = ""
    speed: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size.value,
            "is_downloaded": self.is_downloaded,
            "download_progress": self.download_progress,
            "memory_usage": self.memory_usage,
            "speed": self.speed
        }


class AudioProcessor:
    """
    音频处理器
    
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


class WhisperService:
    """
    Whisper 语音识别服务主类
    
    负责调用 Ollama Whisper API 进行语音识别
    """
    
    DEFAULT_MODEL = WhisperModelSize.BASE
    SUPPORTED_LANGUAGES = ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'ru']
    
    def __init__(self, base_url: str = None, model_size: WhisperModelSize = None):
        self.base_url = base_url or "http://localhost:11434"
        self.model_size = model_size or WhisperModelSize.BASE
        self.model_name = f"whisper:{self.model_size.value}"
        self._is_model_loaded = False
        self._transcribe_lock = threading.Lock()
    
    def check_model_status(self) -> ModelInfo:
        """
        检查模型状态
        
        Returns:
            模型信息
        """
        is_downloaded = self._check_model_exists()
        
        return ModelInfo(
            name=self.model_name,
            size=self.model_size,
            is_downloaded=is_downloaded,
            memory_usage=self.model_size.memory_estimate,
            speed=self.model_size.speed_estimate
        )
    
    def _check_model_exists(self) -> bool:
        """检查模型是否已下载"""
        try:
            import requests
            
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            
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
        """
        下载 Whisper 模型
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            是否下载成功
        """
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
                        
                        if 'status' in data:
                            logger.info(f"下载状态: {data['status']}")
                        
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
    
    def transcribe(self, audio_path: str, 
                   language: str = 'zh',
                   progress_callback: Callable[[float], None] = None) -> Optional[TranscriptionResult]:
        """
        转写音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码（zh/en/ja/ko等）
            progress_callback: 进度回调
            
        Returns:
            转写结果，失败返回 None
        """
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
                        model=self.model_name
                    )
                    
                    logger.info(f"转写完成: {duration:.1f}秒, {len(text)}字符")
                    return transcribed
                    
                else:
                    logger.error(f"转写失败: {response.status_code}")
                    return None
                    
            except Exception as e:
                logger.error(f"转写过程出错: {e}")
                return None
    
    def transcribe_with_preprocessing(self, audio_path: str,
                                        language: str = 'zh',
                                        remove_silence: bool = True,
                                        progress_callback: Callable[[float], None] = None) -> Optional[TranscriptionResult]:
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
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        获取可用的模型列表
        
        Returns:
            模型信息列表
        """
        models = []
        
        try:
            import requests
            
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                installed_models = [m['name'] for m in data.get('models', [])]
            else:
                installed_models = []
                
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            installed_models = []
        
        for size in WhisperModelSize:
            model_name = f"whisper:{size.value}"
            info = ModelInfo(
                name=model_name,
                size=size,
                is_downloaded=any(
                    model_name in m or m == model_name 
                    for m in installed_models
                ),
                memory_usage=size.memory_estimate,
                speed=size.speed_estimate
            )
            models.append(info)
        
        return models


class AudioRecorder:
    """
    音频录制器
    
    负责录制麦克风音频
    """
    
    def __init__(self):
        self._is_recording = False
        self._record_thread = None
        self._audio_data = []
    
    def start_recording(self, on_data_callback: Callable[[bytes], None] = None,
                        sample_rate: int = 16000) -> bool:
        """
        开始录制
        
        Args:
            on_data_callback: 数据回调
            sample_rate: 采样率
            
        Returns:
            是否开始成功
        """
        try:
            import pyaudio
            import wave
            
            self._audio_data = []
            self._is_recording = True
            
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                frames_per_buffer=1024
            )
            
            def record_loop():
                while self._is_recording:
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                        self._audio_data.append(data)
                        if on_data_callback:
                            on_data_callback(data)
                    except Exception:
                        break
            
            self._record_thread = threading.Thread(target=record_loop, daemon=True)
            self._record_thread.start()
            
            self._audio_stream = stream
            self._audio = audio
            
            return True
            
        except ImportError:
            logger.error("pyaudio 未安装")
            return False
        except Exception as e:
            logger.error(f"开始录制失败: {e}")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """
        停止录制并保存文件
        
        Returns:
            录制文件路径，失败返回 None
        """
        self._is_recording = False
        
        if self._record_thread:
            self._record_thread.join(timeout=2)
        
        if hasattr(self, '_audio_stream'):
            self._audio_stream.stop_stream()
            self._audio_stream.close()
        
        if hasattr(self, '_audio'):
            self._audio.terminate()
        
        if not self._audio_data:
            return None
        
        temp_file = tempfile.mktemp(suffix='.wav')
        
        try:
            import wave
            
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b''.join(self._audio_data))
            
            return temp_file
            
        except Exception as e:
            logger.error(f"保存音频失败: {e}")
            return None
    
    def cancel_recording(self) -> None:
        """取消录制"""
        self._is_recording = False
        
        if self._record_thread:
            self._record_thread.join(timeout=1)
        
        if hasattr(self, '_audio_stream'):
            try:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            except Exception:
                pass
        
        if hasattr(self, '_audio'):
            try:
                self._audio.terminate()
            except Exception:
                pass
        
        self._audio_data = []


# 单例实例
_whisper_service_instance: Optional[WhisperService] = None


def get_whisper_service(base_url: str = None, 
                        model_size: WhisperModelSize = None) -> WhisperService:
    """
    获取 Whisper 服务单例
    
    Args:
        base_url: Ollama API 地址
        model_size: 模型大小
        
    Returns:
        WhisperService 实例
    """
    global _whisper_service_instance
    
    if _whisper_service_instance is None:
        _whisper_service_instance = WhisperService(base_url, model_size)
    
    return _whisper_service_instance


if __name__ == "__main__":
    print("=" * 60)
    print("Whisper 语音识别服务测试")
    print("=" * 60)
    
    service = get_whisper_service()
    
    print("\n1. 检查模型状态...")
    model_info = service.check_model_status()
    print(f"  模型: {model_info.name}")
    print(f"  大小: {model_info.size.value}")
    print(f"  已下载: {model_info.is_downloaded}")
    print(f"  内存需求: {model_info.memory_usage}")
    print(f"  速度: {model_info.speed}")
    
    print("\n2. 获取可用模型列表...")
    models = service.get_available_models()
    for m in models:
        print(f"  {m.name}: {'已安装' if m.is_downloaded else '未安装'} ({m.size.memory_usage})")
    
    print("\n" + "=" * 60)
    print("服务测试完成")
    print("=" * 60)
    print("\n注意: 需要先运行 'ollama pull whisper:base' 下载模型")
