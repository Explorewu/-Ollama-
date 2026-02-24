/**
 * 聊天模块
 * 核心聊天功能
 */
(function() {
    const Chat = {
        init(app) {
            this.app = app;
        },

        handleChatInput() {
            const app = this.app;
            const input = document.getElementById('chatInput');
            const sendBtn = document.getElementById('sendBtn');
            const charCount = document.getElementById('charCount');

            const length = input.value.length;
            const hasContent = input.value.trim() || app.state.chatImageBase64;
            sendBtn.disabled = !hasContent || !app.state.selectedModel || app.state.isGenerating;
            
            if (charCount) {
                charCount.textContent = `${length} / 4000`;
            }
        },

        handleChatKeydown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        },

        async handleChatImageUpload(file) {
            const app = this.app;
            if (!file.type.startsWith('image/')) {
                app.showToast('请上传图片文件', 'error');
                return;
            }

            const maxSize = 500 * 1024;
            let finalFile = file;

            if (file.size > maxSize) {
                try {
                    finalFile = await this.compressImage(file, maxSize);
                    app.showToast(`图片已压缩: ${(file.size / 1024).toFixed(1)}KB → ${(finalFile.size / 1024).toFixed(1)}KB`, 'info');
                } catch (error) {
                    console.error('图片压缩失败:', error);
                    app.showToast('图片压缩失败，使用原图', 'warning');
                }
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                app.state.chatImage = e.target.result;
                app.state.chatImageBase64 = e.target.result.split(',')[1];

                const preview = document.getElementById('chatImagePreview');
                const previewImg = document.getElementById('chatPreviewImg');
                if (preview && previewImg) {
                    previewImg.src = e.target.result;
                    preview.style.display = 'block';
                }

                this.handleChatInput();
            };
            reader.readAsDataURL(finalFile);
        },

        compressImage(file, maxSize) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        let quality = 0.9;
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');

                        const maxWidth = 1920;
                        const maxHeight = 1920;
                        let width = img.width;
                        let height = img.height;

                        if (width > maxWidth) {
                            height = (maxWidth / width) * height;
                            width = maxWidth;
                        }
                        if (height > maxHeight) {
                            width = (maxHeight / height) * width;
                            height = maxHeight;
                        }

                        canvas.width = width;
                        canvas.height = height;
                        ctx.drawImage(img, 0, 0, width, height);

                        const tryCompress = (q) => {
                            canvas.toBlob((blob) => {
                                if (blob.size <= maxSize || q <= 0.1) {
                                    resolve(new File([blob], file.name, { type: 'image/jpeg' }));
                                } else {
                                    tryCompress(q - 0.1);
                                }
                            }, 'image/jpeg', q);
                        };

                        tryCompress(quality);
                    };
                    img.onerror = reject;
                    img.src = e.target.result;
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        },

        clearChatImage() {
            const app = this.app;
            app.state.chatImage = null;
            app.state.chatImageBase64 = null;

            const preview = document.getElementById('chatImagePreview');
            const previewImg = document.getElementById('chatPreviewImg');
            if (preview) preview.style.display = 'none';
            if (previewImg) previewImg.src = '';

            this.handleChatInput();
        },

        showLoadingState() {
            const app = this.app;
            app.state.isGenerating = true;

            const sendBtn = document.getElementById('sendBtn');
            const overlaySendBtn = document.getElementById('overlaySendBtn');

            if (sendBtn) {
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<span class="loading-spinner"><span></span><span></span><span></span></span>';
            }
            if (overlaySendBtn) {
                overlaySendBtn.disabled = true;
                overlaySendBtn.innerHTML = '<span class="loading-spinner"><span></span><span></span><span></span></span>';
            }
        },

        hideLoadingState() {
            const app = this.app;
            app.state.isGenerating = false;

            const sendBtn = document.getElementById('sendBtn');
            const overlaySendBtn = document.getElementById('overlaySendBtn');

            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
            }
            if (overlaySendBtn) {
                overlaySendBtn.disabled = false;
                overlaySendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
            }
        },

        appendMessage(role, content, imageData = null) {
            const app = this.app;
            const chatHistory = document.getElementById('chatHistory');
            if (!chatHistory) return;

            const messagesContainer = chatHistory.querySelector('.chat-messages') || chatHistory;
            const messageEl = document.createElement('div');
            messageEl.className = `message ${role}`;

            const avatar = role === 'user' ? '👤' : '🤖';
            const currentPersona = Storage.getCurrentPersona();
            const displayAvatar = role === 'assistant' ? currentPersona.avatar : avatar;

            let imageHtml = '';
            if (imageData) {
                imageHtml = `<div class="message-image"><img src="${imageData}" alt="上传的图片"></div>`;
            }

            messageEl.innerHTML = `
                <div class="message-avatar">${displayAvatar}</div>
                <div class="message-content-wrapper">
                    ${imageHtml}
                    <div class="message-content">${app.escapeHtml(content)}</div>
                    <div class="message-actions">
                        <button class="message-action-btn" title="复制" onclick="App.copyMessage(this)">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                        </button>
                        <button class="message-action-btn" title="重新发送" onclick="App.resendMessage(this)">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="1 4 1 10 7 10"></polyline>
                                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            `;

            messagesContainer.appendChild(messageEl);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            return messageEl;
        },

        updateStreamingResponse(chunk) {
            const app = this.app;
            const chatHistory = document.getElementById('chatHistory');
            const messagesContainer = chatHistory?.querySelector('.chat-messages') || chatHistory;
            const lastMessage = messagesContainer?.querySelector('.message.assistant:last-child .message-content');

            if (lastMessage) {
                lastMessage.textContent += chunk;
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        },

        async sendMessage() {
            const app = this.app;
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            const hasImage = app.state.chatImageBase64;

            if ((!message && !hasImage) || !app.state.selectedModel || app.state.isGenerating) {
                return;
            }

            if (!hasImage && typeof ImageGenAPI !== 'undefined' && ImageGenAPI.detectGenerateIntent(message)) {
                await app.handleImageGenerationRequest(message);
                return;
            }

            if (!app.state.currentConversation) {
                app.startNewChat(app.state.selectedModel);
                if (!app.state.currentConversation) {
                    app.showToast('创建对话失败，请重试', 'error');
                    return;
                }
            }

            input.value = '';
            this.handleChatInput();
            input.style.height = 'auto';
            input.style.height = '24px';

            app.enterChatOverlay();

            let finalMessage = message;
            let imageData = app.state.chatImage;

            if (hasImage) {
                const visionPrompt = message || '请描述这张图片的内容';
                this.appendMessage('user', message || '请分析这张图片', imageData);
                this.showLoadingState();

                try {
                    const visionResult = await VisionAPI.analyze(app.state.chatImage, visionPrompt);
                    if (visionResult.error) {
                        throw new Error(visionResult.error);
                    }
                    finalMessage = `[用户上传了一张图片，问题是: ${visionPrompt}]\n\n[图片分析结果]: ${visionResult.result}\n\n[用户]: ${message || ''}`;
                } catch (error) {
                    app.showToast(`图片分析失败: ${error.message}`, 'error');
                    this.appendMessage('assistant', `抱歉，图片分析失败: ${error.message}`);
                    this.hideLoadingState();
                    this.clearChatImage();
                    return;
                }
                this.clearChatImage();
            } else {
                this.appendMessage('user', message);
            }

            Storage.addMessage(app.state.currentConversation.id, {
                role: 'user',
                content: finalMessage,
                hasImage: hasImage
            });

            let conversation = Storage.getConversation(app.state.currentConversation?.id);
            if (!conversation) {
                const newConversation = Storage.createConversation(app.state.selectedModel);
                app.state.currentConversation = newConversation;
                Storage.setCurrentConversationId(newConversation.id);
                Storage.addMessage(newConversation.id, {
                    role: 'user',
                    content: finalMessage,
                    hasImage: hasImage
                });
                conversation = newConversation;
            }

            if (!hasImage) {
                this.showLoadingState();
            }

            try {
                const messages = conversation.messages.map(m => ({
                    role: m.role,
                    content: m.content
                }));

                const response = await API.chat({
                    model: app.state.selectedModel,
                    messages: messages,
                    conversationId: app.state.currentConversation.id
                }, (chunk) => {
                    this.updateStreamingResponse(chunk);
                });

                if (app.state.currentConversation.title === '新对话') {
                    const title = message.slice(0, 20) + (message.length > 20 ? '...' : '');
                    Storage.updateConversation(app.state.currentConversation.id, { title });
                    app.loadConversations();
                }

            } catch (error) {
                app.showToast(`生成回复失败: ${error.message}`, 'error');
                this.appendMessage('assistant', `抱歉，发生了错误: ${error.message}`);
            } finally {
                this.hideLoadingState();
            }
        },

        resendMessage(btn) {
            const app = this.app;
            const messageEl = btn.closest('.message');
            const contentEl = messageEl?.querySelector('.message-content');
            if (!contentEl) return;

            const input = document.getElementById('chatInput');
            if (input) {
                input.value = contentEl.textContent;
                this.handleChatInput();
                input.focus();
            }
        },

        copyMessage(btn) {
            const app = this.app;
            const messageEl = btn.closest('.message');
            const contentEl = messageEl?.querySelector('.message-content');
            if (!contentEl) return;

            navigator.clipboard.writeText(contentEl.textContent).then(() => {
                app.showToast('已复制到剪贴板', 'success');
            }).catch(() => {
                app.showToast('复制失败', 'error');
            });
        }
    };

    window.AppChat = Chat;
})();
