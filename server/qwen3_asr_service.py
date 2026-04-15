"""Qwen3-ASR 语音识别服务模块

基于阿里达摩院 Qwen3-ASR 模型
特点：识别准确率高、抗噪能力强、体积小、推理速度快
支持 30 种语言和 22 种中文方言

使用 qwen-asr 官方包进行推理
模型缓存位置：<project>/models/audio/asr (新) 或 <project>/.ollama/models/asr (旧，兼容)

优化特性：
- 懒加载模式：首次使用时才加载模型
- 状态缓存：记录模型加载状态，失败后跳过
- 超时控制：防止模型加载无限等待
- 路径兼容：支持新的统一目录结构和旧路径

使用方法:
    service = Qwen3ASRService()
    result = service.transcribe("audio.wav", language="zh")
    print(result.text)
"""

import os
import time
import json
import logging
import tempfile
import subprocess
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_STATUS_FILE = PROJECT_DIR / ".ollama" / "models" / "asr" / "model_status.json"


def load_model_status() -> Dict[str, Any]:
    if MODEL_STATUS_FILE.exists():
        try:
            with open(MODEL_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载模型状态缓存失败: {e}")
    return {}


def save_model_status(status: Dict[str, Any]):
    try:
        MODEL_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存模型状态缓存失败: {e}")


def is_model_disabled(model_name: str) -> bool:
    status = load_model_status()
    return status.get(model_name, {}).get("disabled", False)


def mark_model_disabled(model_name: str, reason: str = ""):
    status = load_model_status()
    status[model_name] = {
        "disabled": True,
        "disabled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason
    }
    save_model_status(status)
    logger.info(f"模型 {model_name} 已标记为禁用，后续启动将跳过加载")


def mark_model_loaded(model_name: str):
    status = load_model_status()
    status[model_name] = {
        "disabled": False,
        "loaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_model_status(status)


@dataclass
class ASRResult:
    text: str
    language: str
    confidence: float
    duration: float
    model: str
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


LANGUAGE_MAP = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "yue": "Cantonese",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "id": "Indonesian",
    "it": "Italian",
    "ru": "Russian",
    "th": "Thai",
    "vi": "Vietnamese",
    "tr": "Turkish",
    "hi": "Hindi",
    "ms": "Malay",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "fil": "Filipino",
    "fa": "Persian",
    "el": "Greek",
    "hu": "Hungarian",
    "mk": "Macedonian",
    "ro": "Romanian",
}


class Qwen3ASRService:
    """
    Qwen3-ASR 语音识别服务

    使用 qwen-asr 官方包进行推理
    支持 30 种语言和 22 种中文方言
    """

    LOAD_TIMEOUT = 120

    def __init__(self, model_name: str = "Qwen/Qwen3-ASR-0.6B"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        self.device = "cpu"
        self.load_error = None
        
        if is_model_disabled(model_name):
            logger.info(f"模型 {model_name} 已标记为禁用，跳过自动加载")
            self.load_error = "模型已被禁用（上次加载失败）"
        else:
            logger.info(f"Qwen3-ASR 服务已初始化（懒加载模式）")
            logger.info(f"模型将在首次转写时自动加载")

    def _find_local_model_path(self) -> Optional[str]:
        """查找本地模型路径（支持新的统一目录结构和旧路径）"""
        possible_paths = [
            # 新的统一目录结构（优先）
            PROJECT_DIR / "models" / "audio" / "asr" / "qwen3-asr" / "qwen" / "Qwen3-ASR-0___6B",
            PROJECT_DIR / "models" / "audio" / "asr" / "qwen3-asr" / "qwen" / "Qwen3-ASR-0.6B",
            PROJECT_DIR / "models" / "audio" / "asr" / "Qwen3-ASR-0.6B",
            # 旧路径（兼容）
            PROJECT_DIR / ".ollama" / "models" / "asr" / "qwen3-asr" / "qwen" / "Qwen3-ASR-0___6B",
            PROJECT_DIR / ".ollama" / "models" / "asr" / "qwen3-asr" / "qwen" / "Qwen3-ASR-0.6B",
            PROJECT_DIR / ".ollama" / "models" / "asr" / "Qwen3-ASR-0.6B",
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "config.json").exists():
                return str(path)
        
        return None

    def _do_load_model(self) -> bool:
        try:
            logger.info(f"正在加载 Qwen3-ASR 模型: {self.model_name}")

            import torch
            from qwen_asr import Qwen3ASRModel

            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            logger.info(f"使用设备: {self.device}")

            local_model_path = self._find_local_model_path()
            
            if local_model_path:
                logger.info(f"从本地路径加载模型: {local_model_path}")
                model_source = local_model_path
            else:
                logger.info("从远程下载模型...")
                model_source = self.model_name

            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            
            self.model = Qwen3ASRModel.from_pretrained(
                model_source,
                dtype=dtype,
                device_map=self.device,
                local_files_only=(local_model_path is not None),
                max_inference_batch_size=8,
                max_new_tokens=512,
            )

            self.is_loaded = True
            self.load_error = None
            mark_model_loaded(self.model_name)
            logger.info("✅ Qwen3-ASR 模型加载成功")
            return True

        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}")
            self.is_loaded = False
            self.load_error = str(e)
            mark_model_disabled(self.model_name, str(e))
            return False

    def _load_model_with_timeout(self) -> bool:
        import threading
        import queue
        
        result_queue = queue.Queue()
        load_error = [None]
        
        def load_task():
            try:
                result = self._do_load_model()
                result_queue.put(result)
            except Exception as e:
                load_error[0] = str(e)
                result_queue.put(False)
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
        thread.join(timeout=self.LOAD_TIMEOUT)
        
        if thread.is_alive():
            logger.error(f"模型加载超时（>{self.LOAD_TIMEOUT}秒）")
            self.load_error = f"加载超时（>{self.LOAD_TIMEOUT}秒）"
            return False
        
        if load_error[0]:
            self.load_error = load_error[0]
            return False
            
        return result_queue.get() if not result_queue.empty() else False

    def ensure_loaded(self) -> bool:
        if self.is_loaded:
            return True
        
        if self.load_error:
            logger.warning(f"模型已标记为禁用: {self.load_error}")
            return False
        
        logger.info("首次使用，正在加载模型...")
        return self._load_model_with_timeout()

    def transcribe(self, audio_path: str, language: str = "zh") -> Optional[ASRResult]:
        if not self.ensure_loaded():
            logger.error(f"模型加载失败: {self.load_error}")
            return None

        tmp_file = None
        try:
            # 检查是否是BytesIO对象
            import io
            if isinstance(audio_path, io.BytesIO):
                # BytesIO对象需要先保存为临时文件
                import tempfile
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                tmp_file.write(audio_path.read())
                tmp_file.close()
                audio_path = tmp_file.name

            is_url = audio_path.startswith(('http://', 'https://'))
            if not is_url and not os.path.exists(audio_path):
                logger.error(f"音频文件不存在: {audio_path}")
                return None

            duration = self._get_audio_duration(audio_path) if not is_url else 0.0
            logger.info(f"开始转写音频{'(URL)' if is_url else f'，时长: {duration:.2f}秒'}")

            lang_name = LANGUAGE_MAP.get(language, language)

            results = self.model.transcribe(
                audio=audio_path,
                language=lang_name,
            )

            if not results:
                logger.error("转写失败: 无结果")
                return None

            result = results[0]
            text = result.text.strip()
            detected_lang = result.language if hasattr(result, 'language') else language

            confidence = min(0.95, 0.7 + min(len(text), 500) / 1000)

            logger.info(f"✅ 转写完成，文本长度: {len(text)} 字符")

            return ASRResult(
                text=text,
                language=detected_lang,
                confidence=confidence,
                duration=duration,
                model=self.model_name
            )

        except Exception as e:
            logger.error(f"❌ 转写失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # 清理临时文件
            if tmp_file and os.path.exists(tmp_file.name):
                try:
                    os.unlink(tmp_file.name)
                except:
                    pass

    def transcribe_with_preprocessing(self, audio_path: str, language: str = "zh") -> Optional[ASRResult]:
        if not self.ensure_loaded():
            return None

        try:
            temp_wav = tempfile.mktemp(suffix=".wav")
            subprocess.run([
                'ffmpeg', '-y', '-i', audio_path,
                '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                temp_wav
            ], capture_output=True, check=True)

            result = self.transcribe(temp_wav, language)
            
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            
            return result

        except Exception as e:
            logger.error(f"预处理转写失败: {e}")
            if 'temp_wav' in dir() and os.path.exists(temp_wav):
                os.remove(temp_wav)
            return None

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
                capture_output=True, text=True, timeout=10
            )
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0
        except Exception:
            return 0.0

    def check_status(self) -> Dict[str, Any]:
        return {
            "is_loaded": self.is_loaded,
            "is_disabled": is_model_disabled(self.model_name),
            "model_name": self.model_name,
            "device": self.device,
            "load_error": self.load_error,
            "supported_languages": list(LANGUAGE_MAP.keys())
        }
    
    def reset_status(self):
        status = load_model_status()
        if self.model_name in status:
            del status[self.model_name]
            save_model_status(status)
        self.load_error = None
        self.is_loaded = False
        self.model = None
        logger.info(f"已重置模型 {self.model_name} 的状态")


_asr_service_instance = None


def get_asr_service() -> Qwen3ASRService:
    global _asr_service_instance
    if _asr_service_instance is None:
        _asr_service_instance = Qwen3ASRService()
    return _asr_service_instance


def reset_asr_service():
    global _asr_service_instance
    _asr_service_instance = None
