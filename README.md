# -Ollama Hub-
## 由AI协助开发（大家不要太认真，做个备份）

Ollama Hub 是一个功能完整的本地大语言模型（LLM）智能平台，集成了多模型对话、视觉理解、语音识别、知识检索（RAG）、模型微调等核心功能。平台采用前后端分离架构，支持离线运行，保护用户隐私。
### 核心特性

- **多模型对话**：支持 Ollama 管理的所有本地模型，可同时与多个模型进行群组讨论
- **视觉理解**：集成 Qwen3-VL-4B 视觉模型，支持图片分析、OCR 识别、场景描述
- **语音交互**：支持语音识别（ASR）和语音合成（TTS），实现语音对话
- **知识检索**：内置 RAG 检索系统，支持本地知识库问答
- **模型微调**：提供完整的模型训练和微调工具链
- **API 开放**：提供 RESTful API，支持第三方应用集成

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端层 (Web UI)                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │智能对话 │ │群组对话 │ │视觉理解 │ │模型管理 │ │  设置   │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                         端口: 8080                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       后端服务层                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Intelligent API │  │  Vision API     │  │   Ollama 服务   │ │
│  │   端口: 5001    │  │   端口: 5003    │  │   端口: 11434   │ │
│  │  - 对话管理     │  │  - 图片分析     │  │  - 模型运行     │ │
│  │  - RAG 检索     │  │  - OCR 识别     │  │  - 模型管理     │ │
│  │  - 记忆服务     │  │  - 场景描述     │  │                 │ │
│  │  - API Key      │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据存储层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ conversations│  │   memories  │  │  rag_index  │             │
│  │    .json    │  │    .json    │  │   BM25+语义 │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 功能模块

### 1. 智能对话

| 功能 | 说明 |
|------|------|
| 多模型切换 | 支持 Ollama 所有本地模型 |
| 流式输出 | 实时显示 AI 回复 |
| 对话历史 | 自动保存，支持续聊 |
| 世界观设定 | 自定义 AI 角色背景 |
| 图片理解 | 上传图片进行对话 |
| 全屏模式 | 沉浸式对话体验 |

### 2. 群组对话

| 功能 | 说明 |
|------|------|
| 多模型讨论 | 多个 AI 模型同时参与讨论 |
| 自动讨论 | AI 自主进行话题讨论 |
| 情感分析 | 实时分析对话情感倾向 |
| 观点聚类 | 自动归纳相似观点 |
| 语音合成 | 为 AI 回复生成语音 |

### 3. 视觉理解

| 功能 | 说明 |
|------|------|
| 图片分析 | 详细分析图片内容 |
| OCR 识别 | 提取图片中的文字 |
| 快速描述 | 生成图片简短描述 |
| 拖拽上传 | 支持拖拽图片到页面 |

### 4. 模型管理

| 功能 | 说明 |
|------|------|
| 模型列表 | 显示所有已安装模型 |
| 模型下载 | 从 Ollama 仓库下载模型 |
| 模型删除 | 删除不需要的模型 |
| 模型信息 | 查看模型参数和大小 |

### 5. 设置中心

| 功能 | 说明 |
|------|------|
| API Key 管理 | 生成和管理 API 密钥 |
| 主题切换 | 亮色/暗色主题 |
| 对话导出 | 导出对话记录 |
| 系统配置 | 调整系统参数 |

---

## 技术栈

### 前端

| 技术 | 用途 |
|------|------|
| HTML5 + CSS3 | 页面结构和样式 |
| JavaScript (ES6+) | 交互逻辑 |
| IndexedDB | 本地数据缓存 |
| Marked.js | Markdown 渲染 |
| Highlight.js | 代码高亮 |

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 后端语言 |
| Flask | Web 框架 |
| Ollama | 模型运行时 |
| Transformers | 模型推理 |
| PyTorch | 深度学习框架 |

### 模型

| 模型 | 用途 |
|------|------|
| Qwen2.5 系列 | 对话生成 |
| Qwen3-VL-4B | 视觉理解 |
| Silero TTS | 语音合成 |
| Whisper | 语音识别 |

---

## 目录结构

```
d:\Explor\ollma\
├── launcher.bat              # 一键启动脚本
├── config.yaml               # RAG 配置文件
├── rag_system.py             # RAG 检索系统
├── ollama.exe                # Ollama 运行时
│
├── server/                   # 后端服务
│   ├── intelligent_api.py    # 主 API 服务 (5001)
│   ├── qwen3_vl_service.py   # 视觉服务 (5003)
│   ├── rag_service.py        # RAG 服务
│   ├── memory_service.py     # 记忆服务
│   ├── api_key_service.py    # API Key 管理
│   ├── web_search_service.py # 网络搜索
│   ├── silero_tts_service.py # 语音合成
│   └── model_fine_tune.py    # 模型微调
│
├── web/                      # 前端界面
│   ├── index.html            # 主页面
│   ├── css/                  # 样式文件
│   │   ├── variables.css     # CSS 变量
│   │   ├── layout.css        # 布局样式
│   │   ├── chat.css          # 对话样式
│   │   ├── settings.css      # 设置样式
│   │   └── ...               # 其他模块
│   └── js/                   # JavaScript 模块
│       ├── app.js            # 主应用逻辑
│       ├── app.events.js     # 事件绑定
│       ├── app.chat.js       # 聊天功能
│       ├── app.group.js      # 群组功能
│       ├── vision-api.js     # 视觉 API
│       ├── hybrid_group_chat.js # 混合群聊
│       └── ...               # 其他模块
│
├── models/                   # 模型文件
│   ├── llm/                  # 语言模型
│   └── vision/               # 视觉模型
│
├── data/                     # 数据存储
│   ├── conversations.json    # 对话记录
│   ├── memories.json         # 记忆数据
│   └── rag_index/            # RAG 索引
│
└── docs/                     # 文档
    └── Action.md             # 更新日志
```

---

## 快速开始

### 1. 启动服务

双击 `launcher.bat` 或运行：

```bash
cd d:\Explor\ollma
.\launcher.bat
```

启动脚本会自动：
1. 启动 Ollama 服务 (端口 11434)
2. 启动后端 API 服务 (端口 5001)
3. 启动视觉服务 (端口 5003)
4. 启动 Web 服务器 (端口 8080)
5. 打开浏览器访问

### 2. 访问界面

打开浏览器访问：http://localhost:8080

### 3. 基本使用

1. **智能对话**：点击左侧"智能对话"，选择模型后开始对话
2. **群组对话**：点击"群组对话"，选择多个模型进行讨论
3. **视觉理解**：点击"视觉理解"，上传图片进行分析
4. **设置**：点击"设置"进行系统配置

---

## API 文档

### 基础地址

| 服务 | 地址 |
|------|------|
| 主 API | http://localhost:5001 |
| 视觉 API | http://localhost:5003 |
| Ollama | http://localhost:11434 |

### 主要端点

#### 对话 API

```bash
# 发送消息
POST /api/chat
Content-Type: application/json
{
    "message": "你好",
    "model": "qwen2.5:7b",
    "conversation_id": "conv_123"
}

# 流式对话
POST /api/chat/stream
Content-Type: application/json
{
    "message": "你好",
    "model": "qwen2.5:7b"
}
```

#### 视觉 API

```bash
# 检查服务状态
GET /api/vision/status

# 图片分析
POST /api/vision/analyze
Content-Type: multipart/form-data
image: [图片文件]
mode: analyze

# OCR 识别
POST /api/vision/ocr
Content-Type: multipart/form-data
image: [图片文件]
```

#### RAG API

```bash
# 检索知识
POST /api/rag/retrieve
Content-Type: application/json
{
    "query": "什么是机器学习？",
    "top_k": 5
}

# 获取状态
GET /api/rag/status
```

#### API Key 管理

```bash
# 生成 Key
POST /api/api-key/generate
Content-Type: application/json
{
    "name": "my-app",
    "expires_days": 30
}

# 列出所有 Key
GET /api/api-key/list

# 撤销 Key
DELETE /api/api-key/revoke/{key_id}
```

### 外部调用示例

```python
import requests

# 使用 API Key 调用
response = requests.post(
    "http://localhost:5001/api/chat/external",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer YOUR_API_KEY"
    },
    json={
        "message": "你好",
        "model": "qwen2.5:7b"
    }
)
print(response.json())
```

---

## 配置说明

### RAG 配置 (config.yaml)

```yaml
rag:
  data_dir: "./data/premium_classics"  # 知识库目录
  index_dir: "./data/rag_index"        # 索引目录
  chunk_size: 512                       # 分块大小
  chunk_overlap: 50                     # 分块重叠
  top_k: 8                              # 返回结果数
  score_threshold: 0.25                 # 相似度阈值
  semantic_weight: 0.0                  # 语义权重
  keyword_weight: 1.0                   # 关键词权重
  cache_size: 1000                      # 缓存大小
  cache_ttl: 7200                       # 缓存过期时间(秒)
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OLLAMA_MODELS | 模型存储路径 | D:\Explor\ollma\models |
| OLLAMA_HOST | Ollama 服务地址 | http://localhost:11434 |

---

## 常见问题

### Q: 服务启动失败？

1. 检查端口是否被占用：`netstat -ano | findstr :5001`
2. 检查 Python 环境：`python --version`
3. 检查依赖安装：`pip install flask flask-cors requests`

### Q: 模型加载失败？

1. 确认模型已安装：`ollama list`
2. 拉取模型：`ollama pull qwen2.5:7b`
3. 检查模型路径配置

### Q: 视觉服务不可用？

1. 检查视觉服务是否启动：访问 http://localhost:5003/api/vision/status
2. 检查模型文件是否存在：`models/vision/qwen3-vl-4b/`
3. 手动启动服务：`python server/qwen3_vl_service.py`

---

## 更新日志

详见 [Action.md](./Action.md)

---

## 许可证

本项目仅供学习和研究使用。
