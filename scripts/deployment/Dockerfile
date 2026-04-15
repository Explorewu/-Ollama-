# 多阶段构建Docker镜像
# 第一阶段：编译环境
FROM nvidia/cuda:12.0-devel-ubuntu22.04 as builder

# 安装编译依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# 克隆并编译llama.cpp
WORKDIR /build
RUN git clone https://github.com/ggerganov/llama.cpp.git
WORKDIR /build/llama.cpp
RUN mkdir build && cd build \
    && cmake .. -DLLAMA_CUBLAS=ON -DCMAKE_BUILD_TYPE=Release \
    && cmake --build . --config Release --target llama-diffusion-cli

# 第二阶段：运行环境
FROM nvidia/cuda:12.0-runtime-ubuntu22.04

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip3 install --no-cache-dir \
    flask==3.1.2 \
    flask-cors==6.0.2 \
    pillow==12.1.1 \
    numpy==2.4.2 \
    requests==2.32.5 \
    gguf==0.17.1

# 复制编译好的可执行文件
COPY --from=builder /build/llama.cpp/build/bin/llama-diffusion-cli /usr/local/bin/

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY server/llama_cpp_native_image_server.py /app/
COPY server/model_paths.py /app/

# 创建模型目录
RUN mkdir -p /app/models/image_gen/images

# 暴露端口
EXPOSE 5004

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5004/api/native_llama_cpp_image/health || exit 1

# 启动服务
CMD ["python3", "llama_cpp_native_image_server.py"]