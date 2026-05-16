/**
 * 语音通话模块
 * 
 * 基于Qwen3-ASR + Qwen3.5-4B + Qwen3-TTS的实时语音交互前端
 * 功能：音频采集、WebSocket通信、音频播放、状态管理
 * 
 * 使用方法:
 *   const voiceCall = new VoiceCall();
 *   voiceCall.connect();
 *   voiceCall.startCall();
 */

class VoiceCall {
    constructor(options = {}) {
        // WebSocket 配置
        const host = (typeof window !== 'undefined' && window.location && window.location.hostname)
            ? window.location.hostname
            : 'localhost';
        this.wsUrl = options.wsUrl || `ws://${host}:5005/voice-call`;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this._intentionalClose = false;
        
        // 心跳保活机制
        this.heartbeatInterval = null;
        this.heartbeatTimeout = 25000;
        this.missedHeartbeats = 0;
        this.maxMissedHeartbeats = 3;
        
        // 连接状态检测
        this.connectionCheckInterval = null;
        this.lastMessageTime = Date.now();
        this.connectionTimeout = 60000;
        
        // 音频采集
        this.mediaRecorder = null;
        this.audioStream = null;
        this.audioContext = null;
        this.analyser = null;
        this.processor = null;
        this.pcmGainNode = null;
        this.inputSampleRate = 0;
        this.targetSampleRate = 16000;
        
        // VAD语音活动检测
        this.vadEnabled = true;
        this.vadThreshold = 0.015;
        this.vadSilenceTimeout = 1200;
        this.vadSilenceStartTime = null;
        this.vadIsSpeaking = false;
        this.vadBuffer = [];
        this.vadMinSpeechDuration = 300;
        this.vadSpeechStartTime = null;
        this.vadNoiseFloor = 0.005;
        this.vadAdaptiveThreshold = 0.015;
        this.vadZCRThreshold = 0.15;
        this.vadEnergyHistory = [];
        this.vadHistorySize = 10;
        this.vadHangoverFrames = 0;
        this.vadMaxHangoverFrames = 5;
        
        // 音频播放
        this.audioPlayer = null;
        this.isPlaying = false;
        this.audioQueue = [];
        this.currentAudioSource = null;
        
        // 通话状态
        this.isInCall = false;
        this.callStartTime = null;
        
        // 回调函数
        this.onTranscript = options.onTranscript || (() => {});
        this.onAiText = options.onAiText || (() => {});
        this.onAiAudio = options.onAiAudio || (() => {});
        this.onStatusChange = options.onStatusChange || (() => {});
        this.onError = options.onError || (() => {});
        this.onConnect = options.onConnect || (() => {});
        this.onDisconnect = options.onDisconnect || (() => {});
        
        // 状态管理
        this._currentStatus = 'idle';
        this._statusCallbacks = [];
        
        // 音频可视化
        this.visualizerCallback = null;
        
        // TTS配置
        this.selectedVoice = options.voice || 'vivian';
        this.ttsSpeed = 1.0;
        this.ttsEmotion = null;
        
        // 音频上下文池
        this._audioContextPool = [];
        this._maxPoolSize = 3;
        
        // 音频缓冲区
        this._audioBufferPool = [];
        this._maxBufferPoolSize = 10;
        
        // 音频解码缓存
        this._decodeCache = new Map();
        this._maxCacheSize = 20;
        
        // 音频队列处理
        this._isProcessingQueue = false;
        this._queueProcessingPromise = null;
        
        // 性能监控
        this._performanceMetrics = {
            totalAudioDuration: 0,
            totalDecodeTime: 0,
            totalPlayTime: 0,
            decodeCount: 0,
            playCount: 0,
            errorCount: 0
        };
        
        // 新增：音频累积缓冲区
        this._audioAccumulationBuffer = [];
        this._accumulationTimeout = null;
        this._accumulationDelay = 100;
        this._minAccumulationSize = 1024;
        
        // 新增：音频预处理队列
        this._preprocessingQueue = [];
        this._isPreprocessing = false;
        
        // 新增：音频播放状态
        this._isAudioPlaying = false;
        this._audioPlaybackQueue = [];
        this._currentPlaybackSource = null;
        
        // 新增：音频上下文状态管理
        this._audioContextState = 'suspended';
        this._audioContextResumePromise = null;
        
        // 新增：音频解码 worker
        this._decodeWorker = null;
        this._initDecodeWorker();
        
        // 新增：音频播放锁
        this._playbackLock = false;
        this._playbackQueue = [];
        
        // 新增：音频上下文恢复重试
        this._resumeRetryCount = 0;
        this._maxResumeRetries = 3;
        
        // 新增：音频播放状态监控
        this._playbackStartTime = 0;
        this._playbackDuration = 0;
        
        // 新增：音频缓冲策略
        this._bufferStrategy = 'adaptive';
        this._targetBufferDuration = 0.5;
        this._maxBufferDuration = 2.0;
        
        // 新增：音频质量监控
        this._qualityMetrics = {
            droppedFrames: 0,
            bufferUnderruns: 0,
            decodeErrors: 0,
            playbackGaps: 0
        };
        
        // 新增：音频会话管理
        this._sessionId = null;
        this._sessionStartTime = null;
        
        // 新增：音频配置
        this._audioConfig = {
            sampleRate: 24000,
            channels: 1,
            bufferSize: 4096,
            encoding: 'pcm_s16le'
        };
    }
    
    _initDecodeWorker() {
        // 简化实现，不使用 worker
        this._decodeWorker = null;
    }
    
    async _ensureAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this._audioConfig.sampleRate,
                latencyHint: 'interactive'
            });
        }
        
        if (this.audioContext.state === 'suspended') {
            try {
                await this.audioContext.resume();
            } catch (e) {
                console.warn('恢复音频上下文失败:', e);
            }
        }
        
        return this.audioContext;
    }
    
    connect() {
        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('WebSocket 已连接');
            return Promise.resolve();
        }
        
        if (this.ws?.readyState === WebSocket.CONNECTING) {
            console.log('WebSocket 正在连接中...');
            return new Promise((resolve, reject) => {
                const checkInterval = setInterval(() => {
                    if (this.ws?.readyState === WebSocket.OPEN) {
                        clearInterval(checkInterval);
                        resolve();
                    } else if (this.ws?.readyState === WebSocket.CLOSED) {
                        clearInterval(checkInterval);
                        reject(new Error('连接失败'));
                    }
                }, 100);
                
                setTimeout(() => {
                    clearInterval(checkInterval);
                    reject(new Error('连接超时'));
                }, 10000);
            });
        }
        
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.wsUrl);
                
                this.ws.onopen = () => {
                    console.log('WebSocket 连接成功');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this._startHeartbeat();
                    this._startConnectionCheck();
                    
                    if (this.selectedVoice && this.selectedVoice !== 'default') {
                        this.ws.send(JSON.stringify({
                            type: 'set_voice',
                            data: { speaker_id: this.selectedVoice },
                            timestamp: Date.now()
                        }));
                    }
                    
                    this.onConnect();
                    resolve();
                };
                
                this.ws.onmessage = (event) => this._handleMessage(event);
                
                this.ws.onclose = () => {
                    console.log('WebSocket 连接关闭');
                    this.isConnected = false;
                    this._stopHeartbeat();
                    this._stopConnectionCheck();
                    this.onDisconnect();
                    
                    if (!this._intentionalClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket 错误:', error);
                    this.onError(error);
                    reject(error);
                };
                
            } catch (error) {
                console.error('创建 WebSocket 失败:', error);
                reject(error);
            }
        });
    }
    
    _handleMessage(event) {
        this.lastMessageTime = Date.now();
        
        try {
            const message = JSON.parse(event.data);
            const { type, data, timestamp } = message;
            
            switch (type) {
                case 'transcript':
                    this.onTranscript(data.text, data.is_final);
                    break;
                    
                case 'ai_text':
                    this.onAiText(data.text);
                    break;
                    
                case 'ai_audio':
                    this._handleAiAudio(data);
                    break;
                    
                case 'pong':
                    this.missedHeartbeats = 0;
                    break;
                    
                case 'voice_changed':
                    console.log('音色已切换:', data.speaker_id);
                    break;
                    
                case 'error':
                    console.error('服务器错误:', data.message);
                    this.onError(new Error(data.message));
                    break;
                    
                default:
                    console.log('未知消息类型:', type);
            }
        } catch (error) {
            console.error('处理消息失败:', error);
        }
    }
    
    _handleAiAudio(data) {
        if (data.audio) {
            this._queueAudio(data.audio, data.format || 'wav');
        }
    }
    
    _queueAudio(base64Audio, format) {
        this._playbackQueue.push({ audio: base64Audio, format });
        this._processPlaybackQueue();
    }
    
    async _processPlaybackQueue() {
        if (this._playbackLock || this._playbackQueue.length === 0) return;
        
        this._playbackLock = true;
        
        try {
            while (this._playbackQueue.length > 0) {
                const { audio, format } = this._playbackQueue.shift();
                await this._playAudio(audio, format);
            }
        } finally {
            this._playbackLock = false;
        }
    }
    
    async _playAudio(base64Audio, format) {
        try {
            const ctx = await this._ensureAudioContext();
            
            const byteCharacters = atob(base64Audio);
            const byteArray = new Uint8Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteArray[i] = byteCharacters.charCodeAt(i);
            }
            
            const arrayBuffer = byteArray.buffer;
            const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
            
            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(ctx.destination);
            
            this._currentPlaybackSource = source;
            
            await new Promise((resolve) => {
                source.onended = resolve;
                source.start(0);
            });
            
        } catch (error) {
            console.error('播放音频失败:', error);
        }
    }
    
    _startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                this.missedHeartbeats++;
                
                if (this.missedHeartbeats >= this.maxMissedHeartbeats) {
                    console.warn('心跳超时，重新连接');
                    this.ws.close();
                }
            }
        }, this.heartbeatTimeout);
    }
    
    _stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    _startConnectionCheck() {
        this.connectionCheckInterval = setInterval(() => {
            const elapsed = Date.now() - this.lastMessageTime;
            if (elapsed > this.connectionTimeout) {
                console.warn('连接超时，重新连接');
                this.ws?.close();
            }
        }, 10000);
    }
    
    _stopConnectionCheck() {
        if (this.connectionCheckInterval) {
            clearInterval(this.connectionCheckInterval);
            this.connectionCheckInterval = null;
        }
    }
    
    async startCall() {
        if (this.isInCall) return;
        
        try {
            await this._ensureAudioContext();
            
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.targetSampleRate,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            this.inputSampleRate = this.audioContext.sampleRate;
            
            const source = this.audioContext.createMediaStreamSource(this.audioStream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 2048;
            
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            this.processor.onaudioprocess = (e) => {
                if (!this.isInCall) return;
                
                const inputData = e.inputBuffer.getChannelData(0);
                const pcmData = this._float32ToInt16(inputData);
                
                if (this.vadEnabled) {
                    this._processVAD(inputData, pcmData);
                } else {
                    this._sendAudioData(pcmData);
                }
                
                if (this.visualizerCallback) {
                    this.visualizerCallback(inputData);
                }
            };
            
            source.connect(this.analyser);
            this.analyser.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            this.isInCall = true;
            this.callStartTime = Date.now();
            
            this._setStatus('calling');
            
        } catch (error) {
            console.error('开始通话失败:', error);
            this.onError(error);
            throw error;
        }
    }
    
    stopCall() {
        if (!this.isInCall) return;
        
        this.isInCall = false;
        
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        if (this.analyser) {
            this.analyser.disconnect();
            this.analyser = null;
        }
        
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }
        
        this._setStatus('idle');
    }
    
    _float32ToInt16(float32Array) {
        const int16Array = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return int16Array;
    }
    
    _processVAD(inputData, pcmData) {
        const rms = this._calculateRMS(inputData);
        const isSpeech = rms > this.vadAdaptiveThreshold;
        
        if (isSpeech) {
            this.vadHangoverFrames = 0;
            
            if (!this.vadIsSpeaking) {
                this.vadIsSpeaking = true;
                this.vadSpeechStartTime = Date.now();
                this.vadBuffer = [];
            }
            
            this.vadBuffer.push(...pcmData);
            
        } else {
            if (this.vadIsSpeaking) {
                this.vadHangoverFrames++;
                
                if (this.vadHangoverFrames < this.vadMaxHangoverFrames) {
                    this.vadBuffer.push(...pcmData);
                } else {
                    const speechDuration = Date.now() - this.vadSpeechStartTime;
                    
                    if (speechDuration >= this.vadMinSpeechDuration && this.vadBuffer.length > 0) {
                        this._sendAudioData(new Int16Array(this.vadBuffer));
                    }
                    
                    this.vadIsSpeaking = false;
                    this.vadBuffer = [];
                    this.vadHangoverFrames = 0;
                }
            }
        }
        
        this.vadEnergyHistory.push(rms);
        if (this.vadEnergyHistory.length > this.vadHistorySize) {
            this.vadEnergyHistory.shift();
        }
        
        const avgEnergy = this.vadEnergyHistory.reduce((a, b) => a + b, 0) / this.vadEnergyHistory.length;
        this.vadAdaptiveThreshold = Math.max(this.vadThreshold, avgEnergy * 1.5);
    }
    
    _calculateRMS(buffer) {
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
            sum += buffer[i] * buffer[i];
        }
        return Math.sqrt(sum / buffer.length);
    }
    
    _sendAudioData(pcmData) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const base64Data = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
            
            this.ws.send(JSON.stringify({
                type: 'audio',
                data: {
                    audio: base64Data,
                    sample_rate: this.inputSampleRate,
                    format: 'pcm_s16le'
                },
                timestamp: Date.now()
            }));
        }
    }
    
    setVoice(voice) {
        const validVoices = ['vivian', 'serena', 'chelsie', 'ethel', 'vivian_warm', 'uncle_fu', 'dylan', 'eric', 'uncle_fu_warm', 'dylan_calm', 'ryan', 'aiden', 'jessica', 'ono_anna', 'sohee'];
        if (!validVoices.includes(voice)) {
            console.warn(`无效的音色: ${voice}，使用默认音色`);
            voice = 'vivian';
        }
        this.selectedVoice = voice;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'set_voice',
                data: { speaker_id: voice },
                timestamp: Date.now()
            }));
        }
        console.log(`音色已设置为: ${voice}`);
    }
    
    _setStatus(status) {
        this._currentStatus = status;
        this.onStatusChange(status);
    }
    
    disconnect() {
        this._intentionalClose = true;
        this.stopCall();
        this._stopHeartbeat();
        this._stopConnectionCheck();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.isConnected = false;
    }
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceCall;
}

// ========== 音色克隆功能 ==========

class VoiceCloneManager {
    constructor() {
        this.modal = document.getElementById('cloneModal');
        this.progressPanel = document.getElementById('cloneProgress');
        
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.recordStartTime = 0;
        this.recordTimer = null;
        this.isRecording = false;
        this.waveformInterval = null;
        
        this.recordedBlob = null;
        this.uploadedFile = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadClonedVoices();
    }
    
    bindEvents() {
        const cloneEntry = document.getElementById('cloneVoiceEntry');
        if (cloneEntry) {
            cloneEntry.addEventListener('click', (e) => {
                e.stopPropagation();
                this.openModal();
            });
        }
        
        const closeBtn = document.getElementById('cloneModalClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }
        
        this.modal?.addEventListener('click', (e) => {
            if (e.target === this.modal) this.closeModal();
        });
        
        document.querySelectorAll('.clone-tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
        
        const recordBtn = document.getElementById('recordBtn');
        if (recordBtn) {
            recordBtn.addEventListener('click', () => this.toggleRecording());
        }
        
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('audioFileInput');
        
        if (uploadArea && fileInput) {
            uploadArea.addEventListener('click', () => fileInput.click());
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) this.handleFileSelect(files[0]);
            });
            
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) this.handleFileSelect(e.target.files[0]);
            });
        }
        
        const clearBtn = document.getElementById('uploadClearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.clearUploadFile();
            });
        }
        
        const recordSubmit = document.getElementById('recordSubmitBtn');
        const uploadSubmit = document.getElementById('uploadSubmitBtn');
        
        if (recordSubmit) {
            recordSubmit.addEventListener('click', () => this.submitClone('record'));
        }
        if (uploadSubmit) {
            uploadSubmit.addEventListener('click', () => this.submitClone('upload'));
        }
        
        ['recordVoiceName', 'uploadVoiceName'].forEach(id => {
            const input = document