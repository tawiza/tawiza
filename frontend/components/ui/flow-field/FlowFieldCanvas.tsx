'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useTheme } from 'next-themes';
import { createNoise2D } from 'simplex-noise';

interface FlowFieldProps {
  isStreaming?: boolean;
  className?: string;
}

// Theme-aware colors
const THEMES = {
  dark: {
    bg: 'rgba(46, 52, 64, 0.05)', // nord0
    particles: ['136, 192, 208', '129, 161, 193'], // nord8, nord9
  },
  light: {
    bg: 'rgba(236, 239, 244, 0.05)', // nord6
    particles: ['94, 129, 172', '76, 86, 106'], // nord10, nord3
  },
};

export default function FlowFieldCanvas({ isStreaming = false, className = '' }: FlowFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const noise2D = useRef(createNoise2D());
  const particlesRef = useRef<Particle[]>([]);
  const timeRef = useRef(0);
  const targetIntensityRef = useRef(0.3);
  const currentIntensityRef = useRef(0.3);
  const { resolvedTheme } = useTheme();

  interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    life: number;
    maxLife: number;
  }

  const createParticle = useCallback((width: number, height: number): Particle => {
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: 0,
      vy: 0,
      life: 0,
      maxLife: 100 + Math.random() * 100,
    };
  }, []);

  const initParticles = useCallback((count: number, width: number, height: number) => {
    particlesRef.current = Array.from({ length: count }, () => createParticle(width, height));
  }, [createParticle]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size (50% resolution for performance)
    const resize = () => {
      const dpr = 0.5; // Lower resolution for performance
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = '100%';
      canvas.style.height = '100%';

      // Reinit particles on resize
      const particleCount = isStreaming ? 80 : 40;
      initParticles(particleCount, canvas.width, canvas.height);
    };

    resize();
    window.addEventListener('resize', resize);

    // Animation loop
    const animate = () => {
      if (document.hidden) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }

      const width = canvas.width;
      const height = canvas.height;

      // Smooth intensity transition
      const targetIntensity = isStreaming ? 1.0 : 0.3;
      targetIntensityRef.current = targetIntensity;
      currentIntensityRef.current += (targetIntensityRef.current - currentIntensityRef.current) * 0.02;
      const intensity = currentIntensityRef.current;

      // Clear with fade effect (theme-aware)
      const isDark = resolvedTheme === 'dark';
      const theme = isDark ? THEMES.dark : THEMES.light;
      ctx.fillStyle = theme.bg;
      ctx.fillRect(0, 0, width, height);

      // Update time
      const speed = 0.0005 + intensity * 0.002;
      timeRef.current += speed;

      // Update and draw particles
      const particles = particlesRef.current;
      const noiseScale = 0.003;

      for (const particle of particles) {
        // Get flow direction from noise
        const noiseVal = noise2D.current(
          particle.x * noiseScale,
          particle.y * noiseScale + timeRef.current
        );
        const angle = noiseVal * Math.PI * 2;

        // Update velocity
        const flowSpeed = 0.5 + intensity * 1.5;
        particle.vx = Math.cos(angle) * flowSpeed;
        particle.vy = Math.sin(angle) * flowSpeed;

        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;

        // Wrap around edges
        if (particle.x < 0) particle.x = width;
        if (particle.x > width) particle.x = 0;
        if (particle.y < 0) particle.y = height;
        if (particle.y > height) particle.y = 0;

        // Update life
        particle.life++;
        if (particle.life > particle.maxLife) {
          particle.x = Math.random() * width;
          particle.y = Math.random() * height;
          particle.life = 0;
          particle.maxLife = 100 + Math.random() * 100;
        }

        // Calculate opacity based on life
        const lifeRatio = particle.life / particle.maxLife;
        const fadeIn = Math.min(lifeRatio * 5, 1);
        const fadeOut = Math.min((1 - lifeRatio) * 5, 1);
        const baseOpacity = 0.1 + intensity * 0.15;
        const opacity = baseOpacity * fadeIn * fadeOut;

        // Draw particle trail
        const trailLength = 3 + intensity * 5;
        ctx.beginPath();
        ctx.moveTo(particle.x, particle.y);
        ctx.lineTo(
          particle.x - particle.vx * trailLength,
          particle.y - particle.vy * trailLength
        );

        // Theme-aware particle colors
        const colors = theme.particles;
        const color = colors[Math.floor(Math.random() * colors.length)];
        ctx.strokeStyle = `rgba(${color}, ${opacity})`;
        ctx.lineWidth = 1 + intensity * 0.5;
        ctx.lineCap = 'round';
        ctx.stroke();
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resize);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isStreaming, initParticles, resolvedTheme]);

  // Update particle count when streaming changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const particleCount = isStreaming ? 80 : 40;
    if (particlesRef.current.length !== particleCount) {
      initParticles(particleCount, canvas.width, canvas.height);
    }
  }, [isStreaming, initParticles]);

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 -z-10 pointer-events-none ${className}`}
      aria-hidden="true"
    />
  );
}
