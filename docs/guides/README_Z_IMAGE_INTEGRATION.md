# Z-Image-Turbo-Art-Q8_0.gguf 图像生成模型集成

## 概述

此项目已集成 Z-Image-Turbo-Art-Q8_0.gguf 图像生成模型，支持使用 llama.cpp 运行 GGUF 格式的图像生成模型。即使在 llama-cpp-python 未完全安装的情况下，系统也提供了高级模拟生成功能。

## 当前状态

- ✅ llama_cpp_image_server.py - 已创建，支持 llama.cpp 模型和高级模拟生成
- ✅ 模型文件路径配置 - 已配置为 `models/image_gen/images/z-image-turbo-art/！Z-Image-Turbo-Art-Q8_0.gguf`
- ✅ 与主API集成 - 已集成到 intelligent_api.py
- ✅ 高级模拟生成 - 即使llama-cpp-python未安装也能生成有意义的图像

## 安装 llama-cpp-python（可选但推荐）

如果要使用真实的 Z-Image-Turbo-Art-Q8_0.gguf 模型，需要安装 llama-cpp-python：

### 方法1：使用批处理脚本
```bash
install_llama_cpp_simple.bat
```

### 方法2：手动安装
```bash
# CPU版本（推荐先尝试）
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 如果有CUDA GPU
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

## 模型文件准备

将 `！Z-Image-Turbo-Art-Q8_0.gguf` 文件放置在以下路径：
```
models/
└── image_gen/
    └── images/
        └── z-image-turbo-art/
            └── ！Z-Image-Turbo-Art-Q8_0.gguf
```

## 启动服务

### 启动 llama.cpp 图像生成服务
```bash
# Windows
start_llama_cpp_image_service.bat

# 或直接运行
python server/llama_cpp_image_server.py
```

服务将在 `http://localhost:5003` 启动。

## 高级模拟生成功能

即使 llama-cpp-python 未安装，系统仍能根据提示词内容生成有意义的图像：

- **自然景观** (`landscape`, `nature`, `forest`, `mountain`) - 生成天空和地面渐变
- **人物肖像** (`portrait`, `person`, `face`) - 生成人脸和背景
- **城市建筑** (`city`, `building`, `architecture`) - 生成建筑群和天空
- **通用抽象** - 生成基于正弦波的彩色图案

系统还会根据提示词中的情感词汇调整色调：
- `happy`, `bright`, `sunny` - 增加亮度和暖色调
- `dark`, `night` - 降低亮度，增加冷色调
- `warm`, `fire` - 增加红色和橙色调

## API 使用

### 直接调用 llama.cpp 服务 (端口 5003)

```json
POST /api/llama_cpp_image/generate
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

系统会自动尝试调用 llama.cpp 服务，如果不可用则使用内置的 Diffusers 服务。

## 故障排除

### 如果遇到编译错误
这是正常的，因为 Windows 上编译 llama-cpp-python 需要额外的工具链。使用预编译版本即可。

### 模拟生成效果不满意
- 尝试安装 llama-cpp-python 以获得真实模型生成效果
- 或调整提示词，使用更具体的描述

### 服务无法启动
- 检查端口 5003 是否已被占用
- 检查模型文件路径是否正确

## 更新主API集成

llama-cpp图像生成功能已集成到主API服务中，会自动尝试调用外部服务，如果失败则回退到现有服务。

## 总结

即使在 llama-cpp-python 未安装的情况下，系统也能提供基于提示词的高级模拟图像生成。一旦安装了 llama-cpp-python 并正确配置了模型文件，就可以使用真正的 Z-Image-Turbo-Art-Q8_0.gguf 模型进行高质量图像生成。