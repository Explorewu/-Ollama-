# -*- coding: utf-8 -*-
"""
测试魔搭社区上的 Qwen3-TTS 模型
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置魔搭社区镜像
os.environ['HF_ENDPOINT'] = 'https://modelscope.cn'

print("=" * 60)
print("测试魔搭社区 Qwen3-TTS 模型")
print("=" * 60)

# 基于魔搭社区信息，尝试正确的模型名称
model_names = [
    # 可能的魔搭社区模型名称
    "qwen/qwen3-tts",
    "qwen/qwen3-tts-25hz",
    "qwen/qwen3-tts-12hz", 
    "qwen/qwen3-tts-tokenizer-25hz",
    "qwen/qwen3-tts-tokenizer-12hz",
    "qwen/qwen3-tts-vd",
    "qwen/qwen3-tts-vc",
    "qwen/qwen3-tts-flash",
    "qwen/qwen3-tts-base",
]

print("\n尝试直接下载测试...")
print("-" * 40)

success_models = []

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
            print(f"    文件列表: {files[:5]}")
        
        success_models.append(model_name)
        
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir)
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ 下载失败: {error_msg[:100]}")
        
        # 如果是401错误，说明模型不存在或需要权限
        if "401" in error_msg:
            print(f"    可能模型不存在或需要特殊权限")
        elif "404" in error_msg:
            print(f"    模型不存在")
        
        # 清理临时目录
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

print("\n" + "=" * 60)
print("下载结果汇总")
print("=" * 60)

if success_models:
    print(f"✅ 成功下载的模型 ({len(success_models)}个):")
    for model in success_models:
        print(f"  - {model}")
else:
    print("❌ 没有找到可用的Qwen3-TTS模型")
    print("\n可能的原因：")
    print("1. Qwen3-TTS可能还未正式发布到公开仓库")
    print("2. 可能需要特殊权限或API密钥")
    print("3. 模型名称可能有误")

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)