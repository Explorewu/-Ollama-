#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预编译二进制文件获取工具
为Windows环境提供快速解决方案
"""

import os
import requests
import zipfile
from pathlib import Path
import json

class PrebuiltBinaryManager:
    """预编译二进制文件管理器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.prebuilt_dir = self.project_root / "prebuilt"
        self.llama_cpp_dir = self.prebuilt_dir / "llama_cpp"
        
        # 预编译版本信息
        self.prebuilt_sources = {
            "github_releases": {
                "url": "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest",
                "pattern": "llama-b*win*x64*zip"
            },
            "huggingface": {
                "url": "https://huggingface.co/api/models/ggml-org/models",
                "pattern": "llama-cpp*win*x64"
            }
        }
    
    def check_existing_binaries(self):
        """检查现有二进制文件"""
        print("🔍 检查现有二进制文件")
        print("=" * 30)
        
        # 检查llama.cpp构建目录
        build_exe = self.project_root / "llama.cpp" / "build" / "bin" / "Release" / "llama-diffusion-cli.exe"
        if build_exe.exists():
            print(f"✅ 找到本地构建的可执行文件: {build_exe}")
            return str(build_exe)
        
        # 检查预编译目录
        prebuilt_exe = self.llama_cpp_dir / "windows-x64" / "llama-diffusion-cli.exe"
        if prebuilt_exe.exists():
            print(f"✅ 找到预编译可执行文件: {prebuilt_exe}")
            return str(prebuilt_exe)
        
        print("❌ 未找到可用的二进制文件")
        return None
    
    def download_from_github(self):
        """从GitHub下载预编译版本"""
        print("\n📥 从GitHub下载预编译版本")
        print("=" * 30)
        
        try:
            # 获取最新发布信息
            response = requests.get(
                self.prebuilt_sources["github_releases"]["url"],
                timeout=30
            )
            
            if response.status_code != 200:
                print("❌ 无法获取GitHub发布信息")
                return False
            
            release_data = response.json()
            assets = release_data.get("assets", [])
            
            # 查找Windows x64版本
            windows_asset = None
            for asset in assets:
                if "win" in asset["name"].lower() and "x64" in asset["name"].lower():
                    windows_asset = asset
                    break
            
            if not windows_asset:
                print("❌ 未找到Windows x64预编译版本")
                return False
            
            # 下载文件
            download_url = windows_asset["browser_download_url"]
            filename = windows_asset["name"]
            
            print(f"📦 下载文件: {filename}")
            print(f"🔗 下载链接: {download_url}")
            
            # 创建下载目录
            download_dir = self.llama_cpp_dir / "downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            filepath = download_dir / filename
            with requests.get(download_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            print(f"✅ 下载完成: {filepath}")
            
            # 解压文件
            if filename.endswith('.zip'):
                self.extract_zip(filepath)
            
            return True
            
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False
    
    def extract_zip(self, zip_path):
        """解压ZIP文件"""
        print(f"🔧 解压文件: {zip_path}")
        
        extract_dir = self.llama_cpp_dir / "windows-x64"
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        print(f"✅ 解压完成到: {extract_dir}")
        
        # 查找可执行文件
        exe_files = list(extract_dir.rglob("*.exe"))
        if exe_files:
            print("🔍 找到以下可执行文件:")
            for exe in exe_files:
                print(f"   - {exe}")
    
    def setup_binary_path(self):
        """设置二进制文件路径"""
        print("\n🔧 设置二进制文件路径")
        print("=" * 30)
        
        # 检查现有文件
        binary_path = self.check_existing_binaries()
        if binary_path:
            return binary_path
        
        # 尝试下载
        if self.download_from_github():
            # 再次检查
            binary_path = self.check_existing_binaries()
            if binary_path:
                return binary_path
        
        # 创建配置文件
        config = {
            "binary_path": binary_path,
            "last_check": "2026-02-15",
            "status": "available" if binary_path else "unavailable"
        }
        
        config_file = self.llama_cpp_dir / "config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 配置文件已保存: {config_file}")
        return binary_path
    
    def create_fallback_solution(self):
        """创建回退解决方案"""
        print("\n🔄 创建回退解决方案")
        print("=" * 30)
        
        # 创建批处理脚本用于手动安装
        install_script = self.prebuilt_dir / "install_prebuilt.bat"
        script_content = """@echo off
REM 预编译二进制文件安装脚本

echo 正在下载预编译的llama.cpp二进制文件...
echo ========================================

REM 创建目录
mkdir "%~dp0\\llama_cpp\\windows-x64" 2>nul

echo 请从以下地址手动下载Windows预编译版本：
echo https://github.com/ggerganov/llama.cpp/releases
echo 
echo 下载后请将可执行文件放置在：
echo %~dp0\\llama_cpp\\windows-x64\\

pause
"""
        
        install_script.write_text(script_content, encoding='utf-8')
        print(f"✅ 创建安装脚本: {install_script}")
        
        # 创建使用说明
        usage_guide = self.prebuilt_dir / "USAGE_GUIDE.md"
        guide_content = """
# 预编译二进制文件使用指南

## 快速开始

1. **运行安装脚本**:
   ```
   install_prebuilt.bat
   ```

2. **手动下载**:
   访问 [llama.cpp GitHub Releases](https://github.com/ggerganov/llama.cpp/releases)
   下载Windows x64版本

3. **放置文件**:
   将下载的可执行文件放到:
   ```
   prebuilt/llama_cpp/windows-x64/
   ```

## 验证安装

运行以下命令验证:
```bash
python windows_llama_cpp_setup.py --check
```

## 故障排除

如果仍有问题，请:
1. 确保Windows Visual C++ Redistributable已安装
2. 检查防火墙设置
3. 尝试以管理员身份运行
"""
        
        usage_guide.write_text(guide_content, encoding='utf-8')
        print(f"✅ 创建使用指南: {usage_guide}")
    
    def run_setup(self):
        """运行完整设置流程"""
        print("🚀 预编译二进制文件设置")
        print("=" * 50)
        
        # 创建目录结构
        self.prebuilt_dir.mkdir(exist_ok=True)
        self.llama_cpp_dir.mkdir(exist_ok=True)
        
        # 检查和设置二进制文件
        binary_path = self.setup_binary_path()
        
        if binary_path:
            print(f"\n🎉 设置成功!")
            print(f"✅ 二进制文件路径: {binary_path}")
            print("💡 现在可以使用真实模型推理功能")
            return True
        else:
            print(f"\n⚠️  自动设置失败")
            self.create_fallback_solution()
            print("💡 请参考使用指南手动完成设置")
            return False

def main():
    """主函数"""
    manager = PrebuiltBinaryManager()
    success = manager.run_setup()
    
    if success:
        print("\n🚀 下一步:")
        print("1. 重启图像生成服务")
        print("2. 测试真实模型推理")
        print("3. 享受性能提升!")
    else:
        print("\n💡 备选方案:")
        print("1. 继续使用高级模拟生成")
        print("2. 等待官方预编译包")
        print("3. 尝试Docker容器方案")

if __name__ == "__main__":
    main()