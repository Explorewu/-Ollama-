# 项目重构记录

## [2026-05-12] 产品侧壁垒 Phase 1: 统一记忆层 + 知识飞轮

**目标**: 构建产品侧壁垒，通过数据沉淀和体验差异化提升迁移成本和技术独占性。

**架构**: 读写分离，读并行，写异步。读路径并行检索TEMG+KG+Memory+RAG四引擎，写路径全部后台线程零阻塞。

**新增模块**:
1. `server/unified_memory.py` — 统一记忆层，ThreadPoolExecutor并行查询，LRU缓存30sTTL，后台异步写入，200ms超时硬限制
2. `server/knowledge_flywheel.py` — 知识飞轮，SQLite增量索引，BM25检索，目录轮询监控，自动索引新增/修改文件
3. `server/api/unified_memory.py` — 统一记忆API蓝图
4. `server/api/knowledge_flywheel.py` — 知识飞轮API蓝图

**Chat流水线改造**:
- `_build_chat_messages`中TEMG串行recall→UnifiedMemoryLayer并行query(TEMG+KG+Memory+RAG)
- 对话结束后分散的`_temg_ingest_turn`+`_kg_extract_if_available`→`_unified_memory_store`统一异步写入
- 降级保障：UnifiedMemoryLayer不可用时自动回退到原分散调用

**API端点**:
- `POST /api/unified-memory/query` — 并行记忆查询
- `GET /api/unified-memory/stats` — 记忆统计
- `POST /api/unified-memory/search` — 跨引擎搜索
- `POST /api/flywheel/index` — 索引目录
- `POST /api/flywheel/search` — 知识搜索
- `GET /api/flywheel/status` — 飞轮状态
- `POST/DELETE /api/flywheel/watch` — 目录监控管理

**修改文件**: server/api/chat.py, server/api/__init__.py, server/intelligent_api.py

## [2026-05-12] Phase 2: 基于数据的快速优化 — check_availability合并 + Fast Path

**数据驱动**: Phase 1 采集到真实timing数据，发现两大瓶颈：check_availability 4,117ms（同一接口调2次）+ AutoToolCaller对闲聊请求注入工具定义导致LLM调用慢12,000ms。

**优化内容**:
1. 合并 check_availability：用 `_get_ollama_model_names()` 一次调用同时判断可用性和模型存在性，省2,200ms
2. Fast Path：CASC意图分类结果传递到路由层，闲聊/问候/情感类意图跳过AutoToolCaller，省~10,000ms
3. `_build_chat_messages` 返回值增加 `casc_intent`，供路由层做分流决策
4. `_handle_auto_tool_call_non_stream` 补全 timing 采集（之前遗漏）

**优化效果**:
- check_availability: 4,117ms → 2,110ms (-49%)
- 总耗时: 22,825ms → 11,006ms (-52%)
- 闲聊请求确认走 Fast Path（无 tool_call_state）

**修改文件**: server/api/chat.py

## [2026-05-11] Phase 1: 请求流水线 Timing 采集中间件

**根因**: 系统无任何性能指标采集，所有优化只能猜测。首Token延迟可能来自Prompt构建阻塞而非推理。

**实现内容**:
1. 新增 `server/timing_collector.py` — 线程安全的计时采集器，单例模式
2. 修改 `server/api/chat.py` — 在请求流水线8个关键节点注入计时
3. 新增 `GET /api/chat/timing` API — 查询聚合统计/最近请求/清除数据
4. SSE 流末尾输出 `timing` 事件 — 前端可实时获取延迟数据

**采集节点**: input_parse → web_search → pre_enhance → temg_recall → casc_classify → context_compress → build_messages → manage_context → build_payload → check_availability → llm_first_token → stream_tok/s

**API用法**:
- `GET /api/chat/timing` — 聚合统计(avg/p95/max/min)
- `GET /api/chat/timing?action=recent&limit=20` — 最近请求明细
- `GET /api/chat/timing?action=clear` — 清除数据

**修改文件**: server/timing_collector.py(新), server/api/chat.py

## [2026-05-11] GPU加速优化 - 启用Vulkan + CPU/GPU混合加载

**根因**: Ollama日志显示 `Vulkan support disabled`，Intel Arc 140T GPU完全闲置，模型100%在CPU运行。

**修复内容**:
1. 设置系统环境变量 `OLLAMA_VULKAN=1`，启用Ollama Vulkan GPU加速
2. start_daemon.py 启动Ollama时注入 `OLLAMA_VULKAN=1`
3. CPU线程数 8→16（充分利用Ultra 9 285H全部核心）
4. GPU_LAYERS 99→40（CPU+GPU混合加载，避免集成GPU内存溢出）
5. GGUF_MODEL_CONFIG 增加 n_gpu_layers=40 配置
6. SemanticStreamBuffer: min_chunk 80→30, max_delay 120→80ms（减少首Token延迟）

**预期提升**: 首Token延迟 3-5倍，生成速度 3-5倍

**修改文件**: local_model_loader.py, config.py, chat.py, start_daemon.py

## [2026-05-10] 第二轮BUG修复 - 并发与数据处理问题

修复了用户指定的7个BUG，涉及并发安全、数据完整性、算法稳定性：

### 修复的问题

1. **BUG-022: memory_service.py 并发写入内存损坏** (高优先级)
   - 问题: 定义了 `_write_lock` 但从未使用，高并发时数据损坏
   - 修复: 添加 `_memory_lock = threading.Lock()`，在 `_load_all()` 和 `_save_all()` 中使用
   - 删除未使用的 `_write_queue` 和 `_write_lock`

2. **BUG-023: rag_system.py 向量数据库维度不匹配** (高优先级)
   - 问题: 索引加载时未验证向量维度与模型是否匹配
   - 修复: 在 `SemanticRetriever._search_index()` 和 `IndexManager.load_index()` 中添加维度验证
   - 维度不匹配时抛出明确错误，提示重新构建索引

3. **BUG-028: ceee_engine.py 稀疏区域选择逻辑缺陷** (中优先级)
   - 问题: 当所有邻居密度都>0时，不会选出任何稀疏区域，导致演化搜索多样性不足
   - 修复: 先检查是否有完全空闲（密度=0）的区域，有则优先返回

4. **BUG-029: context_compressor.py L3策略丢失历史信息** (中优先级)
   - 问题: 滑动窗口只保留最近轮次，丢弃的历史信息中可能有关键事实
   - 修复: 添加 `_extract_important_info()` 方法，从即将丢弃的消息中提取重要内容作为摘要

5. **BUG-030: knowledge_graph.py LLM提取失败静默忽略** (中优先级)
   - 问题: `logger.debug()` 级别太低，生产环境看不到错误信息
   - 修复: 改为 `logger.warning()`，并区分 HTTP错误、JSON解析失败、ImportError

6. **BUG-031: ciscg_engine.py N-gram模型数据稀疏** (低优先级)
   - 问题: 语料不足时 N-gram 模型不可靠
   - 修复: 添加平滑技术（Add-k smoothing），语料<10条时警告，词汇表固定大小

7. **BUG-032: init.js 本地存储键名格式不一致** (低优先级)
   - 问题: 硬编码字符串分散各处，维护困难
   - 修复: 定义 `StorageKeys` 常量对象统一管理，所有 localStorage 操作使用常量

**修复文件**:
- server/memory_service.py
- rag_system.py
- server/ceee_engine.py
- server/context_compressor.py
- server/knowledge_graph.py
- server/ciscg_engine.py
- web/js/app/init.js

## [2026-05-05] SELSS 自进化语言技能系统集成

采用分层扩展方案，在现有function_engine上构建六层SELSS架构：

### 架构
P1技能注册表(三级tier+生命力+SQLite) → P2语义检索(Ollama/GGUF/TF-IDF三级) → P3执行环路(调用-执行-反馈) → P4自进化(触发/蒸馏/沙箱) → P5治理(去重/淘汰/自适应) → P6前端(技能面板/教学/治理)

### 新增文件
- `server/skill_retriever.py` - 语义检索引擎
- `server/skill_execution.py` - 执行环路引擎
- `server/skill_evolution.py` - 自进化管理器
- `server/skill_governor.py` - 治理模块

### 修改文件
- `server/function_engine.py` - 扩展SkillRegistry(三级/生命力/SQLite持久化)
- `server/api/functions.py` - 新增30+条API路由
- `web/js/features/function_manager.js` - 新增SkillManager前端
- `web/js/core/query_loop.js` - 集成SkillExecutionAdapter
- `web/index.html` - 技能页面/导航/样式

### 关键设计
- 技能三级: atomic(原子) → logic(逻辑组合) → workflow(工作流)
- 生命力SVS: 频率×0.4 + 成功率×0.3 + 时效×0.2 + 年龄×0.1
- 进化触发: 失败补偿/组合成功/直接教学
- 沙箱验证: 重放测试+变异测试+静态检查
- 自适应控制: 根据准确率/延迟/Token动态调整检索参数

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
