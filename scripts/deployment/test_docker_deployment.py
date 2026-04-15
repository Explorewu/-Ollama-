#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker环境部署测试脚本
验证Docker容器中的llama.cpp服务是否正常工作
"""

import requests
import json
import time
import subprocess
import sys

def check_docker_environment():
    """检查Docker环境"""
    print("🔍 检查Docker环境...")
    
    try:
        # 检查Docker是否运行
        result = subprocess.run(['docker', 'version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Docker未运行或未安装")
            return False
        
        print("✅ Docker环境正常")
        
        # 检查容器状态
        result = subprocess.run(['docker-compose', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        if "llama-cpp-image-service" in result.stdout:
            print("✅ 检测到GPU版本容器")
            return "gpu"
        elif "llama-cpp-image-service-cpu" in result.stdout:
            print("✅ 检测到CPU版本容器")
            return "cpu"
        else:
            print("⚠️  未检测到运行中的容器")
            return None
            
    except subprocess.TimeoutExpired:
        print("❌ Docker命令超时")
        return False
    except FileNotFoundError:
        print("❌ 未找到Docker命令，请确保Docker已安装并添加到PATH")
        return False
    except Exception as e:
        print(f"❌ 检查Docker环境时出错: {e}")
        return False

def test_docker_service(port, version_name):
    """测试Docker服务"""
    print(f"\n🧪 测试{version_name}版本服务 (端口: {port})")
    print("=" * 50)
    
    base_url = f"http://localhost:{port}"
    
    # 1. 健康检查
    print("1. 🔍 健康检查")
    try:
        response = requests.get(f"{base_url}/api/native_llama_cpp_image/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ 服务状态: {health_data.get('status')}")
            print(f"   🎯 llama.cpp可用: {health_data.get('llama_cpp_available')}")
            print(f"   🎯 真实模型可用: {health_data.get('real_model_available')}")
            print(f"   📦 模型已加载: {health_data.get('model_loaded')}")
        else:
            print(f"   ❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False
    
    # 2. 模型加载测试
    print("\n2. 📦 模型加载测试")
    try:
        load_data = {"model": "z-image-turbo-art"}
        response = requests.post(
            f"{base_url}/api/native_llama_cpp_image/load_model",
            json=load_data,
            timeout=30
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
    
    # 3. 图像生成测试
    print("\n3. 🎨 图像生成测试")
    try:
        generate_data = {
            "prompt": "一个美丽的山水风景画，青山绿水",
            "width": 256,
            "height": 256,
            "steps": 10
        }
        
        print("   🚀 开始生成图像...")
        start_time = time.time()
        
        response = requests.post(
            f"{base_url}/api/native_llama_cpp_image/generate",
            json=generate_data,
            timeout=120
        )
        
        generation_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"   ✅ 图像生成成功!")
                print(f"   ⏱️  生成耗时: {generation_time:.2f} 秒")
                print(f"   📝 提示词: {result.get('prompt', '')[:30]}...")
                print(f"   📁 文件名: {result.get('filename')}")
                print(f"   🎯 运行模式: {result.get('mode')}")
                return True
            else:
                print(f"   ❌ 生成失败: {result.get('error')}")
                return False
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   📝 错误信息: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ 请求超时")
        return False
    except Exception as e:
        print(f"   ❌ 图像生成测试异常: {e}")
        return False

def main():
    """主函数"""
    print("🐳 Docker环境部署测试")
    print("=" * 60)
    
    # 检查Docker环境
    docker_status = check_docker_environment()
    
    if not docker_status:
        print("\n❌ Docker环境检查失败")
        print("💡 请确保:")
        print("   1. Docker Desktop已安装并运行")
        print("   2. 执行了 deploy_docker.bat 脚本")
        print("   3. 容器已成功启动")
        return
    
    # 测试服务
    test_results = []
    
    if docker_status == "gpu" or docker_status == "both":
        result = test_docker_service(5005, "GPU")
        test_results.append(("GPU版本", result))
    
    if docker_status == "cpu" or docker_status == "both":
        result = test_docker_service(5006, "CPU")
        test_results.append(("CPU版本", result))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for version_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {version_name}")
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"\n总计: {passed}/{total} 个版本测试通过")
    
    if passed == total:
        print("🎉 所有Docker服务测试通过！")
        print("✅ 现在可以使用Docker环境进行图像生成")
    elif passed > 0:
        print("⚠️  部分服务正常，可以使用正常运行的版本")
    else:
        print("❌ 所有Docker服务测试失败")
        print("💡 建议检查:")
        print("   1. Docker容器日志: docker-compose logs")
        print("   2. 容器状态: docker-compose ps")
        print("   3. 重新部署: deploy_docker.bat")
    
    print("=" * 60)

if __name__ == "__main__":
    main()