# -*- coding: utf-8 -*-
"""
测试 Qwen 模型名称是否正确
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from huggingface_hub import HfApi, list_models

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

api = HfApi()

print("=" * 60)
print("测试 Qwen 模型名称")
print("=" * 60)

# 测试可能的模型名称
model_names = [
    "Qwen/Qwen3-ASR-0.6B",
    "Qwen/Qwen3-ASR-Flash", 
    "Qwen/Qwen3-TTS-0.6B",
    "Qwen/Qwen3-TTS",
    "Qwen/Qwen3-ASR",
    "Qwen/Qwen3-TTS-Base"
]

for model_name in model_names:
    print(f"\n测试模型: {model_name}")
    try:
        # 尝试获取模型信息
        model_info = api.model_info(model_name)
        print(f"✅ 模型存在: {model_name}")
        print(f"   模型ID: {model_info.id}")
        print(f"   下载量: {model_info.downloads}")
        print(f"   标签: {model_info.tags}")
    except Exception as e:
        print(f"❌ 模型不存在或访问失败: {e}")

print("\n" + "=" * 60)
print("搜索 Qwen 相关的语音模型...")
print("=" * 60)

# 搜索 Qwen 语音相关的模型
try:
    models = list_models(
        author="Qwen",
        search="ASR TTS speech voice",
        limit=10
    )
    
    print(f"找到 {len(models)} 个相关模型:")
    for model in models:
        print(f"  - {model.id} (下载量: {model.downloads})")
        
except Exception as e:
    print(f"搜索失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)