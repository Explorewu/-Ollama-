/**
 * 本地 llama.cpp 图像生成前端集成模块
 * 与现有 ImageGen 模块协同工作
 */

const NativeImageGen = {
    serverUrl: `http://${window.location.hostname || 'localhost'}:5001`,
    state: {
        isGenerating: false,
        history: [],
        selectedModel: "z-image-turbo-art",
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
            console.log('✅ NativeImageGen 初始化完成');
        } catch (error) {
            console.error('NativeImageGen 初始化失败:', error);
            this.state.isInitialized = true;
        }
    },

    getStatus() {
        return {
            isInitialized: this.state.isInitialized,
            isHealthy: this.state.serverHealthy,
            isGenerating: this.state.isGenerating,
            modelCount: 1,
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
            
            const modelsUrl = `${this.serverUrl}/api/native_llama_cpp_image/models`;
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            try {
                const response = await fetch(modelsUrl, { signal: controller.signal });
                clearTimeout(timeoutId);
                const data = await response.json();
                
                if (data && data.success) {
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
                "z-image-turbo-art": {
                    "name": "Z-Image-Turbo-Art (本地)",
                    "description": "使用本地llama.cpp的高质量图像生成模型",
                    "default_prompt": "masterpiece, best quality, highly detailed, artistic, creative, vibrant colors",
                    "default_negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
                }
            },
            current_model: "z-image-turbo-art",
            llama_cpp_available: false
        };
    },

    async generate(params) {
        const {
            model = "z-image-turbo-art",
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
                    error: "本地llama.cpp图像服务未启动，请先运行: start_native_llama_cpp_service.bat"
                };
            }

            const generateUrl = `${this.serverUrl}/api/native_llama_cpp_image/generate`;
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
                const imageUrl = result.image_url ? `${this.serverUrl}${result.image_url}` : result.imageUrl;
                const data = {
                    url: imageUrl,
                    filename: result.filename,
                    model: result.model,
                    prompt: result.prompt,
                    mode: result.mode || "native", // native 或 simulated
                    generation_time: result.generation_time,
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
                    mode: data.mode,
                    generationTime: data.generation_time,
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
                    ? "本地llama.cpp图像服务未启动，请先运行: start_native_llama_cpp_service.bat"
                    : error.message
            };
        } finally {
            this.state.isGenerating = false;
        }
    },

    async checkHealth() {
        try {
            const response = await fetch(`${this.serverUrl}/api/native_llama_cpp_image/health`);
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
            "z-image-turbo-art": {
                positive: "masterpiece, best quality, highly detailed, artistic, creative, vibrant colors",
                negative: "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, low quality"
            }
        };
        return templates[modelKey] || templates["z-image-turbo-art"];
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
            "realistic": {
                name: "写实",
                suffix: "photorealistic, realistic, natural, professional photography"
            },
            "abstract": {
                name: "抽象艺术",
                suffix: "abstract art, colorful, artistic, creative, modern art"
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
            const switchUrl = `${this.serverUrl}/api/native_llama_cpp_image/load_model`;
            
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
                mode: "simulated"
            };
        }
    },
    
    async getStats() {
        try {
            const response = await fetch(`${this.serverUrl}/api/native_llama_cpp_image/health`);
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

// 扩展现有的ImageGen模块
if (window.ImageGen) {
    // 保存原始的generate方法
    const originalGenerate = ImageGen.generate.bind(ImageGen);
    
    // 重写generate方法，优先使用本地服务
    ImageGen.generate = async function(params) {
        // 首先尝试使用本地llama.cpp服务
        try {
            const result = await NativeImageGen.generate(params);
            if (result.success) {
                console.log('✅ 使用本地llama.cpp服务生成图像');
                return result;
            }
        } catch (error) {
            console.log('❌ 本地服务不可用，回退到原服务:', error.message);
        }
        
        // 如果本地服务不可用，使用原始服务
        console.log('🔄 回退到原始图像生成服务');
        return originalGenerate(params);
    };
    
    // 扩展模型列表
    const originalGetModels = ImageGen.getModels.bind(ImageGen);
    ImageGen.getModels = async function() {
        const originalModels = await originalGetModels();
        
        // 添加本地模型
        try {
            const nativeModels = await NativeImageGen.getModels();
            if (nativeModels && nativeModels.success) {
                // 合并模型列表
                const combinedModels = { ...originalModels };
                if (combinedModels.models) {
                    combinedModels.models["z-image-turbo-art-local"] = {
                        id: "z-image-turbo-art-local",
                        name: "Z-Image-Turbo-Art (本地)",
                        style: "艺术创作",
                        size: "~12GB",
                        pipeline: "LlamaCppDiffusion",
                        description: "使用本地llama.cpp的高质量图像生成模型",
                        local: true
                    };
                }
                return combinedModels;
            }
        } catch (error) {
            console.log('获取本地模型列表失败:', error.message);
        }
        
        return originalModels;
    };
    
    // 初始化本地服务
    NativeImageGen.init();
}

// 导出模块
window.NativeImageGen = NativeImageGen;