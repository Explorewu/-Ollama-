#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版图片生成脚本
创建更美观的模拟风景图片
"""

import requests
import json
import base64
from PIL import Image, ImageDraw, ImageFont
import random
import os
import time
import math

def create_landscape_image(prompt, width=512, height=512):
    """创建风景图片"""
    # 创建基础图片
    image = Image.new('RGB', (width, height), color=(135, 206, 235))  # 天空蓝
    draw = ImageDraw.Draw(image)
    
    # 绘制天空渐变效果
    for y in range(height // 2):
        # 从浅蓝到深蓝的渐变
        r = max(100, 135 - y // 10)
        g = max(150, 206 - y // 8)
        b = max(200, 235 - y // 6)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 绘制太阳
    sun_x = width - 100
    sun_y = 80
    sun_radius = 40
    draw.ellipse([sun_x - sun_radius, sun_y - sun_radius, 
                  sun_x + sun_radius, sun_y + sun_radius], 
                 fill=(255, 255, 200))  # 淡黄色太阳
    
    # 绘制太阳光晕
    for i in range(5):
        radius = sun_radius + 10 + i * 8
        alpha = 150 - i * 25
        # 绘制光晕圆圈
        draw.ellipse([sun_x - radius, sun_y - radius, 
                      sun_x + radius, sun_y + radius], 
                     outline=(255, 255, 180, alpha), width=2)
    
    # 绘制远山
    mountain_y = height // 2
    points = [(0, height)]
    for x in range(0, width + 1, 20):
        y = mountain_y + random.randint(-30, 30)
        points.append((x, y))
    points.append((width, height))
    points.append((0, height))
    
    # 绘制山脉（深绿色）
    draw.polygon(points, fill=(34, 139, 34))
    
    # 绘制近景山丘
    hill_y = height * 3 // 4
    hill_points = [(0, height)]
    for x in range(0, width + 1, 15):
        y = hill_y + random.randint(-20, 20)
        hill_points.append((x, y))
    hill_points.append((width, height))
    hill_points.append((0, height))
    
    # 绘制山丘（浅绿色）
    draw.polygon(hill_points, fill=(50, 205, 50))
    
    # 绘制草地
    grass_y = height * 7 // 8
    draw.rectangle([0, grass_y, width, height], fill=(34, 139, 34))
    
    # 添加一些装饰元素
    # 树木
    for i in range(8):
        x = random.randint(20, width - 20)
        if x < sun_x - 100 or x > sun_x + 100:  # 避开太阳区域
            tree_height = random.randint(30, 60)
            # 树干
            draw.rectangle([x-3, grass_y-tree_height, x+3, grass_y], fill=(139, 69, 19))
            # 树冠
            draw.ellipse([x-15, grass_y-tree_height-20, x+15, grass_y-tree_height+10], 
                        fill=(0, 100, 0))
    
    # 添加云朵
    for i in range(3):
        cloud_x = random.randint(50, width - 100)
        cloud_y = random.randint(30, height // 3)
        # 绘制云朵的几个圆形组成
        for j in range(5):
            offset_x = random.randint(-20, 20)
            offset_y = random.randint(-15, 15)
            radius = random.randint(15, 25)
            draw.ellipse([cloud_x + offset_x - radius, cloud_y + offset_y - radius,
                         cloud_x + offset_x + radius, cloud_y + offset_y + radius],
                        fill=(255, 255, 255))
    
    # 在图片底部添加信息
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    # 添加半透明背景框
    info_text = f"AI Generated Landscape | Prompt: {prompt[:30]}..."
    text_bbox = draw.textbbox((0, 0), info_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # 半透明背景
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([10, height-40, text_width+20, height-10], 
                          fill=(0, 0, 0, 128))
    image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(image)
    
    # 绘制文本
    draw.text((15, height-35), info_text, fill=(255, 255, 255), font=font)
    
    # 添加时间戳
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((width-150, height-25), timestamp, fill=(255, 255, 255), font=font)
    
    return image

def save_image(image, filename=None):
    """保存图片到输出目录"""
    if filename is None:
        timestamp = int(time.time())
        filename = f"landscape_{timestamp}.png"
    
    output_dir = "server/outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    image.save(filepath, "PNG")
    
    return filepath, filename

def generate_beautiful_landscape():
    """生成美丽的风景图片"""
    prompt = "beautiful landscape with mountains and sunset, golden hour lighting, cinematic composition"
    
    print("🎨 正在生成美丽的风景图片...")
    print(f"提示词: {prompt}")
    
    # 生成图片
    image = create_landscape_image(prompt)
    
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
            "model": "beautiful-landscape-generator",
            "prompt": prompt,
            "width": image.width,
            "height": image.height
        }
    }
    
    return response

def main():
    print("🎨 增强版风景图片生成工具")
    print("=" * 50)
    print("创建美丽的模拟风景图片")
    print()
    
    try:
        result = generate_beautiful_landscape()
        if result["success"]:
            data = result["data"]
            print(f"\n🎉 图片生成完成！")
            print(f"访问地址: http://localhost:5001{data['image_url']}")
            print(f"本地路径: {os.path.join('server/outputs', data['filename'])}")
            
            # 在浏览器中打开图片
            full_path = os.path.join(os.getcwd(), "server", "outputs", data['filename'])
            print(f"正在打开图片...")
            os.startfile(full_path)
        else:
            print("❌ 生成失败")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()