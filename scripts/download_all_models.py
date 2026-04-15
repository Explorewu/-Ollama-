# -*- coding: utf-8 -*-
"""
预下载所有需要的模型文件
- Qwen3-ASR-Flash (语音识别)
- Qwen3-TTS (语音合成)
使用国内镜像源，确保下载速度和安全性
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.model_downloader import get_model_downloader, MirrorSource

def download_models():
    """下载所有需要的模型"""
    print("=" * 60)
    print("       预下载语音模型文件")
    print("=" * 60)
    
    downloader = get_model_downloader(default_mirror=MirrorSource.WISEMODEL)
    
    # 模型列表（使用新的统一目录结构）
    models = [
        {
            "id": "Qwen/Qwen3-ASR-0.6B",
            "dir": "models/audio/asr/Qwen3-ASR-0.6B",
            "desc": "语音识别模型 (约 300MB)"
        },
        {
            "id": "Qwen/Qwen3-TTS-0.6B", 
            "dir": "models/audio/tts/Qwen3-TTS-0.6B",
            "desc": "语音合成模型 (约 500MB)"
        }
    ]
    
    success_count = 0
    
    for model in models:
        print(f"\n[{models.index(model) + 1}/{len(models)}] 下载 {model['desc']}")
        print(f"模型ID: {model['id']}")
        print(f"保存位置: {model['dir']}")
        
        success = downloader.download_with_auto_retry(
            model_id=model['id'],
            local_dir=model['dir'],
            mirrors=[
                MirrorSource.WISEMODEL,  # 智谱AI镜像（最快）
                MirrorSource.HF_MIRROR,   # HF镜像
                MirrorSource.MODELSCOPE,  # 阿里ModelScope
                MirrorSource.HUGGINGFACE  # 官方源
            ]
        )
        
        if success:
            print(f"✅ {model['desc']} 下载成功")
            success_count += 1
        else:
            print(f"❌ {model['desc']} 下载失败")
    
    print("\n" + "=" * 60)
    print(f"下载完成: {success_count}/{len(models)} 个模型")
    print("=" * 60)
    
    return success_count == len(models)

if __name__ == "__main__":
    success = download_models()
    sys.exit(0 if success else 1)
