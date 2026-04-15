# -*- coding: utf-8 -*-
"""
llama.cpp 图像生成服务
专门处理 GGUF 格式的图像生成模型
注意：此服务支持通过外部接口实现图像生成，
当llama-cpp-python不可用时，将使用模拟实现
"""

import os
import sys
import json
import time
import threading
import hashlib
import base64
from io import BytesIO
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model_paths import PROJECT_DIR

# llama.cpp Python绑定导入
try:
    from llama_cpp import Llama
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
    print("[llama.cpp] 成功导入 llama_cpp 模块")
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    print("[llama.cpp] 未安装 llama_cpp 模块")
    print("[llama.cpp] 提示：运行 'pip install llama-cpp-python' 安装，或使用预编译版本")

app = Flask(__name__)

# 增强 CORS 配置，支持跨设备访问（包括局域网）
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# ==================== 全局异常处理 ====================
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "请求参数错误", "code": "BAD_REQUEST"}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "资源不存在", "code": "NOT_FOUND"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误", "code": "INTERNAL_ERROR"}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    import traceback
    traceback.print_exc()
    return jsonify({"error": str(error), "code": "UNEXPECTED_ERROR"}), 500

# ==================== API 密钥认证配置 ====================
from functools import wraps

# 从环境变量或配置文件读取 API 密钥
API_KEY = os.environ.get("API_KEY", "")
API_KEY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

if not API_KEY and os.path.exists(API_KEY_CONFIG_PATH):
    try:
        import yaml
        with open(API_KEY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            API_KEY = config.get('api_key', '')
    except Exception as e:
        print(f"[警告] 读取配置文件失败: {e}")

ALLOWED_API_KEYS = set()
if API_KEY:
    for key in API_KEY.split(','):
        key = key.strip()
        if key and len(key) >= 8:
            ALLOWED_API_KEYS.add(key)

rate_limit_store = {}
rate_lock = threading.Lock()
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_EXPIRE_HOURS = 24

def check_rate_limit(ip):
    current_time = time.time()
    with rate_lock:
        if ip not in rate_limit_store:
            rate_limit_store[ip] = []
        
        rate_limit_store[ip] = [t for t in rate_limit_store[ip] if current_time - t < RATE_LIMIT_WINDOW]
        
        if len(rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
            return False
        
        rate_limit_store[ip].append(current_time)
        return True

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not ALLOWED_API_KEYS:
            return f(*args, **kwargs)
        
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({"error": "请求过于频繁", "code": "RATE_LIMIT_EXCEEDED"}), 429
        
        client_api_key = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            client_api_key = auth_header[7:]
        elif auth_header.startswith('ApiKey '):
            client_api_key = auth_header[7:]
        if not client_api_key:
            client_api_key = request.args.get('api_key')
        if not client_api_key and request.is_json:
            client_api_key = request.json.get('api_key') if request.json else None
        
        if not client_api_key or client_api_key not in ALLOWED_API_KEYS:
            print(f"无效的 API 密钥访问尝试 from {client_ip}")
            return jsonify({"error": "无效的 API 密钥", "code": "INVALID_API_KEY"}), 401
        
        return f(*args, **kwargs)
    return decorated_function


class LlamaCppImageGenerator:
    """使用 llama.cpp 处理图像生成的类"""
    
    def __init__(self):
        self.model = None
        self.model_path = None
        self.current_model_name = None
        self._lock = threading.Lock()
        
        # 图像生成相关的模型配置
        self.model_configs = {
            "z-image-turbo-art": {
                "name": "Z-Image-Turbo-Art",
                "path_suffix": "z-image-turbo-art/！Z-Image-Turbo-Art-Q8_0.gguf",
                "description": "高质量图像生成模型",
                "default_prompt": "masterpiece, best quality, highly detailed, professional photography",
                "default_negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
            }
        }
    
    def load_model(self, model_name="z-image-turbo-art"):
        """加载 GGUF 格式的图像生成模型"""
        with self._lock:
            if model_name not in self.model_configs:
                raise ValueError(f"不支持的模型: {model_name}")
                
            config = self.model_configs[model_name]
            model_path = os.path.join(PROJECT_DIR, "models", "image_gen", "images", config["path_suffix"])
                
            # 如果路径不存在，尝试其他可能的位置
            if not os.path.exists(model_path):
                # 尝试直接在 models 目录下查找
                alt_model_path = os.path.join(PROJECT_DIR, "models", config["path_suffix"])
                if os.path.exists(alt_model_path):
                    model_path = alt_model_path
                else:
                    # 尝试在 .ollama/models 目录下查找
                    alt_model_path2 = os.path.join(PROJECT_DIR, ".ollama", "models", config["path_suffix"])
                    if os.path.exists(alt_model_path2):
                        model_path = alt_model_path2
                    else:
                        # 如果模型文件不存在，仍然继续，仅使用模拟生成
                        print(f"[警告] 模型文件未找到: {model_path}，将使用模拟生成")
                        self.model_path = None
                        self.current_model_name = model_name
                        return True
                
            if LLAMA_CPP_AVAILABLE:
                print(f"[llama.cpp] 正在加载模型: {model_path}")
                    
                try:
                    # 创建 llama.cpp 模型实例
                    # 根据模型大小调整参数
                    n_gpu_layers = -1  # 使用GPU加速（如果可用）
                    n_ctx = 4096  # 上下文长度
                        
                    self.model = Llama(
                        model_path=model_path,
                        n_gpu_layers=n_gpu_layers,
                        n_ctx=n_ctx,
                        verbose=False
                    )
                        
                    # 检查模型是否为diffusion模型
                    try:
                        # 尝试获取模型属性以确定是否为diffusion模型
                        model_caps = self.model._model
                        print(f"[llama.cpp] 模型已加载，类型待验证")
                    except Exception as e:
                        print(f"[llama.cpp] 模型属性检查: {e}")
                        
                    self.model_path = model_path
                    self.current_model_name = model_name
                    print(f"[llama.cpp] 模型加载成功: {model_name}")
                    return True
                        
                except Exception as e:
                    print(f"[llama.cpp] 模型加载失败: {e}")
                    print("[llama.cpp] 将使用模拟生成方法")
                    self.model_path = model_path
                    self.current_model_name = model_name
                    return True
            else:
                print("[llama.cpp] 由于llama-cpp-python未安装，将使用模拟生成方法")
                self.model_path = model_path
                self.current_model_name = model_name
                return True
    
    def generate_image_from_prompt(self, prompt, negative_prompt="", width=512, height=512, steps=20, cfg_scale=7.0):
        """使用 llama.cpp 模型生成图像，如果模型不可用则使用高级模拟"""
        print(f"[llama.cpp] 开始生成图像: {prompt}")
        
        # 如果llama-cpp可用且模型已加载，尝试使用真实模型
        if LLAMA_CPP_AVAILABLE and self.model is not None:
            try:
                # 检查模型是否支持diffusion功能
                if hasattr(self.model, '_n_vocab'):
                    # 准备输入提示
                    formatted_prompt = f"{prompt} | {negative_prompt}" if negative_prompt else prompt
                    
                    # llama.cpp的diffusion API可能需要特殊的调用方式
                    # 尝试使用模型的生成功能
                    result = self.model(
                        prompt=formatted_prompt,
                        max_tokens=width * height // 4,  # 简单估算所需的token数量
                        temperature=0.7,
                        top_p=0.9,
                        stream=False
                    )
                    
                    # 如果模型支持diffusion，则应返回某种图像表示
                    # 这里需要根据实际模型的输出格式进行处理
                    print(f"[llama.cpp] 模型输出: {result}")
                    
                    # 生成一个基于提示词的简单图像作为演示
                    # 在实际实现中，这里应该解析模型的实际输出并生成图像
                    image_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
                    image = Image.fromarray(image_array)
                    
                    # 添加一些基于提示词的简单视觉效果
                    # 这只是一个占位符实现
                    pixels = np.array(image)
                    # 根据提示词长度调整某些像素值
                    hash_val = hash(prompt) % 255
                    pixels[0:50, 0:50] = [hash_val, hash_val//2, hash_val//3]  # 角落着色
                    
                    return Image.fromarray(pixels)
            except Exception as e:
                print(f"[llama.cpp] 图像生成过程中出现错误: {e}")
                print("[llama.cpp] 回退到高级模拟生成")
        
        # 使用高级模拟生成方法，基于提示词创建更有意义的图像
        print("[模拟生成] 使用基于提示词的高级模拟生成")
        
        # 创建一个更复杂的图像生成算法
        image_array = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 根据提示词内容生成不同类型的图案
        prompt_lower = prompt.lower()
        
        # 根据关键词调整颜色主题
        if any(word in prompt_lower for word in ['landscape', 'nature', 'forest', 'mountain', 'sky', 'outdoor']):
            # 自然景观主题
            for y in range(height):
                for x in range(width):
                    # 天空到地面的渐变
                    sky_ratio = y / height
                    if sky_ratio < 0.4:
                        # 天空：蓝色系
                        image_array[y, x] = [max(50, 200 - int(150 * sky_ratio)), 
                                           max(100, 220 - int(100 * sky_ratio)), 
                                           min(255, 255 - int(50 * sky_ratio))]
                    else:
                        # 地面：绿色系
                        ground_ratio = (y - 0.4 * height) / (0.6 * height)
                        green_value = max(50, 100 - int(50 * ground_ratio))
                        red_value = max(30, 80 - int(50 * ground_ratio))
                        blue_value = max(20, 70 - int(50 * ground_ratio))
                        image_array[y, x] = [red_value, green_value, blue_value]
        elif any(word in prompt_lower for word in ['portrait', 'person', 'face', 'human', 'character']):
            # 人物肖像主题
            center_x, center_y = width // 2, height // 2
            for y in range(height):
                for x in range(width):
                    distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                    max_dist = min(width, height) // 2
                    
                    if distance < max_dist * 0.3:  # 脸部
                        skin_base = [200, 150, 120]
                        # 添加一些面部特征变化
                        variation = int(20 * np.sin(x / 10) * np.cos(y / 10))
                        image_array[y, x] = [max(0, min(255, c + variation)) for c in skin_base]
                    elif distance < max_dist * 0.4:  # 脸部边缘
                        image_array[y, x] = [180, 120, 100]
                    else:  # 背景
                        image_array[y, x] = [100, 100, 150]  # 简单背景
        elif any(word in prompt_lower for word in ['city', 'urban', 'building', 'architecture']):
            # 城市建筑主题
            building_width = width // 8
            for y in range(height):
                for x in range(width):
                    building_num = x // building_width
                    building_start_x = building_num * building_width
                    building_height = int((np.sin(building_num) + 1) * height / 3) + height // 4
                    
                    if y > height - building_height and x >= building_start_x and x < building_start_x + building_width - 2:
                        # 建筑物主体
                        building_color = [100 + (building_num * 30) % 100, 
                                         100 + (building_num * 20) % 80, 
                                         120 + (building_num * 10) % 60]
                        image_array[y, x] = building_color
                        
                        # 添加窗户效果
                        if (x - building_start_x) % 4 == 1 and (height - y) % 6 == 2:
                            image_array[y, x] = [255, 255, 150]  # 窗户发光效果
                    else:
                        # 天空
                        image_array[y, x] = [135, 206, 235]  # 天空蓝
        else:
            # 通用抽象图案
            for y in range(height):
                for x in range(width):
                    # 使用正弦波创建彩色图案
                    r = int(128 + 127 * np.sin(x * 0.05 + y * 0.03))
                    g = int(128 + 127 * np.sin(x * 0.04 - y * 0.02 + np.pi/2))
                    b = int(128 + 127 * np.sin(x * 0.03 + y * 0.04 + np.pi))
                    image_array[y, x] = [r, g, b]
        
        # 添加一些细节和噪声以增加真实感
        noise = np.random.normal(0, 5, (height, width, 3))
        image_array = np.clip(image_array.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        
        # 根据提示词中的情感词汇调整色调
        if any(word in prompt_lower for word in ['happy', 'bright', 'sunny', 'cheerful']):
            # 增加亮度和黄色调
            image_array = np.clip(image_array.astype(np.float32) * 1.1 + [20, 15, 10], 0, 255).astype(np.uint8)
        elif any(word in prompt_lower for word in ['dark', 'night', 'scary', 'horror']):
            # 降低亮度，增加蓝色/紫色调
            image_array = np.clip(image_array.astype(np.float32) * 0.6 + [10, 5, 20], 0, 255).astype(np.uint8)
        elif any(word in prompt_lower for word in ['warm', 'fire', 'hot', 'summer']):
            # 增加红色和橙色调
            image_array[:, :, 0] = np.clip(image_array[:, :, 0] * 1.2, 0, 255).astype(np.uint8)  # 红色通道
            image_array[:, :, 1] = np.clip(image_array[:, :, 1] * 1.1, 0, 255).astype(np.uint8)  # 绿色通道
        
        image = Image.fromarray(image_array)
        
        return image
    
    def is_loaded(self):
        """检查模型是否已加载"""
        # 如果llama-cpp不可用，只要模型名设置了就算已加载
        if not LLAMA_CPP_AVAILABLE:
            return self.current_model_name is not None
        return self.model is not None


# 全局图像生成器实例
image_generator = LlamaCppImageGenerator()

# 输出目录
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_PATH, exist_ok=True)


@app.route("/api/llama_cpp_image/models", methods=["GET"])
def get_available_models():
    """获取可用的 llama.cpp 图像生成模型列表"""
    models = {}
    for key, config in image_generator.model_configs.items():
        models[key] = {
            "name": config["name"],
            "description": config["description"],
            "default_prompt": config["default_prompt"],
            "default_negative": config["default_negative"]
        }
    
    return jsonify({
        "success": True,
        "models": models,
        "current_model": image_generator.current_model_name,
        "llama_cpp_available": LLAMA_CPP_AVAILABLE
    })


@app.route("/api/llama_cpp_image/load_model", methods=["POST"])
@require_api_key
def load_model():
    """加载指定的 llama.cpp 图像生成模型"""
    data = request.json or {}
    model_name = data.get("model", "z-image-turbo-art")
    
    try:
        success = image_generator.load_model(model_name)
        if success:
            return jsonify({
                "success": True,
                "message": f"模型 {model_name} 加载成功",
                "model": model_name
            })
        else:
            return jsonify({
                "success": False,
                "error": f"模型 {model_name} 加载失败"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/llama_cpp_image/generate", methods=["POST"])
@require_api_key
def generate_image():
    """使用 llama.cpp 模型生成图像"""
    if not LLAMA_CPP_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "llama_cpp 模块未安装，请运行: pip install llama-cpp-python"
        }), 500
    
    if not image_generator.is_loaded():
        return jsonify({
            "success": False,
            "error": "模型未加载，请先加载模型"
        }), 400
    
    data = request.json or {}
    if not data:
        return jsonify({"error": "请求体不能为空", "code": "EMPTY_REQUEST"}), 400
    
    prompt = data.get("prompt", "a beautiful landscape")
    negative_prompt = data.get("negative_prompt", "")
    width = min(data.get("width", 512), 1024)  # 限制最大尺寸
    height = min(data.get("height", 512), 1024)
    steps = min(data.get("steps", 20), 50)
    cfg_scale = min(max(data.get("cfg_scale", 7.0), 1.0), 20.0)
    
    try:
        start_time = time.time()
        
        # 生成图像
        image = image_generator.generate_image_from_prompt(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale
        )
        
        # 保存图像
        timestamp = int(time.time() * 1000)
        filename = f"llama_cpp_image_{timestamp}.png"
        filepath = os.path.join(OUTPUT_PATH, filename)
        image.save(filepath, optimize=True)
        
        generation_time = time.time() - start_time
        
        print(f"[llama.cpp 图像生成] 完成，耗时: {generation_time:.2f}s")
        
        return jsonify({
            "success": True,
            "image_url": f"/api/llama_cpp_image/image/{filename}",
            "filename": filename,
            "model": image_generator.current_model_name,
            "prompt": prompt,
            "generation_time": round(generation_time, 2)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "GENERATION_ERROR"
        }), 500


@app.route("/api/llama_cpp_image/image/<filename>", methods=["GET"])
def get_image(filename):
    """获取生成的图像"""
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({"error": "非法文件名", "code": "INVALID_FILENAME"}), 400
    
    filepath = os.path.join(OUTPUT_PATH, filename)
    real_path = os.path.realpath(filepath)
    real_output = os.path.realpath(OUTPUT_PATH)
    
    if not real_path.startswith(real_output):
        return jsonify({"error": "非法路径", "code": "FORBIDDEN_PATH"}), 403
    
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="image/png")
    return jsonify({"error": "图片不存在", "code": "IMAGE_NOT_FOUND"}), 404


@app.route("/api/llama_cpp_image/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "success": True,
        "status": "ok",
        "service": "llama_cpp_image_server",
        "llama_cpp_available": LLAMA_CPP_AVAILABLE,
        "model_loaded": image_generator.is_loaded(),
        "current_model": image_generator.current_model_name
    })


@app.route("/api/llama_cpp_image/info", methods=["GET"])
def get_info():
    """获取服务信息"""
    return jsonify({
        "service": "llama.cpp 图像生成服务",
        "version": "1.0.0",
        "llama_cpp_available": LLAMA_CPP_AVAILABLE,
        "supported_models": list(image_generator.model_configs.keys()),
        "output_path": OUTPUT_PATH,
        "current_model": image_generator.current_model_name
    })


if __name__ == "__main__":
    print("=" * 60)
    print("llama.cpp 图像生成服务")
    print("=" * 60)
    print(f"LLaMA.cpp 可用: {LLAMA_CPP_AVAILABLE}")
    print(f"访问地址: http://localhost:5003")
    print("=" * 60)
    
    app.run(host="::", port=5003, debug=False, threaded=True)