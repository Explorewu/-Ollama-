/**
 * 混合群聊前端控制器
 * 功能：
 * 1. 全自动聊天控制（开始/暂停/停止/状态显示）
 * 2. 世界设定配置面板
 * 3. 情感可视化面板（曲线图+可收纳）
 * 4. 观点聚类显示
 * 5. 语音合成控制
 * 6. 角色性格自动匹配音色
 */

const HybridGroupChat = (function() {
    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001/api/group_chat`;
    
    const EMOTION_COLORS = {
        neutral: '#9CA3AF',
        happy: '#10B981',
        sad: '#3B82F6',
        angry: '#EF4444',
        surprised: '#F59E0B',
        thoughtful: '#8B5CF6',
        curious: '#EC4899',
        enthusiastic: '#F97316',
        skeptical: '#6366F1',
        analytical: '#14B8A6'
    };
    
    let state = {
        isRunning: false,
        isPaused: false,
        currentTopic: '',
        maxTurns: 4,
        autoStop: false,
        isVisible: true,
        panels: {
            emotion: true,
            viewpoint: false,
            world: false,
            voice: false
        },
        emotionHistory: [],
        viewpointClusters: [],
        audioContext: null,
        backendAvailable: false
    };
    
    const callbacks = {
        onStatusChange: null,
        onEmotionUpdate: null,
        onViewpointUpdate: null,
        onMessage: null,
        onTopicChange: null
    };
    
    async function init() {
        try {
            // 检查后端服务是否可用
            state.backendAvailable = await checkBackendAvailability();
            
            if (!state.backendAvailable) {
                console.warn(`⚠️ 混合群聊后端服务未启动 (${window.location.hostname || 'localhost'}:5001)，仅提供基础界面`);
                // showBackendUnavailableWarning(); // 不再阻塞 UI
                showNotification('后端服务未连接，部分功能受限', 'warning');
            } else {
                await loadStatus();
                await loadEmotions();
                await loadViewpoints();
            }
            
            setupEventListeners();
            renderPanels(); // 确保渲染面板
            
            if (state.backendAvailable) {
                startPolling();
            }
            
            console.log('✅ HybridGroupChat 初始化完成');
        } catch (e) {
            console.error('❌ HybridGroupChat 初始化失败:', e);
            renderPanels(); // 出错也尝试渲染
        }
    }
    
    async function checkBackendAvailability() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);
            
            const response = await fetch(`${API_BASE}/status`, {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            return response.ok;
        } catch (e) {
            return false;
        }
    }
    
    function showBackendUnavailableWarning() {
        const container = document.getElementById('hybridPanelsContainer');
        if (container) {
            container.innerHTML = `
                <div class="hybrid-unavailable-warning">
                    <div class="warning-icon">⚠️</div>
                    <div class="warning-text">
                        <p>混合群聊控制面板需要后端服务支持</p>
                        <p class="warning-hint">请运行: python hybrid_group_chat_api.py</p>
                    </div>
                </div>
            `;
        }
    }
    
    async function loadStatus() {
        try {
            const response = await fetch(`${API_BASE}/status`);
            const data = await response.json();
            
            if (data.success) {
                state.isRunning = data.data.state === 'running';
                state.isPaused = data.data.state === 'paused';
                state.currentTopic = data.data.topic;
                if (data.data.config) {
                    state.maxTurns = data.data.config.max_turns || state.maxTurns;
                    state.autoStop = Boolean(data.data.config.auto_stop);
                }
                
                if (callbacks.onStatusChange) {
                    callbacks.onStatusChange(data.data);
                }
            }
        } catch (e) {
            console.error('加载状态失败:', e);
        }
    }
    
    async function loadEmotions() {
        try {
            const response = await fetch(`${API_BASE}/emotions`);
            const data = await response.json();
            
            if (data.success) {
                state.emotionHistory = data.data;
                
                if (callbacks.onEmotionUpdate) {
                    callbacks.onEmotionUpdate(data.data);
                }
            }
        } catch (e) {
            console.error('加载情感历史失败:', e);
        }
    }
    
    async function loadViewpoints() {
        try {
            const response = await fetch(`${API_BASE}/viewpoints`);
            const data = await response.json();
            
            if (data.success) {
                state.viewpointClusters = data.data.clusters || [];
                
                if (callbacks.onViewpointUpdate) {
                    callbacks.onViewpointUpdate(data.data);
                }
            }
        } catch (e) {
            console.error('加载观点聚类失败:', e);
        }
    }
    
    function setupEventListeners() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                toggleAllPanels(false);
            }
        });
    }
    
    function startPolling() {
        setInterval(() => {
            if (state.isRunning && !state.isPaused) {
                loadStatus();
                loadEmotions();
                loadViewpoints();
            }
        }, 3000);
    }
    
    async function startAutoChat(topic = null) {
        try {
            const response = await fetch(`${API_BASE}/auto_chat/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: topic })
            });
            
            const data = await response.json();
            
            if (data.success) {
                state.isRunning = true;
                state.isPaused = false;
                state.currentTopic = data.data.topic;
                
                showNotification('自动讨论已开始', 'success');
                
                if (callbacks.onStatusChange) {
                    callbacks.onStatusChange({ state: 'running', topic: state.currentTopic });
                }
                
                return true;
            } else {
                showNotification(data.error || '启动失败', 'error');
                return false;
            }
        } catch (e) {
            console.error('开始自动聊天失败:', e);
            showNotification('启动失败: ' + e.message, 'error');
            return false;
        }
    }
    
    async function pauseAutoChat() {
        try {
            const response = await fetch(`${API_BASE}/auto_chat/pause`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                state.isPaused = true;
                showNotification('自动讨论已暂停', 'info');
                
                if (callbacks.onStatusChange) {
                    callbacks.onStatusChange({ state: 'paused', topic: state.currentTopic });
                }
                
                return true;
            }
            return false;
        } catch (e) {
            console.error('暂停失败:', e);
            return false;
        }
    }
    
    async function resumeAutoChat() {
        try {
            const response = await fetch(`${API_BASE}/auto_chat/resume`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                state.isPaused = false;
                showNotification('自动讨论已继续', 'success');
                
                if (callbacks.onStatusChange) {
                    callbacks.onStatusChange({ state: 'running', topic: state.currentTopic });
                }
                
                return true;
            }
            return false;
        } catch (e) {
            console.error('继续失败:', e);
            return false;
        }
    }
    
    async function stopAutoChat(reason = '手动停止') {
        try {
            const response = await fetch(`${API_BASE}/auto_chat/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: reason })
            });
            
            const data = await response.json();
            
            if (data.success) {
                state.isRunning = false;
                state.isPaused = false;
                showNotification('自动讨论已停止', 'info');
                
                await loadStatus();
                
                return true;
            }
            return false;
        } catch (e) {
            console.error('停止失败:', e);
            return false;
        }
    }
    
    async function updateConfig(config) {
        try {
            const response = await fetch(`${API_BASE}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (config.max_turns) {
                    state.maxTurns = config.max_turns;
                }
                if (typeof config.auto_stop !== 'undefined') {
                    state.autoStop = config.auto_stop;
                }
                
                showNotification('配置已更新', 'success');
                return true;
            }
            return false;
        } catch (e) {
            console.error('更新配置失败:', e);
            return false;
        }
    }
    
    async function setWorldSetting(setting) {
        try {
            const response = await fetch(`${API_BASE}/world_setting`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(setting)
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('世界设定已更新', 'success');
                return true;
            }
            return false;
        } catch (e) {
            console.error('设置世界设定失败:', e);
            return false;
        }
    }
    
    async function synthesizeSpeech(text, character) {
        try {
            const response = await fetch(`${API_BASE}/tts/synthesize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, character: character })
            });
            
            const data = await response.json();
            
            if (data.success && data.data.audio) {
                await playAudio(data.data.audio, data.data.format);
                return true;
            }
            return false;
        } catch (e) {
            console.error('语音合成失败:', e);
            return false;
        }
    }
    
    async function playAudio(base64Audio, format) {
        try {
            const audioBytes = base64ToArrayBuffer(base64Audio);
            
            if (!state.audioContext) {
                state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            if (state.audioContext.state === 'suspended') {
                await state.audioContext.resume();
            }
            
            const audioBuffer = await state.audioContext.decodeAudioData(audioBytes);
            
            const source = state.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(state.audioContext.destination);
            source.start(0);
            
            return true;
        } catch (e) {
            console.error('播放音频失败:', e);
            return false;
        }
    }
    
    function base64ToArrayBuffer(base64) {
        const binaryString = window.atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        return bytes.buffer;
    }
    
    function togglePanel(panelName) {
        state.panels[panelName] = !state.panels[panelName];
        renderPanels();
        
        saveState();
    }
    
    function toggleAllPanels(visible) {
        for (const key in state.panels) {
            state.panels[key] = visible;
        }
        renderPanels();
    }
    
    function toggleVisibility() {
        state.isVisible = !state.isVisible;
        renderPanels();
        saveState();
        showNotification(state.isVisible ? '面板已显示' : '面板已隐藏', 'info');
    }
    
    function renderControlPanel() {
        if (!state.isVisible) {
            return `<div class="hybrid-control-panel hidden" id="hybridControlPanel" style="display:none;"></div>`;
        }
        
        return `
            <div class="hybrid-control-panel" id="hybridControlPanel">
                <div class="control-header">
                    <h3>🤖 混合智能控制</h3>
                    <div class="control-status">
                        ${state.isRunning ? 
                            `<span class="status-badge running">运行中</span>` : 
                            `<span class="status-badge idle">已停止</span>`
                        }
                        ${state.isPaused ? `<span class="status-badge paused">已暂停</span>` : ''}
                    </div>
                </div>
                
                <div class="control-topic">
                    <span class="topic-label">当前话题：</span>
                    <span class="topic-content">${state.currentTopic || '暂无话题'}</span>
                </div>
                
                <div class="control-buttons">
                    ${!state.isRunning ? 
                        `<button class="btn btn-primary" onclick="HybridGroupChat.startAutoChat()">
                            ▶ 开始自动讨论
                        </button>` : 
                        `<button class="btn btn-warning" onclick="HybridGroupChat.pauseAutoChat()">
                            ⏸ 暂停
                        </button>
                        <button class="btn btn-danger" onclick="HybridGroupChat.stopAutoChat()">
                            ⏹ 停止
                        </button>`
                    }
                    ${state.isPaused ?
                        `<button class="btn btn-success" onclick="HybridGroupChat.resumeAutoChat()">
                            ▶ 继续
                        </button>` : ''
                    }
                </div>
                
                <div class="control-settings">
                    <div class="setting-row">
                        <label>最大轮数：</label>
                        <input type="number" class="setting-input" 
                               value="${state.maxTurns}" min="3" max="20"
                               onchange="HybridGroupChat.updateConfig({max_turns: this.value})">
                    </div>
                    <div class="setting-row">
                        <label>
                            <input type="checkbox" ${state.autoStop ? 'checked' : ''}
                                   onchange="HybridGroupChat.updateConfig({auto_stop: this.checked})">
                            自动停止
                        </label>
                    </div>
                </div>
                
                <div class="panel-toggles">
                    <button class="panel-toggle ${state.panels.emotion ? 'active' : ''}" 
                            onclick="HybridGroupChat.togglePanel('emotion')">
                        💭 情感
                    </button>
                    <button class="panel-toggle ${state.panels.viewpoint ? 'active' : ''}" 
                            onclick="HybridGroupChat.togglePanel('viewpoint')">
                        💡 观点
                    </button>
                    <button class="panel-toggle ${state.panels.world ? 'active' : ''}" 
                            onclick="HybridGroupChat.togglePanel('world')">
                        🌍 世界
                    </button>
                    <button class="panel-toggle ${state.panels.voice ? 'active' : ''}" 
                            onclick="HybridGroupChat.togglePanel('voice')">
                        🔊 语音
                    </button>
                </div>
            </div>
        `;
    }
    
    function renderEmotionPanel() {
        if (!state.panels.emotion) return '';
        
        const history = state.emotionHistory.slice(-20);
        
        let chartData = '';
        if (history.length > 1) {
            const maxLen = 20;
            const padding = Math.max(0, maxLen - history.length);
            const values = history.map(h => h.emotions.neutral || 0.5);
            const paddedValues = Array(padding).fill(null).concat(values);
            
            chartData = paddedValues.map((v, i) => {
                const x = (i / maxLen) * 100;
                const y = (1 - v) * 100;
                return `${x},${y}`;
            }).join(' ');
        }
        
        const emotionStats = {};
        history.forEach(h => {
            if (h.dominant) {
                emotionStats[h.dominant] = (emotionStats[h.dominant] || 0) + 1;
            }
        });
        
        const topEmotions = Object.entries(emotionStats)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5);
        
        return `
            <div class="emotion-panel ${state.panels.emotion ? 'visible' : ''}" id="emotionPanel">
                <div class="panel-header">
                    <h4>💭 情感可视化</h4>
                    <button class="panel-close" onclick="HybridGroupChat.togglePanel('emotion')">×</button>
                </div>
                
                <div class="emotion-chart-container">
                    <svg class="emotion-chart" viewBox="0 0 100 100" preserveAspectRatio="none">
                        ${chartData ? 
                            `<polyline class="emotion-line" points="${chartData}" fill="none" stroke="#6366F1" stroke-width="1"/>` : 
                            '<text x="50" y="50" text-anchor="middle" fill="#6B7280">暂无数据</text>'
                        }
                    </svg>
                    <div class="chart-labels">
                        <span>高</span>
                        <span>低</span>
                    </div>
                </div>
                
                <div class="emotion-stats">
                    <h5>情感分布</h5>
                    <div class="emotion-bars">
                        ${topEmotions.map(([emotion, count]) => `
                            <div class="emotion-bar-item">
                                <span class="emotion-name">${getEmotionIcon(emotion)} ${emotion}</span>
                                <div class="emotion-bar-bg">
                                    <div class="emotion-bar-fill" 
                                         style="width: ${(count / history.length * 100) || 0}%; 
                                                background: ${EMOTION_COLORS[emotion] || '#9CA3AF'}">
                                    </div>
                                </div>
                                <span class="emotion-count">${count}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div class="emotion-legend">
                    ${Object.entries(EMOTION_COLORS).map(([emotion, color]) => `
                        <span class="legend-item">
                            <span class="legend-color" style="background: ${color}"></span>
                            ${emotion}
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    function renderViewpointPanel() {
        if (!state.panels.viewpoint) return '';
        
        const clusters = state.viewpointClusters;
        
        return `
            <div class="viewpoint-panel ${state.panels.viewpoint ? 'visible' : ''}" id="viewpointPanel">
                <div class="panel-header">
                    <h4>💡 观点聚类</h4>
                    <button class="panel-close" onclick="HybridGroupChat.togglePanel('viewpoint')">×</button>
                </div>
                
                <div class="viewpoint-content">
                    ${clusters.length === 0 ? 
                        '<p class="empty-message">暂无观点数据，讨论开始后自动更新</p>' :
                        clusters.map((cluster, index) => `
                            <div class="viewpoint-cluster">
                                <div class="cluster-header">
                                    <span class="cluster-id">#${index + 1}</span>
                                    <span class="cluster-sentiment ${cluster.sentiment}">${cluster.sentiment}</span>
                                    <span class="cluster-strength">强度: ${Math.round(cluster.strength * 100)}%</span>
                                </div>
                                <div class="cluster-viewpoint">
                                    ${cluster.viewpoint.substring(0, 100)}${cluster.viewpoint.length > 100 ? '...' : ''}
                                </div>
                                <div class="cluster-supporters">
                                    支持者: ${cluster.supporting_models.map(m => m.split(':')[0]).join(', ')}
                                </div>
                            </div>
                        `).join('')
                    }
                </div>
            </div>
        `;
    }
    
    function renderWorldPanel() {
        if (!state.panels.world) return '';
        
        return `
            <div class="world-panel ${state.panels.world ? 'visible' : ''}" id="worldPanel">
                <div class="panel-header">
                    <h4>🌍 世界设定</h4>
                    <button class="panel-close" onclick="HybridGroupChat.togglePanel('world')">×</button>
                </div>
                
                <div class="world-content">
                    <div class="form-group">
                        <label>世界标题</label>
                        <input type="text" id="worldTitle" placeholder="如：赛博朋克未来世界">
                    </div>
                    
                    <div class="form-group">
                        <label>背景描述</label>
                        <textarea id="worldBackground" rows="3" 
                                  placeholder="描述这个世界的背景设定..."></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>世界规则（每行一条）</label>
                        <textarea id="worldRules" rows="3" 
                                  placeholder="1. 人工智能统治世界&#10;2. 人类与AI和平共处..."></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>讨论话题（每行一个）</label>
                        <textarea id="worldTopics" rows="3" 
                                  placeholder="AI是否应该拥有权利？&#10;人类如何与AI共存？"></textarea>
                    </div>
                    
                    <button class="btn btn-primary" onclick="HybridGroupChat.saveWorldSetting()">
                        保存设定
                    </button>
                </div>
            </div>
        `;
    }
    
    function renderVoicePanel() {
        if (!state.panels.voice) return '';
        
        const backendWarning = !state.backendAvailable ? 
            `<div class="voice-warning" style="background: #fff3e0; color: #e65100; padding: 12px; margin-bottom: 12px; border-radius: 6px; font-size: 13px; border: 1px solid #ffcc80;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 16px;">⚠️</span>
                    <strong>后端服务未连接</strong>
                </div>
                <div style="margin-bottom: 10px;">语音合成功能暂时不可用，请启动后端服务。</div>
                <button onclick="HybridGroupChat.startBackendService()" style="background: #2196F3; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    ▶ 启动服务
                </button>
                <div style="margin-top: 8px; font-size: 11px; opacity: 0.8;">
                    命令: <code style="background: rgba(0,0,0,0.1); padding: 2px 4px; border-radius: 3px;">python server/intelligent_api.py</code>
                </div>
            </div>` : '';
        
        return `
            <div class="voice-panel ${state.panels.voice ? 'visible' : ''}" id="hybridVoicePanel">
                <div class="panel-header">
                    <h4>🔊 语音合成</h4>
                    <button class="panel-close" onclick="HybridGroupChat.togglePanel('voice')">×</button>
                </div>
                
                <div class="voice-content">
                    ${backendWarning}
                    <p class="voice-info">
                        根据角色性格自动匹配音色，点击消息旁的🔊按钮播放
                    </p>
                    
                    <div class="voice-profiles">
                        <h5>角色音色配置</h5>
                        <div class="profile-list">
                            <div class="profile-item">
                                <span>🎭 古代书生</span>
                                <span class="profile-detail">音色: basa, 语速: 0.85x, 音调: -2</span>
                            </div>
                            <div class="profile-item">
                                <span>🔬 科幻AI</span>
                                <span class="profile-detail">音色: aidar, 语速: 1.1x, 音调: +5</span>
                            </div>
                            <div class="profile-item">
                                <span>💼 心理咨询师</span>
                                <span class="profile-detail">音色: baya, 语速: 0.9x, 音调: +2</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    async function startBackendService() {
        try {
            showNotification('正在启动后端服务...', 'info');
            const response = await fetch('http://localhost:5001/api/health');
            if (response.ok) {
                showNotification('后端服务已启动！正在重新连接...', 'success');
                await checkBackendAvailability();
                if (state.backendAvailable) {
                    renderPanels();
                }
            }
        } catch (e) {
            showNotification('无法连接到后端服务，请手动启动: python server/intelligent_api.py', 'error');
        }
    }
    
    function renderPanels() {
        const container = document.getElementById('hybridPanelsContainer');
        if (container) {
            container.innerHTML = renderControlPanel() + 
                                  renderEmotionPanel() + 
                                  renderViewpointPanel() + 
                                  renderWorldPanel() + 
                                  renderVoicePanel();
        }
    }
    
    async function saveWorldSetting() {
        const setting = {
            title: document.getElementById('worldTitle')?.value || '',
            background: document.getElementById('worldBackground')?.value || '',
            rules: (document.getElementById('worldRules')?.value || '').split('\n').filter(r => r.trim()),
            main_topics: (document.getElementById('worldTopics')?.value || '').split('\n').filter(t => t.trim())
        };
        
        await setWorldSetting(setting);
    }
    
    function getEmotionIcon(emotion) {
        const icons = {
            neutral: '😐',
            happy: '😊',
            sad: '😢',
            angry: '😠',
            surprised: '😲',
            thoughtful: '🤔',
            curious: '🤨',
            enthusiastic: '🤩',
            skeptical: '🤔',
            analytical: '🧐'
        };
        return icons[emotion] || '😐';
    }
    
    function showNotification(message, type = 'info') {
        const container = document.getElementById('notificationContainer');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span class="notification-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
            <span class="notification-message">${message}</span>
        `;
        
        container.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    function saveState() {
        try {
            localStorage.setItem('hybrid_group_chat_state', JSON.stringify({
                panels: state.panels,
                maxTurns: state.maxTurns,
                autoStop: state.autoStop
            }));
        } catch (e) {
            console.error('保存状态失败:', e);
        }
    }
    
    function loadState() {
        try {
            const saved = localStorage.getItem('hybrid_group_chat_state');
            if (saved) {
                const data = JSON.parse(saved);
                state.panels = { ...state.panels, ...data.panels };
                state.maxTurns = data.maxTurns || 4;
                state.autoStop = data.autoStop || false;
            }
        } catch (e) {
            console.error('加载状态失败:', e);
        }
    }
    
    function registerCallback(event, callback) {
        if (callbacks.hasOwnProperty(event)) {
            callbacks[event] = callback;
        }
    }
    
    loadState();
    
    return {
        init,
        startAutoChat,
        pauseAutoChat,
        resumeAutoChat,
        stopAutoChat,
        updateConfig,
        setWorldSetting,
        synthesizeSpeech,
        startBackendService,
        togglePanel,
        toggleAllPanels,
        toggleVisibility,
        saveWorldSetting,
        registerCallback,
        getState: () => state,
        getEmotionHistory: () => state.emotionHistory,
        getViewpointClusters: () => state.viewpointClusters,
        renderPanels
    };
})();


if (typeof module !== 'undefined' && module.exports) {
    module.exports = HybridGroupChat;
}
