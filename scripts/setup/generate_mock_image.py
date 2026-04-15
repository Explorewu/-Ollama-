#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版图片生成脚本
使用模拟模式生成图片
"""

import requests
import json
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import os
import time

def create_mock_image(prompt, width=512, height=512):
    """创建模拟图片"""
    # 创建基础图片
    image = Image.new('RGB', (width, height), color=(73, 109, 137))
    draw = ImageDraw.Draw(image)
    
    # 添加文本
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        # 如果没有找到字体，使用默认字体
        font = ImageFont.load_default()
    
    # 在图片上绘制提示词
    text = f"AI Generated Image\nPrompt: {prompt[:50]}..."
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # 添加背景框
    draw.rectangle([x-10, y-10, x+text_width+10, y+text_height+10], 
                   fill=(255, 255, 255, 200))
    
    # 绘制文本
    draw.text((x, y), text, fill=(0, 0, 0), font=font)
    
    # 添加时间戳
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((10, height-30), f"Generated: {timestamp}", fill=(255, 255, 255), font=font)
    
    return image

def save_image(image, filename=None):
    """保存图片到输出目录"""
    if filename is None:
        timestamp = int(time.time())
        filename = f"generated_image_{timestamp}.png"
    
    output_dir = "server/outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    image.save(filepath, "PNG")
    
    return filepath, filename

def generate_mock_image_api():
    """模拟API生成图片"""
    prompt = "beautiful landscape with mountains and sunset, golden hour lighting, cinematic composition"
    
    print("🎨 正在生成模拟图片...")
    print(f"提示词: {prompt}")
    
    # 生成图片
    image = create_mock_image(prompt)
    
    # 保存图片
    filepath, filename = save_image(image)
    
    print(f"✅ 图片生成成功！")
    print(f"文件路径: {filepath}")
    print(f"文件名: {filename}")
    print(f"尺寸: {image.width} x {image.height}")
    
    # 返回模拟API响应
    response = {
        "success": True,
        "data": {
            "image_url": f"/api/image/{filename}",
            "filename": filename,
            "model": "mock-model",
            "prompt": prompt,
            "width": image.width,
            "height": image.height
        }
    }
    
    return response

def main():
    print("🎨 简化版图片生成工具")
    print("=" * 50)
    print("使用模拟模式生成图片（无需真实模型）")
    print()
    
    try:
        result = generate_mock_image_api()
        if result["success"]:
            data = result["data"]
            print(f"\n🎉 图片生成完成！")
            print(f"访问地址: http://localhost:5001{data['image_url']}")
            print(f"本地路径: {os.path.join('server/outputs', data['filename'])}")
        else:
            print("❌ 生成失败")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()