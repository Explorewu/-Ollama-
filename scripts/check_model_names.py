# -*- coding: utf-8 -*-
"""
检查 Qwen 语音模型名称的正确性
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("=" * 60)
print("检查 Qwen 语音模型名称")
print("=" * 60)

# 基于搜索结果，尝试正确的模型名称
model_names = [
    # 可能的 ASR 模型名称
    "Qwen/Qwen3-ASR",
    "Qwen/Qwen3-ASR-0.6B", 
    "Qwen/Qwen3-ASR-Flash",
    "Qwen/Qwen3-ASR-1.7B",
    
    # 可能的 TTS 模型名称
    "Qwen/Qwen3-TTS",
    "Qwen/Qwen3-TTS-0.6B",
    "Qwen/Qwen3-TTS-1.7B",
    "Qwen/Qwen3-TTS-Base",
    
    # 其他可能的名称
    "Qwen/Qwen3-ASR-0.6B-Chat",
    "Qwen/Qwen3-TTS-0.6B-Chat",
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
        print(f"  ❌ 下载失败: {str(e)[:100]}")
        # 清理临时目录
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)