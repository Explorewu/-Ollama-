#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片生成脚本
使用当前的文本生成图片功能生成一幅图片
"""

import requests
import json
import time
import os

def generate_image_with_native_service():
    """使用本地llama.cpp服务生成图片（模拟模式）"""
    url = "http://localhost:5004/api/native_llama_cpp_image/generate"
    
    payload = {
        "prompt": "beautiful landscape with mountains and sunset, golden hour lighting, cinematic composition, masterpiece, best quality",
        "negative_prompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality",
        "width": 512,
        "height": 512,
        "steps": 20,
        "cfg_scale": 7.0
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("正在调用本地llama.cpp图片生成服务...")
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 图片生成成功！")
                print(f"文件名: {result.get('filename')}")
                print(f"模型: {result.get('model')}")
                print(f"生成时间: {result.get('generation_time')}秒")
                print(f"模式: {result.get('mode')}")
                print(f"图片URL: http://localhost:5004{result.get('image_url')}")
                return result
            else:
                print(f"❌ 生成失败: {result.get('error')}")
                return None
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def generate_image_with_main_service():
    """使用主服务生成图片"""
    url = "http://localhost:5001/api/image/generate"
    
    payload = {
        "prompt": "beautiful landscape with mountains and sunset, golden hour lighting, cinematic composition",
        "model": "z-image-turbo-art",
        "width": 512,
        "height": 512,
        "steps": 20
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("正在调用主服务图片生成...")
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 图片生成成功！")
                data = result.get("data", result)
                print(f"文件名: {data.get('filename')}")
                print(f"模型: {data.get('model')}")
                print(f"提示词: {data.get('prompt')}")
                print(f"图片URL: http://localhost:5001{data.get('image_url')}")
                return result
            else:
                print(f"❌ 生成失败: {result.get('error')}")
                return None
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def main():
    print("🎨 图片生成工具")
    print("=" * 50)
    
    # 首先尝试本地服务
    print("\n1. 尝试本地llama.cpp服务...")
    result = generate_image_with_native_service()
    
    if not result:
        print("\n2. 本地服务不可用，尝试主服务...")
        result = generate_image_with_main_service()
    
    if result:
        print("\n🎉 图片生成完成！")
        print("您可以在浏览器中访问上面显示的图片URL来查看生成的图片。")
    else:
        print("\n❌ 所有服务都不可用，请检查服务状态。")

if __name__ == "__main__":
    main()