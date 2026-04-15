#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安装 llama-cpp-python 的脚本
支持 CUDA 和 CPU 版本
"""

import subprocess
import sys
import platform
import os

def check_cuda_availability():
    """检查CUDA是否可用"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        # 如果torch不可用，尝试通过nvidia-smi检查
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False

def install_llama_cpp():
    """安装llama-cpp-python"""
    print("检查系统环境...")
    
    # 检查是否支持CUDA
    cuda_available = check_cuda_availability()
    
    print(f"CUDA 可用性: {'是' if cuda_available else '否'}")
    print(f"操作系统: {platform.system()}")
    print(f"Python 版本: {sys.version}")
    
    if cuda_available:
        print("检测到CUDA环境，安装支持CUDA的版本...")
        # 安装支持CUDA的版本
        cmd = [
            sys.executable, "-m", "pip", "install", 
            "llama-cpp-python", 
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cu121"
        ]
    else:
        print("使用CPU版本...")
        # 安装CPU版本
        cmd = [
            sys.executable, "-m", "pip", 
            "install", "llama-cpp-python"
        ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ llama-cpp-python 安装成功!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ 安装失败:")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        return False

def verify_installation():
    """验证安装"""
    try:
        import llama_cpp
        print("✅ llama_cpp 模块导入成功!")
        
        # 尝试创建一个最小的实例来测试
        from llama_cpp import Llama
        print("✅ Llama 类可以正常导入")
        return True
    except ImportError as e:
        print(f"❌ llama_cpp 模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试时发生错误: {e}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("llama-cpp-python 安装脚本")
    print("="*50)
    
    # 安装
    success = install_llama_cpp()
    
    if success:
        print("\n" + "="*50)
        print("验证安装...")
        print("="*50)
        verify_installation()
        
        print("\n" + "="*50)
        print("安装完成!")
        print("现在您可以启动 llama_cpp_image_server.py 服务")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("安装失败，请手动安装:")
        print("  CPU版本: pip install llama-cpp-python")
        print("  CUDA版本: pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121")
        print("="*50)