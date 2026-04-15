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
        this.heartbeatTimeout = 25000; // 25秒发送一次心跳
        this.missedHeartbeats = 0;
        this.maxMissedHeartbeats = 3; // 最多允许3次心跳丢失
        
        // 连接状态检测
        this.connectionCheckInterval = null;
        this.lastMessageTime = Date.now();
        this.connectionTimeout = 60000; // 60秒无消息认为连接断开
        
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
        this.vadThreshold = 0.02;  // 音量阈值，低于此值认为是静音
        this.vadSilenceTimeout = 1500;  // 静音超时（毫秒）
        this.vadSpeechStartThreshold = 0.03;  // 语音开始阈值
        this.vadSpeechEndThreshold = 0.015;  // 语音结束阈值
        this.vadIsSpeechActive = false;
        this.vadLastSpeechTime = 0;
        this.vadSpeechBuffer = [];  // 语音缓冲区
        this.vadMaxBufferSize = 50;  // 最大缓冲区大小（约5秒音频）
        this.vadMinSpeechDuration = 800;  // 最小语音持续时间（毫秒），避免逐字识别
        
        // 音频播放
        this.audioPlayer = null;
        this.audioQueue = [];
        this.isPlaying = false;
        
        // 通话状态
        this.isInCall = false;
        this.isSpeaking = false;
        this.isAiSpeaking = false;
        this.currentTranscript = '';
        this.currentAiText = '';
        
        // 对话历史
        this.conversationHistory = [];

        // TTS 音色选择
        this.selectedVoice = options.voice || 'default';

        // 回调函数
        this.onTranscript = options.onTranscript || (() => {});
        this.onAiText = options.onAiText || (() => {});
        this.onStatusChange = options.onStatusChange || (() => {});
        this.onError = options.onError || (() => {});
        this.onHistoryUpdate = options.onHistoryUpdate || (() => {});
        
        // 音频可视化数据
        this.visualizerData = new Uint8Array(0);
        
        // 绑定方法
        this._handleAudioData = this._handleAudioData.bind(this);
        this._handlePcmAudio = this._handlePcmAudio.bind(this);
        this._processAudioQueue = this._processAudioQueue.bind(this);
    }
    
    /**
     * 连接到 WebSocket 服务器
     */
    async connect() {
        // 先清理旧连接
        if (this.ws) {
            try {
                if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
                    this.ws.close();
                }
            } catch (e) {
                console.warn('清理旧WebSocket时出错:', e);
            }
            this.ws = null;
            this.isConnected = false;
        }
        
        this._intentionalClose = false;
        
        try {
            this.ws = new WebSocket(this.wsUrl);
            
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('连接超时'));
                }, 5000);
                
                this.ws.onopen = () => {
                    clearTimeout(timeout);
                    console.log('[Voice Debug] WebSocket 已连接');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this._startHeartbeat(); // 启动心跳
                    this._startConnectionCheck(); // 启动连接检测
                    this._emitStatus('connected');
                    resolve();
                };
                
                this.ws.onerror = (error) => {
                    clearTimeout(timeout);
                    console.error('[Voice Debug] WebSocket 连接错误:', error);
                    reject(error);
                };
            });
            
            this.ws.onmessage = (event) => {
                this._handleMessage(event.data);
                this.lastMessageTime = Date.now(); // 更新最后消息时间
                this.missedHeartbeats = 0; // 收到消息重置心跳计数
            };
            
            this.ws.onclose = () => {
                console.log('语音通话服务已断开');
                this.isConnected = false;
                this._stopHeartbeat();
                this._stopConnectionCheck(); // 停止连接检测
                this._emitStatus('disconnected');
                if (!this._intentionalClose) {
                    this._attemptReconnect();
                }
            };
            
            return true;
            
        } catch (error) {
            console.error('连接失败:', error);
            this.onError(error);
            return false;
        }
    }
    
    /**
     * 断开连接
     */
    disconnect() {
        this._intentionalClose = true;
        this._stopHeartbeat(); // 停止心跳
        this._stopConnectionCheck(); // 停止连接检测
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
        this.reconnectAttempts = 0; // 重置重试计数
        this._emitStatus('disconnected');
    }
    
    /**
     * 尝试重新连接
     */
    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('重连次数已达上限');
            this._emitStatus('reconnect_failed');
            return;
        }
        
        this.reconnectAttempts++;
        console.log(`尝试重新连接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        
        // 清理旧状态
        this._stopHeartbeat();
        this._stopConnectionCheck();
        if (this.ws) {
            try {
                this.ws.close();
            } catch (e) {}
            this.ws = null;
        }
        this.isConnected = false;
        this.isInCall = false;
        this.isSpeaking = false;
        this.isAiSpeaking = false;
        
        // 发送重连状态
        this._emitStatus('reconnecting', { attempt: this.reconnectAttempts });
        
        setTimeout(() => {
            this.connect();
        }, 2000 * this.reconnectAttempts);
    }
    
    /**
     * 开始通话
     */
    async startCall() {
        if (this.isInCall) {
            console.log('已经在通话中');
            return;
        }
        
        // 确保已连接
        if (!this.isConnected) {
            const connected = await this.connect();
            if (!connected) {
                throw new Error('无法连接到语音服务');
            }
        }
        
        try {
            // 初始化音频采集
            await this._initAudioCapture();
            
            // 初始化音频播放
            this._initAudioPlayer();
            
            this.isInCall = true;
            
            // 开始录音
            this._startRecording();
            this._emitStatus('call_started');
            
            console.log('通话已开始');
            
        } catch (error) {
            console.error('开始通话失败:', error);
            this.onError(error);
            throw error;
        }
    }
    
    /**
     * 结束通话
     */
    async endCall() {
        if (!this.isInCall) {
            return;
        }

        this._stopRecording();

        this._stopPlayback();

        // 清理VAD状态
        this.vadIsSpeechActive = false;
        this.vadSpeechBuffer = [];

        // 清理音频流
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }

        // 关闭音频上下文
        if (this.audioContext && this.audioContext.state !== 'closed') {
            await this.audioContext.close();
            this.audioContext = null;
        }

        this.isInCall = false;
        this.isSpeaking = false;
        this.isAiSpeaking = false;
        this.currentTranscript = '';
        this.currentAiText = '';

        // 断开WebSocket连接
        this.disconnect();

        this._emitStatus('call_ended');

        console.log('通话已结束');
    }
    
    /**
     * 设置TTS音色
     * @param {string} voice - 音色ID: 'default', 'vivian', 'serena', 'uncle_fu', 'dylan'
     */
    setVoice(voice) {
        const validVoices = ['default', 'vivian', 'serena', 'uncle_fu', 'dylan'];
        if (!validVoices.includes(voice)) {
            console.warn(`无效的音色: ${voice}，使用默认音色`);
            voice = 'default';
        }
        this.selectedVoice = voice;
        console.log(`音色已设置为: ${voice}`);
    }

    /**
     * 获取当前音色
     */
    getVoice() {
        return this.selectedVoice;
    }

    /**
     * 打断AI说话
     */
    interrupt() {
        if (!this.isInCall || !this.isAiSpeaking) {
            return;
        }
        
        // 停止当前播放
        this._stopPlayback();
        
        // 发送打断消息
        this._sendMessage('interrupt', {});
        
        this.isAiSpeaking = false;
        this._emitStatus('interrupted');
        
        console.log('已打断AI');
    }
    
    /**
     * 初始化音频采集
     */
    async _initAudioCapture() {
        try {
            // 获取麦克风权限
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 16000
                }
            });
            
            // 创建音频上下文（尽量使用设备默认采样率）
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.inputSampleRate = this.audioContext.sampleRate;
            
            // 创建分析器用于可视化
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            
            const source = this.audioContext.createMediaStreamSource(this.audioStream);
            source.connect(this.analyser);
            
            // 优先使用PCM捕获（服务端期望16-bit PCM）
            if (this.audioContext.createScriptProcessor) {
                this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
                this.processor.onaudioprocess = this._handlePcmAudio;
                
                this.pcmGainNode = this.audioContext.createGain();
                this.pcmGainNode.gain.value = 0;
                
                source.connect(this.processor);
                this.processor.connect(this.pcmGainNode);
                this.pcmGainNode.connect(this.audioContext.destination);
            } else {
                // 兼容性回退：使用MediaRecorder（可能需要服务端解码）
                this.mediaRecorder = new MediaRecorder(this.audioStream, {
                    mimeType: 'audio/webm;codecs=opus',
                    audioBitsPerSecond: 16000
                });
                this.mediaRecorder.ondataavailable = this._handleAudioData;
            }
            
            // 开始可视化数据更新
            this._startVisualizer();
            
        } catch (error) {
            console.error('初始化音频采集失败:', error);
            if (error.name === 'NotAllowedError') {
                throw new Error('麦克风权限被拒绝，请在浏览器设置中允许访问麦克风');
            } else if (error.name === 'NotFoundError') {
                throw new Error('未找到麦克风设备，请检查设备连接');
            } else if (error.name === 'NotReadableError') {
                throw new Error('麦克风被其他程序占用，请关闭其他使用麦克风的应用');
            } else if (error.name === 'NotSupportedError') {
                throw new Error('浏览器不支持音频采集，请使用Chrome/Edge/Firefox');
            } else if (error.name === 'SecurityError') {
                throw new Error('安全限制：请使用 localhost 或 HTTPS 访问');
            }
            throw error;
        }
    }
    
    /**
     * 处理音频数据
     */
    _handleAudioData(event) {
        if (event.data.size > 0) {
            const reader = new FileReader();
            reader.onloadend = () => {
                const arrayBuffer = reader.result;
                const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
                
                // 发送音频数据
                this._sendMessage('audio_chunk', { audio: base64 });
            };
            reader.readAsArrayBuffer(event.data);
        }
    }

    /**
     * 处理PCM音频数据（ScriptProcessor）
     */
    _handlePcmAudio(event) {
        if (!this.isInCall) return;
        
        const input = event.inputBuffer.getChannelData(0);
        
        // VAD检测：计算当前帧的音量（RMS）
        if (this.vadEnabled) {
            const rms = this._calculateRMS(input);
            const now = Date.now();

            // 语音开始检测
            if (!this.vadIsSpeechActive && rms > this.vadSpeechStartThreshold) {
                this.vadIsSpeechActive = true;
                this.vadSpeechStartTime = now;
                this.vadLastSpeechTime = now;
                console.log('VAD: 检测到语音开始');
            }

            // 语音持续检测
            if (this.vadIsSpeechActive) {
                if (rms > this.vadSpeechEndThreshold) {
                    this.vadLastSpeechTime = now;
                }

                // 检查是否语音结束（静音超时）
                if (now - this.vadLastSpeechTime > this.vadSilenceTimeout) {
                    const speechDuration = now - this.vadSpeechStartTime;
                    this.vadIsSpeechActive = false;
                    console.log(`VAD: 检测到语音结束，持续 ${speechDuration}ms`);

                    // 只发送持续时间超过最小阈值的语音
                    if (speechDuration >= this.vadMinSpeechDuration) {
                        if (this.vadSpeechBuffer.length > 0) {
                            this._sendSpeechBuffer();
                        }
                    } else {
                        console.log(`VAD: 语音太短 (${speechDuration}ms)，丢弃`);
                        this.vadSpeechBuffer = [];
                    }
                    return;
                }
            }
            
            // 静音时不缓存
            if (!this.vadIsSpeechActive && rms < this.vadThreshold) {
                return;
            }
        }
        
        // 下采样并转换为PCM16
        const downsampled = this._downsampleBuffer(input, this.inputSampleRate, this.targetSampleRate);
        const pcm16 = this._floatTo16BitPCM(downsampled);
        
        if (this.vadEnabled) {
            // VAD模式：只缓存，不实时发送
            this.vadSpeechBuffer.push(pcm16);
            
            // 限制缓冲区大小
            if (this.vadSpeechBuffer.length > this.vadMaxBufferSize) {
                this.vadSpeechBuffer.shift();
            }
        } else {
            // 不使用VAD时，直接发送所有数据
            const base64 = this._arrayBufferToBase64(pcm16.buffer);
            this._sendMessage('audio_chunk', { audio: base64 });
        }
    }
    
    /**
     * 计算音频RMS（均方根）音量
     */
    _calculateRMS(buffer) {
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
            sum += buffer[i] * buffer[i];
        }
        return Math.sqrt(sum / buffer.length);
    }
    
    /**
     * 发送语音缓冲区数据
     */
    _sendSpeechBuffer() {
        if (this.vadSpeechBuffer.length === 0) {
            return;
        }

        // 合并所有缓冲的PCM数据
        const totalLength = this.vadSpeechBuffer.reduce((sum, arr) => sum + arr.length, 0);
        console.log(`VAD: 发送缓冲区，包含 ${this.vadSpeechBuffer.length} 个块，共 ${totalLength} 采样`);

        const merged = new Int16Array(totalLength);
        let offset = 0;
        for (const chunk of this.vadSpeechBuffer) {
            merged.set(chunk, offset);
            offset += chunk.length;
        }

        // 先发送开始说话
        this._sendMessage('start_speaking', {});

        // 发送合并后的音频
        const base64 = this._arrayBufferToBase64(merged.buffer);
        this._sendMessage('audio_chunk', { audio: base64 });

        // 发送停止说话，触发后端处理
        this._sendMessage('stop_speaking', {});

        // 清空缓冲区
        this.vadSpeechBuffer = [];
    }
    
    /**
     * 开始录音
     */
    _startRecording() {
        if (!this.mediaRecorder && !this.processor) return;
        
        // VAD模式下由VAD控制发送，不需要发start_speaking
        if (!this.vadEnabled) {
            this._sendMessage('start_speaking', {});
        }
        
        // 开始录音（MediaRecorder模式）
        if (this.mediaRecorder) {
            this.mediaRecorder.start(100);
        }
        this.isSpeaking = true;
        
        this._emitStatus('speaking_started');
    }
    
    /**
     * 停止录音
     */
    _stopRecording() {
        if (!this.mediaRecorder && !this.processor) return;
        
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        
        // VAD模式下由VAD控制发送，不需要发stop_speaking
        if (!this.vadEnabled) {
            this._sendMessage('stop_speaking', {});
        }
        
        this.isSpeaking = false;
        this._emitStatus('speaking_stopped');
    }

    _downsampleBuffer(buffer, inputRate, targetRate) {
        if (targetRate >= inputRate) {
            return buffer;
        }
        const ratio = inputRate / targetRate;
        const newLength = Math.round(buffer.length / ratio);
        const result = new Float32Array(newLength);
        let offsetResult = 0;
        let offsetBuffer = 0;
        while (offsetResult < result.length) {
            const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
            let accum = 0;
            let count = 0;
            for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
                accum += buffer[i];
                count++;
            }
            result[offsetResult] = accum / Math.max(1, count);
            offsetResult++;
            offsetBuffer = nextOffsetBuffer;
        }
        return result;
    }

    _floatTo16BitPCM(float32Array) {
        const output = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            let s = Math.max(-1, Math.min(1, float32Array[i]));
            output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        return output;
    }

    _arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
    
    /**
     * 初始化音频播放器
     */
    _initAudioPlayer() {
        this.audioQueue = [];
        this.isPlaying = false;
        this._currentSource = null;
    }
    
    /**
     * 播放音频数据
     */
    async _playAudio(base64Audio) {
        console.log('[TTS Debug] _playAudio 被调用, base64长度:', base64Audio?.length || 0);
        try {
            const binaryString = atob(base64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            console.log('[TTS Debug] base64解码成功, 字节数:', bytes.length);
            
            if (!this.audioContext || this.audioContext.state === 'closed') {
                console.log('[TTS Debug] 创建新的 AudioContext');
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            console.log('[TTS Debug] AudioContext 状态:', this.audioContext.state);
            
            if (this.audioContext.state === 'suspended') {
                console.log('[TTS Debug] 尝试恢复 AudioContext');
                await this.audioContext.resume();
                console.log('[TTS Debug] AudioContext 恢复后状态:', this.audioContext.state);
            }
            
            console.log('[TTS Debug] 开始解码音频数据...');
            const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer.slice(0));
            console.log('[TTS Debug] 音频解码成功, 时长:', audioBuffer.duration, '秒, 采样率:', audioBuffer.sampleRate);
            
            // 停止当前播放
            if (this._currentSource) {
                try { this._currentSource.stop(); } catch (e) {}
            }
            
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            
            this._currentSource = source;
            this.isAiSpeaking = true;
            this._emitStatus('ai_speaking_started');
            
            console.log('[TTS Debug] 开始播放音频...');
            return new Promise((resolve) => {
                source.onended = () => {
                    console.log('[TTS Debug] 音频播放结束');
                    this._currentSource = null;
                    this.isAiSpeaking = false;
                    this._emitStatus('ai_speaking_ended');
                    resolve();
                };
                source.start(0);
                console.log('[TTS Debug] 音频已开始播放');
            });
            
        } catch (error) {
            console.error('[TTS Debug] 播放音频失败:', error);
            this.isAiSpeaking = false;
        }
    }
    
    /**
     * 停止播放
     */
    _stopPlayback() {
        this.audioQueue = [];
        this.isPlaying = false;
        
        if (this._currentSource) {
            try { this._currentSource.stop(); } catch (e) {}
            this._currentSource = null;
        }
        
        this.isAiSpeaking = false;
    }
    
    /**
     * 处理音频队列
     */
    async _processAudioQueue() {
        console.log('[TTS Debug] _processAudioQueue 被调用, isPlaying:', this.isPlaying, '队列长度:', this.audioQueue.length, 'isInCall:', this.isInCall);
        if (this.isPlaying || this.audioQueue.length === 0) {
            console.log('[TTS Debug] 跳过处理: isPlaying=', this.isPlaying, '队列空=', this.audioQueue.length === 0);
            return;
        }
        
        this.isPlaying = true;
        console.log('[TTS Debug] 开始处理音频队列, 当前队列长度:', this.audioQueue.length);
        
        while (this.audioQueue.length > 0 && this.isInCall) {
            const audioData = this.audioQueue.shift();
            console.log('[TTS Debug] 从队列取出音频数据, 剩余:', this.audioQueue.length);
            await this._playAudio(audioData);
        }
        
        this.isPlaying = false;
        console.log('[TTS Debug] 音频队列处理完成');
    }
    
    /**
     * 开始音频可视化
     */
    _startVisualizer() {
        const updateVisualizer = () => {
            if (!this.analyser || !this.isInCall) return;
            
            const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.analyser.getByteFrequencyData(dataArray);
            this.visualizerData = dataArray;
            
            requestAnimationFrame(updateVisualizer);
        };
        
        updateVisualizer();
    }
    
    /**
     * 获取可视化数据
     */
    getVisualizerData() {
        return this.visualizerData;
    }
    
    /**
     * 处理WebSocket消息
     */
    _handleMessage(data) {
        try {
            const message = JSON.parse(data);
            const { type, data: msgData } = message;
            
            if (type !== 'pong') {
                console.log('[Voice Debug] 收到消息:', type, msgData ? JSON.stringify(msgData).substring(0, 100) : '');
            }
            
            switch (type) {
                case 'connected':
                    console.log('[Voice Debug] 服务器确认连接:', msgData);
                    break;
                    
                case 'transcript':
                    // ASR识别结果
                    console.log('[Voice Debug] ASR识别结果:', msgData.text, 'is_final:', msgData.is_final);
                    this.currentTranscript = msgData.text;
                    this.onTranscript(msgData.text, msgData.is_final);

                    // 添加到对话历史（用户）
                    if (msgData.text && msgData.is_final) {
                        this._addToHistory('user', msgData.text);
                    }
                    this._emitStatus('transcript_received', msgData);
                    break;

                case 'ai_text':
                    // AI文本回复
                    this.currentAiText = msgData.text;
                    this.onAiText(msgData.text);

                    // 添加到对话历史（AI）
                    if (msgData.text) {
                        this._addToHistory('ai', msgData.text);
                    }
                    this._emitStatus('ai_text_received', msgData);
                    break;
                    
                case 'ai_audio':
                    // AI音频回复
                    console.log('[TTS Debug] 收到 ai_audio 消息, audio长度:', msgData.audio?.length || 0, 'sampleRate:', msgData.sample_rate, 'duration:', msgData.duration_ms);
                    this.audioQueue.push(msgData.audio);
                    console.log('[TTS Debug] 音频已加入队列, 当前队列长度:', this.audioQueue.length);
                    this._processAudioQueue();
                    break;
                    
                case 'interrupted':
                    // 打断确认
                    console.log('AI已停止');
                    this._emitStatus('interrupted', msgData);
                    break;
                    
                case 'status':
                    // 状态更新
                    this._emitStatus('server_status', msgData);
                    break;
                    
                case 'error':
                    // 错误消息
                    console.error('服务器错误:', msgData);
                    this.onError(new Error(msgData.message));
                    break;
                    
                case 'pong':
                    // 心跳响应
                    break;
                    
                default:
                    console.log('未知消息类型:', type);
            }
            
        } catch (error) {
            console.error('处理消息失败:', error);
        }
    }
    
    /**
     * 发送消息
     */
    _sendMessage(type, data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            const errorMsg = 'WebSocket未连接，无法发送消息';
            console.warn('[Voice Debug]', errorMsg, 'readyState:', this.ws?.readyState);
            
            if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                this.onError(new Error('正在连接中，请稍后重试...'));
            } else if (this.ws && this.ws.readyState === WebSocket.CLOSING) {
                this.onError(new Error('连接正在关闭，请稍后重试...'));
            } else {
                this.onError(new Error('连接已断开，正在尝试重新连接...'));
                if (!this._intentionalClose) {
                    this._attemptReconnect();
                }
            }
            return false;
        }
        
        const message = {
            type: type,
            data: data,
            timestamp: Date.now()
        };
        
        this.ws.send(JSON.stringify(message));
        console.log('[Voice Debug] 发送消息:', type, data?.audio ? `audio(${data.audio.length}chars)` : JSON.stringify(data).substring(0, 100));
        return true;
    }
    
    /**
     * 发送心跳
     */
    _sendPing() {
        this._sendMessage('ping', {});
    }
    
    /**
     * 启动心跳机制
     */
    _startHeartbeat() {
        this._stopHeartbeat(); // 先停止旧的心跳
        
        this.missedHeartbeats = 0;
        this.heartbeatInterval = setInterval(() => {
            if (!this.isConnected) {
                this._stopHeartbeat();
                return;
            }
            
            this.missedHeartbeats++;
            
            if (this.missedHeartbeats > this.maxMissedHeartbeats) {
                console.warn('心跳超时，连接可能已断开');
                this._stopHeartbeat();
                this._handleConnectionLost();
                return;
            }
            
            this._sendPing();
        }, this.heartbeatTimeout);
        
        console.log('心跳机制已启动');
    }
    
    /**
     * 停止心跳机制
     */
    _stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
        this.missedHeartbeats = 0;
    }
    
    /**
     * 启动连接状态检测
     */
    _startConnectionCheck() {
        this._stopConnectionCheck(); // 先停止旧的检测
        
        this.lastMessageTime = Date.now();
        this.connectionCheckInterval = setInterval(() => {
            const now = Date.now();
            const elapsed = now - this.lastMessageTime;
            
            if (elapsed > this.connectionTimeout) {
                console.warn(`连接超时: ${elapsed}ms 无消息`);
                this._handleConnectionLost();
            }
        }, 10000); // 每10秒检查一次
        
        console.log('连接状态检测已启动');
    }
    
    /**
     * 停止连接状态检测
     */
    _stopConnectionCheck() {
        if (this.connectionCheckInterval) {
            clearInterval(this.connectionCheckInterval);
            this.connectionCheckInterval = null;
        }
    }
    
    /**
     * 处理连接丢失
     */
    _handleConnectionLost() {
        console.log('检测到连接丢失，尝试重连...');
        this._stopHeartbeat();
        this._stopConnectionCheck();
        
        if (this.ws) {
            try {
                this.ws.close();
            } catch (e) {}
        }
        
        this.isConnected = false;
        this._emitStatus('disconnected');
        
        if (!this._intentionalClose) {
            this._attemptReconnect();
        }
    }
    
    /**
     * 获取当前状态
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            isInCall: this.isInCall,
            isSpeaking: this.isSpeaking,
            isAiSpeaking: this.isAiSpeaking,
            currentTranscript: this.currentTranscript,
            currentAiText: this.currentAiText,
            conversationLength: this.conversationHistory.length
        };
    }
    
    /**
     * 获取对话历史
     */
    getConversationHistory() {
        return [...this.conversationHistory];
    }
    
    /**
     * 清空对话历史
     */
    
    /**
     * 添加到对话历史
     * @param {string} role - 'user' 或 'ai'
     * @param {string} text - 对话文本
     * @private
     */
    _addToHistory(role, text) {
        if (!text || typeof text !== 'string') return;

        const entry = {
            role: role,
            text: text.trim(),
            timestamp: Date.now()
        };

        this.conversationHistory.push(entry);

        // 限制历史长度
        if (this.conversationHistory.length > 100) {
            this.conversationHistory.shift();
        }

        // 触发历史更新回调
        this.onHistoryUpdate(role, text, entry);

        // 触发自定义事件
        const event = new CustomEvent('voiceCallHistory', {
            detail: { role, text, entry }
        });
        document.dispatchEvent(event);
    }

    /**
     * 清空对话历史
     */
    clearHistory() {
        this.conversationHistory = [];
        this.currentTranscript = '';
        this.currentAiText = '';

        // 触发自定义事件
        const event = new CustomEvent('voiceCallHistory', {
            detail: { action: 'clear' }
        });
        document.dispatchEvent(event);
    }

    /**
     * 触发状态变更事件
     */
    _emitStatus(status, data = null) {
        this.onStatusChange(status, data);
        
        // 触发自定义事件
        const event = new CustomEvent('voiceCallStatus', {
            detail: { status, data }
        });
        document.dispatchEvent(event);
    }
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceCall;
}
