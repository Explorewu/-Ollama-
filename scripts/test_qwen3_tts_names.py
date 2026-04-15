# -*- coding: utf-8 -*-
"""
测试 Qwen3-TTS 的正确模型名称
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("=" * 60)
print("测试 Qwen3-TTS 模型名称")
print("=" * 60)

# 基于搜索结果，尝试正确的模型名称
model_names = [
    # 可能的 TTS 模型名称
    "qwen/qwen3-tts-vd-flash",
    "qwen/qwen3-tts-vc-flash", 
    "qwen/qwen3-audio-chat",
    "qwen/qwen3-tts",
    "qwen/qwen3-tts-base",
    "qwen/qwen3-tts-0.6b",
    "qwen/qwen3-tts-1.7b",
    "Qwen/Qwen3-TTS-VD-Flash",
    "Qwen/Qwen3-TTS-VC-Flash",
    "Qwen/Qwen3-Audio-Chat",
]

print("\n尝试直接下载测试...")
print("-" * 40)

for model_name in model_names:
    print(f"\n测试: {model_name}")
    
    # 创建临时目录
    temp_dir = f"./temp_test_{model_name.replace('/', '_')}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 尝试直接下载
        from huggingface_hub import snapshot_download
        
        print(f"  正在下载...")
        snapshot_download(
            repo_id=model_name,
            local_dir=temp_dir,
            local_dir_use_symlinks=False,
            resume_download=False,
            allow_patterns=["*.json", "*.py", "*.md"],  # 只下载小文件测试
            max_workers=1
        )
        
        # 检查下载的文件
        files = os.listdir(temp_dir)
        print(f"  ✅ 下载成功! 文件数: {len(files)}")
        if files:
            print(f"    文件列表: {files[:5]}")  # 显示前5个文件
        
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir)
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 下载失败: {error_msg[:100]}")
        
        # 如果是401错误，说明模型不存在或需要权限
        if "401" in error_msg:
            print(f"    可能模型不存在或需要特殊权限")
        
        # 清理临时目录
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)