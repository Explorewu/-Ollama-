"""
ASR 服务工厂
用于创建不同类型的 ASR 服务实例
"""
import logging
from typing import Dict, Optional, Type, List, Any
from .base import ASRService, ASREngineType, EngineInfo, TranscriptionResult

# 尝试导入具体服务类
try:
    from qwen3_asr_service import get_asr_service as get_qwen_service
    from local_whisper_service import get_local_whisper_service
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from qwen3_asr_service import get_asr_service as get_qwen_service
    from local_whisper_service import get_local_whisper_service

logger = logging.getLogger(__name__)

# ==================== 适配器类 ====================

class QwenASRAdapter(ASRService):
    """Qwen3 ASR 服务适配器"""
    
    def __init__(self):
        super().__init__()
        self._service = get_qwen_service()
        
    def initialize(self) -> bool:
        return True  # 懒加载，始终视为初始化成功
        
    def get_engine_info(self) -> EngineInfo:
        status = self._service.check_status()
        return EngineInfo(
            name="Qwen3-ASR",
            engine_type=ASREngineType.QWEN3_ASR,
            is_available=not status.get("is_disabled", False),
            description="基于 Qwen3-ASR-Flash 的高性能语音识别",
            version="3.0"
        )
        
    def transcribe(self, audio_path: str, language: str = 'zh', progress_callback=None) -> Optional[TranscriptionResult]:
        result = self._service.transcribe(audio_path, language)
        if result:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                confidence=result.confidence,
                duration=result.duration,
                model=result.model,
                engine=ASREngineType.QWEN3_ASR,
                timestamp=result.timestamp
            )
        return None
        
    def transcribe_with_preprocessing(self, audio_path: str, language: str = 'zh', remove_silence: bool = True, progress_callback=None) -> Optional[TranscriptionResult]:
        result = self._service.transcribe(audio_path, language)
        if result:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                confidence=result.confidence,
                duration=result.duration,
                model=result.model,
                engine=ASREngineType.QWEN3_ASR,
                timestamp=result.timestamp
            )
        return None

    def check_status(self) -> Dict[str, Any]:
        """透传原始服务的状态检查"""
        return self._service.check_status()


class LocalWhisperAdapter(ASRService):
    """本地 Whisper 服务适配器"""
    
    def __init__(self):
        super().__init__()
        self._service = get_local_whisper_service()
        
    def initialize(self) -> bool:
        return True  # 懒加载，实际加载由 load_model 控制
        
    def load_model(self) -> bool:
        """显式加载模型"""
        return self._service.load_model()
        
    def check_status(self) -> Dict[str, Any]:
        """透传原始服务的状态检查"""
        return self._service.check_status()
        
    def get_engine_info(self) -> EngineInfo:
        status = self._service.check_status()
        return EngineInfo(
            name="Local Whisper",
            engine_type=ASREngineType.WHISPER_LOCAL,
            is_available=status.get("is_loaded", False),
            description="基于 OpenAI Whisper 的本地语音识别",
            version="base"
        )
        
    def transcribe(self, audio_path: str, language: str = 'zh', progress_callback=None) -> Optional[TranscriptionResult]:
        result = self._service.transcribe(audio_path, language)
        if result:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                confidence=result.confidence,
                duration=result.duration,
                model=result.model,
                engine=ASREngineType.WHISPER_LOCAL,
                timestamp=result.timestamp
            )
        return None

    def transcribe_with_preprocessing(self, audio_path: str, language: str = 'zh', remove_silence: bool = True, progress_callback=None) -> Optional[TranscriptionResult]:
        result = self._service.transcribe_with_preprocessing(audio_path, language, preprocess=remove_silence)
        if result:
            return TranscriptionResult(
                text=result.text,
                language=result.language,
                confidence=result.confidence,
                duration=result.duration,
                model=result.model,
                engine=ASREngineType.WHISPER_LOCAL,
                timestamp=result.timestamp
            )
        return None


_engines: Dict[ASREngineType, Type[ASRService]] = {
    ASREngineType.QWEN3_ASR: QwenASRAdapter,
    ASREngineType.WHISPER_LOCAL: LocalWhisperAdapter
}
_available_engines: List[EngineInfo] = []


def register_engine(engine_type: ASREngineType, engine_class: Type[ASRService]) -> None:
    """
    注册 ASR 引擎
    
    Args:
        engine_type: 引擎类型
        engine_class: 引擎类
    """
    _engines[engine_type] = engine_class
    logger.info(f"已注册 ASR 引擎: {engine_type.value}")


def get_available_engines() -> List[EngineInfo]:
    """
    获取可用的引擎列表
    
    Returns:
        引擎信息列表
    """
    if not _available_engines:
        for engine_type, engine_class in _engines.items():
            try:
                info = engine_class.get_engine_info() if hasattr(engine_class, 'get_engine_info') else None
                if info is None:
                    info = EngineInfo(
                        name=engine_type.value,
                        engine_type=engine_type,
                        is_available=True,
                        description=f"{engine_type.value} ASR Engine"
                    )
                _available_engines.append(info)
            except Exception as e:
                logger.warning(f"获取引擎 {engine_type.value} 信息失败: {e}")
    
    return _available_engines


def create_asr_service(
    engine_type: ASREngineType = ASREngineType.WHISPER_OLLAMA,
    **kwargs
) -> Optional[ASRService]:
    """
    创建 ASR 服务实例
    
    Args:
        engine_type: 引擎类型
        **kwargs: 引擎特定的参数
        
    Returns:
        ASR 服务实例，失败返回 None
    """
    if engine_type not in _engines:
        logger.error(f"未知的 ASR 引擎类型: {engine_type.value}")
        return None
    
    try:
        engine_class = _engines[engine_type]
        service = engine_class(**kwargs)
        
        if not service.initialize():
            logger.error(f"初始化 {engine_type.value} 引擎失败")
            return None
        
        logger.info(f"成功创建 {engine_type.value} ASR 服务")
        return service
        
    except Exception as e:
        logger.error(f"创建 {engine_type.value} 引擎失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_best_available_service(**kwargs) -> Optional[ASRService]:
    """
    创建最佳可用的 ASR 服务
    
    Args:
        **kwargs: 引擎特定的参数
        
    Returns:
        ASR 服务实例
    """
    priority_order = [
        ASREngineType.QWEN3_ASR,
        ASREngineType.WHISPER_LOCAL,
        ASREngineType.WHISPER_OLLAMA,
    ]
    
    for engine_type in priority_order:
        service = create_asr_service(engine_type, **kwargs)
        if service:
            return service
    
    logger.error("没有可用的 ASR 引擎")
    return None
