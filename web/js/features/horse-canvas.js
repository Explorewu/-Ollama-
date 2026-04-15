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

            const breathOffset = Math.sin(breathPhase) * 1.5;
            const runCycle = Math.sin(legPhase);
            const bounce = Math.abs(Math.sin(legPhase)) * 6;

            this.ctx.save();
            this.ctx.translate(0, -bounce);

            this.drawRealisticHorse(color, maneColor, tailColor, breathOffset, legPhase, runCycle);
            
            this.ctx.restore();
            this.ctx.restore();

            horse.x += horse.speed * this.speedMultiplier;
            
            if (horse.x > this.width + 250) {
                horse.x = -250;
                horse.y = this.height * 0.4 + Math.random() * this.height * 0.35;
                horse.baseY = horse.y;
            }

            horse.breathPhase += 0.03 * this.speedMultiplier;
            horse.legPhase += 0.15 * this.speedMultiplier;
        }

        drawRealisticHorse(color, maneColor, tailColor, breathOffset, legPhase, runCycle) {
            this.ctx.save();
            
            this.drawHorseNeck(color, breathOffset);
            this.drawHorseBodyRealistic(color, breathOffset);
            this.drawHorseHeadRealistic(color, breathOffset, runCycle);
            this.drawHorseLegsRealistic(color, legPhase);
            this.drawHorseManeRealistic(maneColor, runCycle);
            this.drawHorseTailRealistic(tailColor, runCycle);
            this.drawHorseDetails(color, breathOffset);
            
            this.ctx.restore();
        }

        drawHorseNeck(color, breathOffset) {
            const neckGradient = this.ctx.createLinearGradient(-30, -60, 40, -20);
            neckGradient.addColorStop(0, color.highlight);
            neckGradient.addColorStop(0.4, color.body);
            neckGradient.addColorStop(1, color.shadow);
            
            this.ctx.fillStyle = neckGradient;
            this.ctx.beginPath();
            this.ctx.moveTo(30, -15 + breathOffset);
            this.ctx.bezierCurveTo(45, -35 + breathOffset, 55, -55 + breathOffset, 50, -75 + breathOffset);
            this.ctx.bezierCurveTo(48, -85 + breathOffset, 40, -90 + breathOffset, 30, -85 + breathOffset);
            this.ctx.bezierCurveTo(15, -80 + breathOffset, 5, -65 + breathOffset, -10, -45 + breathOffset);
            this.ctx.bezierCurveTo(-20, -30 + breathOffset, -25, -15 + breathOffset, -30, 0);
            this.ctx.lineTo(30, -15 + breathOffset);
            this.ctx.fill();
        }

        drawHorseBodyRealistic(color, breathOffset) {
            const bodyGradient = this.ctx.createLinearGradient(-80, -40, -80, 40);
            bodyGradient.addColorStop(0, color.highlight);
            bodyGradient.addColorStop(0.3, color.body);
            bodyGradient.addColorStop(0.7, color.body);
            bodyGradient.addColorStop(1, color.shadow);
            
            this.ctx.fillStyle = bodyGradient;
            this.ctx.beginPath();
            this.ctx.moveTo(-85, -10 + breathOffset);
            this.ctx.bezierCurveTo(-90, -30 + breathOffset, -80, -45 + breathOffset, -60, -45 + breathOffset);
            this.ctx.bezierCurveTo(-30, -48 + breathOffset, 10, -40 + breathOffset, 35, -25 + breathOffset);
            this.ctx.bezierCurveTo(50, -15 + breathOffset, 55, 0, 50, 15);
            this.ctx.bezierCurveTo(40, 30, 10, 35, -30, 35);
            this.ctx.bezierCurveTo(-60, 35, -85, 25, -90, 10);
            this.ctx.bezierCurveTo(-95, 0, -90, -10 + breathOffset, -85, -10 + breathOffset);
            this.ctx.fill();

            this.ctx.fillStyle = color.highlight;
            this.ctx.globalAlpha = 0.25;
            this.ctx.beginPath();
            this.ctx.ellipse(-30, -25 + breathOffset, 35, 15, -0.2, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;

            this.ctx.strokeStyle = color.shadow;
            this.ctx.lineWidth = 1;
            this.ctx.globalAlpha = 0.5;
            this.ctx.beginPath();
            this.ctx.moveTo(-20, 35);
            this.ctx.bezierCurveTo(-10, 32, 5, 28, 15, 25);
            this.ctx.stroke();
            this.ctx.globalAlpha = 1;
        }

        drawHorseHeadRealistic(color, breathOffset, runCycle) {
            const headX = 65;
            const headY = -70 + breathOffset;
            const headTilt = Math.sin(runCycle * 0.3) * 0.05;
            
            this.ctx.save();
            this.ctx.translate(headX, headY);
            this.ctx.rotate(headTilt);

            const headGradient = this.ctx.createLinearGradient(-15, -30, 30, 10);
            headGradient.addColorStop(0, color.highlight);
            headGradient.addColorStop(0.5, color.body);
            headGradient.addColorStop(1, color.shadow);
            
            this.ctx.fillStyle = headGradient;
            this.ctx.beginPath();
            this.ctx.moveTo(-10, -25);
            this.ctx.bezierCurveTo(-15, -35, -10, -45, 5, -48);
            this.ctx.bezierCurveTo(20, -50, 35, -45, 40, -35);
            this.ctx.bezierCurveTo(45, -25, 42, -15, 38, -5);
            this.ctx.bezierCurveTo(35, 5, 25, 12, 15, 15);
            this.ctx.bezierCurveTo(5, 18, -5, 15, -8, 5);
            this.ctx.bezierCurveTo(-12, -5, -12, -15, -10, -25);
            this.ctx.fill();

            this.ctx.fillStyle = '#0a0503';
            this.ctx.beginPath();
            this.ctx.ellipse(25, -30, 8, 5, 0.2, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = '#ffffff';
            this.ctx.beginPath();
            this.ctx.arc(27, -32, 2, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = '#1a0f08';
            this.ctx.beginPath();
            this.ctx.ellipse(38, -15, 5, 3, 0.3, 0, Math.PI * 2);
            this.ctx.fill();
            
            this.ctx.fillStyle = '#0a0503';
            this.ctx.beginPath();
            this.ctx.ellipse(40, -15, 2.5, 1.5, 0.3, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = color.body;
            this.ctx.beginPath();
            this.ctx.moveTo(38, -5);
            this.ctx.bezierCurveTo(42, 0, 40, 8, 35, 12);
            this.ctx.lineTo(30, 8);
            this.ctx.bezierCurveTo(35, 5, 38, 0, 38, -5);
            this.ctx.fill();

            this.ctx.strokeStyle = color.shadow;
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.moveTo(10, 15);
            this.ctx.bezierCurveTo(15, 22, 20, 25, 25, 22);
            this.ctx.stroke();

            this.ctx.restore();
        }

        drawHorseLegsRealistic(color, legPhase) {
            const frontRightPhase = legPhase;
            const frontLeftPhase = legPhase + Math.PI * 0.5;
            const backRightPhase = legPhase + Math.PI;
            const backLeftPhase = legPhase + Math.PI * 1.5;

            this.drawSingleLeg(-65, 35, color, backLeftPhase, true, true);
            this.drawSingleLeg(-45, 35, color, backRightPhase, true, false);
            this.drawSingleLeg(25, 30, color, frontLeftPhase, false, true);
            this.drawSingleLeg(40, 28, color, frontRightPhase, false, false);
        }

        drawSingleLeg(baseX, baseY, color, phase, isBack, isFar) {
            const swing = Math.sin(phase) * 25;
            const kneeBend = Math.cos(phase) * 20;
            const hockBend = Math.sin(phase + 0.5) * 15;
            
            const upperLength = isBack ? 35 : 32;
            const lowerLength = isBack ? 40 : 38;
            const fetlockLength = 15;

            const shoulderX = baseX;
            const shoulderY = baseY;
            
            const elbowX = shoulderX + swing * 0.3;
            const elbowY = shoulderY + upperLength * 0.6;
            
            const kneeX = shoulderX + swing * 0.6;
            const kneeY = shoulderY + upperLength;
            
            const fetlockX = kneeX + swing * 0.4 + kneeBend * 0.3;
            const fetlockY = kneeY + lowerLength;
            
            const hoofX = fetlockX + hockBend * 0.2;
            const hoofY = fetlockY + fetlockLength;

            const legGradient = this.ctx.createLinearGradient(
                shoulderX - 6, shoulderY, 
                shoulderX + 6, hoofY
            );
            legGradient.addColorStop(0, color.body);
            legGradient.addColorStop(0.5, color.highlight);
            legGradient.addColorStop(1, color.shadow);

            this.ctx.strokeStyle = legGradient;
            this.ctx.lineWidth = isFar ? 7 : 9;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';

            this.ctx.beginPath();
            this.ctx.moveTo(shoulderX, shoulderY);
            this.ctx.quadraticCurveTo(elbowX, elbowY, kneeX, kneeY);
            this.ctx.stroke();

            this.ctx.lineWidth = isFar ? 6 : 8;
            this.ctx.beginPath();
            this.ctx.moveTo(kneeX, kneeY);
            this.ctx.quadraticCurveTo(
                kneeX + kneeBend * 0.2, 
                kneeY + lowerLength * 0.5,
                fetlockX, 
                fetlockY
            );
            this.ctx.stroke();

            this.ctx.lineWidth = isFar ? 4 : 5;
            this.ctx.beginPath();
            this.ctx.moveTo(fetlockX, fetlockY);
            this.ctx.lineTo(hoofX, hoofY);
            this.ctx.stroke();

            this.ctx.fillStyle = '#1a0f08';
            this.ctx.beginPath();
            this.ctx.ellipse(hoofX, hoofY + 4, 8, 5, swing * 0.01, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = color.highlight;
            this.ctx.globalAlpha = 0.3;
            this.ctx.beginPath();
            this.ctx.ellipse(shoulderX + 2, shoulderY + 5, 4, 8, 0.3, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;
        }

        drawHorseManeRealistic(maneColor, runCycle) {
            const maneStrands = 12;
            const baseX = 50;
            const baseY = -85;
            
            for (let i = 0; i < maneStrands; i++) {
                const t = i / maneStrands;
                const startX = baseX - t * 80;
                const startY = baseY + t * 35;
                const wave = Math.sin(runCycle + i * 0.4) * (8 + i * 1.5);
                const length = 25 + i * 3 + Math.sin(runCycle + i) * 5;
                
                const strandGradient = this.ctx.createLinearGradient(
                    startX, startY, 
                    startX - wave, startY + length
                );
                strandGradient.addColorStop(0, maneColor);
                strandGradient.addColorStop(1, '#0a0503');
                
                this.ctx.strokeStyle = strandGradient;
                this.ctx.lineWidth = 3 - t * 1.5;
                this.ctx.lineCap = 'round';
                
                this.ctx.beginPath();
                this.ctx.moveTo(startX, startY);
                this.ctx.bezierCurveTo(
                    startX - wave * 0.3, startY + length * 0.3,
                    startX - wave * 0.7, startY + length * 0.6,
                    startX - wave, startY + length
                );
                this.ctx.stroke();
            }
        }

        drawHorseTailRealistic(tailColor, runCycle) {
            const tailBaseX = -85;
            const tailBaseY = -5;
            const tailStrands = 8;
            
            for (let i = 0; i < tailStrands; i++) {
                const wave = Math.sin(runCycle + i * 0.5) * (15 + i * 4);
                const length = 40 + i * 8 + Math.sin(runCycle + i * 0.3) * 10;
                const spread = (i - tailStrands / 2) * 3;
                
                const tailGradient = this.ctx.createLinearGradient(
                    tailBaseX, tailBaseY,
                    tailBaseX - 40 + wave, tailBaseY + length
                );
                tailGradient.addColorStop(0, tailColor);
                tailGradient.addColorStop(1, '#0a0503');
                
                this.ctx.strokeStyle = tailGradient;
                this.ctx.lineWidth = 5 - i * 0.4;
                this.ctx.lineCap = 'round';
                this.ctx.globalAlpha = 1 - i * 0.08;
                
                this.ctx.beginPath();
                this.ctx.moveTo(tailBaseX, tailBaseY);
                this.ctx.bezierCurveTo(
                    tailBaseX - 15 + wave * 0.3, tailBaseY + length * 0.3,
                    tailBaseX - 30 + wave * 0.7 + spread, tailBaseY + length * 0.6,
                    tailBaseX - 40 + wave + spread, tailBaseY + length
                );
                this.ctx.stroke();
            }
            this.ctx.globalAlpha = 1;
        }

        drawHorseDetails(color, breathOffset) {
            this.ctx.fillStyle = color.shadow;
            this.ctx.globalAlpha = 0.4;
            this.ctx.beginPath();
            this.ctx.ellipse(-50, 5 + breathOffset, 8, 4, 0.5, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;

            this.ctx.fillStyle = color.highlight;
            this.ctx.globalAlpha = 0.2;
            this.ctx.beginPath();
            this.ctx.ellipse(35, -50 + breathOffset, 6, 3, 0.3, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;
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
