import React, { useRef, useEffect } from 'react';

const InteractiveBackground = ({ theme = 'dark' }) => {
    const canvasRef = useRef(null);
    const mouseRef = useRef({ x: null, y: null });

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        let animationFrameId;

        const resizeCanvas = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };

        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        // Constants
        const PARTICLE_COUNT = 80;
        const CONNECTION_DISTANCE = 160;
        const MOUSE_DISTANCE = 250;

        // Theme Colors
        const colors = theme === 'dark' ? {
            //dark mode
            particle1: 'rgba(0, 212, 255,', // Cyan
            particle2: 'rgba(180, 0, 255,', // Purple
            connection: 'rgba(100, 100, 180,',
            mouseConnection: 'rgba(0, 212, 255,',
            mouseGlowStart: 'rgba(40, 20, 100, 0.2)',
            mouseGlowEnd: 'rgba(0, 0, 0, 0)'
        } : {
            //light mode
            particle1: 'rgba(0, 0, 0,', // Black
            particle2: 'rgba(50, 50, 50,', // Dark Gray for variety
            connection: 'rgba(0, 0, 0,', // Black lines
            mouseConnection: 'rgba(0, 0, 0,', // Black mouse lines
            mouseGlowStart: 'rgba(255, 255, 255, 0)', // Transparent (No Glow)
            mouseGlowEnd: 'rgba(255, 255, 255, 0)'
        };

        // Particle Class
        class Particle {
            constructor() {
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
                this.vx = (Math.random() - 0.5) * 0.4;
                this.vy = (Math.random() - 0.5) * 0.4;
                this.size = Math.random() * 2 + 1;
                // Sidebar uses Purple/Pink/Blue. Let's start with faint purple.
                this.baseAlpha = Math.random() * 0.4 + 0.1;
                // Add color variance
                this.colorType = Math.random() > 0.5 ? 'type1' : 'type2';
            }

            update() {
                this.x += this.vx;
                this.y += this.vy;

                // Bounce off edges
                if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
                if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
            }

            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                if (this.colorType === 'type1') {
                    ctx.fillStyle = `${colors.particle1} ${this.baseAlpha})`;
                } else {
                    ctx.fillStyle = `${colors.particle2} ${this.baseAlpha})`;
                }
                ctx.fill();
            }
        }

        // Init Particles
        const particles = Array.from({ length: PARTICLE_COUNT }, () => new Particle());

        // Animation Loop
        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // 1. Mouse Searchlight / Glow Effect
            if (mouseRef.current.x != null) {
                // Create a heavy radial gradient around mouse to "reveal" the network
                const gradient = ctx.createRadialGradient(
                    mouseRef.current.x, mouseRef.current.y, 0,
                    mouseRef.current.x, mouseRef.current.y, 400
                );

                gradient.addColorStop(0, colors.mouseGlowStart);
                gradient.addColorStop(1, colors.mouseGlowEnd);

                ctx.fillStyle = gradient;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            }

            // Draw particles
            particles.forEach(particle => {
                particle.update();
                particle.draw();
            });

            // Draw Connections
            particles.forEach((p1, i) => {
                // Connect to other particles
                for (let j = i + 1; j < particles.length; j++) {
                    const p2 = particles[j];
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < CONNECTION_DISTANCE) {
                        const alpha = (1 - dist / CONNECTION_DISTANCE) * 0.2;
                        ctx.beginPath();
                        ctx.strokeStyle = `${colors.connection} ${alpha})`;
                        ctx.lineWidth = 0.5;
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.stroke();
                    }
                }

                // Connect to Mouse
                if (mouseRef.current.x != null) {
                    const dx = p1.x - mouseRef.current.x;
                    const dy = p1.y - mouseRef.current.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < MOUSE_DISTANCE) {
                        const alpha = (1 - dist / MOUSE_DISTANCE) * 0.8;
                        ctx.beginPath();
                        // Highlight for mouse connections
                        ctx.strokeStyle = `${colors.mouseConnection} ${alpha})`;
                        ctx.lineWidth = 1.0;
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(mouseRef.current.x, mouseRef.current.y);
                        ctx.stroke();
                    }
                }
            });

            animationFrameId = requestAnimationFrame(animate);
        };

        animate();

        // Mouse Handlers
        const handleMouseMove = (e) => {
            mouseRef.current = { x: e.clientX, y: e.clientY };
        };

        const handleMouseLeave = () => {
            mouseRef.current = { x: null, y: null };
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseout', handleMouseLeave);

        return () => {
            window.removeEventListener('resize', resizeCanvas);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseout', handleMouseLeave);
            cancelAnimationFrame(animationFrameId);
        };
    }, [theme]);

    return (
        <canvas
            ref={canvasRef}
            className="fixed inset-0 pointer-events-none z-0"
            style={{ width: '100%', height: '100%' }}
        />
    );
};

export default InteractiveBackground;
