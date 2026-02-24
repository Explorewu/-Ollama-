/**
 * 文生图 API 模块
 * 集成到聊天和群组功能中
 */

const ImageGen = {
    serverUrl: `http://${window.location.hostname || 'localhost'}:5001`,
    state: {
        isGenerating: false,
        history: [],
        selectedModel: "z-image-turbo",
        isInitialized: false,
        serverHealthy: false,
        modelsCache: null,
        modelsCacheTime: 0
    },

    async init() {
        if (this.state.isInitialized) return;
        
        try {
            this.state.serverHealthy = await this.checkHealth();
            this.state.isInitialized = true;
            console.log('✅ ImageGen 初始化完成');
        } catch (error) {
            console.error('ImageGen 初始化失败:', error);
            this.state.isInitialized = true;
        }
    },

    getStatus() {
        return {
            isInitialized: this.state.isInitialized,
            isHealthy: this.state.serverHealthy,
            isGenerating: this.state.isGenerating,
            modelCount: 3,
            selectedModel: this.state.selectedModel,
            historyCount: this.state.history.length
        };
    },

    async getModels() {
        try {
            const CACHE_DURATION = 30000;
            const now = Date.now();
            
            if (this.state.modelsCache && (now - this.state.modelsCacheTime) < CACHE_DURATION) {
                return this.state.modelsCache;
            }
            
            const modelsUrl = `${this.serverUrl}/api/models`;
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            try {
                const response = await fetch(modelsUrl, { signal: controller.signal });
                clearTimeout(timeoutId);
                const data = await response.json();
                
                if (data && (data.success || data.models)) {
                    this.state.modelsCache = data;
                    this.state.modelsCacheTime = now;
                    return data;
                }
            } catch (fetchError) {
                clearTimeout(timeoutId);
                throw fetchError;
            }
            
            return this.state.modelsCache || this.getDefaultModels();
        } catch (error) {
            console.error("获取模型列表失败:", error);
            if (this.state.modelsCache) {
                return this.state.modelsCache;
            }
            return this.getDefaultModels();
        }
    },

    getDefaultModels() {
        return {
            success: true,
            models: {
                "z-image-turbo": {
                    "id": "Tongyi-MAI/Z-Image-Turbo",
                    "name": "Z-Image Turbo",
                    "style": "通用",
                    "size": "~6GB"
                }
            },
            current_model: "z-image-turbo",
            device: "cpu",
            preloaded: []
        };
    },

    async generate(params) {
        const {
            model = "z-image-turbo",
            prompt = "",
            negativePrompt = "",
            width = 384,
            height = 384,
            steps = 20,
            cfgScale = 7
        } = params;

        if (this.state.isGenerating) {
            return {
                success: false,
                error: "已有任务正在进行中，请稍候..."
            };
        }

        this.state.isGenerating = true;

        try {
            const isHealthy = await this.checkHealth();
            if (!isHealthy) {
                return {
                    success: false,
                    error: "文生图服务未启动或端口不可达，请先运行: python server/image_server.py"
                };
            }

            const generateUrl = `${this.serverUrl}/api/generate`;
            const response = await fetch(generateUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    model,
                    prompt,
                    negative_prompt: negativePrompt,
                    width: Math.min(width, 512),
                    height: Math.min(height, 512),
                    steps: Math.min(steps, 50),
                    cfg_scale: Math.min(Math.max(cfgScale, 1), 20)
                })
            });

            let result = null;
            try {
                result = await response.json();
            } catch (error) {
                result = null;
            }

            if (!response.ok) {
                return {
                    success: false,
                    error: (result && result.error) ? result.error : `服务响应异常(${response.status})`
                };
            }

            if (result.success) {
                // 兼容两种返回格式: {data: {...}} 或直接 {...}
                const imageData = result.data || result;
                const imageUrl = imageData.image_url ? `${this.serverUrl}${imageData.image_url}` : imageData.imageUrl;
                const data = {
                    url: imageUrl,
                    filename: imageData.filename,
                    model: imageData.model,
                    prompt: prompt,
                    timestamp: Date.now()
                };
                
                this.state.history.unshift(data);
                if (this.state.history.length > 50) {
                    this.state.history.pop();
                }

                return {
                    success: true,
                    imageUrl: data.url,
                    filename: data.filename,
                    model: data.model,
                    prompt: data.prompt,
                    timestamp: data.timestamp
                };
            } else {
                return {
                    success: false,
                    error: (result && result.error) ? result.error : "生成失败，请重试"
                };
            }
        } catch (error) {
            console.error("图片生成失败:", error);
            return {
                success: false,
                error: error.message === "Failed to fetch"
                    ? "文生图服务未启动或端口不可达，请先运行: python server/image_server.py"
                    : error.message
            };
        } finally {
            this.state.isGenerating = false;
        }
    },

    async checkHealth() {
        try {
            const response = await fetch(`${this.serverUrl}/api/health`);
            const result = await response.json();
            const isHealthy = result.status === "ok" || result.success;
            this.state.serverHealthy = isHealthy;
            return isHealthy;
        } catch (error) {
            this.state.serverHealthy = false;
            return false;
        }
    },

    getDefaultPrompt(modelKey) {
        const templates = {
            "ssd-1b": {
                positive: "masterpiece, best quality, highly detailed, professional photography, realistic",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality, worst quality"
            },
            "kook-qwen-2512": {
                positive: "masterpiece, best quality, highly detailed, anime style, illustration",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality, worst quality"
            },
            "z-image-turbo-art": {
                positive: "masterpiece, best quality, highly detailed, artistic, creative, vibrant colors",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
            },
            "z-image-turbo": {
                positive: "masterpiece, best quality, highly detailed, professional photography",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
            },
            "stable-diffusion-1.5": {
                positive: "best quality, masterpiece, high resolution, detailed",
                negative: "low quality, worst quality, blurry, deformed, ugly"
            },
            "waifu-diffusion-v1-4": {
                positive: "anime style, detailed eyes, beautiful face, colorful, illustration",
                negative: "blurry, bad anatomy, deformed eyes, text, watermark"
            },
            "anything-v3": {
                positive: "anime style, beautiful detailed eyes, beautiful detailed face, soft lighting",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers"
            }
        };
        return templates[modelKey] || templates["z-image-turbo"];
    },

    getStyleTemplates() {
        return {
            "japanese_anime": {
                name: "日式动漫",
                suffix: "anime style, japanese animation, cel shading, vibrant colors"
            },
            "cyberpunk": {
                name: "赛博朋克",
                suffix: "cyberpunk, neon lights, futuristic city, sci-fi, dystopian"
            },
            "fantasy": {
                name: "奇幻",
                suffix: "fantasy, magical, ethereal, mystical, dreamlike"
            },
            "portrait": {
                name: "人像",
                suffix: "portrait, beautiful face, detailed eyes, professional photography"
            },
            "landscape": {
                name: "风景",
                suffix: "landscape, beautiful scenery, nature, breathtaking view"
            },
            "fantasy_anime": {
                name: "幻想动漫",
                suffix: "fantasy anime, magical girl, ethereal, beautiful wings"
            },
            "realistic": {
                name: "写实",
                suffix: "photorealistic, realistic, natural, professional photography"
            },
            "sketch": {
                name: "素描",
                suffix: "sketch, drawing, pencil, artistic, hand drawn"
            }
        };
    },

    selectModel(modelKey) {
        this.state.selectedModel = modelKey;
    },

    getHistory() {
        return this.state.history;
    },

    clearHistory() {
        this.state.history = [];
    },

    async switchModel(modelKey) {
        try {
            const switchUrl = `${this.serverUrl}/api/switch`;
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);
            
            const response = await fetch(switchUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ model: modelKey }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            const result = await response.json();
            
            if (result.success) {
                this.state.selectedModel = modelKey;
                return result;
            } else {
                return { success: false, error: result.error || "切换失败" };
            }
        } catch (error) {
            console.error("切换模型失败:", error);
            
            this.state.selectedModel = modelKey;
            return {
                success: true,
                message: "已选择模型（本地模式）",
                model: modelKey,
                cached: false
            };
        }
    },
    
    async preloadModel(modelKey) {
        try {
            const preloadUrl = `${this.serverUrl}/api/preload`;
            
            const response = await fetch(preloadUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ model: modelKey })
            });
            
            return await response.json();
        } catch (error) {
            console.error("预加载模型失败:", error);
            return { success: false, error: error.message };
        }
    },
    
    async getStats() {
        try {
            const response = await fetch(`${this.serverUrl}/api/stats`);
            return await response.json();
        } catch (error) {
            console.error("获取统计失败:", error);
            return null;
        }
    },

    downloadImage(url, filename) {
        const link = document.createElement('a');
        link.href = url;
        link.download = filename || 'generated_image.png';
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
};

window.ImageGen = ImageGen;
