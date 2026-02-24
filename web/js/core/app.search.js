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

    window.AppSearch = Search;
})();
