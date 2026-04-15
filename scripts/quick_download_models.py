# -*- coding: utf-8 -*-
"""
快速下载 Qwen 语音模型
使用 huggingface_hub 官方方式，更稳定
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from huggingface_hub import snapshot_download

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, '.ollama', 'models')

models = [
    {
        'id': 'Qwen/Qwen3-ASR-0.6B',
        'local_dir': os.path.join(MODELS_DIR, 'asr', 'Qwen3-ASR-0.6B')
    },
    {
        'id': 'Qwen/Qwen3-TTS-0.6B',
        'local_dir': os.path.join(MODELS_DIR, 'tts', 'Qwen3-TTS-0.6B')
    }
]

print("=" * 60)
print("开始下载 Qwen 语音模型")
print("使用镜像源: https://hf-mirror.com")
print("=" * 60)

for i, model in enumerate(models):
    print(f"\n[{i+1}/{len(models)}] 下载 {model['id']}")
    print(f"保存到: {model['local_dir']}")
    
    # 检查是否已下载
    if os.path.exists(model['local_dir']) and len(os.listdir(model['local_dir'])) > 3:
        print(f"✅ 模型已存在，跳过")
        continue
    
    try:
        snapshot_download(
            repo_id=model['id'],
            local_dir=model['local_dir'],
            local_dir_use_symlinks=False,
            resume_download=True
        )
        print(f"✅ {model['id']} 下载完成")
    except Exception as e:
        print(f"❌ 下载失败: {e}")

print("\n" + "=" * 60)
print("下载任务完成！")
print("=" * 60)
