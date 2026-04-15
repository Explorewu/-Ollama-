# 项目重构记录

## [2026-04-01] 接入 Qwen3.5-9B-Uncensored GGUF 模型

将 D:\Etertainment 目录下的 GGUF 模型接入系统：

### 实现方案
采用 **Ollama 注册方案**（无需安装额外依赖）：
1. 创建 Modelfile 指向 GGUF 文件路径
2. 使用 `ollama create` 命令注册模型
3. 系统自动通过现有 Ollama API 调用

### 新增/修改文件
- `Modelfiles/qwen3.5-9b-uncensored.modelfile` - 模型配置文件
- `Modelfiles/register_models.bat` - 添加注册命令
- `server/local_model_loader.py` - 添加 GGUF 支持（备用方案）
- `server/utils/config.py` - 添加 GGUF_MODEL_CONFIG

### 使用方式
```bash
# 注册模型到 Ollama
cd D:\Explore\ollma\Modelfiles
ollama create qwen3.5-9b-uncensored -f qwen3.5-9b-uncensored.modelfile

# API 调用
POST /api/chat {"model": "qwen3.5-9b-uncensored", "message": "你好"}
```

## [2026-03-07] Flask API 服务重构 (intelligent_api.py)

根据代码审查报告修复关键问题：

### 修复的问题
1. **模块级副作用** (高优先级)
   - 原代码在 import 时就初始化所有服务
   - 改用应用工厂模式 `create_app()`
   - 延迟初始化，支持测试和多实例

2. **CORS 安全配置** (高优先级)
   - 原配置 `"origins": "*"` 与 `supports_credentials: True` 冲突
   - 改为从环境变量读取允许的来源
   - 默认只允许 localhost

3. **路由与初始化混合** (中优先级)
   - `register_all_routes` 同时做路由注册和服务初始化
   - 分离为 `init_api_services()` 和 `register_routes()`

4. **服务失败处理** (中优先级)
   - 定义必需服务和可选服务
   - 必需服务失败时抛出异常
   - 可选服务失败仅警告

5. **环境变量支持**
   - `FLASK_ENV=development` 开启调试模式
   - `ALLOWED_ORIGINS` 配置 CORS 来源

### 新增功能
- `get_app()` 延迟初始化函数
- 全局错误处理器 (500, 404)
- 服务状态存储在 `app.services`

**修复文件**: server/intelligent_api.py

## [2026-03-06] 语音功能全面审查与修复

修复了语音服务模块中的多个严重bug：

### 修复的问题
1. **qwen3_tts_service.py** - 致命错误
   - `AutoModelForTextToSpeech` 类在 transformers 中不存在
   - `torch.no_grad()` 使用时未导入 torch
   - 重构为使用 `qwen_tts` 包，添加 edge-tts 降级方案

2. **qwen3_asr_service.py** - 变量作用域bug
   - `wf` 变量在 `with` 块外被使用，导致 AttributeError
   - 将 `duration = wf.getnframes() / 16000` 移入 `with` 块内

3. **silero_tts_service.py** - API兼容性问题
   - 直接 `import torch` 会在未安装时报错
   - 添加延迟导入和 edge-tts 降级方案
   - 修复 silero_tts API 调用方式

### 改进
- 所有 TTS 服务统一添加 `TTSResult` 数据类
- 添加 `audio_to_base64()` 方法用于 WebSocket 传输
- 添加 `check_status()` 方法用于服务状态监控
- 统一降级方案：优先使用本地模型，失败则使用 edge-tts

**修复文件**: server/qwen3_tts_service.py, server/qwen3_asr_service.py, server/silero_tts_service.py

## [2026-03-06] 修复 WebSocket 连接问题

解决语音通话页面"WebSocket未连接，无法发送消息"错误：

1. **根本原因** - 每次点击开始通话都创建新实例，导致连接不断重置
2. **实例复用** - 添加判断，只在首次创建 VoiceCall 实例
3. **错误处理** - 增强 _sendMessage 方法，区分连接状态（连接中/关闭中/已断开）
4. **用户提示** - 添加重连状态显示，错误自动恢复，字幕提示错误信息
5. **状态监控** - 完善状态回调，处理断开、重连失败等状态

**修复文件**: web/voice_call.html, web/js/features/voice_call.js
**测试**: 连接稳定性提升，错误提示清晰，自动重连机制生效

## [2026-03-05] 实现Qwen3语音通话功能

基于Qwen3-ASR + Qwen3.5-4B + Qwen3-TTS实现实时语音交互系统：

1. **Qwen3-TTS服务** - 新增语音合成模块，支持5种预设音色，97ms超低延迟
2. **语音通话服务** - WebSocket实时通信，单路通话，支持打断
3. **前端通话模块** - 音频采集、播放、可视化，独立通话页面
4. **启动脚本** - 一键启动，自动检查依赖和环境

**技术栈**: WebSocket + Qwen3系列模型 + 流式处理
**延迟**: 端到端约500ms，支持实时对话
**文件**: server/qwen3_tts_service.py, server/voice_call_service.py, web/voice_call.html, web/js/features/voice_call.js

## [2025-02-24] 重新设计输入框和发送按钮

对输入区域进行了现代化改造：

1. **圆形发送按钮** - 更现代的玻璃态设计
2. **动态波纹效果** - 输入框聚焦时的流动光效
3. **增强的悬停动画** - 按钮悬停时的脉冲效果
4. **统一设计语言** - 应用到普通聊天和群聊输入框

## [2025-02-24] 修复全屏模式样式问题

修复了两个问题：

1. **发送按钮变灰色** - 全屏模式下发送按钮样式未更新，现在使用统一设计
2. **全屏模式字体看不清** - 更新了全屏模式的输入框、按钮样式，使用主色调
3. **退出全屏按钮不明显** - 重新设计退出按钮，使用绿色主色调，更醒目

## [2025-02-24] 重绘马匹动画

重新设计了欢迎界面的马匹动画，使其更接近真实马匹形象：

1. **真实比例** - 头部、颈部、身体比例更接近真实马匹
2. **细节丰富** - 添加了马耳、鼻孔、嘴唇等细节
3. **腿部动画** - 四条腿独立运动，有膝关节弯曲效果
4. **鬃毛和尾巴** - 更自然的飘动效果，多条发丝
5. **肌肉质感** - 添加了高光和阴影，增强立体感

## [2025-02-24] 改用 SVG 动画

将欢迎界面的 Canvas 动画替换为纯 SVG 动画：

1. **删除 Canvas** - 移除了 horse-canvas.js 和 canvas 元素
2. **SVG 动画** - 使用 SMIL 动画实现马匹奔跑效果
3. **动态元素** - 星空闪烁、太阳呼吸、远山移动、尘土飞扬
4. **性能优化** - SVG 原生动画，无需 JavaScript 计算
5. **兼容性** - 更好的浏览器原生支持

## 2026-02-24 - 欢迎界面 Canvas 动画升级

### 目标
将欢迎页面的静态 SVG 马群改为具象风格 Canvas 动画

### 新增文件
- `web/js/features/horse-canvas.js` - Canvas 动画引擎
  - 具象风格马匹渲染（渐变颜色、肌肉线条）
  - 腿部奔跑动画、鬃毛尾巴飘动
  - 星辰、粒子效果（尘土飞扬）
  - 月亮光晕、雾气层
