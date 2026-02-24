const TokenStats = (() => {
    const STORAGE_KEY = 'token_stats_usage';

    function nowDateKey() {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    function nowMonthKey() {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        return `${yyyy}-${mm}`;
    }

    function loadUsage() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (!saved) {
                return {
                    daily: { date: nowDateKey(), prompt: 0, completion: 0, total: 0, calls: 0 },
                    monthly: { month: nowMonthKey(), prompt: 0, completion: 0, total: 0, calls: 0 }
                };
            }
            const parsed = JSON.parse(saved);
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (_) {
            return {
                daily: { date: nowDateKey(), prompt: 0, completion: 0, total: 0, calls: 0 },
                monthly: { month: nowMonthKey(), prompt: 0, completion: 0, total: 0, calls: 0 }
            };
        }
    }

    function normalizeUsage(usage) {
        const date = nowDateKey();
        const month = nowMonthKey();

        if (!usage.daily || usage.daily.date !== date) {
            usage.daily = { date, prompt: 0, completion: 0, total: 0, calls: 0 };
        }
        if (!usage.monthly || usage.monthly.month !== month) {
            usage.monthly = { month, prompt: 0, completion: 0, total: 0, calls: 0 };
        }
        usage.daily.prompt = Number(usage.daily.prompt || 0);
        usage.daily.completion = Number(usage.daily.completion || 0);
        usage.daily.total = Number(usage.daily.total || 0);
        usage.daily.calls = Number(usage.daily.calls || 0);

        usage.monthly.prompt = Number(usage.monthly.prompt || 0);
        usage.monthly.completion = Number(usage.monthly.completion || 0);
        usage.monthly.total = Number(usage.monthly.total || 0);
        usage.monthly.calls = Number(usage.monthly.calls || 0);

        return usage;
    }

    function saveUsage(usage) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(usage));
        } catch (_) {}
    }

    function getEnabled() {
        try {
            if (!window.ApiChat || typeof window.ApiChat.getConfig !== 'function') return false;
            const config = window.ApiChat.getConfig();
            return Boolean(config?.tokenTracking?.enabled);
        } catch (_) {
            return false;
        }
    }

    function ensureWidget() {
        let el = document.getElementById('tokenStatsWidget');
        if (el) return el;

        el = document.createElement('div');
        el.id = 'tokenStatsWidget';
        el.className = 'token-stats-widget';
        el.innerHTML = `
            <div class="token-stats-header">
                <div class="token-stats-title">TOKEN 统计</div>
                <button class="token-stats-close" type="button" aria-label="关闭">×</button>
            </div>
            <div class="token-stats-body">
                <div class="token-stats-row">
                    <div class="token-stats-label">今日</div>
                    <div class="token-stats-value" data-field="daily">0</div>
                </div>
                <div class="token-stats-row">
                    <div class="token-stats-label">本月</div>
                    <div class="token-stats-value" data-field="monthly">0</div>
                </div>
                <div class="token-stats-meta" data-field="meta"></div>
            </div>
        `;

        document.body.appendChild(el);

        const closeBtn = el.querySelector('.token-stats-close');
        closeBtn?.addEventListener('click', () => {
            try {
                if (window.ApiChat && typeof window.ApiChat.getConfig === 'function') {
                    const config = window.ApiChat.getConfig();
                    if (config?.tokenTracking) {
                        config.tokenTracking.enabled = false;
                        window.ApiChat.saveConfig?.();
                    }
                }
            } catch (_) {}
            update();
        });

        return el;
    }

    function formatNumber(n) {
        const num = Number(n || 0);
        if (num < 1000) return String(num);
        if (num < 1000000) return `${(num / 1000).toFixed(1)}k`;
        return `${(num / 1000000).toFixed(1)}m`;
    }

    function update() {
        const enabled = getEnabled();
        const el = ensureWidget();
        el.style.display = enabled ? 'block' : 'none';
        if (!enabled) return;

        const usage = normalizeUsage(loadUsage());

        const dailyTotal = usage.daily.total || (usage.daily.prompt + usage.daily.completion);
        const monthlyTotal = usage.monthly.total || (usage.monthly.prompt + usage.monthly.completion);

        el.querySelector('[data-field="daily"]').textContent = formatNumber(dailyTotal);
        el.querySelector('[data-field="monthly"]').textContent = formatNumber(monthlyTotal);

        const meta = el.querySelector('[data-field="meta"]');
        if (meta) {
            meta.textContent = `调用: 今日 ${usage.daily.calls} 次 · 本月 ${usage.monthly.calls} 次`;
        }
    }

    function recordUsage({ promptEvalCount = 0, evalCount = 0, calls = 1 } = {}) {
        if (!getEnabled()) return;

        const usage = normalizeUsage(loadUsage());
        const prompt = Math.max(0, Number(promptEvalCount || 0));
        const completion = Math.max(0, Number(evalCount || 0));
        const callCount = Math.max(0, Number(calls || 0));

        usage.daily.prompt += prompt;
        usage.daily.completion += completion;
        usage.daily.total += prompt + completion;
        usage.daily.calls += callCount;

        usage.monthly.prompt += prompt;
        usage.monthly.completion += completion;
        usage.monthly.total += prompt + completion;
        usage.monthly.calls += callCount;

        saveUsage(usage);
        update();
    }

    function init() {
        ensureWidget();
        update();
        setInterval(update, 5000);
    }

    return { init, update, recordUsage };
})();

window.TokenStats = TokenStats;
