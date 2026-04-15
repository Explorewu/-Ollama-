#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows环境下llama-cpp-python编译问题解决方案
专家级架构设计 - 渐进式部署策略
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
import urllib.request
import zipfile
import tarfile

class WindowsLlamaCppSetup:
    """Windows环境下llama-cpp-python安装管理器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.llama_cpp_dir = self.project_root / "llama.cpp"
        self.build_dir = self.llama_cpp_dir / "build"
        self.bin_dir = self.build_dir / "bin"
        
        # 检查系统环境
        self.system_check()
    
    def system_check(self):
        """系统环境检查"""
        print("🔍 Windows系统环境检查")
        print("=" * 50)
        
        # 检查操作系统
        if platform.system() != "Windows":
            raise EnvironmentError("此脚本仅支持Windows系统")
        
        print(f"✅ 操作系统: Windows {platform.version()}")
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version < (3, 8):
            raise EnvironmentError("需要Python 3.8或更高版本")
        
        print(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # 检查架构
        architecture = platform.machine()
        print(f"✅ 系统架构: {architecture}")
        
        return True
    
    def check_prerequisites(self):
        """检查前置条件"""
        print("\n📋 前置条件检查")
        print("=" * 30)
        
        prerequisites = {
            "Visual Studio": self.check_visual_studio(),
            "CMake": self.check_cmake(),
            "Git": self.check_git(),
            "CUDA": self.check_cuda()
        }
        
        missing = [tool for tool, available in prerequisites.items() if not available]
        
        if missing:
            print(f"⚠️  缺少以下工具: {', '.join(missing)}")
            print("💡 建议安装Visual Studio Community (包含C++工具链)")
            return False
        else:
            print("✅ 所有前置条件满足")
            return True
    
    def check_visual_studio(self):
        """检查Visual Studio"""
        try:
            # 检查Visual Studio命令行工具
            result = subprocess.run(
                ["where", "cl.exe"], 
                capture_output=True, 
                text=True, 
                shell=True
            )
            return result.returncode == 0
        except:
            return False
    
    def check_cmake(self):
        """检查CMake"""
        try:
            result = subprocess.run(
                ["cmake", "--version"], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def check_git(self):
        """检查Git"""
        try:
            result = subprocess.run(
                ["git", "--version"], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def check_cuda(self):
        """检查CUDA"""
        try:
            # 检查NVIDIA驱动和CUDA
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def setup_build_environment(self):
        """设置构建环境"""
        print("\n🔧 设置构建环境")
        print("=" * 30)
        
        # 创建构建目录
        self.build_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 构建目录: {self.build_dir}")
        
        # 设置环境变量
        env_vars = {
            "CC": "cl.exe",
            "CXX": "cl.exe",
            "CUDA_PATH": os.environ.get("CUDA_PATH", "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.0")
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            print(f"✅ 环境变量 {key}: {value}")
        
        return True
    
    def build_llama_cpp(self):
        """构建llama.cpp"""
        print("\n🔨 构建llama.cpp")
        print("=" * 30)
        
        # 进入llama.cpp目录
        os.chdir(self.llama_cpp_dir)
        
        try:
            # 清理之前的构建
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
                print("✅ 清理旧构建文件")
            
            # 创建构建目录
            self.build_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(self.build_dir)
            
            # 配置CMake
            cmake_cmd = [
                "cmake", "..",
                "-DLLAMA_CUBLAS=ON",  # 启用CUDA支持
                "-DCMAKE_BUILD_TYPE=Release",
                "-G", "Visual Studio 17 2022"
            ]
            
            print("🔧 配置CMake...")
            print(f"命令: {' '.join(cmake_cmd)}")
            
            result = subprocess.run(
                cmake_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"❌ CMake配置失败: {result.stderr}")
                return False
            
            print("✅ CMake配置成功")
            
            # 构建项目
            build_cmd = [
                "cmake", "--build", ".",
                "--config", "Release",
                "--target", "llama-diffusion-cli"
            ]
            
            print("🔨 开始构建...")
            print(f"命令: {' '.join(build_cmd)}")
            
            result = subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30分钟超时
            )
            
            if result.returncode != 0:
                print(f"❌ 构建失败: {result.stderr}")
                return False
            
            print("✅ 构建成功")
            
            # 检查可执行文件
            exe_path = self.bin_dir / "Release" / "llama-diffusion-cli.exe"
            if exe_path.exists():
                print(f"✅ 可执行文件: {exe_path}")
                return True
            else:
                print("❌ 可执行文件未找到")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ 构建超时")
            return False
        except Exception as e:
            print(f"❌ 构建过程中出错: {e}")
            return False
    
    def install_llama_cpp_python(self):
        """安装llama-cpp-python"""
        print("\n🐍 安装llama-cpp-python")
        print("=" * 30)
        
        try:
            # 设置编译环境变量
            env = os.environ.copy()
            env["FORCE_CMAKE"] = "1"
            env["CMAKE_ARGS"] = f"-DLLAMA_CUBLAS=ON -DCMAKE_BUILD_TYPE=Release"
            
            # 安装llama-cpp-python
            install_cmd = [
                sys.executable, "-m", "pip", "install",
                "llama-cpp-python",
                "--force-reinstall",
                "--no-cache-dir"
            ]
            
            print("🔧 开始安装...")
            print(f"命令: {' '.join(install_cmd)}")
            
            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=600  # 10分钟超时
            )
            
            if result.returncode != 0:
                print(f"❌ 安装失败: {result.stderr}")
                return False
            
            print("✅ 安装成功")
            
            # 验证安装
            try:
                import llama_cpp
                print(f"✅ llama_cpp版本: {llama_cpp.__version__}")
                return True
            except ImportError:
                print("❌ 导入测试失败")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ 安装超时")
            return False
        except Exception as e:
            print(f"❌ 安装过程中出错: {e}")
            return False
    
    def create_prebuilt_binaries(self):
        """创建预编译二进制文件方案"""
        print("\n📦 创建预编译二进制文件方案")
        print("=" * 40)
        
        # 创建预编译目录结构
        prebuilt_dir = self.project_root / "prebuilt" / "llama_cpp"
        prebuilt_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建说明文件
        readme_content = """
# 预编译的llama.cpp二进制文件

## 使用说明

1. 将对应的二进制文件复制到项目目录
2. 确保文件权限正确
3. 重启服务即可使用真实模型推理

## 文件结构
- windows-x64/          # Windows 64位版本
  - llama-diffusion-cli.exe
  - ggml-cuda.dll
  - 其他依赖库

## 下载地址
可以从以下地址获取预编译版本：
- GitHub Releases: https://github.com/ggerganov/llama.cpp/releases
- HuggingFace: 搜索llama.cpp预编译版本
"""
        
        readme_file = prebuilt_dir / "README.md"
        readme_file.write_text(readme_content, encoding='utf-8')
        print(f"✅ 创建说明文件: {readme_file}")
        
        return True
    
    def run_comprehensive_setup(self):
        """运行完整设置流程"""
        print("🚀 Windows llama-cpp-python 完整设置流程")
        print("=" * 60)
        
        try:
            # 1. 系统检查
            if not self.system_check():
                return False
            
            # 2. 前置条件检查
            if not self.check_prerequisites():
                print("\n💡 解决方案:")
                print("1. 安装Visual Studio Community (免费)")
                print("2. 确保安装C++开发工具")
                print("3. 安装Git和CMake")
                print("4. 或者使用预编译二进制文件方案")
                return False
            
            # 3. 设置构建环境
            if not self.setup_build_environment():
                return False
            
            # 4. 构建llama.cpp
            if not self.build_llama_cpp():
                print("\n⚠️  构建失败，尝试预编译方案...")
                self.create_prebuilt_binaries()
                return False
            
            # 5. 安装llama-cpp-python
            if not self.install_llama_cpp_python():
                return False
            
            print("\n🎉 完整设置成功!")
            print("✅ 现在可以使用真实的llama.cpp模型推理")
            return True
            
        except Exception as e:
            print(f"\n❌ 设置过程中出现错误: {e}")
            print("💡 建议使用预编译二进制文件方案")
            self.create_prebuilt_binaries()
            return False

def main():
    """主函数"""
    setup = WindowsLlamaCppSetup()
    
    print("🦙 Windows llama-cpp-python 编译问题解决方案")
    print("=" * 60)
    print("专家级架构设计 - 渐进式部署策略")
    print("=" * 60)
    
    # 运行完整设置
    success = setup.run_comprehensive_setup()
    
    if success:
        print("\n🚀 下一步建议:")
        print("1. 重启图像生成服务")
        print("2. 测试真实模型推理功能")
        print("3. 验证性能提升效果")
    else:
        print("\n💡 备选方案:")
        print("1. 使用预编译二进译文件")
        print("2. 继续使用高级模拟生成")
        print("3. 等待官方预编译包发布")

if __name__ == "__main__":
    main()