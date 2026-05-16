# Action Log

## 2026-05-11: 前端冗余文件清理

### 问题
前端存在大量未被引用的文件和重复功能代码，导致代码库混乱、维护困难。

### 清理内容
1. **删除 js/app/ 目录（12个文件）**：avatar.js, behavior-contract.js, chat-background.js, conversation.js, group-chat.js, init.js, message-render.js, message-send.js, settings-ui.js, sidebar.js, stream-recovery.js, tts.js - 功能已在index.html内联实现
2. **删除 js/core/ 未引用文件（7个）**：app.events.js, app.group.js, app.persona.js, app.search.js, app.settings.js, app.v3.js, query_loop_bridge.js
3. **保留并重建 js/core/ 被引用文件（3个）**：svg_icons.js, app.feature_toggle.js, query_loop.js - 被index.html引用，误删后重建
4. **删除 js/services/ 冗余文件（2个）**：health_monitor.js（保留v3）, module_manager.js
5. **删除 css/legacy/ 未引用文件（36个）**：仅保留被主题变体使用的4个文件（chat-input-artistic.css, chat-input-modern.css, music.css, settings-artistic.css）

### 收益
- 减少约50个冗余文件
- 代码库更清晰，避免维护困惑
- 消除HealthMonitor重复定义冲突

## 2026-05-11: 音乐模块前端API对齐与系统性排查修复

### 问题
音乐模块(music_ui.js)与播放器核心(music_player.js)存在严重的API不匹配，导致模块无法初始化和交互。技能模块正常。

### 修复内容
1. **service.state→getState()**：music_ui.js访问不存在的state属性，改为调用getState()方法
2. **事件名对齐**：MusicPlayer发出onPlay/onPause/onTrackChange等，MusicUI监听play/pause/trackChange，7/8事件名不匹配，全部加on前缀
3. **方法名对齐**：seek(pct)→seekByProgress(pct)、prev()→previous()、setMode()→setPlayMode()、play(trackId)→playTrack(idx)、scan()→scanLibrary()、getPlaylists()→fetchPlaylists()、getLibrary()→fetchLibrary()
4. **添加toggleMute()**：MusicPlayer新增muted状态和toggleMute()方法
5. **播放模式名**：repeat→loop、repeat-one→single
6. **Dock导航**：添加音乐图标入口
7. **进度数据**：data.current→data.currentTime

## 2026-05-11: GGUF调用流程性能优化与Bug修复

### 问题
GGUF模型调用存在严重性能问题：单次请求触发4次完整磁盘扫描，llama-server启动阻塞最长300秒。

### 修复内容（local_model_loader.py）
1. **发现缓存**：`_discover_gguf_models()`/`_discover_safetensors_models()` 添加30秒TTL缓存，磁盘扫描从每次40ms降至0ms（命中时）
2. **消除冗余**：`is_local_model_available()` 不再重复调用 `get_gguf_model_path()`
3. **启动优化**：`STARTUP_TIMEOUT` 从300s降至120s，轮询间隔自适应（0.5s→1s→2s）
4. **匹配安全**：模糊匹配从 `in` 子串改为分隔符边界匹配，防止 `qwen3` 误匹配 `qwen3.5-9b-uncensored`
5. **健康检查**：连续2次失败才杀进程，避免长请求时误杀
6. **并发安全**：`_get_llama_server()` 添加per-model锁，防止重复启动
7. **搜索目录**：移除 `~/.ollama/models`（blob目录无GGUF文件，扫描极慢）
8. **卸载精确**：`unload_model()` key匹配要求后缀为纯数字，防止误删

## 2026-05-12: 动态Favicon状态管理器 + 启动脚本修复

### 问题
1. 浏览器标签页图标是静态emoji，无法反映模型实时状态
2. 启动脚本端口冲突时无法自动恢复

### 改动
1. **FaviconManager**（index.html）：根据模型8种状态（idle/thinking/searching/generating/summarizing/answering/done/error/unavailable）动态生成SVG文字图标，每种状态有独立颜色、字体和CSS动画（呼吸/旋转/脉冲/抖动）
2. **updateStage钩子**：FaviconManager.setState(stage) 接入状态变更事件
3. **健康监听**：HealthMonitor检测到所有服务不可用时自动切换unavailable状态
4. **start_all.bat**：添加 `--force` 参数，端口冲突时自动停旧服务重启

### 修复
- KnowledgeGraphPanel变量声明被误删导致searchInput未定义：恢复overlay/panel/searchInput等7个DOM引用声明

## 2026-05-12: 模型可用性检查统一标准化

### 问题
模型可用性检查逻辑分散在 chat.py 和 voice_call_service.py 中，各自直接调用 local_model_loader 和 model_registry，导致：
1. 降级逻辑不一致（chat.py 已用 model_availability.py，voice_call_service.py 仍直接调用）
2. 冗余的 is_gguf 重复检查（generate_response 内部函数中重复获取）
3. 缺少 Ollama 前置检查（voice_call_service 直接发 HTTP 请求才知道不可用）

### 改动
1. **voice_call_service.py**：`_try_local_model_stream` 改用 `check_model_availability()`，保留 ImportError 降级到旧路径；`_try_ollama_stream` 新增 Ollama 前置可用性检查
2. **chat.py**：移除 `generate_response` 和 `_handle_chat` 非流式路径中的冗余 `is_gguf = is_gguf_model(model)`（外层已获取）；`_handle_auto_tool_call_stream` 和 `_handle_auto_tool_call_non_stream` 改用 `check_model_availability()`，ImportError 时降级到旧路径

## 2026-05-12: 对话组标签栏样式重设计 + 初始化时序修复

### 问题
1. 对话组标签栏样式简陋，缺乏精致感。
2. 对话组标签栏始终为空（`<!-- 动态填充 -->`），因为初始化代码在普通 `<script>` 中同步执行，此时 `defer` 加载的 `unified_conv_group.js` 尚未执行，`UnifiedConvGroup` 为 `undefined`，导致 `if` 判断失败，初始化代码从未运行。

### 改动
1. **样式重设计**（"温润精致"风格）：
   - 标签栏背景改为 `linear-gradient(180deg, var(--bg-primary), var(--bg-secondary))` 渐变
   - 标签增加 `font-weight: 450` 和 `letter-spacing: 0.01em` 优化字重
   - 激活标签增加底部细线指示器（`::after` 伪元素）
   - 颜色圆点 hover 时放大 1.15x，激活时带光晕阴影
   - "+" 按钮 hover 时 SVG 旋转 90° 动画
   - 右键菜单增加 `backdrop-filter: blur(12px)` 毛玻璃效果
   - 所有过渡动画统一为 `cubic-bezier(0.25, 1, 0.5, 1)` 缓动曲线
2. **初始化时序修复**：将对话组系统初始化代码包裹在 `document.addEventListener('DOMContentLoaded', ...)` 中，确保在 `defer` 脚本执行完毕后再初始化。

## 2026-05-14: 前端直连 Ollama 全部改为后端代理

### 问题
前端多处代码直接请求 Ollama 的 11434 端口，导致 CORS 跨域错误。浏览器拦截了跨域请求，但后端代理（5001 端口）配了 CORS 头所以没问题。

### 改动
1. **api.js**：移除 `baseUrl`（11434）配置，`request()` 全部走 `backend` 服务；`checkHealth()` 改用 `/api/health`；`getAllModels()`/`pullModel()`/`generate()` 的 `baseUrl` 全部改为 `apiBaseUrl`
2. **unified_client.js**：移除 `ServiceConfig.ollama` 服务配置，前端不再维护 Ollama 直连地址
3. **group_chat_enhanced.js**：`fetch` 从 `localhost:11434/api/chat` 改为 `localhost:5001/api/ollama/chat`
4.5. **vision-api.js**：`fetch` 从 `localhost:11434/api/generate` 改为 `localhost:5001/api/generate`
6. **health_monitor.v3.js**：回退配置中 ollama 的 `baseUrl` 从 11434 改为 5001
7. **ollama_proxy.py**：新增 `/api/ollama/chat` 路由，转发到 Ollama 的 `/api/chat`（避免与后端主聊天路由冲突）

## 2026-05-15: 音乐播放器CSS UI重设计

### 改动（music.css）
1. **环境光晕**：新增 `.music-ambient-glow`，blur(80px)背景光，播放时4s呼吸脉冲动画，暗色模式独立参数
2. **封面呼吸**：`.music-cover-frame.playing` 添加 scale(1→1.02→1) 4s呼吸动画
3. **波形可视化器**：重构为双层结构（bars+reflection），圆角顶部、渐变色、变化宽度、底部倒影遮罩
4. **简化列表**：6列→4列(36px 1fr 120px 60px)，artist合并为track副标题，hover显示播放按钮替代actions列
5. **空状态增强**：图标72px、间距加大、新增CTA按钮样式
6. **曲目切换过渡**：`.transitioning` 类实现淡出+位移（info）和缩放（cover）
7. **进度条渐变**：fill改为primary→primary-light渐变，thumb添加glow阴影
8. **MiniBar**：顶部border-image渐变线，进度条渐变填充，thumb发光
9. **播放列表激活**：`.active` 左侧3px主色边框+背景提升+封面阴影
10. **搜索框**：focus-within时宽度从220px扩展到280px
11. 新增 `--music-primary-light` 变量支持渐变效果，响应式断点适配4列

## 2026-05-15: 技能与音乐模块移入设置页

### 问题
技能管理和音乐播放器作为独立页面占据侧边坞导航位，但使用频率低于对话/模型等核心功能，导致导航栏臃肿。

### 改动
1. **侧边坞精简**：移除「技能」和「音乐」两个导航项，坞内仅保留对话/模型/群聊/语音/设置5项
2. **设置页入口**：新增「技能管理」和「音乐播放器」入口卡片（与CEEE/CISECG等引擎入口风格一致）
3. **覆盖层面板**：新增 `#skillsOverlay` 和 `#musicOverlay`，点击入口弹出全屏覆盖层，关闭按钮+遮罩点击关闭
4. **页面容器移除**：删除 `#page-skills` 和 `#page-music` 独立页面容器
5. **MusicUI适配**：`_createDomStructure`/`_cacheElements`/`show`/`hide` 优先查找 `#musicOverlayContent`，降级到 `#page-music`；minibar展开按钮改为打开overlay
6. **CSS选择器扩展**：`#page-skills`→`#page-skills, #skillsOverlay`；`#page-music`→`#page-music, #musicOverlayContent`
7. **事件绑定**：main.js 新增 settingSkillsEntry/settingMusicEntry 点击处理，含SkillManager初始化和MusicUI初始化

## 2026-05-15: 聊天气泡样式切换无效修复

### 问题
设置页中「聊天气泡」下拉框切换（柔和卡片/磨砂玻璃/极简留白/精致描边）无效果。

### 原因
基础样式 `.message-bubble` 直接使用固定值（如 `var(--bg-primary)`），而气泡样式变量选择器 `body[data-bubble-style] .message-bubble` 虽然定义了新变量值，但基础样式中没有使用这些变量，导致变量更新后样式不变。

### 修复（main.css）
1. `.message-bubble` 基础样式改用气泡变量：`background: var(--chat-bubble-ai-bg, var(--bg-primary))`
2. `.bubble-segment` 同样改用气泡变量
3. `.message-row.user .message-bubble` 改用 `var(--chat-bubble-user-bg, ...)`
4. `.message-row.ai .message-bubble` 改用 `var(--chat-bubble-ai-bg, ...)`
5. `border-radius`/`border-color`/`box-shadow` 同样改用对应变量

现在切换气泡样式时，CSS变量值更新，气泡外观会立即响应变化。

## 2026-05-15: CSS变量与设置项一致性修复

### 问题
检查发现多处CSS变量定义但基础样式未使用、设置项实现不完整等问题。

### 修复内容

**1. 头像样式CSS变量未使用（main.css）**
- `.message-avatar` 基础样式改用CSS变量：`border-radius: var(--chat-avatar-radius, 50%)`
- 添加 `border` 和 `box-shadow` 变量支持

**2. 主题基调设置实现不完整（main.js + main.css）**
- JS: 改用 `document.body.dataset.themeTone = uiSettings.themeTone || 'balanced'`
- CSS: 新增 `body[data-theme-tone="calm/contrast/balanced"]` 选择器定义 `--text-secondary` 变量

**3. 气泡样式"soft"缺少显式定义（main.css）**
- 新增 `body[data-bubble-style="soft"]` 选择器，显式定义默认气泡变量

**4. 清理未使用设置项（main.js）**
- 移除 `uiSettings.reasoningSummary` 默认值（无UI控件且未被使用）

## 2026-05-15: 模型反馈与字体优化

### 问题
1. 代码块样式完全缺失，Markdown渲染器生成 `.code-block` 等类名但CSS无定义
2. 流式传输卡顿，渲染频率过高
3. 字体渲染效果不够优雅，缺少系统级优化

### 修复内容

**1. 代码块与消息内容样式（main.css）**
- 新增 `.code-block` 完整样式：圆角边框、语言标签头、复制按钮
- 新增 `.code-content` 代码内容区：等宽字体、行高、tab-size
- 新增代码语法高亮色：`.code-keyword`/`.code-string`/`.code-number` 等，支持深色模式
- 新增 `.answer-content` 消息内容样式：标题/列表/引用/表格/链接
- 新增 `.inline-code` 内联代码样式
- 新增 `.thinking-chain` 思考链折叠面板样式

**2. 流式传输优化（api.js）**
- BATCH_INTERVAL: 16ms → 32ms（降低渲染频率）
- MAX_BATCH_SIZE: 50 → 80（增大批量大小）
- 新增 MIN_FLUSH_CHARS: 20（最小刷新字符数）
- 新增 `scheduleRender()` 使用 requestAnimationFrame 调度渲染
- 新增 `findSentenceBoundary()` 智能句子边界检测

**3. 字体系统优化（main.css）**
- 新增字体变量：`--font-sans`/`--font-mono`/`--font-display`
- 新增字体大小层级：`--text-xs` 到 `--text-3xl`
- 新增行高/字重/字间距层级变量
- body 新增字体渲染优化：
  - `-webkit-font-smoothing: antialiased`
  - `-moz-osx-font-smoothing: grayscale`
  - `text-rendering: optimizeLegibility`
  - `font-feature-settings: 'kern' 1, 'liga' 1, 'calt' 1`
- 代码字体禁用连字：`font-feature-settings: 'liga' 0`
