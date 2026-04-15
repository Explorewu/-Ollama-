/**
 * 情感化设计模块 v2
 * 提供智能问候（模型实时生成）、状态反馈、快捷指令等功能
 */
const EmotionalDesign = {

    greetings: {
        morning: ['早上好！新的一天开始了，有什么我可以帮你的？', '早呀！今天想做些什么？', '早上好，准备好了吗？', '早安！来杯咖啡，开始工作吧~'],
        afternoon: ['下午好！需要我帮什么忙？', '下午啦，要不要来杯下午茶？', '下午好，继续加油！'],
        evening: ['晚上好！辛苦了一天~', '晚上好，放松一下吧！', '晚饭后的时光，想聊点什么？'],
        night: ['这么晚了还在忙？注意休息哦~', '夜深了，别熬太晚！', '还没睡？需要什么帮助？'],
        default: ['你好，有什么我可以帮你的？', '我准备好了，随时可以开始！', '需要我帮忙做什么？', '嗨，我们开始吧！']
    },

    getGreeting() {
        const hour = new Date().getHours();
        let category = 'default';
        if (hour >= 6 && hour < 12) category = 'morning';
        else if (hour >= 12 && hour < 18) category = 'afternoon';
        else if (hour >= 18 && hour < 22) category = 'evening';
        else if (hour >= 22 || hour < 6) category = 'night';
        const list = this.greetings[category];
        return list[Math.floor(Math.random() * list.length)];
    },

    commands: {
        '/new': {
            name: '新建对话',
            description: '开始一个新的对话',
            execute: () => {
                if (typeof Storage !== 'undefined') {
                    const model = window._currentModel || '';
                    const conv = Storage.createConversation(model);
                    window._currentConversationId = conv.id;
                    Storage.setCurrentConversationId(conv.id);
                    const history = document.getElementById('chatHistory');
                    if (history) history.innerHTML = '';
                }
            }
        },
        '/clear': {
            name: '清空对话',
            description: '清空当前对话的所有消息',
            execute: () => {
                const convId = window._currentConversationId;
                if (typeof Storage !== 'undefined' && convId) {
                    Storage.clearMessages(convId);
                    const history = document.getElementById('chatHistory');
                    if (history) history.innerHTML = '';
                }
            }
        },
        '/model': {
            name: '切换模型',
            description: '切换到指定模型，例如：/model qwen3.5:0.8b',
            execute: (_app, args) => {
                if (args && args.length > 0) {
                    const modelName = args.join(' ');
                    const select = document.getElementById('chatModelSelect');
                    if (select) {
                        const options = Array.from(select.options);
                        const match = options.find(o => o.value.toLowerCase().includes(modelName.toLowerCase()));
                        if (match) {
                            select.value = match.value;
                            select.dispatchEvent(new Event('change'));
                        }
                    }
                }
            }
        },
        '/help': {
            name: '帮助',
            description: '显示所有可用命令',
            execute: () => {
                const helpText = Object.entries(EmotionalDesign.commands)
                    .map(([cmd, info]) => `${cmd} - ${info.description}`)
                    .join('\n');
                alert('快捷命令：\n' + helpText);
            }
        },
        '/theme': {
            name: '切换主题',
            description: '切换亮色/暗色主题',
            execute: () => {
                document.documentElement.classList.toggle('theme-light');
            }
        }
    },

    parseAndExecuteCommand(message, app) {
        const trimmed = message.trim();
        if (!trimmed.startsWith('/')) return false;
        const parts = trimmed.split(' ');
        const cmd = parts[0].toLowerCase();
        const args = parts.slice(1);
        if (this.commands[cmd]) {
            this.commands[cmd].execute(app, args);
            return true;
        }
        app.showToast(`未知命令: ${cmd}，输入 /help 查看所有命令`, 'error');
        return true;
    },

    statusIndicators: {
        connection: {
            connected: { text: '已连接', color: '#10b981' },
            connecting: { text: '连接中...', color: '#f59e0b' },
            disconnected: { text: '已断开', color: '#ef4444' }
        },
        model: {
            loaded: { text: '已加载', color: '#10b981' },
            loading: { text: '加载中...', color: '#f59e0b' },
            unloaded: { text: '未加载', color: '#6b7280' }
        }
    },

    getStatusHTML(type, status) {
        const indicator = this.statusIndicators[type]?.[status];
        if (!indicator) return '';
        return `<span class="status-indicator" style="display:inline-flex;align-items:center;gap:6px;">
            <span class="status-dot" style="width:8px;height:8px;border-radius:50%;background:${indicator.color};animation:pulse 2s infinite;"></span>
            <span style="color:${indicator.color};font-size:12px;">${indicator.text}</span>
        </span>`;
    },

    addAnimations() {
        if (document.getElementById('emotional-styles')) return;
        const style = document.createElement('style');
        style.id = 'emotional-styles';
        style.textContent = `
            @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.6;transform:scale(1.1)} }
            @keyframes typing { 0%,60%,100%{opacity:.3} 30%{opacity:1} }
            .typing-dot { animation: typing 1.4s infinite; }
            .typing-dot:nth-child(2) { animation-delay: .2s; }
            .typing-dot:nth-child(3) { animation-delay: .4s; }
            @keyframes greetingSlideIn { from{transform:translateY(20px);opacity:0} to{transform:translateY(0);opacity:1} }
            @keyframes greetingSlideOut { from{transform:translateY(0);opacity:1} to{transform:translateY(-20px);opacity:0} }
            .smart-greeting-toast {
                position:fixed; bottom:80px; left:50%; transform:translateX(-50%);
                z-index:9999; padding:14px 24px; border-radius:16px;
                background:rgba(30,30,40,0.92); color:#e8e8f0; font-size:14px;
                box-shadow:0 8px 32px rgba(0,0,0,0.4); backdrop-filter:blur(12px);
                animation:greetingSlideIn .4s ease; max-width:400px; text-align:center;
                border:1px solid rgba(255,255,255,0.08);
            }
            .smart-greeting-toast.hiding { animation:greetingSlideOut .3s ease forwards; }
        `;
        document.head.appendChild(style);
    },

    getThinkingAnimation() {
        return `<div class="thinking-indicator" style="display:flex;align-items:center;gap:4px;padding:8px 0;">
            <span class="typing-dot" style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.6);"></span>
            <span class="typing-dot" style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.6);"></span>
            <span class="typing-dot" style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.6);"></span>
        </div>`;
    },

    init(app) {
        console.log('🎨 情感化设计模块 v2 已加载');
        this.addAnimations();
        SmartGreeting.init(app);
    }
};

/**
 * SmartGreeting - 智能问候系统
 * 
 * 核心机制：
 * 1. 模型空闲时调用后端API生成个性化问候语
 * 2. 存储到localStorage（带过期时间）
 * 3. 空闲超时或定时弹出
 * 4. 自动清理过期消息释放内存
 */
const SmartGreeting = {
    STORAGE_KEY: 'smart_greetings',
    IDLE_THRESHOLD: 5 * 60 * 1000,
    GENERATE_COOLDOWN: 10 * 60 * 1000,
    MAX_CACHE_SIZE: 5,
    CHECK_INTERVAL: 60 * 1000,

    _app: null,
    _lastActivity: Date.now(),
    _lastGenerate: 0,
    _isGenerating: false,
    _checkTimer: null,
    _activityListeners: [],

    init(app) {
        this._app = app;
        console.log('💡 智能问候系统已初始化');

        this._bindActivityTracking();
        this._cleanupExpired();
        this._startPeriodicCheck();

        setTimeout(() => this._tryGenerateIfNeeded(), 3000);
    },

    _bindActivityTracking() {
        const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
        const handler = () => { this._lastActivity = Date.now(); };
        events.forEach(evt => {
            document.addEventListener(evt, handler, { passive: true });
        });
        this._activityListeners = events.map(evt => ({ event: evt, handler }));
    },

    _isIdle() {
        return (Date.now() - this._lastActivity) > this.IDLE_THRESHOLD;
    },

    _getCache() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch {
            return [];
        }
    },

    _saveCache(greetings) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(greetings));
        } catch {
            // localStorage满了，清理一半
            const half = greetings.slice(Math.floor(greetings.length / 2));
            try { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(half)); } catch {}
        }
    },

    _cleanupExpired() {
        const now = Date.now() / 1000;
        let cache = this._getCache();
        const before = cache.length;
        cache = cache.filter(g => !g.expires_at || g.expires_at > now);
        if (cache.length !== before) {
            this._saveCache(cache);
        }
        // 后端也清理
        const apiBase = this._getApiBase();
        if (apiBase) {
            fetch(`${apiBase}/api/greeting/cleanup`, { method: 'POST' }).catch(() => {});
        }
        return cache;
    },

    _getApiBase() {
        const host = window.location.hostname || 'localhost';
        return `http://${host}:5001`;
    },

    async _tryGenerateIfNeeded() {
        if (this._isGenerating) return;
        const now = Date.now();
        if (now - this._lastGenerate < this.GENERATE_COOLDOWN) return;

        const cache = this._getCache();
        const undisplayed = cache.filter(g => !g.displayed);
        if (undisplayed.length >= 2) return;

        await this._generateGreeting('time');
    },

    async _generateGreeting(type = 'time', context = null) {
        if (this._isGenerating) return null;
        this._isGenerating = true;
        this._lastGenerate = Date.now();

        try {
            const apiBase = this._getApiBase();
            const model = this._app?.state?.selectedModel || '';
            const resp = await fetch(`${apiBase}/api/greeting/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, context, model })
            });

            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            if (data.success && data.data) {
                const greeting = data.data;
                this._addToCache(greeting);
                console.log(`💡 智能问候已生成: ${greeting.content}`);
                return greeting;
            }
        } catch (e) {
            console.warn('智能问候生成失败，使用备用:', e.message);
            return this._generateFallback(type);
        } finally {
            this._isGenerating = false;
        }
        return null;
    },

    _generateFallback(type) {
        const greeting = EmotionalDesign.getGreeting();
        const now = Date.now() / 1000;
        const data = {
            id: `fb_${Date.now()}`,
            content: greeting,
            type: type,
            period: this._getTimePeriod(),
            generated_at: now,
            scheduled_at: now + 30,
            displayed: false,
            expires_at: now + 1800,
        };
        this._addToCache(data);
        return data;
    },

    _getTimePeriod() {
        const hour = new Date().getHours();
        if (hour >= 6 && hour < 12) return 'morning';
        if (hour >= 12 && hour < 18) return 'afternoon';
        if (hour >= 18 && hour < 22) return 'evening';
        return 'night';
    },

    _addToCache(greeting) {
        let cache = this._getCache();
        cache.push(greeting);
        cache.sort((a, b) => (a.scheduled_at || 0) - (b.scheduled_at || 0));
        if (cache.length > this.MAX_CACHE_SIZE) {
            cache = cache.slice(-this.MAX_CACHE_SIZE);
        }
        this._saveCache(cache);
    },

    _startPeriodicCheck() {
        if (this._checkTimer) clearInterval(this._checkTimer);
        this._checkTimer = setInterval(() => {
            this._checkAndDisplay();
            if (this._isIdle()) {
                this._tryGenerateIfNeeded();
            }
        }, this.CHECK_INTERVAL);
    },

    _checkAndDisplay() {
        const now = Date.now() / 1000;
        const cache = this._cleanupExpired();
        const pending = cache.filter(g =>
            !g.displayed &&
            g.scheduled_at &&
            g.scheduled_at <= now &&
            (!g.expires_at || g.expires_at > now)
        );

        if (pending.length > 0) {
            this._displayGreeting(pending[0]);
        }
    },

    _displayGreeting(greeting) {
        // 标记为已显示
        let cache = this._getCache();
        const idx = cache.findIndex(g => g.id === greeting.id);
        if (idx !== -1) {
            cache[idx].displayed = true;
            this._saveCache(cache);
        }

        // 后端也标记
        const apiBase = this._getApiBase();
        fetch(`${apiBase}/api/greeting/mark_displayed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: greeting.id })
        }).catch(() => {});

        // 更新聊天页欢迎消息
        const welcomeBubble = document.querySelector('#chatHistory .message-bubble');
        if (welcomeBubble) {
            welcomeBubble.textContent = greeting.content;
        }

        // 弹出Toast
        this._showGreetingToast(greeting.content);

        // 清理已显示的旧消息
        setTimeout(() => this._cleanupDisplayed(), 5000);
    },

    _showGreetingToast(content) {
        // 移除已有的
        document.querySelectorAll('.smart-greeting-toast').forEach(el => el.remove());

        const toast = document.createElement('div');
        toast.className = 'smart-greeting-toast';
        toast.textContent = content;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    _cleanupDisplayed() {
        let cache = this._getCache();
        const before = cache.length;
        // 保留未显示的，已显示的删除
        cache = cache.filter(g => !g.displayed);
        if (cache.length !== before) {
            this._saveCache(cache);
        }
    },

    // 手动触发空闲问候
    async triggerIdleGreeting() {
        if (this._isIdle()) {
            const greeting = await this._generateGreeting('idle');
            if (greeting) {
                this._displayGreeting(greeting);
            }
        }
    },

    // 手动触发上下文问候
    async triggerContextGreeting(context) {
        const greeting = await this._generateGreeting('context', context);
        if (greeting) {
            this._displayGreeting(greeting);
        }
    },

    destroy() {
        if (this._checkTimer) {
            clearInterval(this._checkTimer);
            this._checkTimer = null;
        }
        this._activityListeners.forEach(({ event, handler }) => {
            document.removeEventListener(event, handler);
        });
        this._activityListeners = [];
    }
};

window.EmotionalDesign = EmotionalDesign;
window.SmartGreeting = SmartGreeting;
