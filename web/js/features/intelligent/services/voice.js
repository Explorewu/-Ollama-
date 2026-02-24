/**
 * 语音识别服务模块
 *
 * 提供语音输入相关的业务逻辑，包括：
 * - 开始/停止录音
 * - 音频数据处理
 * - 语音识别
 * - 录音状态管理
 */

const VoiceService = (function() {
    // API基础URL
    const API_BASE = `http://${window.location.hostname || 'localhost'}:5001`;

    // 录音配置
    const RECORDING_CONFIG = {
        mimeType: 'audio/webm',
        audioBitsPerSecond: 128000
    };

    // 状态回调
    let stateCallbacks = {
        onStart: null,
        onStop: null,
        onData: null,
        onError: null,
        onTranscription: null
    };

    /**
     * 初始化语音服务
     * @returns {Promise<boolean>}
     */
    async function init() {
        try {
            // 检查浏览器支持
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.warn('[VoiceService] 浏览器不支持录音功能');
                return false;
            }

            console.log('[VoiceService] 初始化完成');
            return true;
        } catch (error) {
            console.error('[VoiceService] 初始化失败:', error);
            return false;
        }
    }

    /**
     * 检查浏览器是否支持录音
     * @returns {boolean}
     */
    function isSupported() {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }

    /**
     * 开始录音
     * @returns {Promise<Object>}
     */
    async function startRecording() {
        if (!isSupported()) {
            return {
                success: false,
                error: '浏览器不支持录音功能'
            };
        }

        const currentState = window.IntelligentStore.getState();
        if (currentState.isRecording) {
            return {
                success: false,
                error: '正在录音中'
            };
        }

        try {
            // 获取麦克风权限
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // 创建MediaRecorder
            const mediaRecorder = new MediaRecorder(stream, RECORDING_CONFIG);
            const audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);

                    // 触发数据回调
                    if (stateCallbacks.onData) {
                        stateCallbacks.onData(event.data);
                    }
                }
            };

            mediaRecorder.onstop = async () => {
                // 停止所有轨道
                stream.getTracks().forEach(track => track.stop());

                // 合并音频数据
                const audioBlob = new Blob(audioChunks, { type: RECORDING_CONFIG.mimeType });

                // 触发停止回调
                if (stateCallbacks.onStop) {
                    stateCallbacks.onStop(audioBlob);
                }

                // 自动进行语音识别
                await transcribeAudio(audioBlob);
            };

            mediaRecorder.onerror = (error) => {
                console.error('[VoiceService] 录音错误:', error);

                if (stateCallbacks.onError) {
                    stateCallbacks.onError(error);
                }

                stopRecording();
            };

            // 开始录音
            mediaRecorder.start(100); // 每100ms收集一次数据

            // 更新状态
            window.IntelligentStore.setState({
                isRecording: true,
                mediaRecorder: mediaRecorder,
                audioChunks: audioChunks
            }, 'VoiceService.startRecording');

            // 触发开始回调
            if (stateCallbacks.onStart) {
                stateCallbacks.onStart();
            }

            return { success: true };
        } catch (error) {
            console.error('[VoiceService] 开始录音失败:', error);

            let errorMessage = '无法访问麦克风';
            if (error.name === 'NotAllowedError') {
                errorMessage = '请允许使用麦克风权限';
            } else if (error.name === 'NotFoundError') {
                errorMessage = '未找到麦克风设备';
            }

            return {
                success: false,
                error: errorMessage
            };
        }
    }

    /**
     * 停止录音
     * @returns {Promise<Object>}
     */
    async function stopRecording() {
        const currentState = window.IntelligentStore.getState();

        if (!currentState.isRecording || !currentState.mediaRecorder) {
            return {
                success: false,
                error: '当前没有在录音'
            };
        }

        try {
            currentState.mediaRecorder.stop();

            // 更新状态
            window.IntelligentStore.setState({
                isRecording: false,
                mediaRecorder: null,
                audioChunks: []
            }, 'VoiceService.stopRecording');

            return { success: true };
        } catch (error) {
            console.error('[VoiceService] 停止录音失败:', error);

            // 重置状态
            window.IntelligentStore.setState({
                isRecording: false,
                mediaRecorder: null,
                audioChunks: []
            }, 'VoiceService.stopRecording');

            return {
                success: false,
                error: '停止录音失败'
            };
        }
    }

    /**
     * 切换录音状态
     * @returns {Promise<Object>}
     */
    async function toggleRecording() {
        const currentState = window.IntelligentStore.getState();

        if (currentState.isRecording) {
            return stopRecording();
        } else {
            return startRecording();
        }
    }

    /**
     * 语音识别
     * @param {Blob} audioBlob - 音频数据
     * @returns {Promise<Object>}
     */
    async function transcribeAudio(audioBlob) {
        if (!audioBlob || audioBlob.size === 0) {
            return {
                success: false,
                error: '音频数据为空'
            };
        }

        try {
            // 创建FormData
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            // 发送识别请求
            const response = await fetch(`${API_BASE}/api/voice/transcribe`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success && stateCallbacks.onTranscription) {
                stateCallbacks.onTranscription(result.data);
            }

            return result;
        } catch (error) {
            console.error('[VoiceService] 语音识别失败:', error);

            return {
                success: false,
                error: '语音识别失败，请检查服务连接'
            };
        }
    }

    /**
     * 设置状态回调
     * @param {Object} callbacks - 回调函数对象
     */
    function setCallbacks(callbacks) {
        stateCallbacks = { ...stateCallbacks, ...callbacks };
    }

    /**
     * 获取录音状态
     * @returns {boolean}
     */
    function isRecording() {
        return window.IntelligentStore.getStateByPath('isRecording') || false;
    }

    /**
     * 获取录音时长（毫秒）
     * @returns {number}
     */
    function getRecordingDuration() {
        const state = window.IntelligentStore.getState();
        if (!state.isRecording || !state.mediaRecorder) {
            return 0;
        }

        // 这里可以添加更精确的时间计算
        return state.mediaRecorder.state === 'recording' ? Date.now() : 0;
    }

    // 公共API
    return {
        init,
        isSupported,
        startRecording,
        stopRecording,
        toggleRecording,
        transcribeAudio,
        setCallbacks,
        isRecording,
        getRecordingDuration
    };
})();

// 导出模块
window.VoiceService = VoiceService;
