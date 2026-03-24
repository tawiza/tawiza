'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useTheme } from 'next-themes';
import { createNoise2D } from 'simplex-noise';

interface BlobBackgroundProps {
  isStreaming?: boolean;
  className?: string;
}

interface Blob {
  x: number;
  y: number;
  baseRadius: number;
  phase: number;
  speed: number;
}

// Monochromatic, ultra-subtle colors - same base for both themes
const COLORS = {
  dark: {
    bg: 'rgba(46, 52, 64, 0.02)', // nord0 - nearly invisible
    // Single neutral blue-gray tone for all blobs
    blobs: [
      { r: 129, g: 161, b: 193 }, // nord9 muted blue
      { r: 129, g: 161, b: 193 }, // same color
      { r: 129, g: 161, b: 193 }, // same color
    ],
  },
  light: {
    bg: 'rgba(236, 239, 244, 0.02)', // nord6 - nearly invisible
    // Darker neutral for visibility on light backgrounds
    blobs: [
      { r: 76, g: 86, b: 106 },   // nord3 dark gray
      { r: 76, g: 86, b: 106 },   // same color
      { r: 76, g: 86, b: 106 },   // same color
    ],
  },
};

export default function BlobBackground({ isStreaming = false, className = '' }: BlobBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const noise2D = useRef(createNoise2D());
  const blobsRef = useRef<Blob[]>([]);
  const timeRef = useRef(0);
  const { resolvedTheme } = useTheme();

  const initBlobs = useCallback((width: number, height: number) => {
    // Create 3 very large, extremely slow-moving blobs
    const count = 3;
    blobsRef.current = Array.from({ length: count }, (_, i) => ({
      x: (width / (count + 1)) * (i + 1) + (Math.random() - 0.5) * 50,
      y: height / 2 + (Math.random() - 0.5) * height * 0.3,
      baseRadius: 150 + Math.random() * 200, // Much larger blobs
      phase: Math.random() * Math.PI * 2,
      speed: 0.1 + Math.random() * 0.1, // Much slower movement
    }));
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const dpr = 0.5; // Lower resolution for smooth blobs
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      initBlobs(canvas.width, canvas.height);
    };

    resize();
    window.addEventListener('resize', resize);

    const animate = () => {
      if (document.hidden) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }

      const width = canvas.width;
      const height = canvas.height;
      const isDark = resolvedTheme === 'dark';
      const colors = isDark ? COLORS.dark : COLORS.light;

      // Clear with very subtle fade
      ctx.fillStyle = colors.bg;
      ctx.fillRect(0, 0, width, height);

      // Update time - extremely slow for realistic, barely-perceptible movement
      const baseSpeed = isStreaming ? 0.004 : 0.001;
      timeRef.current += baseSpeed;

      // Draw blobs with organic movement
      const blobs = blobsRef.current;

      for (let i = 0; i < blobs.length; i++) {
        const blob = blobs[i];
        const color = colors.blobs[i % colors.blobs.length];

        // Very subtle organic movement using noise
        const noiseX = noise2D.current(i * 0.5, timeRef.current * blob.speed) * 15;
        const noiseY = noise2D.current(i * 0.5 + 100, timeRef.current * blob.speed) * 15;

        const x = blob.x + noiseX;
        const y = blob.y + noiseY;

        // Very subtle pulsing radius - almost imperceptible
        const pulseAmount = isStreaming ? 0.05 : 0.02;
        const pulse = Math.sin(timeRef.current * 0.5 + blob.phase) * pulseAmount + 1;
        const radius = blob.baseRadius * pulse * (isStreaming ? 1.1 : 1);

        // Create radial gradient for ultra-soft blob
        const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);

        // Ultra-subtle opacity - barely visible
        const baseOpacity = isStreaming ? 0.025 : 0.012;
        gradient.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${baseOpacity})`);
        gradient.addColorStop(0.4, `rgba(${color.r}, ${color.g}, ${color.b}, ${baseOpacity * 0.6})`);
        gradient.addColorStop(0.7, `rgba(${color.r}, ${color.g}, ${color.b}, ${baseOpacity * 0.2})`);
        gradient.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        // Add very subtle inner glow only when streaming
        if (isStreaming) {
          const innerRadius = radius * 0.4;
          const innerGradient = ctx.createRadialGradient(x, y, 0, x, y, innerRadius);
          innerGradient.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${baseOpacity * 0.4})`);
          innerGradient.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);
          ctx.beginPath();
          ctx.arc(x, y, innerRadius, 0, Math.PI * 2);
          ctx.fillStyle = innerGradient;
          ctx.fill();
        }
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
  }, [isStreaming, initBlobs, resolvedTheme]);

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 -z-10 pointer-events-none ${className}`}
      aria-hidden="true"
    />
  );
}
