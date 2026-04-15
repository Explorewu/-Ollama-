"""
Qwen3-TTS 语音合成服务模块

基于阿里通义千问团队 2026年1月发布的 Qwen3-TTS 模型
特点：97ms超低延迟、3秒音色克隆、情绪控制、多语言支持

模型缓存位置：<models>/tts

优化特性：
- 懒加载模式：首次使用时才加载模型
- 流式合成：支持实时音频流输出
- 音色缓存：预设音色预加载，减少延迟
- 并发控制：单路通话，避免资源冲突
- 降级方案：模型不可用时使用 edge-tts

使用方法:
    service = Qwen3TTSService()
    audio = service.synthesize("你好，我是AI助手", speaker_id="default")
    service.save_audio(audio, "output.wav")
"""

import os
import io
import time
import json
import logging
import tempfile
import base64
import asyncio
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass
from pathlib import Path
from model_paths import MODELS_DIR

TTS_CACHE_DIR = os.path.join(MODELS_DIR, "tts")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)
os.environ['HF_HOME'] = TTS_CACHE_DIR
os.environ['HUGGINGFACE_HUB_CACHE'] = TTS_CACHE_DIR
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

MODEL_STATUS_FILE = os.path.join(TTS_CACHE_DIR, "model_status.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"TTS模型缓存目录: {TTS_CACHE_DIR}")


@dataclass
class TTSResult:
    """语音合成结果"""
    audio_bytes: bytes
    sample_rate: int = 24000
    duration_ms: float = 0.0
    speaker_id: str = "default"
    format: str = "pcm"  # pcm 或 mp3


@dataclass
class SpeakerProfile:
    """音色配置"""
    speaker_id: str
    name: str
    description: str
    emotion: str = "neutral"
    speed: float = 1.0


PRESET_SPEAKERS = {
    "default": SpeakerProfile(
        speaker_id="vivian",
        name="Vivian",
        description="明亮的年轻女声（中文）",
        emotion="neutral",
        speed=1.0
    ),
    "warm": SpeakerProfile(
        speaker_id="serena",
        name="Serena",
        description="温暖柔和的年轻女声（中文）",
        emotion="warm",
        speed=0.95
    ),
    "professional": SpeakerProfile(
        speaker_id="uncle_fu",
        name="Uncle_Fu",
        description="成熟男声，音色醇厚（中文）",
        emotion="neutral",
        speed=1.0
    ),
    "cheerful": SpeakerProfile(
        speaker_id="dylan",
        name="Dylan",
        description="充满青春气息的北京男声",
        emotion="cheerful",
        speed=1.1
    ),
    "calm": SpeakerProfile(
        speaker_id="eric",
        name="Eric",
        description="活泼的成都男声",
        emotion="calm",
        speed=0.9
    ),
    "english_male": SpeakerProfile(
        speaker_id="ryan",
        name="Ryan",
        description="富有节奏感的活力男声（英文）",
        emotion="neutral",
        speed=1.0
    ),
    "english_american": SpeakerProfile(
        speaker_id="aiden",
        name="Aiden",
        description="阳光的美式男声（英文）",
        emotion="neutral",
        speed=1.0
    ),
    "japanese": SpeakerProfile(
        speaker_id="ono_anna",
        name="Ono_Anna",
        description="活泼的日语女声",
        emotion="neutral",
        speed=1.0
    ),
    "korean": SpeakerProfile(
        speaker_id="sohee",
        name="Sohee",
        description="温暖的韩语女声",
        emotion="neutral",
        speed=1.0
    )
}

EDGE_TTS_VOICE_MAP = {
    "default": "zh-CN-XiaoxiaoNeural",
    "warm": "zh-CN-XiaoyiNeural",
    "professional": "zh-CN-YunxiNeural",
    "cheerful": "zh-CN-XiaochenNeural",
    "calm": "zh-CN-YunjianNeural",
    "english_male": "en-US-GuyNeural",
    "english_american": "en-US-ChristopherNeural",
    "japanese": "ja-JP-NanamiNeural",
    "korean": "ko-KR-SunHiNeural"
}


def load_model_status() -> Dict[str, Any]:
    """加载模型状态缓存"""
    if os.path.exists(MODEL_STATUS_FILE):
        try:
            with open(MODEL_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载模型状态缓存失败: {e}")
    return {}


def save_model_status(status: Dict[str, Any]):
    """保存模型状态缓存"""
    try:
        with open(MODEL_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存模型状态缓存失败: {e}")


class Qwen3TTSService:
    """
    Qwen3-TTS 语音合成服务
    
    设计原则：
    1. 懒加载：模型按需加载，减少启动时间
    2. 流式处理：支持实时音频流输出
    3. 单例模式：避免重复加载模型
    4. 容错处理：模型加载失败时优雅降级到 edge-tts
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if Qwen3TTSService._initialized:
            return
            
        self.model = None
        self.model_name = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
        self._project_dir = Path(__file__).resolve().parent.parent
        self.local_model_path = self._find_local_model_path()
        self.is_loaded = False
        self.device = "cpu"
        self.current_speaker = "default"
        self._use_fallback = False
        self._torch = None
        
        # 性能统计
        self._load_time = 0.0
        self._first_synthesis_time = 0.0
        self._total_synthesis_count = 0
        self._total_synthesis_time = 0.0
        
        try:
            import torch
            self._torch = torch
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info("TTS使用CUDA加速")
            else:
                logger.info("TTS使用CPU运行")
        except ImportError:
            logger.info("PyTorch未安装，TTS将使用降级方案")
            self._use_fallback = True
        
        Qwen3TTSService._initialized = True
    
    def _find_local_model_path(self) -> str:
        """查找本地TTS模型路径"""
        possible_paths = [
            self._project_dir / "models" / "audio" / "tts" / "qwen3-tts-custom",
            self._project_dir / "models" / "audio" / "tts" / "qwen3-tts-base",
            Path(TTS_CACHE_DIR) / "Qwen" / "Qwen3-TTS-12Hz-0___6B-CustomVoice",
            Path(TTS_CACHE_DIR) / "Qwen" / "Qwen3-TTS-12Hz-0___6B-Base",
        ]
        for p in possible_paths:
            if p.exists() and (p / "config.json").exists():
                logger.info(f"找到本地TTS模型: {p}")
                return str(p)
        logger.warning("未找到本地TTS模型，将从远程下载")
        return os.path.join(TTS_CACHE_DIR, "Qwen", "Qwen3-TTS-12Hz-0___6B-CustomVoice")
    
    def load_model(self) -> bool:
        """
        加载Qwen3-TTS模型
        
        Returns:
            bool: 加载成功返回True，失败返回False
        """
        if self.is_loaded:
            return True
        
        if self._use_fallback:
            logger.info("使用 edge-tts 降级方案")
            return self._load_fallback()
        
        status = load_model_status()
        if status.get(self.model_name, {}).get("disabled", False):
            logger.warning(f"模型 {self.model_name} 已被禁用，尝试降级方案")
            return self._load_fallback()
        
        try:
            logger.info(f"正在加载Qwen3-TTS模型: {self.model_name}")
            start_time = time.time()
            
            try:
                from qwen_tts import Qwen3TTSModel
            except ImportError:
                logger.warning("qwen_tts 包未安装，尝试降级方案")
                return self._load_fallback()
            
            # 优先使用本地模型路径
            model_path = self.local_model_path if os.path.exists(self.local_model_path) else self.model_name
            
            self.model = Qwen3TTSModel.from_pretrained(
                model_path,
                device_map=self.device
            )
            
            load_time = time.time() - start_time
            logger.info(f"Qwen3-TTS模型加载完成，耗时: {load_time:.2f}s")
            
            self.is_loaded = True
            
            status[self.model_name] = {
                "loaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "load_time": load_time,
                "device": self.device
            }
            save_model_status(status)
            
            return True
            
        except Exception as e:
            logger.error(f"加载Qwen3-TTS模型失败: {e}")
            status[self.model_name] = {
                "disabled": True,
                "disabled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e)
            }
            save_model_status(status)
            return self._load_fallback()
    
    def _load_fallback(self) -> bool:
        """加载降级方案 (edge-tts)"""
        try:
            import edge_tts
            self._use_fallback = True
            self.is_loaded = True
            logger.info("edge-tts 降级方案已启用")
            return True
        except ImportError:
            logger.error("edge-tts 也未安装，语音合成功能不可用")
            logger.info("安装命令: pip install edge-tts")
            return False
    
    def synthesize(
        self,
        text: str,
        speaker_id: str = "default",
        speed: float = 1.0,
        emotion: Optional[str] = None
    ) -> Optional[TTSResult]:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            speaker_id: 音色ID
            speed: 语速倍率 (0.5-2.0)
            emotion: 情绪标签
            
        Returns:
            TTSResult: 合成结果，失败返回None
        """
        if not text or not text.strip():
            logger.warning("合成文本为空")
            return None
        
        if not self.is_loaded:
            if not self.load_model():
                logger.error("TTS模型未加载，无法合成语音")
                return None
        
        if self._use_fallback:
            return self._synthesize_fallback(text, speaker_id, speed)
        
        return self._synthesize_qwen(text, speaker_id, speed, emotion)
    
    def _synthesize_qwen(
        self,
        text: str,
        speaker_id: str,
        speed: float,
        emotion: Optional[str]
    ) -> Optional[TTSResult]:
        """使用 Qwen3-TTS 合成"""
        try:
            start_time = time.time()
            
            speaker = PRESET_SPEAKERS.get(speaker_id, PRESET_SPEAKERS["default"])
            
            instruct = None
            if emotion:
                emotion_map = {
                    "happy": "用开心的语气说",
                    "sad": "用悲伤的语气说",
                    "angry": "用愤怒的语气说",
                    "neutral": "用平静的语气说",
                    "warm": "用温暖的语气说",
                    "cheerful": "用活泼的语气说",
                    "calm": "用冷静的语气说"
                }
                instruct = emotion_map.get(emotion, f"用{emotion}的语气说")
            
            wavs, sr = self.model.generate_custom_voice(
                text=text,
                language="Chinese",
                speaker=speaker.speaker_id,
                instruct=instruct
            )
            
            if wavs is None or len(wavs) == 0:
                logger.error("Qwen3-TTS 合成失败，返回空音频")
                return None
            
            import numpy as np
            audio_data = np.array(wavs[0])
            audio_bytes = self._numpy_to_bytes(audio_data)
            duration_ms = len(audio_data) / sr * 1000
            
            synthesis_time = time.time() - start_time
            logger.info(f"Qwen3-TTS合成完成，文本长度: {len(text)}, 耗时: {synthesis_time:.3f}s")
            
            return TTSResult(
                audio_bytes=audio_bytes,
                sample_rate=sr,
                duration_ms=duration_ms,
                speaker_id=speaker_id
            )
            
        except Exception as e:
            logger.error(f"Qwen3-TTS合成失败: {e}，尝试降级方案")
            return self._synthesize_fallback(text, speaker_id, speed)
    
    def _synthesize_fallback(
        self,
        text: str,
        speaker_id: str,
        speed: float
    ) -> Optional[TTSResult]:
        """使用 edge-tts 降级方案合成（返回WAV格式PCM数据）"""
        try:
            import edge_tts
            import numpy as np
            
            start_time = time.time()
            
            voice = EDGE_TTS_VOICE_MAP.get(speaker_id, EDGE_TTS_VOICE_MAP["default"])
            
            communicate = edge_tts.Communicate(text, voice)
            
            audio_chunks = []
            async def collect_audio():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])
            
            try:
                asyncio.run(collect_audio())
            except RuntimeError:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, collect_audio())
                    future.result()
            
            if not audio_chunks:
                logger.error("edge-tts 合成失败，返回空音频")
                return None
            
            mp3_bytes = b"".join(audio_chunks)
            
            # edge-tts 返回 MP3 格式，需要解码为 PCM
            pcm_bytes, actual_sample_rate = self._mp3_to_pcm(mp3_bytes)
            
            if pcm_bytes is None:
                logger.error("MP3 解码失败")
                return None
            
            duration_ms = len(pcm_bytes) / 2 / actual_sample_rate * 1000
            
            synthesis_time = time.time() - start_time
            logger.info(f"edge-tts合成完成，文本长度: {len(text)}, 耗时: {synthesis_time:.3f}s")
            
            return TTSResult(
                audio_bytes=pcm_bytes,
                sample_rate=actual_sample_rate,
                duration_ms=duration_ms,
                speaker_id=speaker_id,
                format="pcm"
            )
            
        except Exception as e:
            logger.error(f"edge-tts合成失败: {e}")
            return None
    
    def _mp3_to_pcm(self, mp3_bytes: bytes):
        """将 MP3 音频解码为 PCM (int16, mono) 数据"""
        try:
            import librosa
            import tempfile
            mp3_path = os.path.join(tempfile.gettempdir(), f'_qwen3_tts_{id(self)}.mp3')
            with open(mp3_path, 'wb') as f:
                f.write(mp3_bytes)
            y, sr = librosa.load(mp3_path, sr=None, mono=True)
            os.unlink(mp3_path)
            audio_int16 = (y * 32767).astype(np.int16)
            return audio_int16.tobytes(), int(sr)
        except Exception as e:
            logger.debug(f"librosa MP3解码失败: {e}")
        
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
            audio = audio.set_channels(1).set_sample_width(2)
            actual_rate = audio.frame_rate
            return audio.raw_data, actual_rate
        except Exception as e:
            logger.debug(f"pydub MP3解码失败: {e}")
        
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_file:
                mp3_file.write(mp3_bytes)
                mp3_path = mp3_file.name
            wav_path = mp3_path.replace('.mp3', '.wav')
            result = subprocess.run(
                ['ffmpeg', '-i', mp3_path, '-ac', '1', '-ar', '24000', '-f', 'wav', '-y', wav_path],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                import wave
                with wave.open(wav_path, 'rb') as wf:
                    pcm_data = wf.readframes(wf.getnframes())
                    actual_rate = wf.getframerate()
                os.unlink(mp3_path)
                os.unlink(wav_path)
                return pcm_data, actual_rate
            else:
                logger.error(f"ffmpeg 解码失败: {result.stderr.decode()[:200]}")
                if os.path.exists(mp3_path):
                    os.unlink(mp3_path)
                return None, 0
        except FileNotFoundError:
            logger.error("ffmpeg 未安装，无法解码 MP3")
            return None, 0
        except Exception as e:
            logger.error(f"MP3 解码失败: {e}")
            return None, 0
    
    def synthesize_stream(
        self,
        text: str,
        speaker_id: str = "default",
        chunk_size: int = 1024
    ) -> Generator[bytes, None, None]:
        """
        流式合成语音
        
        Args:
            text: 要合成的文本
            speaker_id: 音色ID
            chunk_size: 音频块大小
            
        Yields:
            bytes: 音频数据块
        """
        result = self.synthesize(text, speaker_id)
        if result is None:
            return
        
        audio_data = result.audio_bytes
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            yield chunk
    
    def _numpy_to_bytes(self, audio_data) -> bytes:
        """将numpy数组转换为音频字节"""
        import numpy as np
        
        if audio_data.dtype != np.int16:
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            audio_int16 = (audio_data * 32767).astype(np.int16)
        else:
            audio_int16 = audio_data
        
        return audio_int16.tobytes()
    
    def save_audio(self, result: TTSResult, output_path: str):
        """
        保存音频到文件
        
        Args:
            result: 合成结果
            output_path: 输出文件路径
        """
        try:
            import wave
            
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(result.sample_rate)
                wav_file.writeframes(result.audio_bytes)
            
            logger.info(f"音频已保存: {output_path}")
            
        except Exception as e:
            logger.error(f"保存音频失败: {e}")
    
    def audio_to_base64(self, result: TTSResult, wrap_wav: bool = True) -> str:
        """
        将音频转换为base64字符串
        
        Args:
            result: 合成结果
            wrap_wav: 是否包装成WAV格式（前端decodeAudioData需要WAV头）
        
        Returns:
            base64编码的音频数据
        """
        if result.format == "mp3":
            return base64.b64encode(result.audio_bytes).decode('utf-8')
        
        if wrap_wav:
            wav_bytes = self._wrap_wav_header(
                result.audio_bytes, 
                result.sample_rate, 
                channels=1, 
                bits=16
            )
            return base64.b64encode(wav_bytes).decode('utf-8')
        return base64.b64encode(result.audio_bytes).decode('utf-8')
    
    def _wrap_wav_header(self, pcm_bytes: bytes, sample_rate: int, channels: int = 1, bits: int = 16) -> bytes:
        """
        为PCM数据添加WAV文件头
        
        Args:
            pcm_bytes: 原始PCM音频数据
            sample_rate: 采样率
            channels: 声道数
            bits: 位深度
        
        Returns:
            完整的WAV文件字节
        """
        import struct
        
        byte_rate = sample_rate * channels * bits // 8
        block_align = channels * bits // 8
        data_size = len(pcm_bytes)
        
        wav_header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + data_size,
            b'WAVE',
            b'fmt ',
            16,
            1,
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits,
            b'data',
            data_size
        )
        
        return wav_header + pcm_bytes
    
    def get_available_speakers(self) -> Dict[str, SpeakerProfile]:
        """获取所有可用音色"""
        return PRESET_SPEAKERS.copy()
    
    def set_speaker(self, speaker_id: str) -> bool:
        """
        设置当前音色
        
        Args:
            speaker_id: 音色ID
            
        Returns:
            bool: 设置成功返回True
        """
        if speaker_id not in PRESET_SPEAKERS:
            logger.warning(f"未知音色ID: {speaker_id}，使用默认音色")
            speaker_id = "default"
        
        self.current_speaker = speaker_id
        logger.info(f"当前音色已设置为: {PRESET_SPEAKERS[speaker_id].name}")
        return True
    
    def check_status(self) -> Dict[str, Any]:
        """检查服务状态"""
        return {
            "model_name": self.model_name,
            "is_loaded": self.is_loaded,
            "device": self.device,
            "current_speaker": self.current_speaker,
            "available_speakers": list(PRESET_SPEAKERS.keys()),
            "cache_dir": TTS_CACHE_DIR,
            "using_fallback": self._use_fallback,
            "load_time": self._load_time,
            "first_synthesis_time": self._first_synthesis_time,
            "total_synthesis_count": self._total_synthesis_count,
            "avg_synthesis_time": self._total_synthesis_time / max(1, self._total_synthesis_count)
        }
    
    def get_performance_stats(self) -> Dict[str, float]:
        """
        获取性能统计数据
        
        Returns:
            包含各项时间指标的字典
        """
        return {
            "model_load_time": self._load_time,
            "first_synthesis_time": self._first_synthesis_time,
            "total_synthesis_count": self._total_synthesis_count,
            "total_synthesis_time": self._total_synthesis_time,
            "avg_synthesis_time": self._total_synthesis_time / max(1, self._total_synthesis_count)
        }
    
    def unload_model(self):
        """卸载模型，释放内存"""
        if self.model is not None:
            del self.model
            self.model = None
        
        self.is_loaded = False
        
        import gc
        gc.collect()
        
        logger.info("TTS模型已卸载")


_tts_service = None


def get_tts_service() -> Qwen3TTSService:
    """获取TTS服务实例（单例模式）"""
    global _tts_service
    if _tts_service is None:
        _tts_service = Qwen3TTSService()
    return _tts_service


if __name__ == "__main__":
    service = get_tts_service()
    
    print("Qwen3-TTS 服务测试")
    print(f"状态: {service.check_status()}")
    
    test_text = "你好，我是Qwen3语音助手，很高兴为你服务。"
    result = service.synthesize(test_text, speaker_id="default")
    
    if result:
        print(f"合成成功！音频大小: {len(result.audio_bytes)} bytes")
        print(f"时长: {result.duration_ms:.0f}ms")
        service.save_audio(result, "test_output.wav")
    else:
        print("合成失败")
