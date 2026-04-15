"""
Silero TTS 语音合成服务
功能：本地语音合成，支持多角色音色匹配
模型：Silero TTS（~100MB，效果好、纯Python、可离线运行）

优化特性：
- 延迟导入：避免启动时加载 torch
- 降级方案：silero 不可用时使用 edge-tts
- 单例模式：避免重复加载模型
"""

import os
import sys
import io
import json
import asyncio
import numpy as np
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
import logging
import base64

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """语音配置"""
    speaker_id: str = "baya"
    language: str = "zh"
    sample_rate: int = 48000
    device: str = "cpu"


@dataclass
class CharacterVoiceProfile:
    """角色音色档案"""
    speaker_id: str = "baya"
    rate: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    emotion: str = "neutral"


@dataclass
class TTSResult:
    """语音合成结果"""
    audio_bytes: bytes
    sample_rate: int = 24000
    duration_ms: float = 0.0
    speaker_id: str = "default"


CHARACTER_VOICE_PROFILES = {
    "古代书生": {
        "speaker_id": "baya",
        "rate": 0.85,
        "pitch": -2,
        "volume": 0.9,
        "emotion": "calm"
    },
    "心理咨询师": {
        "speaker_id": "baya",
        "rate": 0.9,
        "pitch": 2,
        "volume": 0.85,
        "emotion": "warm"
    },
    "科幻AI": {
        "speaker_id": "aidar",
        "rate": 1.1,
        "pitch": 5,
        "volume": 1.0,
        "emotion": "neutral"
    },
    "脱口秀演员": {
        "speaker_id": "baya",
        "rate": 1.2,
        "pitch": 3,
        "volume": 1.1,
        "emotion": "cheerful"
    },
    "神秘管家": {
        "speaker_id": "aidar",
        "rate": 0.8,
        "pitch": -3,
        "volume": 0.85,
        "emotion": "serious"
    },
    "理性分析师": {
        "speaker_id": "aidar",
        "rate": 1.0,
        "pitch": 0,
        "volume": 0.95,
        "emotion": "neutral"
    },
    "创意作家": {
        "speaker_id": "baya",
        "rate": 0.95,
        "pitch": 4,
        "volume": 0.9,
        "emotion": "cheerful"
    },
    "历史学者": {
        "speaker_id": "aidar",
        "rate": 0.85,
        "pitch": -1,
        "volume": 0.9,
        "emotion": "calm"
    },
    "default": {
        "speaker_id": "baya",
        "rate": 1.0,
        "pitch": 0,
        "volume": 1.0,
        "emotion": "neutral"
    }
}

EDGE_TTS_VOICE_MAP = {
    "baya": "zh-CN-XiaoxiaoNeural",
    "aidar": "zh-CN-YunxiNeural",
    "eugene": "zh-CN-YunjianNeural",
    "kseniya": "zh-CN-XiaoyiNeural",
    "xenia": "zh-CN-XiaochenNeural"
}


class SileroTTSService:
    """
    Silero TTS 语音合成服务
    支持：本地运行、多角色音色、情感参数调整、降级方案
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model = None
        self.device = None
        self.voices_dir = Path(__file__).parent.parent / "models" / "silero_voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self._model_lock = threading.Lock()
        self._use_fallback = False
        self._use_edge_tts = False
        self._initialized = True
        logger.info("✓ SileroTTSService 初始化完成")
    
    def load_model(self) -> bool:
        """加载TTS模型（优先edge-tts用于中文，Silero用于其他语言）"""
        with self._model_lock:
            if self._use_edge_tts or self.model is not None:
                return True
            
            # 优先加载 edge-tts（支持中文）
            try:
                import edge_tts
                self._use_edge_tts = True
                logger.info("✓ edge-tts 已启用（中文语音合成）")
                return True
            except ImportError:
                logger.warning("edge-tts 未安装，尝试 Silero TTS")
            
            # Silero TTS 作为备选（不支持中文）
            try:
                import torch
                
                self.device = torch.device("cpu")
                logger.info(f"正在加载 Silero TTS 模型，设备: {self.device}")
                
                try:
                    import silero_tts
                    
                    torch.hub.set_dir(str(self.voices_dir))
                    
                    self.model, _ = torch.hub.load(
                        repo_or_dir='snakers4/silero-models',
                        model='silero_tts',
                        language='ru',
                        speaker='baya_v2',
                        trust_repo=True
                    )
                    self.model.to(self.device)
                    
                    logger.info("✓ Silero TTS 模型加载成功（仅支持俄语/英语）")
                    return True
                    
                except Exception as e:
                    logger.warning(f"Silero TTS 加载失败: {e}")
                    return False
                
            except ImportError as e:
                logger.warning(f"缺少依赖: {e}")
                return False
            except Exception as e:
                logger.error(f"✗ TTS 模型加载失败: {e}")
                return False
    
    def get_voice_profile(self, character_name: str) -> Dict[str, Any]:
        """获取角色对应的音色配置"""
        profile = CHARACTER_VOICE_PROFILES.get(character_name)
        if profile:
            return profile.copy()
        return CHARACTER_VOICE_PROFILES["default"].copy()
    
    def synthesize(
        self,
        text: str,
        character_name: str = "default",
        sample_rate: int = 48000
    ) -> Optional[np.ndarray]:
        """
        语音合成
        
        Args:
            text: 要合成的文本
            character_name: 角色名称
            sample_rate: 采样率
        
        Returns:
            音频数据 (numpy array) 或 None
        """
        if not text or not text.strip():
            logger.warning("合成文本为空")
            return None
        
        if not self.load_model():
            logger.warning("TTS模型未加载")
            return None
        
        if self._use_edge_tts:
            result = self._synthesize_fallback(text, character_name, sample_rate)
            if result:
                audio_array = np.frombuffer(result.audio_bytes, dtype=np.int16)
                return audio_array.astype(np.float32) / 32768.0
            return None
        
        try:
            profile = self.get_voice_profile(character_name)
            speaker = profile["speaker_id"]
            
            logger.info(f"合成语音: [{character_name}] {text[:30]}...")
            
            try:
                audio = self.model.apply_tts(
                    texts=[text],
                    sample_rate=sample_rate
                )
                
                if audio and len(audio) > 0:
                    audio_data = audio[0].numpy() if hasattr(audio[0], 'numpy') else np.array(audio[0])
                    return audio_data
                
            except AttributeError:
                audio = self.model.generate(text)
                if audio is not None:
                    audio_data = audio.cpu().numpy() if hasattr(audio, 'cpu') else np.array(audio)
                    return audio_data
            
            return None
            
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None
    
    def synthesize_to_result(
        self,
        text: str,
        character_name: str = "default",
        sample_rate: int = 24000
    ) -> Optional[TTSResult]:
        """
        合成语音并返回 TTSResult
        
        Args:
            text: 要合成的文本
            character_name: 角色名称
            sample_rate: 采样率
        
        Returns:
            TTSResult 或 None
        """
        if not self.load_model():
            logger.warning("TTS模型未加载")
            return None
        
        if self._use_edge_tts:
            return self._synthesize_fallback(text, character_name, sample_rate)
        
        audio_data = self.synthesize(text, character_name, sample_rate)
        if audio_data is None:
            return None
        
        audio_int16 = (audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        duration_ms = len(audio_data) / sample_rate * 1000
        
        return TTSResult(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
            speaker_id=character_name
        )
    
    def _synthesize_fallback(
        self,
        text: str,
        character_name: str,
        sample_rate: int
    ) -> Optional[TTSResult]:
        """使用 edge-tts 降级方案合成（返回WAV格式PCM数据）"""
        try:
            import edge_tts
            
            profile = self.get_voice_profile(character_name)
            speaker = profile.get("speaker_id", "baya")
            voice = EDGE_TTS_VOICE_MAP.get(speaker, EDGE_TTS_VOICE_MAP["baya"])
            
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
            
            return TTSResult(
                audio_bytes=pcm_bytes,
                sample_rate=actual_sample_rate,
                duration_ms=duration_ms,
                speaker_id=character_name
            )
            
        except Exception as e:
            logger.error(f"edge-tts合成失败: {e}")
            return None
    
    def _mp3_to_pcm(self, mp3_bytes: bytes):
        """将 MP3 音频解码为 PCM (int16, mono) 数据"""
        try:
            import librosa
            import tempfile
            mp3_path = os.path.join(tempfile.gettempdir(), f'_tts_{id(self)}.mp3')
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
    
    def synthesize_with_emotion(
        self,
        text: str,
        character_name: str = "default",
        emotion: str = "neutral",
        sample_rate: int = 48000
    ) -> Optional[np.ndarray]:
        """带情感的语音合成"""
        profile = self.get_voice_profile(character_name)
        profile["emotion"] = emotion
        
        return self.synthesize(text, character_name, sample_rate)
    
    def save_audio(
        self,
        audio_data: np.ndarray,
        output_path: str,
        sample_rate: int = 48000
    ) -> bool:
        """保存音频文件"""
        try:
            from scipy.io import wavfile
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            audio_int16 = (audio_data * 32767).astype(np.int16)
            wavfile.write(str(output_path), sample_rate, audio_int16)
            
            logger.info(f"✓ 音频已保存: {output_path}")
            return True
        except ImportError:
            logger.warning("scipy未安装，使用简单WAV保存")
            return self._save_audio_simple(audio_data, output_path, sample_rate)
        except Exception as e:
            logger.error(f"保存音频失败: {e}")
            return False
    
    def save_audio_from_result(self, result: TTSResult, output_path: str) -> bool:
        """从 TTSResult 保存音频文件"""
        try:
            import wave
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with wave.open(str(output_path), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(result.sample_rate)
                wf.writeframes(result.audio_bytes)
            
            logger.info(f"✓ 音频已保存: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存音频失败: {e}")
            return False
    
    def _save_audio_simple(
        self,
        audio_data: np.ndarray,
        output_path: str,
        sample_rate: int = 48000
    ) -> bool:
        """简单WAV保存（无scipy依赖）"""
        try:
            import wave
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            with wave.open(str(output_path), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            
            logger.info(f"✓ 音频已保存(简单模式): {output_path}")
            return True
        except Exception as e:
            logger.error(f"简单保存音频失败: {e}")
            return False
    
    def audio_to_base64(self, result: TTSResult) -> str:
        """将音频转换为base64字符串"""
        return base64.b64encode(result.audio_bytes).decode('utf-8')
    
    def play_audio(self, audio_data: np.ndarray, sample_rate: int = 48000) -> bool:
        """播放音频（使用pydub）"""
        try:
            from pydub import AudioSegment
            from pydub.playback import play
            
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_segment = AudioSegment(
                audio_int16.tobytes(),
                frame_rate=sample_rate,
                sample_width=2,
                channels=1
            )
            
            play(audio_segment)
            return True
        except ImportError:
            logger.warning("pydub未安装，无法播放音频")
            return False
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
            return False
    
    def get_available_speakers(self) -> list:
        """获取可用的说话人列表"""
        return ["baya", "aidar", "eugene", "kseniya", "xenia"]
    
    def get_character_profiles(self) -> Dict[str, Dict]:
        """获取所有角色音色配置"""
        return CHARACTER_VOICE_PROFILES.copy()
    
    def add_custom_profile(
        self,
        character_name: str,
        speaker_id: str,
        rate: float = 1.0,
        pitch: float = 0.0,
        volume: float = 1.0,
        emotion: str = "neutral"
    ) -> bool:
        """添加自定义角色音色配置"""
        try:
            CHARACTER_VOICE_PROFILES[character_name] = {
                "speaker_id": speaker_id,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "emotion": emotion
            }
            logger.info(f"✓ 已添加角色音色配置: {character_name}")
            return True
        except Exception as e:
            logger.error(f"添加角色音色配置失败: {e}")
            return False
    
    def check_status(self) -> Dict[str, Any]:
        """检查服务状态"""
        return {
            "is_loaded": self.model is not None,
            "using_edge_tts": self._use_edge_tts,
            "using_fallback": self._use_fallback,
            "device": str(self.device) if self.device else "cpu",
            "available_speakers": self.get_available_speakers(),
            "character_profiles": list(CHARACTER_VOICE_PROFILES.keys())
        }


_tts_service = None


def get_tts_service() -> SileroTTSService:
    """获取TTS服务单例"""
    global _tts_service
    if _tts_service is None:
        _tts_service = SileroTTSService()
    return _tts_service


if __name__ == "__main__":
    service = get_tts_service()
    
    print("Silero TTS 服务测试")
    print(f"状态: {service.check_status()}")
    
    result = service.synthesize_to_result("你好，我是智能助手", "default")
    if result:
        print(f"语音合成成功，音频大小: {len(result.audio_bytes)} bytes")
        print(f"时长: {result.duration_ms:.0f}ms")
        service.save_audio_from_result(result, "test_output.wav")
    else:
        print("模型加载失败，请检查依赖")
