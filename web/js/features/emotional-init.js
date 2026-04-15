// 情感化设计补充脚本 - 自动加载到 index.html
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        // 优先使用 SmartGreeting 的缓存
        if (typeof SmartGreeting !== 'undefined') {
            const cache = SmartGreeting._getCache();
            const undisplayed = cache.filter(g => !g.displayed);
            if (undisplayed.length > 0) {
                const bubbles = document.querySelectorAll('#chatHistory .message-bubble');
                if (bubbles.length > 0) {
                    bubbles[0].textContent = undisplayed[0].content;
                }
                return;
            }
        }

        // 备用：使用静态问候语
        const bubbles = document.querySelectorAll('#chatHistory .message-bubble');
        if (bubbles.length > 0) {
            if (typeof EmotionalDesign !== 'undefined' && EmotionalDesign.getGreeting) {
                bubbles[0].textContent = EmotionalDesign.getGreeting();
            } else {
                const hour = new Date().getHours();
                let greeting = '你好，有什么我可以帮你的？';
                if (hour >= 6 && hour < 12) greeting = '早上好！新的一天开始了~';
                else if (hour >= 12 && hour < 18) greeting = '下午好！需要我帮忙吗？';
                else if (hour >= 18 && hour < 22) greeting = '晚上好，辛苦了一天~';
                else greeting = '这么晚了还在忙？注意休息哦~';
                bubbles[0].textContent = greeting;
            }
        }
    }, 300);
});
