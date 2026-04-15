# -*- coding: utf-8 -*-
"""
本地 llama.cpp 图像生成服务
使用项目中的本地 llama.cpp 源码进行图像生成
"""

import os
import sys
import json
import time
import threading
import subprocess
import hashlib
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model_paths import PROJECT_DIR

# 配置本地llama.cpp路径
LLAMA_CPP_DIR = os.path.join(PROJECT_DIR, "llama.cpp")
LLAMA_CPP_BUILD_DIR = os.path.join(LLAMA_CPP_DIR, "build")
LLAMA_CPP_EXE = os.path.join(LLAMA_CPP_BUILD_DIR, "bin", "llama-diffusion-cli.exe")

app = Flask(__name__)

# CORS配置
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# 全局异常处理
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

class NativeLlamaCppImageGenerator:
    """使用本地编译的llama.cpp进行图像生成"""
    
    def __init__(self):
        self.model_path = None
        self.current_model_name = None
        self._lock = threading.Lock()
        
        # 检查llama.cpp可执行文件
        self.llama_cpp_available = self._check_llama_cpp_availability()
        
        # 模型配置
        self.model_configs = {
            "z-image-turbo-art": {
                "name": "Z-Image-Turbo-Art",
                "path_suffix": "z-image-turbo-art/Z-Image-Turbo-Art-Q8_0.gguf",
                "description": "高质量图像生成模型",
                "default_prompt": "masterpiece, best quality, highly detailed, professional photography",
                "default_negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
            }
        }
    
    def _check_llama_cpp_availability(self):
        """检查本地llama.cpp是否可用"""
        if os.path.exists(LLAMA_CPP_EXE):
            print(f"[llama.cpp] 找到本地编译的可执行文件: {LLAMA_CPP_EXE}")
            return True
        else:
            print(f"[llama.cpp] 未找到本地编译的可执行文件: {LLAMA_CPP_EXE}")
            print("[llama.cpp] 真实模型不可用，请安装预编译二进制文件或Docker环境")
            return False
    
    def load_model(self, model_name="z-image-turbo-art"):
        """加载模型"""
        with self._lock:
            if model_name not in self.model_configs:
                raise ValueError(f"不支持的模型: {model_name}")
            
            config = self.model_configs[model_name]
            model_path = os.path.join(PROJECT_DIR, "models", "image", config["path_suffix"])
            
            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                # 尝试其他可能的位置
                alt_paths = [
                    os.path.join(PROJECT_DIR, "models", "image_gen", "images", config["path_suffix"]),
                    os.path.join(PROJECT_DIR, "models", config["path_suffix"]),
                    os.path.join(PROJECT_DIR, ".ollama", "models", config["path_suffix"])
                ]
                
                for alt_path in alt_paths:
                    if os.path.exists(alt_path):
                        model_path = alt_path
                        break
                else:
                    print(f"[错误] 模型文件未找到: {model_path}")
                    print("[llama.cpp] 真实模型不可用，请确保模型文件存在")
                    self.model_path = None
                    self.current_model_name = model_name
                    return False
            
            self.model_path = model_path
            self.current_model_name = model_name
            
            if self.llama_cpp_available:
                print(f"[llama.cpp] 模型路径已设置: {model_path}")
                print("[llama.cpp] 准备使用本地llama.cpp进行图像生成")
            else:
                print(f"[错误] 真实模型不可用: {model_path}")
                print("[llama.cpp] 请安装预编译二进制文件或Docker环境")
            
            return True
    
    def generate_image_from_prompt(self, prompt, negative_prompt="", width=512, height=512, steps=20, cfg_scale=7.0):
        """生成图像 - 严格真实模型模式"""
        print(f"[图像生成] 开始生成图像: {prompt}")
        
        # 严格检查：必须有可用的真实模型
        if not self._is_real_model_available():
            raise RuntimeError("真实模型不可用，请安装预编译二进制文件或Docker环境")
        
        # 执行真实模型推理
        try:
            result = self._generate_with_native_llama_cpp(
                prompt, negative_prompt, width, height, steps, cfg_scale
            )
            if result is not None:
                return result
            else:
                raise RuntimeError("真实模型推理返回空结果")
        except Exception as e:
            print(f"[llama.cpp] 真实模型推理失败: {e}")
            raise RuntimeError(f"真实模型推理失败: {str(e)}")
    
    def _generate_with_native_llama_cpp(self, prompt, negative_prompt, width, height, steps, cfg_scale):
        """使用本地llama.cpp生成图像"""
        print(f"[llama.cpp] 使用本地可执行文件生成图像")
        
        # 构建命令行参数
        cmd = [
            LLAMA_CPP_EXE,
            "-m", self.model_path,
            "-p", prompt,
            "-ub", str(min(width * height, 2048)),  # 限制最大序列长度
            "--diffusion-steps", str(steps),
            "--diffusion-algorithm", "4",  # CONFIDENCE_BASED
            "--temp", "0.7",
            "--top-p", "0.9"
        ]
        
        # 如果有负向提示词
        if negative_prompt:
            cmd.extend(["--negative-prompt", negative_prompt])
        
        print(f"[llama.cpp] 执行命令: {' '.join(cmd)}")
        
        try:
            # 执行命令并获取输出
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                cwd=LLAMA_CPP_DIR
            )
            
            if result.returncode == 0:
                print(f"[llama.cpp] 生成成功")
                print(f"[llama.cpp] 输出: {result.stdout[:200]}...")
                
                # 解析模型输出并生成图像
                # 这里需要根据实际的diffusion模型输出格式进行处理
                # 暂时返回None，需要后续实现真实的图像解析逻辑
                return None
            else:
                print(f"[llama.cpp] 执行失败，返回码: {result.returncode}")
                print(f"[llama.cpp] 错误输出: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("[llama.cpp] 生成超时")
            return None
        except Exception as e:
            print(f"[llama.cpp] 执行异常: {e}")
            return None
    
    def _is_real_model_available(self):
        """检查真实模型是否可用"""
        return (self.llama_cpp_available and 
                self.model_path and 
                os.path.exists(self.model_path))

# 已移除所有模拟生成相关代码
# 系统现在严格依赖真实模型推理
    
    def is_loaded(self):
        """检查模型是否已加载"""
        return self.current_model_name is not None

# 全局图像生成器实例
image_generator = NativeLlamaCppImageGenerator()

# 输出目录
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_PATH, exist_ok=True)

# API路由
@app.route("/api/native_llama_cpp_image/models", methods=["GET"])
def get_available_models():
    """获取可用模型列表"""
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
        "llama_cpp_available": image_generator.llama_cpp_available,
        "real_model_available": image_generator._is_real_model_available(),
        "llama_cpp_exe": LLAMA_CPP_EXE if image_generator.llama_cpp_available else None
    })

@app.route("/api/native_llama_cpp_image/load_model", methods=["POST"])
def load_model():
    """加载模型"""
    data = request.json or {}
    model_name = data.get("model", "z-image-turbo-art")
    
    try:
        success = image_generator.load_model(model_name)
        if success:
            return jsonify({
                "success": True,
                "message": f"模型 {model_name} 加载成功",
                "model": model_name,
                "mode": "native" if image_generator._is_real_model_available() else "unavailable",
                "real_model_available": image_generator._is_real_model_available()
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

@app.route("/api/native_llama_cpp_image/generate", methods=["POST"])
def generate_image():
    """生成图像"""
    data = request.json or {}
    if not data:
        return jsonify({"error": "请求体不能为空", "code": "EMPTY_REQUEST"}), 400
    
    prompt = data.get("prompt", "a beautiful landscape")
    negative_prompt = data.get("negative_prompt", "")
    width = min(data.get("width", 512), 1024)
    height = min(data.get("height", 512), 1024)
    steps = min(data.get("steps", 20), 50)
    cfg_scale = min(max(data.get("cfg_scale", 7.0), 1.0), 20.0)
    
    if not image_generator.is_loaded():
        return jsonify({
            "success": False,
            "error": "模型未加载，请先加载模型"
        }), 400
    
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
        filename = f"native_llama_cpp_image_{timestamp}.png"
        filepath = os.path.join(OUTPUT_PATH, filename)
        image.save(filepath, optimize=True)
        
        generation_time = time.time() - start_time
        
        print(f"[图像生成] 完成，耗时: {generation_time:.2f}s")
        
        return jsonify({
            "success": True,
            "image_url": f"/api/native_llama_cpp_image/image/{filename}",
            "filename": filename,
            "model": image_generator.current_model_name,
            "prompt": prompt,
            "generation_time": round(generation_time, 2),
            "mode": "native" if image_generator._is_real_model_available() else "unavailable",
            "real_model_available": image_generator._is_real_model_available()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "GENERATION_ERROR"
        }), 500

@app.route("/api/native_llama_cpp_image/image/<filename>", methods=["GET"])
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

@app.route("/api/native_llama_cpp_image/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "success": True,
        "status": "ok",
        "service": "native_llama_cpp_image_server",
        "llama_cpp_available": image_generator.llama_cpp_available,
        "llama_cpp_exe": LLAMA_CPP_EXE if image_generator.llama_cpp_available else None,
        "model_loaded": image_generator.is_loaded(),
        "current_model": image_generator.current_model_name
    })

if __name__ == "__main__":
    print("=" * 60)
    print("本地 llama.cpp 图像生成服务")
    print("=" * 60)
    print(f"llama.cpp 可用: {image_generator.llama_cpp_available}")
    print(f"可执行文件: {LLAMA_CPP_EXE if image_generator.llama_cpp_available else 'N/A'}")
    print(f"访问地址: http://localhost:5004")
    print("=" * 60)
    
    app.run(host="::", port=5004, debug=False, threaded=True)