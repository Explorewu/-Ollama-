# llama.cpp 图像生成服务集成

此项目集成了使用 llama.cpp 运行 GGUF 格式的图像生成模型，特别是 `！Z-Image-Turbo-Art-Q8_0.gguf` 模型。

## 架构概述

- **llama_cpp_image_server.py**: 专门处理 GGUF 格式的图像生成模型服务
- **集成到 intelligent_api.py**: 与现有智能API服务集成
- **支持模型**: `！Z-Image-Turbo-Art-Q8_0.gguf` 及其他 GGUF 格式的图像生成模型

## 安装依赖

首先安装必要的依赖：

```bash
# 运行安装脚本（自动检测CUDA支持）
python install_llama_cpp.py
```

或者手动安装：

```bash
# CPU版本
pip install llama-cpp-python

# CUDA版本 (如果您的系统支持CUDA)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

## 模型准备

将 `！Z-Image-Turbo-Art-Q8_0.gguf` 模型文件放置在以下目录之一：

- `models/image_gen/images/z-image-turbo-art/！Z-Image-Turbo-Art-Q8_0.gguf`
- 或者 `models/！Z-Image-Turbo-Art-Q8_0.gguf`

## 启动服务

### 启动 llama.cpp 图像生成服务

```bash
# Windows
start_llama_cpp_image_service.bat

# 或直接运行
python server/llama_cpp_image_server.py
```

服务将在 `http://localhost:5003` 启动。

### 启动主API服务（可选）

如果需要与主API集成：

```bash
python server/intelligent_api.py
```

## API 端点

### llama.cpp 图像生成服务 (端口 5003)

- `GET /api/llama_cpp_image/health` - 健康检查
- `GET /api/llama_cpp_image/models` - 获取可用模型列表
- `POST /api/llama_cpp_image/load_model` - 加载模型
- `POST /api/llama_cpp_image/generate` - 生成图像
- `GET /api/llama_cpp_image/image/<filename>` - 获取生成的图像
- `GET /api/llama_cpp_image/info` - 获取服务信息

#### 生成图像请求示例

```json
{
  "prompt": "a beautiful landscape with mountains and lake",
  "negative_prompt": "blurry, low quality, bad art",
  "width": 512,
  "height": 512,
  "steps": 20,
  "cfg_scale": 7.0,
  "model": "z-image-turbo-art"
}
```

### 主API集成 (端口 5000)

llama.cpp 图像生成功能已集成到主API服务中，可以通过现有的 `/api/image/generate` 端点调用。

## 测试服务

运行测试脚本验证服务：

```bash
python test_llama_cpp_image.py
```

## 集成细节

- 主API服务 (intelligent_api.py) 现在包含对 llama.cpp 图像生成服务的调用
- 自动检测 `LLAMA_CPP_IMAGE_SERVER_URL` 环境变量指向的图像生成服务
- 支持与现有的 Diffusers 图像生成服务并存

## 配置选项

通过环境变量配置：

- `LLAMA_CPP_IMAGE_SERVER_URL`: llama.cpp 图像生成服务的URL (默认: `http://localhost:5003`)

## 注意事项

1. 确保模型文件路径正确
2. GGUF 图像生成模型需要特殊的处理，此实现在 llama.cpp 的 diffusion 功能基础上构建
3. 根据硬件性能调整图像尺寸和生成步数
4. 服务首次启动时加载模型可能需要较长时间

## 故障排除

如果遇到问题：

1. 检查模型文件是否存在且路径正确
2. 确认 llama-cpp-python 已正确安装
3. 查看服务启动日志中的错误信息
4. 确保有足够的内存来加载模型