// 情感化设计补充脚本 - 自动加载到 index.html
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const bubbles = document.querySelectorAll('#chatHistory .message-bubble, #chatHistory .bubble-group');
        if (bubbles.length === 0) return;

        if (typeof SmartGreeting !== 'undefined') {
            const cache = SmartGreeting._getCache();
            const undisplayed = cache.filter(g => !g.displayed);
            if (undisplayed.length > 0) {
                const content = undisplayed[0].content || '';
                if (typeof App !== 'undefined' && App.escapeHtml) {
                    bubbles[0].innerHTML = App.escapeHtml(content);
                } else {
                    bubbles[0].textContent = content;
                }
                return;
            }
        }

        if (typeof EmotionalDesign !== 'undefined' && EmotionalDesign.getGreeting) {
            const greeting = EmotionalDesign.getGreeting();
            if (typeof App !== 'undefined' && App.escapeHtml) {
                bubbles[0].innerHTML = App.escapeHtml(greeting);
            } else {
                bubbles[0].textContent = greeting;
            }
        } else {
            const hour = new Date().getHours();
            let greeting = '你好，有什么我可以帮你的？';
            if (hour >= 6 && hour < 12) greeting = '早上好！新的一天开始了~';
            else if (hour >= 12 && hour < 18) greeting = '下午好！需要我帮忙吗？';
            else if (hour >= 18 && hour < 22) greeting = '晚上好，辛苦了一天~';
            else greeting = '这么晚了还在忙？注意休息哦~';
            bubbles[0].textContent = greeting;
        }
    }, 300);
});
