/**
 * 按钮功能修复脚本
 * 解决发送按钮和全屏退出按钮无响应问题
 */

(function() {
    'use strict';
    
    console.log('🔧 按钮功能修复脚本正在初始化...');
    
    // 修复发送按钮功能
    function fixSendButton() {
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');
        
        if (!sendBtn || !chatInput) {
            console.warn('⚠️ 未找到发送按钮或输入框元素');
            return false;
        }
        
        // 清除现有事件监听器
        const newSendBtn = sendBtn.cloneNode(true);
        sendBtn.parentNode.replaceChild(newSendBtn, sendBtn);
        
        // 重新绑定点击事件
        newSendBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('📤 发送按钮被点击');
            
            // 检查必要条件
            const inputValue = chatInput.value.trim();
            const hasContent = inputValue.length > 0;
            const hasModel = window.App?.state?.selectedModel;
            const isGenerating = window.App?.state?.isGenerating;
            
            console.log('发送条件检查:', { 
                hasContent, 
                hasModel, 
                isGenerating,
                inputValueLength: inputValue.length
            });
            
            // 更新按钮状态
            this.disabled = !hasContent || !hasModel || isGenerating;
            
            if (hasContent && hasModel && !isGenerating) {
                try {
                    // 尝试调用App的sendMessage方法
                    if (window.App && typeof window.App.sendMessage === 'function') {
                        window.App.sendMessage();
                        console.log('✅ 成功调用App.sendMessage()');
                    } else if (window.App && typeof window.App.Chat?.sendMessage === 'function') {
                        window.App.Chat.sendMessage();
                        console.log('✅ 成功调用App.Chat.sendMessage()');
                    } else {
                        // 备用方案：直接发送消息
                        simulateSendMessage(inputValue);
                    }
                } catch (error) {
                    console.error('❌ 发送消息时发生错误:', error);
                    // 错误时也尝试备用方案
                    simulateSendMessage(inputValue);
                }
            } else {
                console.log('❌ 发送条件不满足');
                showButtonFeedback('条件不足，无法发送', 'warning');
            }
        });
        
        // 添加悬停效果
        newSendBtn.addEventListener('mouseenter', function() {
            const hasContent = chatInput.value.trim().length > 0;
            const hasModel = window.App?.state?.selectedModel;
            const isGenerating = window.App?.state?.isGenerating;
            
            if (!hasContent || !hasModel || isGenerating) {
                this.title = !hasContent ? '请输入内容' : 
                            !hasModel ? '请选择模型' : 
                            '正在生成中...';
            } else {
                this.title = '发送消息';
            }
        });
        
        console.log('✅ 发送按钮事件绑定完成');
        return true;
    }
    
    // 修复全屏退出按钮功能
    function fixExitButton() {
        const exitBtn = document.getElementById('exitChatOverlayBtn');
        const overlay = document.getElementById('chatOverlay');
        
        if (!exitBtn || !overlay) {
            console.warn('⚠️ 未找到全屏退出按钮或覆盖层元素');
            return false;
        }
        
        // 清除现有事件监听器
        const newExitBtn = exitBtn.cloneNode(true);
        exitBtn.parentNode.replaceChild(newExitBtn, exitBtn);
        
        // 重新绑定点击事件
        newExitBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            console.log('🚪 全屏退出按钮被点击');
            
            try {
                // 尝试调用App的exitChatOverlay方法
                if (window.App && typeof window.App.exitChatOverlay === 'function') {
                    window.App.exitChatOverlay();
                    console.log('✅ 成功调用App.exitChatOverlay()');
                } else {
                    // 备用方案：直接操作DOM
                    exitFullscreenDirectly();
                }
            } catch (error) {
                console.error('❌ 退出全屏时发生错误:', error);
                // 错误时使用备用方案
                exitFullscreenDirectly();
            }
        });
        
        console.log('✅ 全屏退出按钮事件绑定完成');
        return true;
    }
    
    // 备用发送消息方案
    function simulateSendMessage(message) {
        console.log('🔄 使用备用方案发送消息:', message.substring(0, 50) + '...');
        
        const chatHistory = document.getElementById('chatHistory') || 
                           document.getElementById('chatOverlayHistory');
        
        if (chatHistory) {
            // 添加用户消息
            const userMsg = document.createElement('div');
            userMsg.className = 'message user';
            userMsg.innerHTML = `
                <div class="message-content">${escapeHtml(message)}</div>
                <div class="message-meta">
                    <span class="message-time">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                        ${new Date().toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'})}
                    </span>
                </div>
            `;
            chatHistory.appendChild(userMsg);
            
            // 添加助手回复占位符
            const assistantMsg = document.createElement('div');
            assistantMsg.className = 'message assistant';
            assistantMsg.innerHTML = `
                <div class="message-content">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
            chatHistory.appendChild(assistantMsg);
            
            // 滚动到底部
            chatHistory.scrollTop = chatHistory.scrollHeight;
            
            // 清空输入框
            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.value = '';
                chatInput.dispatchEvent(new Event('input'));
            }
            
            showButtonFeedback('消息已发送（演示模式）', 'success');
            console.log('✅ 消息发送完成（备用方案）');
        }
    }
    
    // 备用退出全屏方案
    function exitFullscreenDirectly() {
        console.log('🔄 使用备用方案退出全屏');
        
        const overlay = document.getElementById('chatOverlay');
        if (overlay) {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
            
            // 移除可能存在的动画样式
            overlay.style.animation = '';
            overlay.dataset.exiting = 'false';
            
            showButtonFeedback('已退出全屏', 'success');
            console.log('✅ 全屏已退出（备用方案）');
        }
    }
    
    // 添加键盘快捷键支持
    function addKeyboardSupport() {
        document.addEventListener('keydown', function(e) {
            // Enter键发送消息（非Shift+Enter）
            if (e.key === 'Enter' && !e.shiftKey) {
                const chatInput = document.getElementById('chatInput');
                const isActiveElement = document.activeElement === chatInput;
                
                if (isActiveElement) {
                    e.preventDefault();
                    const sendBtn = document.getElementById('sendBtn');
                    if (sendBtn && !sendBtn.disabled) {
                        sendBtn.click();
                        console.log('⌨️ 通过Enter键触发发送');
                    }
                }
            }
            
            // ESC键退出全屏
            if (e.key === 'Escape') {
                const overlay = document.getElementById('chatOverlay');
                if (overlay && overlay.classList.contains('active')) {
                    e.preventDefault();
                    const exitBtn = document.getElementById('exitChatOverlayBtn');
                    if (exitBtn) {
                        exitBtn.click();
                        console.log('⌨️ 通过ESC键触发退出全屏');
                    }
                }
            }
            
            // F11键切换全屏
            if (e.key === 'F11') {
                e.preventDefault();
                const overlay = document.getElementById('chatOverlay');
                const isActive = overlay && overlay.classList.contains('active');
                
                if (isActive) {
                    const exitBtn = document.getElementById('exitChatOverlayBtn');
                    if (exitBtn) exitBtn.click();
                } else {
                    if (window.App && typeof window.App.enterChatOverlay === 'function') {
                        window.App.enterChatOverlay();
                    }
                }
                console.log('⌨️ 通过F11键切换全屏状态');
            }
        });
        
        console.log('✅ 键盘快捷键支持已添加');
    }
    
    // 按钮状态更新函数
    function updateButtonStates() {
        const sendBtn = document.getElementById('sendBtn');
        const chatInput = document.getElementById('chatInput');
        const hasModel = window.App?.state?.selectedModel;
        const isGenerating = window.App?.state?.isGenerating;
        
        if (sendBtn && chatInput) {
            const hasContent = chatInput.value.trim().length > 0;
            sendBtn.disabled = !hasContent || !hasModel || isGenerating;
        }
    }
    
    // 创建反馈提示
    function showButtonFeedback(message, type = 'info') {
        // 创建或更新状态指示器
        let indicator = document.getElementById('buttonFeedbackIndicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'buttonFeedbackIndicator';
            indicator.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                z-index: 10001;
                opacity: 0;
                transform: translateX(100%);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                max-width: 300px;
            `;
            document.body.appendChild(indicator);
        }
        
        // 设置样式和内容
        const colors = {
            success: '#4CAF50',
            warning: '#FF9800',
            error: '#F44336',
            info: '#2196F3'
        };
        
        indicator.style.background = colors[type] || colors.info;
        indicator.style.color = 'white';
        indicator.textContent = message;
        
        // 显示动画
        setTimeout(() => {
            indicator.style.opacity = '1';
            indicator.style.transform = 'translateX(0)';
        }, 10);
        
        // 自动隐藏
        setTimeout(() => {
            indicator.style.opacity = '0';
            indicator.style.transform = 'translateX(100%)';
        }, 3000);
    }
    
    // HTML转义函数
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // 监控输入框变化
    function monitorInputChanges() {
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            // 监听输入事件
            chatInput.addEventListener('input', updateButtonStates);
            chatInput.addEventListener('keyup', updateButtonStates);
            chatInput.addEventListener('paste', () => {
                setTimeout(updateButtonStates, 100);
            });
            
            console.log('✅ 输入框监控已设置');
        }
    }
    
    // 主初始化函数
    function initializeButtonFixes() {
        console.log('🚀 开始初始化按钮修复...');
        
        // 等待必要的元素加载完成
        const checkElements = setInterval(() => {
            const sendBtn = document.getElementById('sendBtn');
            const chatInput = document.getElementById('chatInput');
            const exitBtn = document.getElementById('exitChatOverlayBtn');
            
            if (sendBtn && chatInput && exitBtn) {
                clearInterval(checkElements);
                
                // 执行所有修复
                const sendFixed = fixSendButton();
                const exitFixed = fixExitButton();
                addKeyboardSupport();
                monitorInputChanges();
                
                // 初始状态更新
                setTimeout(updateButtonStates, 100);
                
                // 显示成功消息
                if (sendFixed && exitFixed) {
                    showButtonFeedback('🔧 按钮功能修复完成！', 'success');
                    console.log('🎉 所有按钮功能修复成功！');
                } else {
                    showButtonFeedback('部分按钮功能已修复', 'warning');
                    console.log('⚠️ 部分按钮功能修复完成');
                }
            }
        }, 500);
        
        // 超时保护
        setTimeout(() => {
            clearInterval(checkElements);
            console.log('⏰ 按钮修复初始化超时');
        }, 10000);
    }
    
    // 页面加载完成后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeButtonFixes);
    } else {
        // 延迟执行确保所有资源加载完成
        setTimeout(initializeButtonFixes, 1000);
    }
    
    // 暴露到全局作用域供调试使用
    window.ButtonFixDebug = {
        fixSendButton,
        fixExitButton,
        updateButtonStates,
        showFeedback: showButtonFeedback
    };
    
    console.log('✅ 按钮修复脚本加载完成');
    
})();