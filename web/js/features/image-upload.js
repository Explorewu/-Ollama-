/**
 * 图片上传模块
 * 提供图片选择、预览、压缩和基本处理功能
 */

const ImageUploader = (function() {
    // 支持的图片格式
    const SUPPORTED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    
    // 最大文件大小 (5MB)
    const MAX_FILE_SIZE = 5 * 1024 * 1024;
    
    // 最大图片尺寸 (4096px)
    const MAX_IMAGE_SIZE = 4096;
    
    // 压缩质量
    const COMPRESSION_QUALITY = 0.8;
    
    // 存储上传的图片
    let uploadedImages = [];
    
    /**
     * 验证图片文件
     * @param {File} file - 文件对象
     * @returns {Object} 验证结果 {valid: boolean, error?: string}
     */
    function validateFile(file) {
        if (!file) {
            return { valid: false, error: '未选择文件' };
        }
        
        if (!SUPPORTED_TYPES.includes(file.type)) {
            return { valid: false, error: '不支持的文件格式，请选择 JPG、PNG、GIF 或 WebP 格式的图片' };
        }
        
        if (file.size > MAX_FILE_SIZE) {
            return { valid: false, error: '文件大小不能超过 5MB' };
        }
        
        return { valid: true };
    }
    
    /**
     * 获取图片尺寸
     * @param {File} file - 文件对象
     * @returns {Promise<Object>} 图片尺寸 {width, height}
     */
    function getImageSize(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(file);
            
            img.onload = function() {
                resolve({
                    width: this.width,
                    height: this.height
                });
                URL.revokeObjectURL(url);
            };
            
            img.onerror = function() {
                reject(new Error('无法读取图片尺寸'));
                URL.revokeObjectURL(url);
            };
            
            img.src = url;
        });
    }
    
    /**
     * 压缩图片
     * @param {File|Blob} file - 文件对象
     * @param {number} maxWidth - 最大宽度
     * @param {number} quality - 压缩质量
     * @returns {Promise<Blob>} 压缩后的图片Blob
     */
    function compressImage(file, maxWidth = 1920, quality = COMPRESSION_QUALITY) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(file);
            
            img.onload = function() {
                const canvas = document.createElement('canvas');
                let width = this.width;
                let height = this.height;
                
                // 调整尺寸
                if (width > maxWidth) {
                    height = Math.round(height * (maxWidth / width));
                    width = maxWidth;
                }
                
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            resolve(blob);
                        } else {
                            reject(new Error('图片压缩失败'));
                        }
                        URL.revokeObjectURL(url);
                    },
                    file.type,
                    quality
                );
            };
            
            img.onerror = function() {
                reject(new Error('无法加载图片'));
                URL.revokeObjectURL(url);
            };
            
            img.src = url;
        });
    }
    
    /**
     * 将图片转换为Base64
     * @param {File|Blob} file - 文件对象
     * @returns {Promise<string>} Base64字符串
     */
    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = function() {
                resolve(reader.result);
            };
            
            reader.onerror = function() {
                reject(new Error('文件读取失败'));
            };
            
            reader.readAsDataURL(file);
        });
    }
    
    /**
     * 格式化文件大小
     * @param {number} bytes - 字节数
     * @returns {string} 格式化后的大小
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) {
            return bytes + ' B';
        } else if (bytes < 1024 * 1024) {
            return (bytes / 1024).toFixed(1) + ' KB';
        } else {
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }
    }
    
    /**
     * 处理单个图片文件
     * @param {File} file - 文件对象
     * @returns {Promise<Object>} 处理后的图片信息
     */
    async function processFile(file) {
        // 验证文件
        const validation = validateFile(file);
        if (!validation.valid) {
            throw new Error(validation.error);
        }
        
        // 获取原始尺寸
        const originalSize = await getImageSize(file);
        
        // 压缩图片
        const compressedBlob = await compressImage(file);
        
        // 转换为Base64
        const base64 = await fileToBase64(compressedBlob);
        
        return {
            id: 'img_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
            name: file.name,
            type: file.type,
            size: compressedBlob.size,
            originalSize: file.size,
            width: originalSize.width,
            height: originalSize.height,
            base64: base64,
            timestamp: new Date().toISOString()
        };
    }
    
    /**
     * 选择图片文件
     * @param {HTMLInputElement} input - 文件输入元素
     * @returns {Promise<Array>} 处理后的图片数组
     */
    async function selectFiles(input) {
        const files = Array.from(input.files || []);
        const results = [];
        
        for (const file of files) {
            try {
                const result = await processFile(file);
                results.push(result);
            } catch (error) {
                console.error('处理图片失败:', error);
                // 可以在这里添加错误提示
            }
        }
        
        // 添加到已上传列表
        uploadedImages = [...uploadedImages, ...results];
        
        return results;
    }
    
    /**
     * 处理拖拽上传
     * @param {DragEvent} event - 拖拽事件
     * @returns {Promise<Array>} 处理后的图片数组
     */
    async function handleDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        
        const files = Array.from(event.dataTransfer.files);
        const results = [];
        
        for (const file of files) {
            if (file.type.startsWith('image/')) {
                try {
                    const result = await processFile(file);
                    results.push(result);
                } catch (error) {
                    console.error('处理图片失败:', error);
                }
            }
        }
        
        uploadedImages = [...uploadedImages, ...results];
        
        return results;
    }
    
    /**
     * 创建上传区域HTML
     * @param {Object} options - 配置选项
     * @returns {string} HTML字符串
     */
    function createUploadArea(options = {}) {
        const {
            id = 'imageUpload',
            multiple = true,
            accept = 'image/*'
        } = options;
        
        return `
            <div class="image-upload-area" id="${id}Area">
                <svg class="image-upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <p class="image-upload-text">点击或拖拽图片到这里上传</p>
                <p class="image-upload-hint">支持 JPG、PNG、GIF、WebP，最大 5MB</p>
                <input type="file" id="${id}" accept="${accept}" ${multiple ? 'multiple' : ''} style="display: none;">
            </div>
        `;
    }
    
    /**
     * 创建预览列表HTML
     * @param {Array} images - 图片数组
     * @returns {string} HTML字符串
     */
    function createPreviewList(images) {
        if (!images || images.length === 0) {
            return '<div class="image-preview-list"></div>';
        }
        
        const items = images.map((img, index) => `
            <div class="image-preview-item" data-id="${img.id}">
                <img src="${img.base64}" alt="${img.name}">
                <button class="image-preview-remove" onclick="ImageUploader.removeImage('${img.id}')" title="移除">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
                <span class="image-preview-size">${img.width}×${img.height}</span>
            </div>
        `).join('');
        
        return `<div class="image-preview-list">${items}</div>`;
    }
    
    /**
     * 移除已上传的图片
     * @param {string} imageId - 图片ID
     * @returns {Object|null} 被移除的图片
     */
    function removeImage(imageId) {
        const index = uploadedImages.findIndex(img => img.id === imageId);
        if (index !== -1) {
            const removed = uploadedImages.splice(index, 1)[0];
            return removed;
        }
        return null;
    }
    
    /**
     * 清空所有已上传的图片
     */
    function clearImages() {
        uploadedImages = [];
    }
    
    /**
     * 获取所有已上传的图片
     * @returns {Array} 图片数组
     */
    function getImages() {
        return [...uploadedImages];
    }
    
    /**
     * 初始化上传区域事件
     * @param {HTMLElement} container - 容器元素
     * @param {Function} onChange - 变化回调
     */
    function initUploadArea(container, onChange) {
        const area = container.querySelector('.image-upload-area');
        const input = container.querySelector('input[type="file"]');
        
        if (!area || !input) {
            console.error('未找到上传区域元素');
            return;
        }
        
        // 点击上传
        area.addEventListener('click', () => {
            input.click();
        });
        
        // 文件选择
        input.addEventListener('change', async () => {
            const results = await selectFiles(input);
            if (onChange) {
                onChange(results, uploadedImages);
            }
        });
        
        // 拖拽事件
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.add('drag-over');
        });
        
        area.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.remove('drag-over');
        });
        
        area.addEventListener('drop', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.remove('drag-over');
            
            const results = await handleDrop(e);
            if (onChange) {
                onChange(results, uploadedImages);
            }
        });
    }
    
    /**
     * 上传图片到服务器（可选方法）
     * @param {string} imageId - 图片ID
     * @param {string} apiUrl - API地址
     * @returns {Promise<Object>} 上传结果
     */
    async function uploadToServer(imageId, apiUrl) {
        const image = uploadedImages.find(img => img.id === imageId);
        if (!image) {
            throw new Error('图片不存在');
        }
        
        // 如果没有提供API地址，返回本地图片数据
        if (!apiUrl) {
            return {
                success: true,
                url: image.base64,
                local: true
            };
        }
        
        // 转换为Blob进行上传
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image: image.base64,
                name: image.name
            })
        });
        
        if (!response.ok) {
            throw new Error('上传失败');
        }
        
        return await response.json();
    }
    
    // 公开API
    return {
        createUploadArea: createUploadArea,
        createPreviewList: createPreviewList,
        initUploadArea: initUploadArea,
        selectFiles: selectFiles,
        handleDrop: handleDrop,
        processFile: processFile,
        compressImage: compressImage,
        fileToBase64: fileToBase64,
        getImageSize: getImageSize,
        formatFileSize: formatFileSize,
        validateFile: validateFile,
        getImages: getImages,
        removeImage: removeImage,
        clearImages: clearImages,
        uploadToServer: uploadToServer,
        SUPPORTED_TYPES: SUPPORTED_TYPES,
        MAX_FILE_SIZE: MAX_FILE_SIZE
    };
})();

// 挂载到全局
window.ImageUploader = ImageUploader;
