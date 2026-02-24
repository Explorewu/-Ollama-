# Docker环境部署完整指南

## 📋 前置要求

### 1. 系统要求
- **操作系统**: Windows 10/11 Pro, Enterprise, 或 Education (64位)
- **内存**: 至少8GB RAM (推荐16GB)
- **存储**: 至少20GB可用空间
- **CPU**: 支持虚拟化技术

### 2. 必需软件
- **Docker Desktop for Windows**
- **WSL 2** (Windows Subsystem for Linux)

## 🚀 安装步骤

### 第一步：安装WSL 2

```powershell
# 以管理员身份运行PowerShell
wsl --install

# 或者手动安装
wsl --install -d Ubuntu
```

### 第二步：安装Docker Desktop

1. 访问 [Docker官网](https://www.docker.com/products/docker-desktop)
2. 下载 Docker Desktop for Windows
3. 运行安装程序
4. 安装过程中选择启用WSL 2后端
5. 重启计算机

### 第三步：配置Docker (可选GPU支持)

#### GPU支持 (NVIDIA显卡)
```powershell
# 安装NVIDIA Container Toolkit
# 从NVIDIA官网下载并安装:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
```

### 第四步：验证安装

```powershell
# 检查Docker版本
docker --version

# 检查Docker是否运行
docker info

# 运行测试容器
docker run hello-world
```

## 🎯 部署llama.cpp服务

### 自动部署 (推荐)

```powershell
# 运行部署脚本
.\deploy_docker.bat

# 脚本会自动:
# 1. 检查Docker环境
# 2. 检查NVIDIA支持
# 3. 验证模型文件
# 4. 构建并启动容器
```

### 手动部署

```powershell
# 构建镜像
docker-compose build

# 启动GPU版本
docker-compose up -d llama-cpp-image-service

# 或启动CPU版本
docker-compose up -d llama-cpp-image-service-cpu

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 📊 服务访问

### 端口映射
- **GPU版本**: `http://localhost:5005`
- **CPU版本**: `http://localhost:5006`

### API端点
```bash
# 健康检查
GET http://localhost:5005/api/native_llama_cpp_image/health

# 模型列表
GET http://localhost:5005/api/native_llama_cpp_image/models

# 加载模型
POST http://localhost:5005/api/native_llama_cpp_image/load_model
{
  "model": "z-image-turbo-art"
}

# 生成图像
POST http://localhost:5005/api/native_llama_cpp_image/generate
{
  "prompt": "美丽的山水风景",
  "width": 512,
  "height": 512,
  "steps": 20
}
```

## 🛠️ 管理命令

```powershell
# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart

# 查看容器日志
docker-compose logs

# 进入容器
docker exec -it llama-cpp-image-service bash

# 删除镜像
docker-compose down --rmi all
```

## 🔧 故障排除

### 常见问题

1. **Docker Desktop无法启动**
   - 确保启用了WSL 2
   - 检查Windows虚拟化功能是否开启
   - 重启Docker Desktop服务

2. **容器构建失败**
   ```powershell
   # 清理Docker缓存
   docker system prune -a
   
   # 重新构建
   docker-compose build --no-cache
   ```

3. **GPU不可用**
   - 确认安装了NVIDIA Container Toolkit
   - 检查Docker设置中的Resources → WSL Integration
   - 验证NVIDIA驱动版本

4. **端口冲突**
   - 修改docker-compose.yml中的端口映射
   - 检查其他服务是否占用5005/5006端口

### 性能优化

```powershell
# 为Docker分配更多资源
# 在Docker Desktop → Settings → Resources中调整:
# - CPUs: 4-8核
# - Memory: 8-16GB
# - Swap: 2-4GB
```

## 📈 性能对比

| 环境 | 首次启动 | 图像生成 | 资源占用 | 易用性 |
|------|----------|----------|----------|--------|
| Docker GPU | 5-10分钟 | 3-8秒 | 高 | ⭐⭐⭐⭐⭐ |
| Docker CPU | 5-10分钟 | 15-30秒 | 中 | ⭐⭐⭐⭐ |
| 本地编译 | 30分钟+ | 3-8秒 | 中 | ⭐⭐⭐ |

## 🎉 验证部署

运行测试脚本验证部署是否成功：

```powershell
python test_docker_deployment.py
```

脚本会自动检测并测试所有运行中的Docker服务。

---
*文档版本: 1.0*  
*更新时间: 2026年2月15日*