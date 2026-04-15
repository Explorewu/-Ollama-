# -*- coding: utf-8 -*-
"""
列出当前系统中所有已安装的模型
"""
import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
OLLAMA_MODELS_DIR = BASE_DIR / ".ollama" / "models"

print("=" * 80)
print("当前系统中的所有模型")
print("=" * 80)

def scan_model_directory(directory, model_type):
    """扫描模型目录"""
    if not os.path.exists(directory):
        return []
    
    models = []
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            # 检查是否是有效的模型目录
            config_files = ['config.json', 'model_index.json', 'configuration.json', 'model.safetensors.index.json']
            has_config = any(os.path.exists(os.path.join(item_path, f)) for f in config_files)
            
            # 计算目录大小
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(item_path):
                for f in files:
                    if not f.startswith('.'):
                        fp = os.path.join(root, f)
                        total_size += os.path.getsize(fp)
                        file_count += 1
            
            models.append({
                'name': item,
                'path': item_path,
                'type': model_type,
                'size_mb': total_size / (1024 * 1024),
                'files': file_count,
                'has_config': has_config
            })
        elif item.endswith('.gguf'):
            # GGUF 格式模型
            size_mb = os.path.getsize(item_path) / (1024 * 1024)
            models.append({
                'name': item,
                'path': item_path,
                'type': model_type,
                'size_mb': size_mb,
                'files': 1,
                'has_config': True
            })
    
    return models

# 扫描各类模型
all_models = []

# 1. 语言模型 (LLM)
print("\n📦 语言模型 (LLM)")
print("-" * 80)
llm_models = scan_model_directory(MODELS_DIR / "llm", "LLM")
for model in llm_models:
    print(f"  ✓ {model['name']}")
    print(f"    路径：{model['path']}")
    print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
    all_models.append(model)

# 2. 图像生成模型
print("\n🎨 图像生成模型")
print("-" * 80)
image_models = scan_model_directory(MODELS_DIR / "image", "Image")
for model in image_models:
    print(f"  ✓ {model['name']}")
    print(f"    路径：{model['path']}")
    print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
    all_models.append(model)

# 3. 语音识别模型 (ASR)
print("\n🎤 语音识别模型 (ASR)")
print("-" * 80)
asr_models = scan_model_directory(MODELS_DIR / "asr", "ASR")
for model in asr_models:
    print(f"  ✓ {model['name']}")
    print(f"    路径：{model['path']}")
    print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
    all_models.append(model)

# 4. 语音合成模型 (TTS)
print("\n🔊 语音合成模型 (TTS)")
print("-" * 80)
tts_models = scan_model_directory(MODELS_DIR / "tts", "TTS")
for model in tts_models:
    print(f"  ✓ {model['name']}")
    print(f"    路径：{model['path']}")
    print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
    all_models.append(model)

# 5. Ollama 模型
print("\n🤖 Ollama 模型")
print("-" * 80)
ollama_models = scan_model_directory(OLLAMA_MODELS_DIR, "Ollama")
for model in ollama_models:
    print(f"  ✓ {model['name']}")
    print(f"    路径：{model['path']}")
    print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
    all_models.append(model)

# 6. HuggingFace 缓存
print("\n💾 HuggingFace 缓存")
print("-" * 80)
hf_cache_dir = MODELS_DIR / "huggingface" / "hub"
if os.path.exists(hf_cache_dir):
    hf_models = scan_model_directory(hf_cache_dir, "HuggingFace")
    for model in hf_models:
        print(f"  ✓ {model['name']}")
        print(f"    路径：{model['path']}")
        print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
        all_models.append(model)
else:
    print("  (无)")

# 7. ModelScope 缓存
print("\n💾 ModelScope 缓存")
print("-" * 80)
ms_cache_dir = MODELS_DIR / "modelscope" / "hub"
if os.path.exists(ms_cache_dir):
    ms_models = scan_model_directory(ms_cache_dir, "ModelScope")
    for model in ms_models:
        print(f"  ✓ {model['name']}")
        print(f"    路径：{model['path']}")
        print(f"    大小：{model['size_mb']:.1f} MB | 文件数：{model['files']}")
        all_models.append(model)
else:
    print("  (无)")

# 汇总统计
print("\n" + "=" * 80)
print("模型汇总统计")
print("=" * 80)

total_size = sum(m['size_mb'] for m in all_models)
total_files = sum(m['files'] for m in all_models)

print(f"总模型数：{len(all_models)}")
print(f"总文件大小：{total_size:.1f} MB ({total_size/1024:.2f} GB)")
print(f"总文件数：{total_files}")

# 按类型统计
from collections import Counter
type_counts = Counter(m['type'] for m in all_models)
for model_type, count in type_counts.items():
    print(f"  {model_type}: {count} 个")

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
