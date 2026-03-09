'use client';

import React, { useEffect, useRef, memo } from 'react';

/**
 * Aurora Mesh Background
 * 
 * Modern ambient background: soft color blobs that drift and morph slowly,
 * creating a living mesh gradient effect. No particles, no grids — just
 * smooth organic color fields with subtle film grain overlay.
 * Adapts to light/dark theme. Minimal GPU usage.
 */

const AlgorithmicBackground = memo(function AlgorithmicBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    // Use lower resolution for performance (blur hides pixels)
    const SCALE = 0.35;
    let width = 0;
    let height = 0;
    let cw = 0;
    let ch = 0;

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      cw = Math.floor(width * SCALE);
      ch = Math.floor(height * SCALE);
      canvas.width = cw;
      canvas.height = ch;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };
    resize();
    window.addEventListener('resize', resize);

    const isDark = () => document.documentElement.classList.contains('dark');

    // Blob definitions — each is a soft radial gradient that drifts
    const blobs = [
      { cx: 0.2, cy: 0.3, rx: 0.35, ry: 0.35, speed: 0.0004, phase: 0, hue: 217 },
      { cx: 0.8, cy: 0.2, rx: 0.3, ry: 0.4, speed: 0.0003, phase: 2, hue: 226 },
      { cx: 0.5, cy: 0.7, rx: 0.4, ry: 0.3, speed: 0.0005, phase: 4, hue: 213 },
      { cx: 0.1, cy: 0.8, rx: 0.25, ry: 0.3, speed: 0.00035, phase: 1.5, hue: 230 },
      { cx: 0.9, cy: 0.6, rx: 0.3, ry: 0.35, speed: 0.00045, phase: 3, hue: 200 },
    ];

    let time = 0;
    let lastFrame = 0;

    // Grain overlay — generated once
    let grainData: ImageData | null = null;
    const generateGrain = () => {
      const gCanvas = document.createElement('canvas');
      gCanvas.width = cw;
      gCanvas.height = ch;
      const gCtx = gCanvas.getContext('2d');
      if (!gCtx) return;
      const imageData = gCtx.createImageData(cw, ch);
      const data = imageData.data;
      for (let i = 0; i < data.length; i += 4) {
        const v = Math.random() * 255;
        data[i] = v;
        data[i + 1] = v;
        data[i + 2] = v;
        data[i + 3] = 8; // Very subtle grain
      }
      grainData = imageData;
    };
    generateGrain();

    const animate = (ts: number) => {
      // Throttle to ~30fps for efficiency
      if (ts - lastFrame < 33) {
        animRef.current = requestAnimationFrame(animate);
        return;
      }
      lastFrame = ts;
      time += 1;

      const dark = isDark();

      // Clear with base background
      ctx.clearRect(0, 0, cw, ch);

      // Draw each blob
      for (const blob of blobs) {
        const t = time * blob.speed + blob.phase;

        // Organic movement: each blob drifts in a lissajous-like pattern
        const bx = (blob.cx + Math.sin(t * 1.1) * 0.08 + Math.sin(t * 0.7) * 0.05) * cw;
        const by = (blob.cy + Math.cos(t * 0.9) * 0.06 + Math.cos(t * 1.3) * 0.04) * ch;
        const rx = blob.rx * cw * (0.9 + Math.sin(t * 0.5) * 0.1);
        const ry = blob.ry * ch * (0.9 + Math.cos(t * 0.6) * 0.1);

        // Elliptical gradient via transform
        ctx.save();
        ctx.translate(bx, by);
        ctx.scale(1, ry / rx);

        const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);

        if (dark) {
          // Dark mode: deeper, richer blue tones
          const alpha1 = 0.06 + Math.sin(t * 0.3) * 0.02;
          const alpha2 = 0.03 + Math.sin(t * 0.4) * 0.01;
          grad.addColorStop(0, `hsla(${blob.hue}, 80%, 60%, ${alpha1})`);
          grad.addColorStop(0.5, `hsla(${blob.hue}, 70%, 45%, ${alpha2})`);
          grad.addColorStop(1, 'hsla(0, 0%, 0%, 0)');
        } else {
          // Light mode: very faint cool tones
          const alpha1 = 0.04 + Math.sin(t * 0.3) * 0.015;
          const alpha2 = 0.02 + Math.sin(t * 0.4) * 0.008;
          grad.addColorStop(0, `hsla(${blob.hue}, 70%, 65%, ${alpha1})`);
          grad.addColorStop(0.5, `hsla(${blob.hue}, 60%, 75%, ${alpha2})`);
          grad.addColorStop(1, 'hsla(0, 0%, 100%, 0)');
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(0, 0, rx, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // Apply grain overlay
      if (grainData && grainData.width === cw && grainData.height === ch) {
        ctx.putImageData(grainData, 0, 0);
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', resize);
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 0,
        imageRendering: 'auto',
        filter: 'blur(1px)',
      }}
    />
  );
});

export default AlgorithmicBackground;
