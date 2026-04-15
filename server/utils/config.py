"""
Application configuration.
"""

import os
from pathlib import Path
from typing import Dict, Any

SERVER_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVER_DIR.parent

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

PORT_WEB = 8080
PORT_API = 5001
PORT_SUMMARY = 5002
PORT_VISION = 5003
PORT_NATIVE_IMAGE = 5004
PORT_OLLAMA = 11434

DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_CHAT_MODEL", "qwen3.5:0.8b")
DEFAULT_OPENAI_COMPAT_MODEL = os.environ.get("DEFAULT_OPENAI_COMPAT_MODEL", DEFAULT_CHAT_MODEL)
DEFAULT_GROUP_CHAT_MODEL = os.environ.get("DEFAULT_GROUP_CHAT_MODEL", "qwen3.5:0.8b")

IMAGE_MODEL_PATH = os.path.join(PROJECT_DIR, "models", "image")
IMAGE_OUTPUT_PATH = os.path.join(SERVER_DIR, "outputs")
MAX_IMAGE_SIZE = 512

LLAMA_CPP_IMAGE_SERVER_URL = os.environ.get("LLAMA_CPP_IMAGE_SERVER_URL", "http://localhost:5003")
NATIVE_LLAMA_CPP_IMAGE_SERVER_URL = os.environ.get("NATIVE_LLAMA_CPP_IMAGE_SERVER_URL", "http://localhost:5004")
VISION_SERVICE_URL = os.environ.get("VISION_SERVICE_URL", "http://localhost:5003")

CONVERSATION_MODE_CONFIG = {
    "standard": {
        "name": "standard",
        "system_prompt": "You are a helpful assistant. Answer clearly and directly.",
        "temperature": 0.6,
        "repeat_penalty": 1.05,
        "description": "Balanced default mode",
    },
    "adult": {
        "name": "adult",
        "system_prompt": "You are a mature, direct assistant. Stay lawful and safe.",
        "temperature": 0.65,
        "repeat_penalty": 1.05,
        "description": "Relaxed tone without explicit unsafe content",
    },
}

SAMPLING_PRESETS = {
    "fast": {
        "temperature": 0.5,
        "top_k": 20,
        "top_p": 0.85,
        "repeat_penalty": 1.05,
        "num_predict": 256,
        "num_ctx": 1536,
    },
    "balanced": {
        "temperature": 0.6,
        "top_k": 30,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_predict": 512,
        "num_ctx": 2048,
    },
    "creative": {
        "temperature": 0.8,
        "top_k": 50,
        "top_p": 0.95,
        "repeat_penalty": 1.05,
        "num_predict": 768,
        "num_ctx": 3072,
    },
    "code": {
        "temperature": 0.35,
        "top_k": 25,
        "top_p": 0.85,
        "repeat_penalty": 1.12,
        "num_predict": 640,
        "num_ctx": 3072,
    },
}

REPETITION_DETECTION_CONFIG = {
    "enabled": True,
    "window_size": 10,
    "min_repeat_count": 3,
    "max_repeat_count": 5,
    "token_threshold": 5,
    "phrase_threshold": 3,
    "base_penalty": 1.08,
    "max_penalty": 1.5,
    "penalty_increment": 0.1,
    "truncate_on_max": True,
}

DEFAULT_CHAT_RUNTIME_CONFIG = {
    "thinking": False,
    "show_reasoning_summary": False,
    "reasoning_summary_level": "off",
    "response_depth": "brief",
    "persona_strength": 40,
    "system_prompt_mode": "template",
    "system_prompt_template": "assistant_brief",
    "system_prompt_custom": "",
    "safety_mode": "balanced",
    "adult_tone_mode": False,
    "adult_tone_acknowledged": False,
    "max_response_tokens": 384,
    "temperature": 0.55,
    "repeat_penalty": 1.08,
    "top_k": 40,
    "top_p": 0.9,
    "num_ctx": 2048,
    "num_threads": 8,
    "keep_alive": "10m",
    "sampling_preset": "fast",
}

DEFAULT_GROUP_CHAT_RUNTIME_CONFIG = {
    "max_turns": 4,
    "history_messages": 4,
    "num_predict": 192,
    "num_ctx": 1536,
    "num_threads": 8,
    "temperature": 0.55,
    "repeat_penalty": 1.08,
    "top_k": 20,
    "top_p": 0.85,
    "keep_alive": "10m",
    "stream_chunk_chars": 80,
}

SYSTEM_PROMPT_TEMPLATES = {
    "assistant_balanced": "You are a professional Chinese assistant. Be concise, accurate, and actionable. 回复时要自然流畅，像和朋友聊天一样。长短句交替使用，偶尔用个比喻或举个例子，让表达更生动。段落之间衔接自然，不要用生硬的标记或固定开头。",
    "assistant_brief": "You are a fast assistant. Give the answer first and keep it short. 回复时要自然流畅，像和朋友聊天一样。长短句交替使用，偶尔用个比喻或举个例子，让表达更生动。段落之间衔接自然，不要用生硬的标记或固定开头。",
    "assistant_deep": "You are a detailed assistant. Explain steps, tradeoffs, and risks only when helpful. 回复时要自然流畅，像和朋友聊天一样。长短句交替使用，偶尔用个比喻或举个例子，让表达更生动。段落之间衔接自然，不要用生硬的标记或固定开头。",
    "roleplay_immersive": "Stay in character while remaining safe and coherent. 回复时要自然流畅，像和朋友聊天一样。长短句交替使用，偶尔用个比喻或举个例子，让表达更生动。段落之间衔接自然，不要用生硬的标记或固定开头。",
}

SAFETY_POLICY_BLOCKS = {
    "strict": "Decline unsafe or high-risk requests and offer safe alternatives.",
    "balanced": "Decline high-risk requests and provide safe, reduced-risk help when possible.",
    "relaxed": "Provide maximum lawful help while still refusing clearly unsafe requests.",
}

IMAGE_MODEL_CONFIG = {
    "ssd-1b": {
        "id": "ssd-1b",
        "name": "SSD-1B",
        "style": "photo",
        "size": "~14GB",
        "pipeline": "StableDiffusionXLPipeline",
        "local_path": os.path.join(IMAGE_MODEL_PATH, "ssd-1b"),
        "default_prompt": "masterpiece, best quality, highly detailed, realistic photo",
        "default_negative": "lowres, bad anatomy, blurry, worst quality",
    },
    "kook-qwen-2512": {
        "id": "kook-qwen-2512",
        "name": "Kook-Qwen-2512",
        "style": "anime",
        "size": "~225MB",
        "pipeline": "StableDiffusionPipeline",
        "local_path": os.path.join(IMAGE_MODEL_PATH, "kook-qwen-2512"),
        "default_prompt": "masterpiece, best quality, anime illustration",
        "default_negative": "lowres, bad anatomy, blurry, worst quality",
    },
    "stable-diffusion-v1-5": {
        "id": "stable-diffusion-v1-5",
        "name": "Stable Diffusion v1.5",
        "style": "classic",
        "size": "~5GB",
        "pipeline": "StableDiffusionPipeline",
        "local_path": os.path.join(IMAGE_MODEL_PATH, "stable-diffusion-v1-5"),
        "default_prompt": "masterpiece, best quality, realistic photo",
        "default_negative": "lowres, bad anatomy, blurry, worst quality, nsfw",
    },
    "z-image-turbo-art": {
        "id": "z-image-turbo-art",
        "name": "Z-Image-Turbo-Art",
        "style": "art",
        "size": "~6GB",
        "pipeline": "StableDiffusionXLPipeline",
        "local_path": os.path.join(IMAGE_MODEL_PATH, "z-image-turbo-art"),
        "default_prompt": "masterpiece, best quality, artistic, vivid colors",
        "default_negative": "lowres, bad anatomy, blurry, worst quality",
    },
}


GGUF_MODEL_CONFIG = {
    "qwen3.5-9b-uncensored": {
        "id": "qwen3.5-9b-uncensored",
        "name": "Qwen3.5-9B-Uncensored",
        "path": r"D:\Etertainment\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "format": "gguf",
        "quantization": "Q4_K_M",
        "n_ctx": 4096,
        "n_threads": 8,
        "description": "Qwen3.5 9B 无审查版本，适合自由对话",
    },
    "qwen3.5-uncensored": {
        "id": "qwen3.5-uncensored",
        "name": "Qwen3.5-Uncensored (Alias)",
        "path": r"D:\Etertainment\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "format": "gguf",
        "quantization": "Q4_K_M",
        "n_ctx": 4096,
        "n_threads": 8,
        "description": "Qwen3.5 无审查版本别名",
    },
}


def get_gguf_model_config(model_name: str) -> Dict[str, Any]:
    """获取 GGUF 模型配置"""
    lowered = model_name.lower()
    if lowered in GGUF_MODEL_CONFIG:
        return GGUF_MODEL_CONFIG[lowered]
    for key, config in GGUF_MODEL_CONFIG.items():
        if key in lowered or lowered in key:
            return config
    return {}


def build_ollama_options(runtime_cfg: Dict[str, Any], preset_name: str = None) -> Dict[str, Any]:
    preset = SAMPLING_PRESETS.get(preset_name or runtime_cfg.get("sampling_preset") or "fast", {})
    options = {
        "temperature": runtime_cfg.get("temperature", preset.get("temperature", 0.55)),
        "repeat_penalty": runtime_cfg.get("repeat_penalty", preset.get("repeat_penalty", 1.08)),
        "top_k": runtime_cfg.get("top_k", preset.get("top_k", 20)),
        "top_p": runtime_cfg.get("top_p", preset.get("top_p", 0.85)),
        "num_predict": runtime_cfg.get("max_response_tokens", runtime_cfg.get("num_predict", preset.get("num_predict", 256))),
        "num_ctx": runtime_cfg.get("num_ctx", preset.get("num_ctx", 2048)),
    }
    return {key: value for key, value in options.items() if value is not None}
