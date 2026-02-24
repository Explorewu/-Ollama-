# 项目目录结构说明

## 主要目录结构

```
ollma/
├── docs/                    # 文档目录
│   ├── guides/             # 使用指南和说明文档
│   │   ├── OPTIMIZED_LAUNCHER_README.md     # 优化启动程序说明
│   │   ├── README_LOCAL_LLAMA_CPP.md        # 本地llama.cpp设置指南
│   │   ├── README_Z_IMAGE_INTEGRATION.md    # Z图像集成熟成
│   │   ├── WINDOWS_LLAMA_CPP_SOLUTION.md    # Windows解决方案
│   │   ├── frontend_integration_guide.md    # 前端集成指南
│   │   └── DOCKER_DEPLOYMENT_GUIDE.md       # Docker部署指南
│   ├── Action.md                           # 行动指南
│   ├── Description.md                      # 项目描述
│   ├── literary_assistant_prompt.md        # 文学助手提示词
│   ├── llama_cpp_image_integration.md      # 图像集成说明
│   ├── optimization_plan.md                # 优化计划
│   └── 前端服务排查报告.md                   # 前端服务排查报告
│
├── scripts/                 # 脚本目录
│   ├── setup/              # 安装设置脚本
│   │   ├── install_llama_cpp.py            # llama.cpp安装脚本
│   │   ├── install_llama_cpp_simple.bat    # 简单安装批处理
│   │   ├── windows_llama_cpp_setup.py      # Windows设置脚本
│   │   └── prebuilt_binary_setup.py        # 预编译二进制设置
│   ├── launchers/          # 启动脚本
│   │   ├── launcher.bat                    # 原始启动器
│   │   ├── 启动后端服务.bat                 # 后端服务启动
│   │   ├── start_llama_cpp_image_service.bat  # 图像服务启动
│   │   ├── start_native_llama_cpp_service.bat # 本地服务启动
│   │   └── migrate_models.bat              # 模型迁移脚本
│   ├── deployment/         # 部署脚本
│   │   ├── deploy_docker.bat               # Docker部署
│   │   ├── docker-compose.yml              # Docker组合配置
│   │   ├── Dockerfile                      # Docker配置
│   │   ├── Dockerfile.cpu                  # CPU版本Docker配置
│   │   └── test_docker_deployment.py       # Docker部署测试
│   └── smoke_test.ps1                      # 烟雾测试脚本
│
├── server/                 # 后端服务
├── web/                   # 前端代码
├── models/                # AI模型
├── data/                  # 数据文件
├── cache/                 # 缓存文件
├── lib/                   # 库文件
├── prebuilt/              # 预编译文件
├── fine_tuned_models/     # 微调模型
├── trained_model/         # 训练模型
│
├── optimized_launcher.bat  # 优化的启动程序（主入口）
├── ollama.exe             # Ollama可执行文件
├── rag_system.py          # RAG系统
├── rag_system.log         # RAG系统日志
├── config.yaml            # 配置文件
├── strict_mode_test.py    # 严格模式测试
├── generated_landscape.png # 生成的风景图
└── landscape_result.html   # 风景生成结果
```

## 主要入口点

### 启动程序
- **`optimized_launcher.bat`** - 主要启动程序（推荐使用）
- `scripts/launchers/launcher.bat` - 原始启动器
- `scripts/launchers/启动后端服务.bat` - 后端服务启动

### 重要文档
- `docs/guides/OPTIMIZED_LAUNCHER_README.md` - 优化启动程序使用说明
- `PROJECT_STRUCTURE.md` - 本文件，项目结构说明

## 目录说明

### docs/
存放所有项目文档，包括使用指南、技术文档和说明文件

### scripts/
包含各种自动化脚本，按功能分类：
- **setup/** - 安装和配置相关脚本
- **launchers/** - 服务启动脚本  
- **deployment/** - 部署相关脚本

### 核心功能目录
- **server/** - 后端API服务
- **web/** - 前端用户界面
- **models/** - AI模型文件
- **data/** - 数据存储

## 使用建议

1. **日常使用**：直接运行 `optimized_launcher.bat`
2. **查看文档**：访问 `docs/` 目录下的相关指南
3. **开发调试**：使用 `scripts/` 目录下的相应脚本
4. **部署上线**：参考 `scripts/deployment/` 目录中的部署脚本