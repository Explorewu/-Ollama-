/**
 * 音频降噪预处理模块 V2
 * 
 * 功能：
 * - 基于Web Audio API的多级降噪处理链
 * - 自适应噪声门控 (Adaptive Noise Gate)
 * - 自动增益控制 (AGC)
 * - 语音活动检测 (VAD) - 基于能量和过零率
 * - 频域滤波处理
 * - 实时降噪处理
 * 
 * 目标：提升噪声环境下语音识别准确率至 90%+
 */

class AudioNoiseReduction {
    constructor() {
        this.audioContext = null;
        this.isSupported = false;
        this.noiseProfile = null;
        this.noiseGateThreshold = -35; // dB - 噪声门阈值
        this.agcTargetLevel = -20; // dB - AGC目标电平
        this.vadThreshold = 0.015; // VAD能量阈值
        this.noiseFloor = 0; // 噪声底噪估计
        this.speechFrames = 0; // 语音帧计数
        this.totalFrames = 0; // 总帧计数
        this.isVoiceActive = false; // 当前是否有语音
        this.init();
    }

    async init() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // 检查浏览器支持
            if (!this.audioContext.createBiquadFilter || !this.audioContext.createDynamicsCompressor) {
                console.warn('[WARN] 浏览器不支持完整的音频处理功能');
                return;
            }
            
            this.isSupported = true;
            console.log('[INIT] 音频降噪模块V2初始化完成');
        } catch (error) {
            console.error('[ERROR] 音频降噪模块初始化失败:', error);
        }
    }

    /**
     * 应用完整的音频降噪处理链
     */
    async processAudioBuffer(audioBuffer) {
        if (!this.isSupported) {
            console.warn('音频降噪不可用，返回原始音频');
            return audioBuffer;
        }

        try {
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;

            // 创建处理链
            const highpassFilter = this.createHighpassFilter();
            const lowpassFilter = this.createLowpassFilter();
            const noiseGate = this.createNoiseGate();
            const compressor = this.createCompressor();
            const spectralFilter = this.createSpectralFilter();

            // 连接处理链：源 -> 高通 -> 低通 -> 噪声门 -> 压缩器 -> 频谱滤波 -> 目标
            source.connect(highpassFilter);
            highpassFilter.connect(lowpassFilter);
            lowpassFilter.connect(noiseGate);
            noiseGate.connect(compressor);
            compressor.connect(spectralFilter);

            // 创建目标节点
            const destination = this.audioContext.createMediaStreamDestination();
            spectralFilter.connect(destination);

            // 处理音频
            const processedBuffer = await this.recordProcessedAudio(source, destination);
            
            return processedBuffer;
        } catch (error) {
            console.error('音频处理失败:', error);
            return audioBuffer; // 降级到原始音频
        }
    }

    /**
     * 创建高通滤波器 (去除低频噪声)
     * 人声频率范围约80Hz-8kHz，低于80Hz的主要是环境噪声
     */
    createHighpassFilter() {
        const filter = this.audioContext.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.value = 80; // 80Hz
        filter.Q.value = 0.707; // 巴特沃斯响应
        return filter;
    }

    /**
     * 创建低通滤波器 (保留人声频率)
     * 人声主要能量集中在300Hz-3.4kHz，保留到4kHz足够
     */
    createLowpassFilter() {
        const filter = this.audioContext.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 4000; // 4kHz
        filter.Q.value = 0.707;
        return filter;
    }

    /**
     * 创建噪声门 (静音时自动关闭)
     * 当信号低于阈值时大幅衰减，有效去除背景噪声
     */
    createNoiseGate() {
        const compressor = this.audioContext.createDynamicsCompressor();
        compressor.threshold.value = this.noiseGateThreshold;
        compressor.knee.value = 0; // 硬拐点（更陡峭的衰减）
        compressor.ratio.value = 20; // 高压缩比（接近门限效果）
        compressor.attack.value = 0.003; // 3ms 快速启动
        compressor.release.value = 0.25; // 250ms 释放时间
        return compressor;
    }

    /**
     * 创建自动增益控制 (AGC)
     * 将语音信号电平稳定在目标水平，提高ASR识别率
     */
    createCompressor() {
        const compressor = this.audioContext.createDynamicsCompressor();
        compressor.threshold.value = this.agcTargetLevel;
        compressor.knee.value = 30; // 软拐点（更自然的压缩）
        compressor.ratio.value = 12; // 中等压缩比
        compressor.attack.value = 0.01; // 10ms 启动时间
        compressor.release.value = 0.15; // 150ms 释放时间
        return compressor;
    }

    /**
     * 创建频谱滤波器 (增强人声频段)
     * 使用多段均衡器针对性增强人声频率
     */
    createSpectralFilter() {
        const filters = [];
        
        // 低频增强 (80-300Hz) - 增加声音厚度
        const lowFilter = this.audioContext.createBiquadFilter();
        lowFilter.type = 'lowshelf';
        lowFilter.frequency.value = 250;
        lowFilter.gain.value = 2;
        filters.push(lowFilter);

        // 中频增强 (300-3000Hz) - 人声核心频段
        const midFilter = this.audioContext.createBiquadFilter();
        midFilter.type = 'peaking';
        midFilter.frequency.value = 1000;
        midFilter.Q.value = 1.0;
        midFilter.gain.value = 4; // 增强人声
        filters.push(midFilter);

        // 中高频增强 (2-4kHz) - 提高清晰度
        const midHighFilter = this.audioContext.createBiquadFilter();
        midHighFilter.type = 'peaking';
        midHighFilter.frequency.value = 3000;
        midHighFilter.Q.value = 1.5;
        midHighFilter.gain.value = 2;
        filters.push(midHighFilter);

        // 高频衰减 (4kHz以上) - 减少嘶嘶声
        const highFilter = this.audioContext.createBiquadFilter();
        highFilter.type = 'highshelf';
        highFilter.frequency.value = 4000;
        highFilter.gain.value = -3;
        filters.push(highFilter);

        // 连接所有滤波器
        let current = filters[0];
        for (let i = 1; i < filters.length; i++) {
            current.connect(filters[i]);
            current = filters[i];
        }
        
        return filters[0];
    }

    /**
     * 录制处理后的音频
     */
    async recordProcessedAudio(source, destination) {
        return new Promise((resolve) => {
            const recorder = new MediaRecorder(destination.stream);
            const chunks = [];

            recorder.ondataavailable = (event) => {
                chunks.push(event.data);
            };

            recorder.onstop = () => {
                const blob = new Blob(chunks, { type: 'audio/wav' });
                
                // 将 Blob 转换为 AudioBuffer
                const reader = new FileReader();
                reader.onload = () => {
                    this.audioContext.decodeAudioData(reader.result, (buffer) => {
                        resolve(buffer);
                    });
                };
                reader.readAsArrayBuffer(blob);
            };

            recorder.start();
            source.start();

            // 根据音频长度设置停止时间
            setTimeout(() => {
                recorder.stop();
            }, source.buffer.duration * 1000 + 100);
        });
    }

    /**
     * 实时音频处理 (用于流式识别)
     */
    createRealTimeProcessor() {
        if (!this.isSupported) {
            return null;
        }

        const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
        
        processor.onaudioprocess = (event) => {
            const inputBuffer = event.inputBuffer;
            const outputBuffer = event.outputBuffer;
            
            for (let channel = 0; channel < inputBuffer.numberOfChannels; channel++) {
                const inputData = inputBuffer.getChannelData(channel);
                const outputData = outputBuffer.getChannelData(channel);
                
                // 实时降噪处理
                this.applyRealTimeNoiseReduction(inputData, outputData);
            }
        };

        return processor;
    }

    /**
     * 实时降噪算法 - 改进的谱减法
     */
    applyRealTimeNoiseReduction(input, output) {
        const alpha = 0.95; // 平滑系数
        const beta = 0.02; // 降噪强度
        const minGain = 0.1; // 最小增益（防止完全静音）
        
        for (let i = 0; i < input.length; i++) {
            // 计算信号能量
            const signalEnergy = input[i] * input[i];
            
            // 估计噪声能量 (指数移动平均)
            if (this.noiseProfile === null) {
                this.noiseProfile = signalEnergy;
            } else {
                this.noiseProfile = alpha * this.noiseProfile + (1 - alpha) * signalEnergy;
            }
            
            // 谱减法降噪
            const noiseReduced = Math.max(minGain * signalEnergy, signalEnergy - beta * this.noiseProfile);
            output[i] = Math.sqrt(noiseReduced) * Math.sign(input[i]);
        }
    }

    /**
     * 语音活动检测 (VAD) - 基于能量和过零率
     * @param {AudioBuffer} audioBuffer - 音频缓冲区
     * @param {number} energyThreshold - 能量阈值
     * @param {number} zcrThreshold - 过零率阈值
     * @returns {boolean} - 是否检测到语音
     */
    detectVoiceActivity(audioBuffer, energyThreshold = null, zcrThreshold = null) {
        energyThreshold = energyThreshold || this.vadThreshold;
        zcrThreshold = zcrThreshold || 0.35;
        
        const data = audioBuffer.getChannelData(0);
        let energy = 0;
        let zeroCrossings = 0;
        
        // 计算RMS能量
        for (let i = 0; i < data.length; i++) {
            energy += data[i] * data[i];
        }
        const rms = Math.sqrt(energy / data.length);
        
        // 计算过零率 (ZCR)
        for (let i = 1; i < data.length; i++) {
            if ((data[i] >= 0 && data[i-1] < 0) || (data[i] < 0 && data[i-1] >= 0)) {
                zeroCrossings++;
            }
        }
        const zcr = zeroCrossings / data.length;
        
        // 语音特征：中等能量 + 适中过零率
        // 噪声通常要么能量很低，要么过零率很高（高频噪声）
        const isSpeech = rms > energyThreshold && zcr < zcrThreshold;
        
        return isSpeech;
    }

    /**
     * 自适应噪声底噪估计
     * 在静音期间学习噪声特征
     */
    estimateNoiseFloor(audioBuffer) {
        const data = audioBuffer.getChannelData(0);
        let energy = 0;
        
        for (let i = 0; i < data.length; i++) {
            energy += data[i] * data[i];
        }
        
        const rms = Math.sqrt(energy / data.length);
        
        // 如果当前帧能量很低，认为是噪声，更新噪声底噪估计
        if (rms < this.vadThreshold * 2) {
            this.noiseFloor = this.noiseFloor * 0.9 + rms * 0.1;
        }
        
        return this.noiseFloor;
    }

    /**
     * 获取处理统计信息
     */
    getStatistics() {
        return {
            supported: this.isSupported,
            noiseGateThreshold: this.noiseGateThreshold,
            agcTargetLevel: this.agcTargetLevel,
            vadThreshold: this.vadThreshold,
            noiseFloor: this.noiseFloor,
            isVoiceActive: this.isVoiceActive,
            noiseProfile: this.noiseProfile
        };
    }
}

// 导出模块
window.AudioNoiseReduction = AudioNoiseReduction;
