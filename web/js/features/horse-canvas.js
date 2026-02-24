/**
 * 万马奔腾 - Canvas 动画引擎
 * 具象风格马群动画 + 粒子效果 + 交互响应
 */
(function() {
    'use strict';

    class HorseCanvas {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d');
            this.horses = [];
            this.particles = [];
            this.stars = [];
            this.time = 0;
            this.mouseX = 0;
            this.mouseY = 0;
            this.isHovering = false;
            this.speedMultiplier = 1;
            this.animationId = null;
            this.resizeTimeout = null;

            this.init();
        }

        init() {
            this.resize();
            this.createStars();
            this.createHorses();
            this.createParticles();
            this.bindEvents();
            this.animate();
        }

        resize() {
            const dpr = window.devicePixelRatio || 1;
            this.canvas.width = window.innerWidth * dpr;
            this.canvas.height = window.innerHeight * dpr;
            this.canvas.style.width = window.innerWidth + 'px';
            this.canvas.style.height = window.innerHeight + 'px';
            this.ctx.scale(dpr, dpr);
            this.width = window.innerWidth;
            this.height = window.innerHeight;
        }

        createStars() {
            this.stars = [];
            const starCount = Math.floor((this.width * this.height) / 8000);
            for (let i = 0; i < starCount; i++) {
                this.stars.push({
                    x: Math.random() * this.width,
                    y: Math.random() * this.height * 0.6,
                    size: Math.random() * 2 + 0.5,
                    twinkle: Math.random() * Math.PI * 2,
                    speed: Math.random() * 0.02 + 0.01
                });
            }
        }

        createHorses() {
            this.horses = [];
            const horseCount = Math.max(8, Math.floor(this.width / 200));
            
            for (let i = 0; i < horseCount; i++) {
                this.horses.push({
                    x: Math.random() * this.width * 1.5 - this.width * 0.25,
                    y: this.height * 0.4 + Math.random() * this.height * 0.35,
                    baseY: this.height * 0.4 + Math.random() * this.height * 0.35,
                    scale: 0.4 + Math.random() * 0.5,
                    speed: 1.5 + Math.random() * 1.5,
                    phase: Math.random() * Math.PI * 2,
                    legPhase: Math.random() * Math.PI * 2,
                    tilt: (Math.random() - 0.5) * 0.1,
                    color: this.getHorseColor(),
                    maneColor: this.getManeColor(),
                    tailColor: this.getTailColor(),
                    layer: Math.floor(Math.random() * 3),
                    opacity: 0.7 + Math.random() * 0.3,
                    breathPhase: Math.random() * Math.PI * 2
                });
            }
            
            this.horses.sort((a, b) => a.layer - b.layer);
        }

        getHorseColor() {
            const colors = [
                { body: '#2d1810', highlight: '#4a2c17', shadow: '#1a0f08' },
                { body: '#3d2817', highlight: '#5a3a25', shadow: '#251508' },
                { body: '#2a1a0f', highlight: '#3f2a1a', shadow: '#1a0d07' },
                { body: '#352015', highlight: '#4d2d1a', shadow: '#201208' }
            ];
            return colors[Math.floor(Math.random() * colors.length)];
        }

        getManeColor() {
            const colors = ['#1a0f08', '#0d0704', '#251510', '#1a0a05'];
            return colors[Math.floor(Math.random() * colors.length)];
        }

        getTailColor() {
            const colors = ['#1a0f08', '#0d0704', '#201008', '#150805'];
            return colors[Math.floor(Math.random() * colors.length)];
        }

        createParticles() {
            this.particles = [];
            const particleCount = 60;
            
            for (let i = 0; i < particleCount; i++) {
                this.particles.push(this.createParticle());
            }
        }

        createParticle() {
            return {
                x: Math.random() * this.width,
                y: this.height * 0.7 + Math.random() * this.height * 0.25,
                size: Math.random() * 4 + 1,
                speedX: Math.random() * 2 + 1,
                speedY: (Math.random() - 0.5) * 0.5,
                opacity: Math.random() * 0.4 + 0.1,
                decay: Math.random() * 0.01 + 0.005,
                color: Math.random() > 0.5 ? '#6b4423' : '#8b5a2b'
            };
        }

        bindEvents() {
            window.addEventListener('resize', () => {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = setTimeout(() => {
                    this.resize();
                    this.createStars();
                    this.createHorses();
                    this.createParticles();
                }, 200);
            });

            this.canvas.addEventListener('mousemove', (e) => {
                this.mouseX = e.clientX;
                this.mouseY = e.clientY;
                this.isHovering = true;
                this.speedMultiplier = 1.8;
            });

            this.canvas.addEventListener('mouseleave', () => {
                this.isHovering = false;
                this.speedMultiplier = 1;
            });

            this.canvas.addEventListener('touchmove', (e) => {
                const touch = e.touches[0];
                this.mouseX = touch.clientX;
                this.mouseY = touch.clientY;
                this.speedMultiplier = 1.5;
            });

            this.canvas.addEventListener('touchend', () => {
                this.speedMultiplier = 1;
            });
        }

        animate() {
            this.time += 0.016 * this.speedMultiplier;
            
            if (!this.isHovering && this.speedMultiplier > 1) {
                this.speedMultiplier = Math.max(1, this.speedMultiplier - 0.02);
            }

            this.ctx.clearRect(0, 0, this.width, this.height);
            
            this.drawSky();
            this.drawStars();
            this.drawMountains();
            this.drawGround();
            this.drawParticles();
            this.drawHorses();
            this.drawMoon();
            this.drawMist();

            this.animationId = requestAnimationFrame(() => this.animate());
        }

        drawSky() {
            const gradient = this.ctx.createLinearGradient(0, 0, 0, this.height);
            gradient.addColorStop(0, '#0a0605');
            gradient.addColorStop(0.3, '#1a0f0a');
            gradient.addColorStop(0.6, '#2d1810');
            gradient.addColorStop(1, '#1a0f08');
            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(0, 0, this.width, this.height);
        }

        drawStars() {
            this.stars.forEach(star => {
                star.twinkle += star.speed;
                const alpha = 0.3 + Math.sin(star.twinkle) * 0.3 + 0.4;
                
                this.ctx.beginPath();
                this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(232, 201, 160, ${alpha})`;
                this.ctx.fill();
            });
        }

        drawMountains() {
            this.ctx.fillStyle = '#2d1810';
            this.ctx.globalAlpha = 0.6;
            this.ctx.beginPath();
            this.ctx.moveTo(0, this.height * 0.55);
            
            for (let x = 0; x <= this.width; x += 50) {
                const y = this.height * 0.55 - Math.sin(x * 0.005 + this.time * 0.1) * 30 
                         - Math.sin(x * 0.01) * 20;
                this.ctx.lineTo(x, y);
            }
            
            this.ctx.lineTo(this.width, this.height);
            this.ctx.lineTo(0, this.height);
            this.ctx.closePath();
            this.ctx.fill();

            this.ctx.fillStyle = '#1a0f08';
            this.ctx.globalAlpha = 0.8;
            this.ctx.beginPath();
            this.ctx.moveTo(0, this.height * 0.65);
            
            for (let x = 0; x <= this.width; x += 40) {
                const y = this.height * 0.65 - Math.sin(x * 0.006 + this.time * 0.15 + 1) * 25 
                         - Math.sin(x * 0.012) * 15;
                this.ctx.lineTo(x, y);
            }
            
            this.ctx.lineTo(this.width, this.height);
            this.ctx.lineTo(0, this.height);
            this.ctx.closePath();
            this.ctx.fill();
            
            this.ctx.globalAlpha = 1;
        }

        drawGround() {
            const gradient = this.ctx.createLinearGradient(0, this.height * 0.7, 0, this.height);
            gradient.addColorStop(0, '#3d2817');
            gradient.addColorStop(0.3, '#2a1a10');
            gradient.addColorStop(1, '#1a0f08');
            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(0, this.height * 0.7, this.width, this.height * 0.3);
        }

        drawMoon() {
            const moonX = this.width * 0.85;
            const moonY = this.height * 0.15;
            const moonRadius = Math.min(this.width, this.height) * 0.08;
            
            const glowGradient = this.ctx.createRadialGradient(
                moonX, moonY, moonRadius * 0.5,
                moonX, moonY, moonRadius * 2.5
            );
            glowGradient.addColorStop(0, 'rgba(232, 201, 160, 0.3)');
            glowGradient.addColorStop(0.5, 'rgba(212, 165, 116, 0.1)');
            glowGradient.addColorStop(1, 'rgba(212, 165, 116, 0)');
            
            this.ctx.beginPath();
            this.ctx.arc(moonX, moonY, moonRadius * 2.5, 0, Math.PI * 2);
            this.ctx.fillStyle = glowGradient;
            this.ctx.fill();

            const pulse = Math.sin(this.time * 0.5) * 0.1 + 1;
            this.ctx.beginPath();
            this.ctx.arc(moonX, moonY, moonRadius * pulse, 0, Math.PI * 2);
            this.ctx.fillStyle = '#d4a574';
            this.ctx.fill();
            
            this.ctx.beginPath();
            this.ctx.arc(moonX, moonY, moonRadius * 0.7 * pulse, 0, Math.PI * 2);
            this.ctx.fillStyle = '#e8c9a0';
            this.ctx.fill();
        }

        drawMist() {
            for (let i = 0; i < 3; i++) {
                const y = this.height * (0.55 + i * 0.08);
                const gradient = this.ctx.createLinearGradient(0, y - 30, 0, y + 30);
                gradient.addColorStop(0, 'rgba(45, 24, 16, 0)');
                gradient.addColorStop(0.5, 'rgba(45, 24, 16, 0.15)');
                gradient.addColorStop(1, 'rgba(45, 24, 16, 0)');
                
                this.ctx.fillStyle = gradient;
                this.ctx.fillRect(0, y - 30, this.width, 60);
            }
        }

        drawHorses() {
            this.horses.forEach(horse => {
                this.drawHorse(horse);
            });
        }

        drawHorse(horse) {
            const { x, y, scale, phase, legPhase, color, maneColor, tailColor, breathPhase, tilt, opacity } = horse;
            
            this.ctx.save();
            this.ctx.translate(x, y);
            this.ctx.rotate(tilt);
            this.ctx.scale(scale, scale);
            this.ctx.globalAlpha = opacity;

            const breathOffset = Math.sin(breathPhase) * 2;
            const runCycle = Math.sin(legPhase);
            const bounce = Math.abs(Math.sin(legPhase)) * 8;

            this.ctx.save();
            this.ctx.translate(0, -bounce);

            this.drawHorseBody(color, breathOffset);
            this.drawHorseHead(color, breathOffset);
            this.drawHorseLegs(color, legPhase);
            this.drawHorseMane(maneColor, runCycle);
            this.drawHorseTail(tailColor, runCycle);
            this.drawHorseEye();
            
            this.ctx.restore();
            this.ctx.restore();

            horse.x += horse.speed * this.speedMultiplier;
            
            if (horse.x > this.width + 200) {
                horse.x = -200;
                horse.y = this.height * 0.4 + Math.random() * this.height * 0.35;
                horse.baseY = horse.y;
            }

            horse.breathPhase += 0.03 * this.speedMultiplier;
            horse.legPhase += 0.15 * this.speedMultiplier;
        }

        drawHorseBody(color, breathOffset) {
            const bodyGradient = this.ctx.createLinearGradient(-60, -30, -60, 30);
            bodyGradient.addColorStop(0, color.highlight);
            bodyGradient.addColorStop(0.5, color.body);
            bodyGradient.addColorStop(1, color.shadow);
            
            this.ctx.fillStyle = bodyGradient;
            this.ctx.beginPath();
            this.ctx.ellipse(0, breathOffset, 70, 35, 0, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.strokeStyle = color.shadow;
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.ellipse(0, breathOffset, 70, 35, 0, 0, Math.PI * 2);
            this.ctx.stroke();

            this.ctx.fillStyle = color.highlight;
            this.ctx.globalAlpha = 0.3;
            this.ctx.beginPath();
            this.ctx.ellipse(-20, -15 + breathOffset, 25, 12, -0.3, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;
        }

        drawHorseHead(color, breathOffset) {
            const headX = 75;
            const headY = -25 + breathOffset;

            const headGradient = this.ctx.createLinearGradient(headX - 25, -15, headX + 15, -35);
            headGradient.addColorStop(0, color.highlight);
            headGradient.addColorStop(1, color.body);
            
            this.ctx.fillStyle = headGradient;
            this.ctx.beginPath();
            this.ctx.moveTo(headX - 25, headY);
            this.ctx.quadraticCurveTo(headX - 30, headY - 15, headX - 20, headY - 25);
            this.ctx.quadraticCurveTo(headX, headY - 40, headX + 20, headY - 30);
            this.ctx.quadraticCurveTo(headX + 30, headY - 20, headX + 25, headY);
            this.ctx.quadraticCurveTo(headX + 20, headY + 10, headX, headY + 5);
            this.ctx.quadraticCurveTo(headX - 15, headY + 5, headX - 25, headY);
            this.ctx.fill();

            this.ctx.fillStyle = '#0d0704';
            this.ctx.beginPath();
            this.ctx.ellipse(headX + 5, headY - 22, 6, 4, 0, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = '#ffffff';
            this.ctx.beginPath();
            this.ctx.arc(headX + 7, headY - 23, 1.5, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = '#1a0f08';
            this.ctx.beginPath();
            this.ctx.ellipse(headX + 25, headY - 12, 4, 3, 0, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = '#0a0503';
            this.ctx.beginPath();
            this.ctx.ellipse(headX + 27, headY - 12, 2, 1.5, 0, 0, Math.PI * 2);
            this.ctx.fill();
        }

        drawHorseLegs(color, legPhase) {
            const legPositions = [
                { x: -45, y: 25, phase: 0 },
                { x: -20, y: 25, phase: Math.PI },
                { x: 15, y: 25, phase: 0 },
                { x: 40, y: 25, phase: Math.PI }
            ];

            legPositions.forEach((leg, index) => {
                const offset = Math.sin(legPhase + leg.phase) * 15;
                const legLength = 45 + (index % 2 === 0 ? 0 : 5);
                
                const legGradient = this.ctx.createLinearGradient(leg.x - 5, 0, leg.x + 5, 0);
                legGradient.addColorStop(0, color.shadow);
                legGradient.addColorStop(0.5, color.body);
                legGradient.addColorStop(1, color.shadow);
                
                this.ctx.strokeStyle = legGradient;
                this.ctx.lineWidth = 8;
                this.ctx.lineCap = 'round';
                this.ctx.beginPath();
                this.ctx.moveTo(leg.x, leg.y);
                
                const kneeX = leg.x + (index % 2 === 0 ? offset : -offset) * 0.5;
                const kneeY = leg.y + legLength * 0.4;
                const footX = leg.x + (index % 2 === 0 ? offset : -offset);
                const footY = leg.y + legLength;
                
                this.ctx.quadraticCurveTo(kneeX, kneeY, footX, footY);
                this.ctx.stroke();

                this.ctx.fillStyle = '#1a0f08';
                this.ctx.beginPath();
                this.ctx.ellipse(footX, footY + 3, 6, 4, 0, 0, Math.PI * 2);
                this.ctx.fill();
            });
        }

        drawHorseMane(maneColor, runCycle) {
            const manePoints = [
                { x: -30, y: -40, offset: 0 },
                { x: -10, y: -45, offset: 5 },
                { x: 10, y: -42, offset: -5 },
                { x: 30, y: -35, offset: 8 },
                { x: 50, y: -25, offset: -3 }
            ];

            manePoints.forEach((point, i) => {
                const wave = Math.sin(runCycle + i * 0.5) * 8;
                
                this.ctx.strokeStyle = maneColor;
                this.ctx.lineWidth = 4 - i * 0.5;
                this.ctx.lineCap = 'round';
                this.ctx.beginPath();
                this.ctx.moveTo(point.x, point.y);
                this.ctx.quadraticCurveTo(
                    point.x + wave, 
                    point.y + 25 + point.offset,
                    point.x + wave * 0.5, 
                    point.y + 45 + point.offset
                );
                this.ctx.stroke();
            });
        }

        drawHorseTail(tailColor, runCycle) {
            const tailBaseX = -60;
            const tailBaseY = -10;

            for (let i = 0; i < 5; i++) {
                const wave = Math.sin(runCycle + i * 0.4) * (10 + i * 3);
                
                this.ctx.strokeStyle = tailColor;
                this.ctx.lineWidth = 6 - i;
                this.ctx.lineCap = 'round';
                this.ctx.globalAlpha = 1 - i * 0.15;
                
                this.ctx.beginPath();
                this.ctx.moveTo(tailBaseX, tailBaseY);
                this.ctx.quadraticCurveTo(
                    tailBaseX - 20 + wave,
                    tailBaseY + 20 + i * 5,
                    tailBaseX - 30 + wave * 1.5,
                    tailBaseY + 45 + i * 8
                );
                this.ctx.stroke();
            }
            this.ctx.globalAlpha = 1;
        }

        drawHorseEye() {
        }

        drawParticles() {
            this.particles.forEach(particle => {
                particle.x += particle.speedX * this.speedMultiplier;
                particle.y += particle.speedY;
                particle.opacity -= particle.decay;
                
                if (particle.opacity <= 0 || particle.x > this.width + 50) {
                    Object.assign(particle, this.createParticle());
                }

                const gradient = this.ctx.createRadialGradient(
                    particle.x, particle.y, 0,
                    particle.x, particle.y, particle.size
                );
                gradient.addColorStop(0, particle.color);
                gradient.addColorStop(1, 'rgba(0,0,0,0)');
                
                this.ctx.fillStyle = gradient;
                this.ctx.globalAlpha = particle.opacity;
                this.ctx.beginPath();
                this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.globalAlpha = 1;
            });

            this.horses.forEach(horse => {
                if (Math.random() < 0.1 * this.speedMultiplier) {
                    const particle = this.particles.find(p => p.opacity <= 0.1);
                    if (particle) {
                        particle.x = horse.x - 50 * horse.scale;
                        particle.y = horse.y + 30 * horse.scale;
                        particle.opacity = 0.3;
                        particle.size = Math.random() * 3 + 1;
                    }
                }
            });
        }

        destroy() {
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
            }
            window.removeEventListener('resize', this.resize);
        }
    }

    window.HorseCanvas = HorseCanvas;
})();
