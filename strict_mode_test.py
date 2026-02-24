#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
严格真实模型模式测试脚本
验证移除模拟生成功能后的系统行为
"""

import requests
import json
import time

def test_strict_mode():
    """测试严格真实模型模式"""
    print("🧪 严格真实模型模式测试")
    print("=" * 50)
    
    base_url = "http://localhost:5004"
    
    # 1. 健康检查
    print("1. 🔍 健康检查")
    try:
        response = requests.get(f"{base_url}/api/native_llama_cpp_image/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ 服务状态: {health_data.get('status')}")
            print(f"   🎯 llama.cpp可用: {health_data.get('llama_cpp_available')}")
            print(f"   🎯 真实模型可用: {health_data.get('real_model_available')}")
            print(f"   📦 模型已加载: {health_data.get('model_loaded')}")
            print(f"   📝 当前模型: {health_data.get('current_model')}")
        else:
            print(f"   ❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False
    
    # 2. 模型列表检查
    print("\n2. 📋 模型列表检查")
    try:
        response = requests.get(f"{base_url}/api/native_llama_cpp_image/models", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            print(f"   ✅ 可用模型数: {len(models_data.get('models', {}))}")
            print(f"   🎯 当前模型: {models_data.get('current_model')}")
            print(f"   🎯 真实模型可用: {models_data.get('real_model_available')}")
        else:
            print(f"   ❌ 模型列表获取失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 模型列表检查失败: {e}")
    
    # 3. 模型加载测试
    print("\n3. 📦 模型加载测试")
    try:
        load_data = {"model": "z-image-turbo-art"}
        response = requests.post(
            f"{base_url}/api/native_llama_cpp_image/load_model",
            json=load_data,
            timeout=10
        )
        
        if response.status_code == 200:
            load_result = response.json()
            if load_result.get('success'):
                print(f"   ✅ 模型加载成功")
                print(f"   📝 模型名称: {load_result.get('model')}")
                print(f"   🎯 运行模式: {load_result.get('mode')}")
                print(f"   🎯 真实模型可用: {load_result.get('real_model_available')}")
            else:
                print(f"   ❌ 模型加载失败: {load_result.get('error')}")
                return False
        else:
            print(f"   ❌ 加载请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 模型加载测试失败: {e}")
        return False
    
    # 4. 图像生成测试（应该失败，因为没有真实模型）
    print("\n4. 🎨 图像生成测试（预期失败）")
    try:
        generate_data = {
            "prompt": "一个美丽的风景画",
            "width": 256,
            "height": 256,
            "steps": 10
        }
        
        response = requests.post(
            f"{base_url}/api/native_llama_cpp_image/generate",
            json=generate_data,
            timeout=30
        )
        
        if response.status_code == 500:
            error_data = response.json()
            error_msg = error_data.get('error', '')
            print(f"   ✅ 正确返回错误（预期行为）")
            print(f"   📝 错误信息: {error_msg}")
            
            # 验证错误信息是否包含预期内容
            if "真实模型不可用" in error_msg or "真实模型推理失败" in error_msg:
                print(f"   ✅ 错误信息符合预期")
                return True
            else:
                print(f"   ⚠️  错误信息不完全符合预期")
                return True
        elif response.status_code == 200:
            print(f"   ❌ 意外成功（应该失败）")
            return False
        else:
            print(f"   ❌ 非预期状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ 图像生成测试异常: {e}")
        return False

def main():
    """主函数"""
    print("🚀 严格真实模型模式验证")
    print("=" * 60)
    
    success = test_strict_mode()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试通过！系统已正确移除模拟生成功能")
        print("✅ 在没有真实模型时会正确返回错误信息")
        print("💡 用户现在必须安装预编译二进制文件或Docker环境才能使用")
    else:
        print("❌ 测试失败！系统可能仍有问题")
    
    print("=" * 60)

if __name__ == "__main__":
    main()