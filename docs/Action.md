# 项目重构记录

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

## 2026-02-24 - 欢迎界面 Canvas 动画升级

### 目标
将欢迎页面的静态 SVG 马群改为具象风格 Canvas 动画

### 新增文件
- `web/js/features/horse-canvas.js` - Canvas 动画引擎
  - 具象风格马匹渲染（渐变颜色、肌肉线条）
  - 腿部奔跑动画、鬃毛尾巴飘动
  - 星辰、粒子效果（尘土飞扬）
  - 月亮光晕、雾气层
  - 鼠标悬停加速交互

### 修改文件
- `web/index.html` - 添加 Canvas 元素，加载 JS
- `web/css/welcome.css` - 添加 Canvas 样式
- `web/js/core/app.js` - 初始化/销毁 Canvas 动画

### 核心改动
1. 用 Canvas 替代静态 SVG，支持实时渲染
2. 马匹有颜色渐变、高光阴影，更真实
3. 添加粒子系统模拟尘土效果
4. 鼠标移动时马群加速，增强交互
5. 进入应用时销毁动画释放资源

### 收益
- 动画流畅无卡顿
- 视觉效果更震撼
- 交互体验更好
- 无需第三方依赖

---

## 2026-02-16 - 智能服务连接优化

### 目标
优化服务连接架构，提升性能和稳定性

### 新增文件
- `server/service_connection_manager.py` - 后端服务连接管理器
- `web/js/api/unified_client.js` - 前端统一 API 客户端
- `web/js/services/health_monitor.js` - 前端健康监控服务

### 核心功能
**后端连接管理器**：
- HTTP 连接池管理（复用连接）
- 健康检查心跳（实时监控）
- 自动重连 + 熔断降级
- 统一超时配置

**前端统一客户端**：
- 请求去重（避免重复请求）
- 智能缓存（减少网络请求）
- 自动重试（提升可靠性）
- 请求队列管理（控制并发）

**健康监控**：
- 实时服务状态监控
- 延迟监控和告警
- 故障自动检测
- 性能趋势分析

### 修改文件
- `server/intelligent_api.py` - 集成连接管理器，新增 `/api/connection/status`、`/api/connection/reset` 端点
- `web/js/api/api.js` - 使用统一客户端，新增健康监控相关方法
- `web/js/services/module_manager.js` - 注册新模块
- `web/index.html` - 加载新 JS 文件

### 收益
- 连接复用减少开销
- 请求缓存提升响应速度
- 熔断机制防止雪崩
- 健康监控及时发现问题

---

## 2026-02-14 - 高优先级重构完成

### 1. ASR/语音识别服务重构
**目标**：消除 whisper_service.py、local_whisper_service.py、qwen3_asr_service.py 的重复代码

**方案**：
- 创建 `server/asr/` 目录结构
- 实现 `base.py` - 抽象基类 `ASRService`、通用数据类、`AudioProcessor`
- 实现 `factory.py` - 工厂模式，支持动态注册和创建引擎
- 迁移 `whisper_ollama.py` - 第一个具体实现

**收益**：代码复用率提升，消除数据类、音频处理、日志配置重复

---

### 2. 模型下载工具重构
**目标**：整合 download_models.py、download_with_mirror.py、re_download.py

**方案**：
- 创建 `server/model_downloader.py` - 统一 `ModelDownloader` 类
- 支持多镜像源自动切换（4个源按优先级）
- 内置断点续传、进度回调、错误重试
- 单例模式，简洁 API

**收益**：从3个文件减少到1个，代码减少约60%

---

### 3. image_server.py 安全加固与代码规范
**目标**：修复安全漏洞、统一响应格式、完善日志

**修复内容**：
- `/api/cache/clear` 添加 `@require_api_key` 认证保护
- 错误响应统一添加 `code` 字段（`UNKNOWN_MODEL`、`MODEL_LOAD_FAILED`）
- scheduler 配置失败添加日志输出
- 清理多余空行，保持代码整洁

---

### 4. 视觉理解模块 Bug 修复
**目标**：修复前后端 API 不匹配、响应格式不统一、并发安全问题

**修复内容**：
- **vision-api.js**：修正 `/api/image/models` → `/api/models`，`/api/image/generate` → `/api/generate`
- **qwen3_vl_service.py**：错误响应统一添加 `code` 字段
- **qwen3_vl_service.py**：添加全局异常处理中间件
- **vision-api.js**：`fetch timeout` 改用 `AbortController` 实现
- **qwen3_vl_service.py**：双重检查锁定修复，锁内二次检查 `model_loaded`

---

## 后续建议
1. 继续迁移 whisper_local 和 qwen3 到 asr/ 模块
2. 逐步替换旧的下载脚本引用为新 model_downloader
3. 进行 RAG 系统重构
