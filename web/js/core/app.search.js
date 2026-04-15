/**
 * 搜索模块
 * 消息搜索功能
 */
(function() {
    const Search = {
        init(app) {
            this.app = app;
            this.initSearchUI();
        },

        initSearchUI() {
            const app = this.app;
            const actions = document.querySelector('#chat-page .chat-actions');
            if (actions) {
                const btn = document.createElement('button');
                btn.className = 'action-link';
                btn.id = 'searchMsgBtn';
                btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> 搜索消息';
                btn.addEventListener('click', () => this.openSearchBar());
                actions.appendChild(btn);
            }
        },

        openSearchBar() {
            const searchBar = document.getElementById('messageSearchBar');
            if (!searchBar) {
                this.createSearchBar();
                return;
            }
            searchBar.classList.add('active');
            const input = searchBar.querySelector('input');
            if (input) {
                input.focus();
            }
        },

        createSearchBar() {
            const app = this.app;
            const chatPage = document.getElementById('chat-page');
            if (!chatPage) return;

            const searchBar = document.createElement('div');
            searchBar.id = 'messageSearchBar';
            searchBar.className = 'search-bar active';
            searchBar.innerHTML = `
                <input type="text" placeholder="搜索消息..." />
                <span class="search-count"></span>
                <button class="search-prev">↑</button>
                <button class="search-next">↓</button>
                <button class="search-close">✕</button>
            `;
            chatPage.appendChild(searchBar);

            const input = searchBar.querySelector('input');
            const close = searchBar.querySelector('.search-close');
            const prev = searchBar.querySelector('.search-prev');
            const next = searchBar.querySelector('.search-next');

            let searchTimeout;
            input.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.runSearch();
                }, 300);
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    if (e.shiftKey) {
                        this.scrollToSearchCurrent(-1);
                    } else {
                        this.scrollToSearchCurrent(1);
                    }
                }
                if (e.key === 'Escape') {
                    this.closeSearchBar();
                }
            });

            close.addEventListener('click', () => this.closeSearchBar());

            prev.addEventListener('click', () => this.scrollToSearchCurrent(-1));
            next.addEventListener('click', () => this.scrollToSearchCurrent(1));

            input.focus();
        },

        closeSearchBar() {
            const searchBar = document.getElementById('messageSearchBar');
            if (searchBar) {
                searchBar.classList.remove('active');
                this.clearSearchHighlights();
            }
        },

        runSearch() {
            const app = this.app;
            this.clearSearchHighlights();

            const searchBar = document.getElementById('messageSearchBar');
            if (!searchBar) return;

            const query = searchBar.querySelector('input').value.trim().toLowerCase();
            if (!query) {
                app.state.searchMatches = [];
                app.state.searchIndex = -1;
                this.updateSearchCount();
                return;
            }

            const messages = document.querySelectorAll('.message-content');
            let matchCount = 0;

            messages.forEach((msg, index) => {
                const text = msg.textContent.toLowerCase();
                if (text.includes(query)) {
                    matchCount++;
                    const innerHTML = msg.innerHTML;
                    const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
                    msg.innerHTML = innerHTML.replace(regex, '<mark class="search-highlight">$1</mark>');
                    app.state.searchMatches.push(msg);
                }
            });

            app.state.searchMatches = Array.from(document.querySelectorAll('.search-highlight')).map(el => el.parentElement);
            app.state.searchIndex = app.state.searchMatches.length > 0 ? 0 : -1;

            this.updateSearchCount();

            if (app.state.searchMatches.length > 0) {
                this.scrollToSearchCurrent(0);
            }
        },

        escapeRegex(string) {
            return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        },

        clearSearchHighlights() {
            const highlights = document.querySelectorAll('.search-highlight');
            highlights.forEach(hl => {
                const parent = hl.parentElement;
                if (parent) {
                    parent.innerHTML = parent.innerHTML.replace(/<\/?mark class="search-highlight">/g, '');
                }
            });
        },

        scrollToSearchCurrent(direction = 1) {
            const app = this.app;
            const matches = app.state.searchMatches || [];
            if (matches.length === 0) return;

            app.state.searchIndex += direction;

            if (app.state.searchIndex >= matches.length) {
                app.state.searchIndex = 0;
            }
            if (app.state.searchIndex < 0) {
                app.state.searchIndex = matches.length - 1;
            }

            const currentMatch = matches[app.state.searchIndex];
            if (currentMatch) {
                currentMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });

                document.querySelectorAll('.search-highlight.active').forEach(el => {
                    el.classList.remove('active');
                });
                const activeHighlight = currentMatch.querySelector('.search-highlight');
                if (activeHighlight) {
                    activeHighlight.classList.add('active');
                }
            }

            this.updateSearchCount();
        },

        clearCurrentMark() {
            document.querySelectorAll('.search-highlight.active').forEach(el => {
                el.classList.remove('active');
            });
        },

        updateSearchCount() {
            const searchBar = document.getElementById('messageSearchBar');
            if (!searchBar) return;

            const countEl = searchBar.querySelector('.search-count');
            const app = this.app;
            if (countEl) {
                if (app.state.searchMatches && app.state.searchMatches.length > 0) {
                    countEl.textContent = `${app.state.searchIndex + 1}/${app.state.searchMatches.length}`;
                } else {
                    countEl.textContent = '';
                }
            }
        }
    };

    /**
     * 模型搜索建议功能
     */
    const ModelSearch = {
        init() {
            this.searchInput = document.getElementById('modelSearch');
            this.suggestionsContainer = document.getElementById('searchSuggestions');
            
            if (!this.searchInput || !this.suggestionsContainer) return;
            
            this.setupEventListeners();
        },
        
        setupEventListeners() {
            // 输入时显示建议
            this.searchInput.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                if (query.length > 0) {
                    this.showSuggestions(query);
                } else {
                    this.hideSuggestions();
                }
            });
            
            // 点击外部关闭建议
            document.addEventListener('click', (e) => {
                if (!this.searchInput.contains(e.target) && 
                    !this.suggestionsContainer.contains(e.target)) {
                    this.hideSuggestions();
                }
            });
            
            // 键盘导航
            this.searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this.hideSuggestions();
                }
            });
        },
        
        showSuggestions(query) {
            // 获取所有模型
            const allModels = window.App?.state?.models || [];
            if (!allModels || allModels.length === 0) return;
            
            // 过滤匹配的模型
            const matches = allModels.filter(model => 
                model.name.toLowerCase().includes(query.toLowerCase()) ||
                (model.details?.family && model.details.family.toLowerCase().includes(query.toLowerCase()))
            ).slice(0, 5); // 最多显示 5 个建议
            
            if (matches.length === 0) {
                this.hideSuggestions();
                return;
            }
            
            // 生成建议 HTML
            this.suggestionsContainer.innerHTML = matches.map(model => `
                <div class="suggestion-item" data-model="${model.name}">
                    <svg class="suggestion-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                        <path d="M2 17l10 5 10-5"/>
                        <path d="M2 12l10 5 10-5"/>
                    </svg>
                    <span class="suggestion-text">${this.highlightMatch(model.name, query)}</span>
                    <span class="suggestion-hint">${model.details?.family || '模型'}</span>
                </div>
            `).join('');
            
            // 添加点击事件
            this.suggestionsContainer.querySelectorAll('.suggestion-item').forEach(item => {
                item.addEventListener('click', () => {
                    const modelName = item.dataset.model;
                    this.searchInput.value = modelName;
                    this.hideSuggestions();
                    
                    // 触发模型选择
                    if (window.App) {
                        window.App.selectModel(modelName);
                    }
                });
            });
        },
        
        hideSuggestions() {
            this.suggestionsContainer.innerHTML = '';
        },
        
        highlightMatch(text, query) {
            const regex = new RegExp(`(${query})`, 'gi');
            return text.replace(regex, '<strong>$1</strong>');
        }
    };
    
    // 初始化模型搜索
    if (typeof window !== 'undefined') {
        window.ModelSearch = ModelSearch;
        
        // DOM 加载完成后初始化
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => ModelSearch.init());
        } else {
            ModelSearch.init();
        }
    }

    window.AppSearch = Search;
})();
