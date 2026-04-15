"""
模型路径配置文件

统一管理模型和缓存目录，默认使用项目目录下的 models。
可通过环境变量覆盖：
- OLLAMA_MODELS: 直接指定 models 目录（优先级最高）
- OLLAMA_HUB_BASE_DIR: 指定基础目录（当 OLLAMA_MODELS 未设置时生效）
"""

import os
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent

# 检查 .ollama 目录是否存在（优先使用）
OLLAMA_MODELS_DIR = PROJECT_DIR / ".ollama" / "models"
if OLLAMA_MODELS_DIR.exists():
    BASE_DIR = OLLAMA_MODELS_DIR
else:
    BASE_DIR = Path(
        os.environ.get("OLLAMA_HUB_BASE_DIR", str(PROJECT_DIR))
    ).expanduser().resolve()

_models_override = os.environ.get("OLLAMA_MODELS", "").strip()
if _models_override:
    MODELS_DIR = str(Path(_models_override).expanduser().resolve())
elif OLLAMA_MODELS_DIR.exists():
    MODELS_DIR = str(OLLAMA_MODELS_DIR)
else:
    MODELS_DIR = str((PROJECT_DIR / "models").resolve())

# 用户 HuggingFace 缓存目录（已下载的模型）
USER_HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"

# 各类模型缓存目录 - 优先使用用户缓存中已下载的模型
HUGGINGFACE_CACHE_DIR = str(USER_HF_CACHE) if USER_HF_CACHE.exists() else os.path.join(MODELS_DIR, "huggingface", "hub")
MODELSCOPE_CACHE_DIR = os.path.join(MODELS_DIR, "modelscope", "hub")

# Whisper 模型目录 - 检查多个可能的位置，优先找有 base.pt 的
WHISPER_SEARCH_PATHS = [
    PROJECT_DIR / "models" / "whisper",
    PROJECT_DIR / ".ollama" / "models" / "whisper",
    Path.home() / ".cache" / "whisper",
]
for p in WHISPER_SEARCH_PATHS:
    if p.exists() and (p / "base.pt").exists():
        WHISPER_CACHE_DIR = str(p)
        break
else:
    WHISPER_CACHE_DIR = next((str(p) for p in WHISPER_SEARCH_PATHS if p.exists()), str(WHISPER_SEARCH_PATHS[0]))

# ASR 模型目录 - 使用 HuggingFace 缓存
ASR_CACHE_DIR = HUGGINGFACE_CACHE_DIR

# 语言模型目录
LLM_MODELS_DIR = os.path.join(MODELS_DIR, "llm")

# 图片模型目录（统一存放在 models/image）
IMAGE_MODELS_DIR = os.path.join(MODELS_DIR, "image")

# 保留旧的 server/models 路径（向后兼容，如果新路径不存在时使用）
OLD_IMAGE_MODELS_DIR = os.path.join(SERVER_DIR, "models")

# 额外的图片模型目录（按优先级搜索）
IMAGE_MODEL_EXTRA_DIRS = [
    IMAGE_MODELS_DIR,
    os.path.join(PROJECT_DIR, "models", "image_gen", "images"),
    os.path.join(PROJECT_DIR, "models", "ollama", "images"),
]


def get_available_image_models():
    """获取所有可用的图片模型目录"""
    models = {}
    search_dirs = [IMAGE_MODELS_DIR] + IMAGE_MODEL_EXTRA_DIRS
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for item in os.listdir(search_dir):
            model_path = os.path.join(search_dir, item)
            if os.path.isdir(model_path):
                # 检查是否是有效的模型目录（包含配置文件）
                if any(os.path.exists(os.path.join(model_path, f)) for f in ['model_index.json', 'config.json', '.safetensors']):
                    models[item] = model_path
    
    return models


def ensure_directories():
    """确保模型目录存在"""
    directories = [
        MODELS_DIR,
        HUGGINGFACE_CACHE_DIR,
        MODELSCOPE_CACHE_DIR,
        WHISPER_CACHE_DIR,
        ASR_CACHE_DIR,
        IMAGE_MODELS_DIR,
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def set_model_environment():
    """设置模型相关环境变量"""
    os.environ["HF_HOME"] = HUGGINGFACE_CACHE_DIR
    os.environ["HUGGINGFACE_HUB_CACHE"] = HUGGINGFACE_CACHE_DIR
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    os.environ["MODELSCOPE_CACHE"] = MODELSCOPE_CACHE_DIR
    os.environ["WHISPER_CACHE_DIR"] = WHISPER_CACHE_DIR

    os.environ["TRANSFORMERS_CACHE"] = HUGGINGFACE_CACHE_DIR
    os.environ["HF_DATASETS_CACHE"] = os.path.join(MODELS_DIR, "datasets")


ensure_directories()
set_model_environment()

if os.environ.get("MODEL_PATHS_VERBOSE", "0") == "1":
    print(f"✓ 模型路径配置完成")
    print(f"  基础目录: {BASE_DIR}")
    print(f"  Models: {MODELS_DIR}")
    print(f"  Hugging Face: {HUGGINGFACE_CACHE_DIR}")
    print(f"  ModelScope: {MODELSCOPE_CACHE_DIR}")
    print(f"  Whisper: {WHISPER_CACHE_DIR}")
    print(f"  ASR: {ASR_CACHE_DIR}")
    print(f"  图片模型: {IMAGE_MODELS_DIR}")
