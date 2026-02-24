/**
 * Ollama Hub - 主题管理模块
 * 
 * 功能：管理应用的主题模式（浅色/深色/跟随系统）
 * 支持系统主题切换监听和本地持久化
 * 优化：流畅的主题切换动画
 */

const ThemeManager = {
    // 主题模式常量
    THEMES: {
        LIGHT: 'light',
        DARK: 'dark',
        AUTO: 'auto'
    },

    // 主题变化事件名
    EVENT_THEME_CHANGE: 'themeChanged',
    
    // 过渡动画时长(ms)
    TRANSITION_DURATION: 300,

    /**
     * 初始化主题系统
     */
    init() {
        // 优先使用存储的主题设置
        const savedTheme = Storage.getTheme();
        this.applyTheme(savedTheme, false); // 初始化时不使用动画

        // 监听系统主题变化（仅在自动模式下）
        this.watchSystemTheme();

        // 监听存储变化（多标签页同步）
        this.watchStorageChanges();
    },

    /**
     * 应用主题
     * @param {string} theme - 主题名称
     * @param {boolean} animate - 是否使用过渡动画
     */
    applyTheme(theme, animate = true) {
        const root = document.documentElement;
        
        // 添加过渡类实现平滑切换
        if (animate) {
            this.addTransitionClass();
        }

        // 移除所有主题类
        root.removeAttribute('data-theme');

        switch (theme) {
            case this.THEMES.DARK:
                root.setAttribute('data-theme', 'dark');
                break;
                
            case this.THEMES.AUTO:
                // 使用系统主题
                if (this.matchesDarkMode()) {
                    root.setAttribute('data-theme', 'dark');
                }
                break;
                
            case this.THEMES.LIGHT:
            default:
                // 默认浅色主题，不设置属性
                break;
        }

        // 更新存储
        Storage.setTheme(theme);

        // 更新UI状态
        this.updateUIState(theme);

        // 触发主题变化事件
        this.dispatchThemeEvent(theme);
        
        // 移除过渡类
        if (animate) {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    this.removeTransitionClass();
                }, this.TRANSITION_DURATION);
            });
        }
    },

    /**
     * 更新主题选择器UI状态
     * @param {string} activeTheme - 当前激活的主题
     */
    updateUIState(activeTheme) {
        const themeOptions = document.querySelectorAll('.theme-option');
        
        themeOptions.forEach(option => {
            if (option.dataset.theme === activeTheme) {
                option.classList.add('active');
            } else {
                option.classList.remove('active');
            }
        });
    },

    /**
     * 获取当前系统是否处于深色模式
     * @returns {boolean}
     */
    matchesDarkMode() {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    },

    /**
     * 监听系统主题变化
     */
    watchSystemTheme() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        mediaQuery.addEventListener('change', (e) => {
            const currentTheme = Storage.getTheme();
            if (currentTheme === this.THEMES.AUTO) {
                this.applyTheme(this.THEMES.AUTO);
            }
        });
    },

    /**
     * 监听存储变化（多标签页同步）
     */
    watchStorageChanges() {
        window.addEventListener('storage', (e) => {
            if (e.key === Storage.STORAGE_KEYS.THEME) {
                const newTheme = e.newValue || this.THEMES.LIGHT;
                this.applyTheme(newTheme);
            }
        });
    },

    /**
     * 调度主题变化事件
     * @param {string} theme - 新主题
     */
    dispatchThemeEvent(theme) {
        const event = new CustomEvent(this.EVENT_THEME_CHANGE, {
            detail: { theme }
        });
        window.dispatchEvent(event);
    },

    /**
     * 切换到下一个主题
     */
    toggleTheme() {
        const currentTheme = Storage.getTheme();
        const themeOrder = [this.THEMES.LIGHT, this.THEMES.DARK, this.THEMES.AUTO];
        const currentIndex = themeOrder.indexOf(currentTheme);
        const nextIndex = (currentIndex + 1) % themeOrder.length;
        const nextTheme = themeOrder[nextIndex];
        
        // 使用带过渡效果的主题切换
        this.applyThemeWithTransition(nextTheme);
        
        // 显示Toast提示
        const themeNames = {
            [this.THEMES.LIGHT]: '浅色主题',
            [this.THEMES.DARK]: '深色主题',
            [this.THEMES.AUTO]: '跟随系统'
        };
        
        App.showToast(`已切换到 ${themeNames[nextTheme]}`, 'success');
    },

    /**
     * 获取当前主题名称
     * @returns {string}
     */
    getCurrentTheme() {
        return Storage.getTheme();
    },

    /**
     * 设置浅色主题
     */
    setLightTheme() {
        this.applyTheme(this.THEMES.LIGHT);
    },

    /**
     * 设置深色主题
     */
    setDarkTheme() {
        this.applyTheme(this.THEMES.DARK);
    },

    /**
     * 设置跟随系统
     */
    setAutoTheme() {
        this.applyTheme(this.THEMES.AUTO);
    },

    /**
     * 添加过渡效果类（实现平滑主题切换）
     */
    addTransitionClass() {
        document.body.classList.add('theme-transitioning');
        // 强制重绘以确保过渡生效
        document.body.offsetHeight;
    },

    /**
     * 移除过渡效果类
     */
    removeTransitionClass() {
        document.body.classList.remove('theme-transitioning');
    },
    
    /**
     * 使用View Transitions API切换主题（如果支持）
     * @param {string} theme - 目标主题
     */
    async applyThemeWithTransition(theme) {
        // 检查是否支持 View Transitions API
        if (!document.startViewTransition) {
            this.applyTheme(theme);
            return;
        }
        
        // 使用原生视图过渡
        const transition = document.startViewTransition(() => {
            this.applyTheme(theme, false);
        });
        
        try {
            await transition.finished;
        } catch (e) {
            // 过渡被中断，忽略错误
        }
    }
};

// 导出模块
window.ThemeManager = ThemeManager;
