/**
 * Vision API - 视觉理解服务客户端
 * 
 * 功能：与后端 Qwen3-VL-4B 视觉服务通信
 * 支持：图片分析、OCR识别、图片描述
 */

const VisionAPI = {
    // 服务配置
    config: {
        baseUrl: `http://${window.location.hostname || 'localhost'}:5003`,
        timeout: 120000,
        retryCount: 2,
        retryDelay: 1000
    },

    // 服务状态
    status: {
        available: false,
        modelLoaded: false,
        lastCheck: null,
        error: null
    },

    /**
     * 初始化视觉服务
     */
    async init() {
        console.log('[VisionAPI] 初始化视觉理解服务...');
        await this.checkStatus();
        return this.status.available;
    },

    /**
     * 检查服务状态
     */
    async checkStatus() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);

            const response = await fetch(`${this.config.baseUrl}/api/vision/status`, {
                method: 'GET',
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                this.status = {
                    available: data.status === 'online',
                    modelLoaded: data.model_loaded,
                    lastCheck: Date.now(),
                    error: data.load_error || null
                };
                console.log('[VisionAPI] 服务状态:', this.status);
            } else {
                this.status.available = false;
                this.status.error = `HTTP ${response.status}`;
            }
        } catch (error) {
            this.status.available = false;
            this.status.error = error.message;
            console.warn('[VisionAPI] 服务不可用:', error.message);
        }
        return this.status;
    },

    /**
     * 预加载模型
     */
    async loadModel() {
        if (this.status.modelLoaded) {
            return { success: true, message: '模型已加载' };
        }

        try {
            const response = await fetch(`${this.config.baseUrl}/api/vision/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            if (data.success) {
                this.status.modelLoaded = true;
            }
            return data;
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    /**
     * 分析图片
     * @param {string} imageData - Base64编码的图片数据（支持 data:image/xxx;base64, 前缀）
     * @param {string} prompt - 分析提示词
     * @returns {Promise<{success: boolean, result?: string, error?: string}>}
     */
    async analyze(imageData, prompt = '请详细描述这张图片的内容') {
        if (!this.status.available) {
            const status = await this.checkStatus();
            if (!status.available) {
                return { 
                    success: false, 
                    error: '视觉服务不可用，请确保服务已启动',
                    fallback: true
                };
            }
        }

        let lastError = null;
        for (let attempt = 0; attempt <= this.config.retryCount; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

                const response = await fetch(`${this.config.baseUrl}/api/vision/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: imageData, prompt }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP ${response.status}`);
                }

                const data = await response.json();
                
                if (data.success) {
                    return {
                        success: true,
                        result: data.result,
                        elapsed: data.elapsed_seconds,
                        prompt: data.prompt
                    };
                } else {
                    throw new Error(data.error || '分析失败');
                }

            } catch (error) {
                lastError = error;
                console.warn(`[VisionAPI] 分析尝试 ${attempt + 1} 失败:`, error.message);
                
                if (error.name === 'AbortError') {
                    return { success: false, error: '请求超时，图片分析时间过长' };
                }

                if (attempt < this.config.retryCount) {
                    await this._delay(this.config.retryDelay * (attempt + 1));
                }
            }
        }

        return { success: false, error: lastError?.message || '图片分析失败' };
    },

    /**
     * OCR 文字识别
     * @param {string} imageData - Base64图片数据
     * @param {string} language - 语言（chinese/english）
     */
    async ocr(imageData, language = 'chinese') {
        if (!this.status.available) {
            await this.checkStatus();
            if (!this.status.available) {
                return { success: false, error: '视觉服务不可用' };
            }
        }

        try {
            const response = await fetch(`${this.config.baseUrl}/api/vision/ocr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData, language })
            });

            const data = await response.json();
            return {
                success: data.success !== false,
                text: data.text,
                elapsed: data.elapsed_seconds,
                error: data.error
            };

        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    /**
     * 快速图片描述
     * @param {string} imageData - Base64图片数据
     */
    async describe(imageData) {
        if (!this.status.available) {
            await this.checkStatus();
            if (!this.status.available) {
                return { success: false, error: '视觉服务不可用' };
            }
        }

        try {
            const response = await fetch(`${this.config.baseUrl}/api/vision/describe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });

            const data = await response.json();
            return {
                success: data.success !== false,
                description: data.description,
                elapsed: data.elapsed_seconds,
                error: data.error
            };

        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    /**
     * 使用 Ollama 视觉模型（备用方案）
     * @param {string} imageData - Base64图片数据
     * @param {string} prompt - 提示词
     * @param {string} model - 视觉模型名称
     */
    async analyzeWithOllama(imageData, prompt = '请描述这张图片', model = 'llava:7b') {
        try {
            // 提取纯 base64 数据
            let base64Data = imageData;
            if (imageData.includes(',')) {
                base64Data = imageData.split(',')[1];
            }

            const response = await fetch(`http://${window.location.hostname || 'localhost'}:11434/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: model,
                    prompt: prompt,
                    images: [base64Data],
                    stream: false
                })
            });

            if (!response.ok) {
                throw new Error(`Ollama 返回 ${response.status}`);
            }

            const data = await response.json();
            return {
                success: true,
                result: data.response,
                model: model
            };

        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    /**
     * 延迟函数
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    /**
     * 压缩图片（用于大图优化）
     * @param {string} imageData - Base64图片数据
     * @param {number} maxWidth - 最大宽度
     * @param {number} quality - 压缩质量 0-1
     */
    async compressImage(imageData, maxWidth = 1024, quality = 0.8) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;

                if (width > maxWidth) {
                    height = Math.round((height * maxWidth) / width);
                    width = maxWidth;
                }

                canvas.width = width;
                canvas.height = height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                const compressedData = canvas.toDataURL('image/jpeg', quality);
                resolve(compressedData);
            };
            img.onerror = () => reject(new Error('图片加载失败'));
            img.src = imageData;
        });
    }
};

// 图片生成 API 模块
const ImageGenAPI = {
    config: {
        baseUrl: `http://${window.location.hostname || 'localhost'}:5001`,
        defaultModel: 'z-image-turbo-art',
        timeout: 300000  // 5分钟超时
    },

    modelAliases: {
        'z-image-turbo-art': 'z-image-turbo'
    },

    status: {
        available: false,
        currentModel: null,
        models: []
    },

    /**
     * 初始化图片生成服务
     */
    async init() {
        console.log('[ImageGenAPI] 初始化图片生成服务...');
        await this.checkStatus();
        await this.loadModels();
        return this.status.available;
    },

    /**
     * 检查服务状态
     */
    async checkStatus() {
        try {
            const response = await fetch(`${this.config.baseUrl}/api/health`);
            if (response.ok) {
                const data = await response.json();
                this.status.available = data.success && data.data?.services?.image?.status === 'ready';
                this.status.currentModel = data.data?.services?.image?.model;
                return this.status;
            }
        } catch (error) {
            this.status.available = false;
            console.warn('[ImageGenAPI] 服务不可用:', error.message);
        }
        return this.status;
    },

    /**
     * 获取可用模型列表
     */
    async loadModels() {
        try {
            const response = await fetch(`${this.config.baseUrl}/api/models`);
            if (response.ok) {
                const data = await response.json();
                if (data.success || data.models) {
                    this.status.models = Object.entries(data.models || {}).map(([key, value]) => ({
                        id: key,
                        ...value
                    }));

                    const availableIds = this.status.models.map(m => m.id);
                    if (availableIds.length > 0) {
                        this.config.defaultModel = this.resolveModelKey(this.config.defaultModel, availableIds);
                    }
                }
            }
        } catch (error) {
            console.warn('[ImageGenAPI] 获取模型列表失败:', error.message);
        }
        return this.status.models;
    },

    /**
     * 解析模型别名并回退到可用模型
     * @param {string} model - 请求模型ID
     * @param {string[]} availableIds - 可用模型列表
     */
    resolveModelKey(model, availableIds = []) {
        const normalized = this.modelAliases[model] || model;
        if (!availableIds.length) return normalized;
        if (availableIds.includes(normalized)) return normalized;
        return availableIds[0];
    },

    /**
     * 生成图片
     * @param {object} params - 生成参数
     * @param {string} params.prompt - 正向提示词
     * @param {string} params.negative_prompt - 负向提示词
     * @param {string} params.model - 模型ID
     * @param {number} params.width - 宽度
     * @param {number} params.height - 高度
     * @param {number} params.steps - 推理步数
     * @param {number} params.cfg_scale - CFG Scale
     * @param {function} onProgress - 进度回调
     */
    async generate(params, onProgress = null) {
        const {
            prompt,
            negative_prompt = '',
            model = this.config.defaultModel,
            width = 512,
            height = 512,
            steps = 20,
            cfg_scale = 7
        } = params;

        if (!prompt) {
            return { success: false, error: '提示词不能为空' };
        }

        try {
            if (!this.status.models.length) {
                await this.loadModels();
            }

            const availableIds = this.status.models.map(m => m.id);
            if (!availableIds.length) {
                return { success: false, error: '未检测到可用绘图模型' };
            }

            const resolvedModel = this.resolveModelKey(model, availableIds);

            if (onProgress) {
                onProgress({ status: 'starting', message: '正在初始化模型...' });
            }

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

            const response = await fetch(`${this.config.baseUrl}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: resolvedModel,
                    prompt,
                    negative_prompt,
                    width,
                    height,
                    steps,
                    cfg_scale
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                const imageData = data.data || data;
                return {
                    success: true,
                    imageUrl: `${this.config.baseUrl}${imageData.image_url}`,
                    filename: imageData.filename,
                    model: imageData.model,
                    prompt: imageData.prompt
                };
            } else {
                throw new Error(data.error || '生成失败');
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                return { success: false, error: '生成超时，请尝试减少步数或图片尺寸' };
            }
            return { success: false, error: error.message };
        }
    },

    /**
     * 检测用户消息是否包含图片生成意图
     * @param {string} message - 用户消息
     */
    detectGenerateIntent(message) {
        const text = (message || '').trim();
        if (!text) return false;

        // 允许“生成图片/图片生成”任意词序，兼容“适合生成图片”。
        const hasImageWord = /(图片|图像|插画|配图|image|picture|illustration|artwork)/i.test(text);
        const hasGenerateWord = /(生成|绘制|画|作画|绘画|文生图|渲染|create|generate|draw|paint|render)/i.test(text);
        if (hasImageWord && hasGenerateWord) return true;

        const patterns = [
            /^(画|绘制|生成|创作|制作|设计|渲染|想象|描绘)(一|张|幅|个|副)?/,
            /(画一|画个|画张|画幅|生成一|生成个|生成张|生成幅)/,
            /^(给我|帮我|请)(画|生成|创建|制作)/,
            /(图片生成|生成图片|AI作画|AI绘画|文生图)/,
            /^(create|generate|draw|make|paint)\s+(a|an|the)?\s*(image|picture|illustration)/i
        ];

        return patterns.some(pattern => pattern.test(text));
    },

    /**
     * 从用户消息中提取图片生成提示词
     * @param {string} message - 用户消息
     */
    extractPrompt(message) {
        const raw = (message || '').trim();
        if (!raw) return '';

        // 优先取引号内最长文本，适配“描述：‘...’”格式
        const quoted = raw.match(/[“"']([^“”"']{8,})[”"']/g);
        if (quoted && quoted.length) {
            const best = quoted
                .map(item => item.replace(/^[“"']|[”"']$/g, '').trim())
                .filter(Boolean)
                .sort((a, b) => b.length - a.length)[0];
            if (best) return best;
        }

        let source = raw;
        const descMatch = raw.match(/描述\s*[：:]\s*([\s\S]+)/);
        if (descMatch && descMatch[1]) {
            source = descMatch[1].trim();
        }

        source = source
            .replace(/^#{1,6}\s+/gm, '')
            .replace(/\*\*/g, '')
            .replace(/`{1,3}/g, '')
            .replace(/^\s*[-*]\s+/gm, '')
            .trim();

        // 移除中文指令前缀
        let prompt = source
            .replace(/^(画|绘制|生成|创作|制作|设计|渲染|想象|描绘)(一|张|幅|个|副)?/, '')
            .replace(/^(给我|帮我|请)(画|生成|创建|制作)/, '')
            .replace(/(的图片|的图像|的画)$/, '')
            .trim();

        // 移除英文指令前缀
        prompt = prompt
            .replace(/^(create|generate|draw|make|paint)\s+(a|an|the)?\s*(image|picture|illustration)\s*(of)?\s*/i, '')
            .trim();

        return prompt || raw;
    }
};

// 导出模块
window.VisionAPI = VisionAPI;
window.ImageGenAPI = ImageGenAPI;
