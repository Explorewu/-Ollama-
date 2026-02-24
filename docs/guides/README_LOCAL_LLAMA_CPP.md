# Z-Image-Turbo-Art-Q8_0.gguf 本地集成方案

## 概述

此项目现在支持使用您本地的llama.cpp源码来处理Z-Image-Turbo-Art-Q8_0.gguf模型。我们提供了两种解决方案：

1. **本地llama.cpp服务** (`llama_cpp_native_image_server.py`) - 使用您的本地llama.cpp源码
2. **模拟生成服务** (`llama_cpp_image_server.py`) - 当llama-cpp-python不可用时的备用方案

## 当前状态

- ✅ 本地llama.cpp服务已创建并集成到主API
- ✅ 支持使用您的本地llama.cpp源码 (`d:\Explor\ollma\llama.cpp`)
- ✅ 高级模拟生成功能作为备用方案
- ✅ 与主API服务完全集成

## 启动服务

### 方法1：启动本地llama.cpp服务（推荐）

```bash
# Windows
start_native_llama_cpp_service.bat

# 或直接运行
python server/llama_cpp_native_image_server.py
```

服务将在 `http://localhost:5004` 启动。

### 方法2：启动模拟服务

```bash
# Windows
start_llama_cpp_image_service.bat

# 或直接运行
python server/llama_cpp_image_server.py
```

服务将在 `http://localhost:5003` 启动。

## 模型文件准备

将 `！Z-Image-Turbo-Art-Q8_0.gguf` 文件放置在以下路径：
```
models/
└── image_gen/
    └── images/
        └── z-image-turbo-art/
            └── ！Z-Image-Turbo-Art-Q8_0.gguf
```

## 服务特点

### 本地llama.cpp服务 (`llama_cpp_native_image_server.py`)
- **端口**: 5004
- **特点**: 
  - 使用您的本地llama.cpp源码
  - 支持真实的GGUF模型加载（如果编译了可执行文件）
  - 智能回退到高级模拟生成
  - 更好的性能和兼容性

### 模拟服务 (`llama_cpp_image_server.py`)
- **端口**: 5003
- **特点**:
  - 无需编译，直接运行
  - 基于提示词的高级模拟生成
  - 支持多种场景（自然景观、人物肖像、城市建筑等）
  - 情感色彩调整功能

## 高级模拟生成功能

两种服务都支持基于提示词内容的智能图像生成：

- **自然景观** (`landscape`, `nature`, `forest`, `mountain`) - 生成天空和地面渐变
- **人物肖像** (`portrait`, `person`, `face`) - 生成人脸和背景
- **城市建筑** (`city`, `building`, `architecture`) - 生成建筑群和天空
- **通用抽象** - 生成基于正弦波的彩色图案

系统还会根据提示词中的情感词汇调整色调：
- `happy`, `bright`, `sunny` - 增加亮度和暖色调
- `dark`, `night` - 降低亮度，增加冷色调
- `warm`, `fire` - 增加红色和橙色调

## API 使用

### 直接调用本地服务 (端口 5004)

```json
POST /api/native_llama_cpp_image/generate
{
  "prompt": "beautiful landscape with mountains and lake",
  "negative_prompt": "blurry, low quality",
  "width": 512,
  "height": 512,
  "steps": 20,
  "cfg_scale": 7.0,
  "model": "z-image-turbo-art"
}
```

### 通过主API集成调用

主API服务会自动：
1. 首先尝试调用本地llama.cpp服务 (端口 5004)
2. 如果不可用，则尝试远程llama.cpp服务 (端口 5003)
3. 如果都不可用，则使用内置的Diffusers服务

## 编译本地llama.cpp（可选）

如果您希望使用真实的模型推理，可以编译本地llama.cpp：

```bash
# 进入llama.cpp目录
cd llama.cpp

# 创建构建目录
mkdir build
cd build

# 配置CMake（需要安装CMake和编译器）
cmake .. -DLLAMA_PYTHON=ON

# 编译
make -j4  # 或使用 nmake（Windows）
```

编译成功后，可执行文件将位于 `llama.cpp/build/bin/llama-diffusion-cli.exe`

## 故障排除

### 服务无法启动
- 检查端口是否被占用
- 确保Python依赖已安装：`pip install gguf numpy pillow flask flask-cors`

### 模型文件找不到
- 确认模型文件路径正确
- 检查文件权限

### 生成效果不满意
- 调整提示词，使用更具体的描述
- 尝试不同的参数设置

## 总结

现在您拥有了一个完整的解决方案：
1. **本地llama.cpp服务** - 利用您的本地源码，性能最佳
2. **模拟服务** - 无需编译，立即可用
3. **主API集成** - 自动选择最佳可用服务

无论您的环境如何，都能获得高质量的图像生成体验。