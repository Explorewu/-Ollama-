"""
图像生成 API 模块

提供图像生成相关接口
"""

import os
import io
import gc
import time
import base64
import logging
import threading
import requests
import psutil
from flask import request, jsonify, send_file

from utils.config import (
    IMAGE_MODEL_PATH, IMAGE_OUTPUT_PATH, MAX_IMAGE_SIZE,
    IMAGE_MODEL_CONFIG, LLAMA_CPP_IMAGE_SERVER_URL,
    NATIVE_LLAMA_CPP_IMAGE_SERVER_URL
)
from utils.auth import require_api_key
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

torch = None
StableDiffusionXLPipeline = None
StableDiffusionPipeline = None

image_pipe = None
image_current_model = None
image_model_lock = threading.Lock()

os.makedirs(IMAGE_MODEL_PATH, exist_ok=True)
os.makedirs(IMAGE_OUTPUT_PATH, exist_ok=True)


def _ensure_torch_and_diffusers():
    """延迟加载 torch 和 diffusers（避免启动时加载大库）"""
    global torch, StableDiffusionXLPipeline, StableDiffusionPipeline
    
    if torch is not None:
        return True
    
    try:
        import torch as _torch
        from diffusers import StableDiffusionXLPipeline as _SDXL
        from diffusers import StableDiffusionPipeline as _SD
        
        torch = _torch
        StableDiffusionXLPipeline = _SDXL
        StableDiffusionPipeline = _SD
        return True
    except ImportError as e:
        logger.error(f"diffusers 库不可用，无法加载图像模型: {e}")
        return False


def load_image_model(model_key):
    """加载图像生成模型"""
    global image_pipe, image_current_model

    if not _ensure_torch_and_diffusers():
        return False

    if image_current_model == model_key and image_pipe is not None:
        return True

    with image_model_lock:
        try:
            logger.info(f"正在加载图像生成模型: {model_key}")
            
            model_config = IMAGE_MODEL_CONFIG.get(model_key)
            if not model_config:
                logger.error(f"未找到模型配置: {model_key}")
                return False
            
            model_path = model_config.get("local_path")
            pipeline_name = model_config.get("pipeline", "StableDiffusionPipeline")
            
            if pipeline_name == "StableDiffusionXLPipeline":
                if model_path and os.path.exists(model_path):
                    image_pipe = StableDiffusionXLPipeline.from_pretrained(
                        model_path,
                        torch_dtype=torch.float32,
                        safety_checker=None,
                        requires_safety_checker=False,
                        use_safetensors=True
                    )
                else:
                    logger.error(f"模型路径不存在: {model_path}")
                    return False
            else:
                if model_path and os.path.exists(model_path):
                    image_pipe = StableDiffusionPipeline.from_pretrained(
                        model_path,
                        torch_dtype=torch.float32,
                        safety_checker=None,
                        requires_safety_checker=False,
                        use_safetensors=True
                    )
                else:
                    image_pipe = StableDiffusionPipeline.from_pretrained(
                        "runwayml/stable-diffusion-v1-5",
                        torch_dtype=torch.float32,
                        safety_checker=None,
                        requires_safety_checker=False
                    )

            if image_pipe is not None:
                image_pipe = image_pipe.to("cpu")
                if hasattr(image_pipe, 'enable_attention_slicing'):
                    image_pipe.enable_attention_slicing()

            image_current_model = model_key
            logger.info(f"图像生成模型加载完成: {model_key}")
            return True
            
        except Exception as e:
            logger.error(f"图像生成模型加载失败: {e}")
            return False


def call_llama_cpp_image_service(prompt, negative_prompt="", width=512, height=512, 
                                  steps=20, cfg_scale=7.0, model="z-image-turbo-art"):
    """调用 llama.cpp 图像生成服务"""
    result = call_native_llama_cpp_image_service(
        prompt, negative_prompt, width, height, steps, cfg_scale, model
    )
    if result:
        return result
    
    try:
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": min(width, MAX_IMAGE_SIZE),
            "height": min(height, MAX_IMAGE_SIZE),
            "steps": min(steps, 50),
            "cfg_scale": min(max(cfg_scale, 1.0), 20.0),
            "model": model
        }
        
        response = requests.post(
            f"{LLAMA_CPP_IMAGE_SERVER_URL}/api/llama_cpp_image/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result
                
    except Exception as e:
        logger.error(f"调用 llama.cpp 图像生成服务失败: {e}")
        
    return None


def call_native_llama_cpp_image_service(prompt, negative_prompt="", width=512, height=512,
                                         steps=20, cfg_scale=7.0, model="z-image-turbo-art"):
    """调用本地 llama.cpp 图像生成服务"""
    try:
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": min(width, MAX_IMAGE_SIZE),
            "height": min(height, MAX_IMAGE_SIZE),
            "steps": min(steps, 50),
            "cfg_scale": min(max(cfg_scale, 1.0), 20.0),
            "model": model
        }
        
        response = requests.post(
            f"{NATIVE_LLAMA_CPP_IMAGE_SERVER_URL}/api/native_llama_cpp_image/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result
                
    except Exception as e:
        logger.error(f"调用本地 llama.cpp 图像生成服务失败: {e}")
        
    return None


def register_image_routes(app):
    """注册图像生成相关路由"""
    
    @app.route('/api/image/models', methods=['GET'])
    def get_image_models():
        """获取可用图像生成模型列表"""
        models = []
        for key, config in IMAGE_MODEL_CONFIG.items():
            models.append({
                "id": key,
                "name": config.get("name", key),
                "style": config.get("style", ""),
                "size": config.get("size", ""),
                "local_path": config.get("local_path", ""),
                "exists": os.path.exists(config.get("local_path", "")) if config.get("local_path") else False
            })
        return jsonify(success_response(data=models))
    
    @app.route('/api/image/generate', methods=['POST'])
    @require_api_key
    def generate_image():
        """生成图像"""
        try:
            data = request.json or {}
            
            prompt = data.get('prompt', '')
            negative_prompt = data.get('negative_prompt', '')
            width = min(data.get('width', 512), MAX_IMAGE_SIZE)
            height = min(data.get('height', 512), MAX_IMAGE_SIZE)
            steps = min(data.get('steps', 20), 50)
            cfg_scale = data.get('cfg_scale', 7.0)
            model = data.get('model', 'kook-qwen-2512')
            
            if not prompt:
                return jsonify(error_response("缺少 prompt 参数", 400)), 400
            
            model_config = IMAGE_MODEL_CONFIG.get(model, IMAGE_MODEL_CONFIG.get("kook-qwen-2512"))
            if not negative_prompt:
                negative_prompt = model_config.get("default_negative", "")
            
            llama_result = call_llama_cpp_image_service(
                prompt, negative_prompt, width, height, steps, cfg_scale, model
            )
            
            if llama_result and llama_result.get("success"):
                return jsonify(success_response(data=llama_result.get("data")))
            
            if not load_image_model(model):
                return jsonify(error_response("图像模型加载失败", 500)), 500
            
            with torch.no_grad():
                image = image_pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    num_inference_steps=steps,
                    guidance_scale=cfg_scale
                ).images[0]
            
            timestamp = int(time.time())
            filename = f"generated_image_{timestamp}.png"
            filepath = os.path.join(IMAGE_OUTPUT_PATH, filename)
            image.save(filepath)
            
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return jsonify(success_response(data={
                "image": img_base64,
                "filename": filename,
                "path": filepath,
                "model": model
            }))
            
        except Exception as e:
            logger.error(f"图像生成失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/image/unload', methods=['POST'])
    def unload_image_model():
        """卸载图像生成模型，释放内存"""
        global image_pipe, image_current_model
        try:
            if image_pipe is not None:
                if torch is not None and torch.cuda.is_available():
                    del image_pipe
                    torch.cuda.empty_cache()
                else:
                    del image_pipe
                gc.collect()
                image_pipe = None
                image_current_model = None
                logger.info("图像模型已卸载，内存已释放")
                return jsonify(success_response(data={
                    "unloaded": True,
                    "message": "图像模型已卸载"
                }))
            else:
                return jsonify(success_response(data={
                    "unloaded": False,
                    "message": "没有已加载的图像模型"
                }))
        except Exception as e:
            logger.error(f"卸载图像模型失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/image/memory', methods=['GET'])
    def get_image_memory():
        """获取图像服务内存状态"""
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            return jsonify(success_response(data={
                "process": {
                    "rss_mb": mem_info.rss / 1024 / 1024,
                    "vms_mb": mem_info.vms / 1024 / 1024,
                    "percent": process.memory_percent()
                },
                "model_loaded": image_pipe is not None,
                "current_model": image_current_model
            }))
        except Exception as e:
            logger.error(f"获取内存状态失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ 图像生成 API 路由已注册")
