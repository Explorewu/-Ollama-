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
    audio = service.synthesize("你好，我是AI助手", speaker_id="vivian")
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
    # ===== 中文女声 (5种) =====
    "vivian": SpeakerProfile(
        speaker_id="vivian", name="Vivian",
        description="明亮自然女声 · 均衡清晰，适合日常对话", emotion="neutral", speed=1.0
    ),
    "serena": SpeakerProfile(
        speaker_id="serena", name="Serena",
        description="温柔知性女声 · 语速舒缓，温暖亲和", emotion="warm", speed=0.88
    ),
    "chelsie": SpeakerProfile(
        speaker_id="chelsie", name="Chelsie",
        description="优雅从容女声 · 沉稳大气，适合正式场景", emotion="warm", speed=0.82
    ),
    "ethel": SpeakerProfile(
        speaker_id="ethel", name="Ethel",
        description="甜美可爱少女 · 活泼轻快，元气满满", emotion="cheerful", speed=1.08
    ),
    "vivian_warm": SpeakerProfile(
        speaker_id="vivian", name="Vivian暖音",
        description="邻家姐姐声 · 明亮中带温暖，亲切自然", emotion="warm", speed=0.92
    ),

    # ===== 中文男声 (5种) =====
    "uncle_fu": SpeakerProfile(
        speaker_id="uncle_fu", name="Uncle Fu",
        description="醇厚成熟男声 · 沉稳可靠，有磁性", emotion="neutral", speed=0.88
    ),
    "dylan": SpeakerProfile(
        speaker_id="dylan", name="Dylan",
        description="阳光活力男声 · 热情洋溢，充满朝气", emotion="cheerful", speed=1.12
    ),
    "eric": SpeakerProfile(
        speaker_id="eric", name="Eric",
        description="沉稳磁性男声 · 低沉厚重，适合讲故事", emotion="calm", speed=0.82
    ),
    "uncle_fu_warm": SpeakerProfile(
        speaker_id="uncle_fu", name="Uncle Fu暖叔",
        description="温柔大叔声 · 成熟中带温和，如沐春风", emotion="warm", speed=0.80
    ),
    "dylan_calm": SpeakerProfile(
        speaker_id="dylan", name="Dylan清朗",
        description="清爽少年音 · 干净清澈，阳光少年感", emotion="calm", speed=0.95
    ),

    # ===== 英文/多语言 (5种) =====
    "ryan": SpeakerProfile(
        speaker_id="ryan", name="Ryan",
        description="英伦绅士男声 · 富有节奏感，适合英文", emotion="neutral", speed=1.0
    ),
    "aiden": SpeakerProfile(
        speaker_id="aiden", name="Aiden",
        description="阳光美式男声 · 开朗自信，美式发音", emotion="cheerful", speed=1.05
    ),
    "jessica": SpeakerProfile(
        speaker_id="jessica", name="Jessica",
        description="优雅英式女声 · 温婉大方，英式发音", emotion="warm", speed=0.9
    ),
    "ono_anna": SpeakerProfile(
        speaker_id="ono_anna", name="Ono Anna",
        description="元气日语女声 · 活泼可爱，日语发音", emotion="cheerful", speed=1.0
    ),
    "sohee": SpeakerProfile(
        speaker_id="sohee", name="Sohee",
        description="温柔韩语女声 · 柔和细腻，韩语发音", emotion="warm", speed=0.95
    )
}

EDGE_TTS_VOICE_MAP = {
    "vivian": "zh-CN-XiaoxiaoNeural",
    "serena": "zh-CN-XiaoyiNeural",
    "chelsie": "zh-CN-XiaohanNeural",
    "ethel": "zh-CN-XiaochenNeural",
    "vivian_warm": "zh-CN-XiaoxiaoNeural",
    "uncle_fu": "zh-CN-YunxiNeural",
    "dylan": "zh-CN-YunyangNeural",
    "eric": "zh-CN-YunjianNeural",
    "uncle_fu_warm": "zh-CN-YunxiNeural",
    "dylan_calm": "zh-CN-YunyangNeural",
    "ryan": "en-US-GuyNeural",
    "aiden": "en-US-ChristopherNeural",
    "jessica": "en-US-JennyNeural",
    "ono_anna": "ja-JP-NanamiNeural",
    "sohee": "ko-KR-SunHiNeural"
}

SPEAKER_ID_ALIAS = {}
for _key, _profile in PRESET_SPEAKERS.items():
    SPEAKER_ID_ALIAS[_profile.speaker_id] = _key
    SPEAKER_ID_ALIAS[_key] = _key


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
        self.current_speaker = "vivian"
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
            
            model_path = self.local_model_path if os.path.exists(self.local_model_path) else self.model_name
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
        speaker_id: str = "vivian",
        speed: float = 1.0,
        emotion: Optional[str] = None,
        emotion_intensity: float = 1.0
    ) -> Optional[TTSResult]:
        if not text or not text.strip():
            logger.warning("合成文本为空")
            return None
        
        if not self.is_loaded:
            if not self.load_model():
                logger.error("TTS模型未加载，无法合成语音")
                return None
        
        if self._use_fallback:
            return self._synthesize_fallback(text, speaker_id, speed)
        
        return self._synthesize_qwen(text, speaker_id, speed, emotion, emotion_intensity)
    
    def _synthesize_qwen(
        self,
        text: str,
        speaker_id: str,
        speed: float,
        emotion: Optional[str],
        emotion_intensity: float = 1.0
    ) -> Optional[TTSResult]:
        try:
            start_time = time.time()
            
            speaker = PRESET_SPEAKERS.get(speaker_id, PRESET_SPEAKERS["vivian"])
            
            instruct = self._build_emotion_instruct(emotion, emotion_intensity)
            
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
            
            # 音频后处理：速度调整 + 音量归一化
            audio_data = self._apply_audio_postprocess(audio_data, sr, speed)
            
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
    
    def _apply_audio_postprocess(self, audio_data, sr: int, speed: float):
        """
        音频后处理算法：
        1. 速度调整 - 通过线性插值重采样
        2. 音量归一化 - 峰值归一化到 -3dB
        """
        import numpy as np
        
        # 1. 速度调整（重采样）
        if abs(speed - 1.0) > 0.01:
            orig_len = len(audio_data)
            new_len = int(orig_len / speed)
            indices = np.linspace(0, orig_len - 1, new_len)
            audio_data = np.interp(indices, np.arange(orig_len), audio_data)
        
        # 2. 音量归一化（峰值归一化到 -3dB）
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            target_peak = 10 ** (-3 / 20)  # -3dB
            scale = target_peak / max_val
            audio_data = audio_data * scale
        
        return audio_data
    
    def _synthesize_fallback(
        self,
        text: str,
        speaker_id: str,
        speed: float
    ) -> Optional[TTSResult]:
        try:
            import edge_tts
            
            start_time = time.time()
            
            voice = EDGE_TTS_VOICE_MAP.get(speaker_id, EDGE_TTS_VOICE_MAP["vivian"])
            
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
            duration_ms = len(mp3_bytes) / 16
            
            synthesis_time = time.time() - start_time
            logger.info(f"edge-tts合成完成（MP3直出），文本长度: {len(text)}, 耗时: {synthesis_time:.3f}s")
            
            return TTSResult(
                audio_bytes=mp3_bytes,
                sample_rate=24000,
                duration_ms=duration_ms,
                speaker_id=speaker_id,
                format="mp3"
            )
            
        except Exception as e:
            logger.error(f"edge-tts合成失败: {e}")
            return None
    
    def synthesize_stream(
        self,
        text: str,
        speaker_id: str = "vivian",
        speed: float = 1.0,
        emotion: Optional[str] = None,
        emotion_intensity: float = 1.0
    ) -> Generator[dict, None, None]:
        import re
        
        sentences = re.split(r'(?<=[。！？；\n])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            sentences = [text]
        
        for i, sentence in enumerate(sentences):
            result = self.synthesize(
                sentence, speaker_id, speed, emotion, emotion_intensity
            )
            if result is None:
                continue
            
            if result.format == "mp3":
                audio_b64 = base64.b64encode(result.audio_bytes).decode('utf-8')
            else:
                wav_bytes = self._wrap_wav_header(
                    result.audio_bytes, result.sample_rate, 1, 16
                )
                audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')
            
            yield {
                "audio": audio_b64,
                "format": result.format if result.format == "mp3" else "wav",
                "sample_rate": result.sample_rate,
                "duration_ms": result.duration_ms,
                "sentence_index": i,
                "sentence_total": len(sentences),
                "text": sentence,
                "is_final": i == len(sentences) - 1
            }
    
    def _build_emotion_instruct(self, emotion: Optional[str], intensity: float = 1.0) -> Optional[str]:
        if not emotion:
            return None
        
        emotion_map = {
            "happy": "开心",
            "sad": "悲伤",
            "angry": "愤怒",
            "neutral": "平静",
            "warm": "温暖",
            "cheerful": "活泼",
            "calm": "冷静",
            "excited": "兴奋",
            "whisper": "轻声细语",
            "serious": "严肃",
            "playful": "俏皮",
            "gentle": "温柔"
        }
        
        emotion_name = emotion_map.get(emotion, emotion)
        intensity = max(0.1, min(2.0, intensity))
        
        if intensity <= 0.5:
            degree = "略微"
        elif intensity <= 0.8:
            degree = "有些"
        elif intensity <= 1.2:
            degree = ""
        elif intensity <= 1.6:
            degree = "非常"
        else:
            degree = "极其"
        
        if degree:
            return f"用{degree}{emotion_name}的语气说"
        return f"用{emotion_name}的语气说"

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
        if speaker_id in PRESET_SPEAKERS:
            self.current_speaker = speaker_id
            logger.info(f"当前音色已设置为: {PRESET_SPEAKERS[speaker_id].name}")
            return True
        logger.warning(f"未知音色ID: {speaker_id}，使用默认音色")
        self.current_speaker = "vivian"
        return False
    
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
    
    def preload(self):
        """异步预加载模型，在服务启动时调用"""
        import threading
        def _load():
            try:
                result = self.load_model()
                if result:
                    logger.info("TTS模型预加载完成")
                else:
                    logger.warning("TTS模型预加载失败，将使用降级方案")
            except Exception as e:
                logger.error(f"TTS模型预加载异常: {e}")
        t = threading.Thread(target=_load, daemon=True, name="tts-preload")
        t.start()
        logger.info("TTS模型预加载已启动（后台线程）")
    
    def unload_model(self):
        """卸载模型，释放内存"""
        if self.model is not None:
            del self.model
            self.model = None
        
        self.is_loaded = False
        
        import gc
        gc.collect()
        
        logger.info("TTS模型已卸载")
    
    # ========== 音色克隆功能 ==========
    
    def clone_voice(
        self,
        ref_audio_path: str,
        ref_text: Optional[str] = None,
        voice_name: str = "克隆音色",
        x_vector_only_mode: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        克隆音色
        
        Args:
            ref_audio_path: 参考音频文件路径（3~10秒）
            ref_text: 参考音频对应的文本（ICL模式需要）
            voice_name: 克隆音色的名称
            x_vector_only_mode: 是否只用声纹嵌入（True=简单模式，False=ICL高质量模式）
        
        Returns:
            包含克隆音色信息的字典，失败返回None
        """
        if not self.is_loaded:
            if not self.load_model():
                logger.error("TTS模型未加载，无法克隆音色")
                return None
        
        if self._use_fallback:
            logger.error("降级模式下不支持音色克隆")
            return None
        
        try:
            import uuid
            import shutil
            
            # 生成唯一ID
            clone_id = f"cloned_{uuid.uuid4().hex[:8]}"
            
            # 保存参考音频到缓存目录
            clone_dir = os.path.join(TTS_CACHE_DIR, "cloned_voices", clone_id)
            os.makedirs(clone_dir, exist_ok=True)
            
            ref_audio_dest = os.path.join(clone_dir, "reference.wav")
            shutil.copy2(ref_audio_path, ref_audio_dest)
            
            # 创建克隆提示
            logger.info(f"正在创建音色克隆提示: {clone_id}")
            start_time = time.time()
            
            if x_vector_only_mode or not ref_text:
                # 简单模式：只用声纹
                prompt = self.model.create_voice_clone_prompt(
                    ref_audio=ref_audio_dest,
                    x_vector_only_mode=True
                )
            else:
                # ICL高质量模式：需要参考文本
                prompt = self.model.create_voice_clone_prompt(
                    ref_audio=ref_audio_dest,
                    ref_text=ref_text,
                    x_vector_only_mode=False
                )
            
            # 保存提示到文件
            prompt_path = os.path.join(clone_dir, "prompt.pkl")
            import pickle
            with open(prompt_path, 'wb') as f:
                pickle.dump(prompt, f)
            
            # 保存元数据
            metadata = {
                "clone_id": clone_id,
                "voice_name": voice_name,
                "ref_text": ref_text,
                "x_vector_only_mode": x_vector_only_mode,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ref_audio_path": ref_audio_dest,
                "prompt_path": prompt_path
            }
            metadata_path = os.path.join(clone_dir, "metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            clone_time = time.time() - start_time
            logger.info(f"音色克隆完成: {clone_id}, 耗时: {clone_time:.2f}s")
            
            return {
                "clone_id": clone_id,
                "voice_name": voice_name,
                "description": f"克隆音色: {voice_name}",
                "ref_text": ref_text,
                "x_vector_only_mode": x_vector_only_mode,
                "created_at": metadata["created_at"]
            }
            
        except Exception as e:
            logger.error(f"音色克隆失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def synthesize_cloned(
        self,
        text: str,
        clone_id: str,
        speed: float = 1.0
    ) -> Optional[TTSResult]:
        """
        使用克隆的音色合成语音
        
        Args:
            text: 要合成的文本
            clone_id: 克隆音色的ID
            speed: 语速
        
        Returns:
            合成结果
        """
        if not self.is_loaded:
            if not self.load_model():
                logger.error("TTS模型未加载")
                return None
        
        try:
            # 加载克隆提示
            clone_dir = os.path.join(TTS_CACHE_DIR, "cloned_voices", clone_id)
            prompt_path = os.path.join(clone_dir, "prompt.pkl")
            
            if not os.path.exists(prompt_path):
                logger.error(f"克隆音色不存在: {clone_id}")
                return None
            
            import pickle
            with open(prompt_path, 'rb') as f:
                prompt = pickle.load(f)
            
            # 使用克隆音色合成
            start_time = time.time()
            wavs, sr = self.model.generate_voice_clone(
                text=text,
                voice_clone_prompt=prompt,
                language="Chinese"
            )
            
            if wavs is None or len(wavs) == 0:
                logger.error("克隆音色合成失败")
                return None
            
            import numpy as np
            audio_data = np.array(wavs[0])
            
            # 应用后处理
            audio_data = self._apply_audio_postprocess(audio_data, sr, speed)
            
            audio_bytes = self._numpy_to_bytes(audio_data)
            duration_ms = len(audio_data) / sr * 1000
            
            synthesis_time = time.time() - start_time
            logger.info(f"克隆音色合成完成: {clone_id}, 耗时: {synthesis_time:.3f}s")
            
            return TTSResult(
                audio_bytes=audio_bytes,
                sample_rate=sr,
                duration_ms=duration_ms,
                speaker_id=clone_id
            )
            
        except Exception as e:
            logger.error(f"克隆音色合成失败: {e}")
            return None
    
    def get_cloned_voices(self) -> List[Dict[str, Any]]:
        """获取所有克隆的音色列表"""
        cloned_voices = []
        cloned_dir = os.path.join(TTS_CACHE_DIR, "cloned_voices")
        
        if not os.path.exists(cloned_dir):
            return cloned_voices
        
        for clone_id in os.listdir(cloned_dir):
            metadata_path = os.path.join(cloned_dir, clone_id, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    cloned_voices.append({
                        "clone_id": metadata.get("clone_id"),
                        "voice_name": metadata.get("voice_name"),
                        "description": f"克隆音色: {metadata.get('voice_name')}",
                        "created_at": metadata.get("created_at")
                    })
                except Exception as e:
                    logger.warning(f"读取克隆音色元数据失败: {clone_id}, {e}")
        
        return cloned_voices
    
    def delete_cloned_voice(self, clone_id: str) -> bool:
        """删除克隆的音色"""
        try:
            clone_dir = os.path.join(TTS_CACHE_DIR, "cloned_voices", clone_id)
            if os.path.exists(clone_dir):
                import shutil
                shutil.rmtree(clone_dir)
                logger.info(f"已删除克隆音色: {clone_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除克隆音色失败: {e}")
            return False


_tts_service = None


def get_tts_service() -> Qwen3TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = Qwen3TTSService()
        _tts_service.preload()
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
