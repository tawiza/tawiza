'use client';

import React, { useEffect, useRef, useState, memo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * IntelligenceHub - Real-time Data Flow Visualization
 *
 * A futuristic HUD-style component showing data flowing between sources
 * and the TAJINE AI core. Impressive visual for the dashboard.
 */

interface DataPulse {
  id: number;
  source: string;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  color: string;
  progress: number;
}

interface DataSource {
  name: string;
  icon: string;
  color: string;
  angle: number;
  active: boolean;
  count: number;
}

const SOURCES: DataSource[] = [
  { name: 'SIRENE', icon: '🏢', color: 'var(--error)', angle: 0, active: true, count: 0 },
  { name: 'INSEE', icon: '📊', color: 'var(--chart-4)', angle: 45, active: true, count: 0 },
  { name: 'BODACC', icon: '📋', color: 'var(--warning)', angle: 90, active: true, count: 0 },
  { name: 'BOAMP', icon: '📑', color: 'var(--success)', angle: 135, active: false, count: 0 },
  { name: 'DVF', icon: '🏠', color: 'var(--error)', angle: 180, active: true, count: 0 },
  { name: 'BAN', icon: '📍', color: 'var(--chart-3)', angle: 225, active: true, count: 0 },
  { name: 'France Travail', icon: '💼', color: 'var(--chart-5)', angle: 270, active: false, count: 0 },
  { name: 'Ollama', icon: '🧠', color: 'var(--success)', angle: 315, active: true, count: 0 },
];

const IntelligenceHub = memo(function IntelligenceHub({
  size = 400,
  showLabels = true,
  className = '',
}: {
  size?: number;
  showLabels?: boolean;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [sources, setSources] = useState<DataSource[]>(SOURCES);
  const [pulses, setPulses] = useState<DataPulse[]>([]);
  const [totalProcessed, setTotalProcessed] = useState(0);
  const [activeConnections, setActiveConnections] = useState(0);
  const pulseIdRef = useRef(0);
  const animationRef = useRef<number>();

  const center = size / 2;
  const radius = size * 0.35;

  // Create new data pulse from a source
  const createPulse = useCallback((source: DataSource) => {
    const rad = (source.angle * Math.PI) / 180;
    const x = center + Math.cos(rad) * radius;
    const y = center + Math.sin(rad) * radius;

    return {
      id: pulseIdRef.current++,
      source: source.name,
      x,
      y,
      targetX: center,
      targetY: center,
      color: source.color,
      progress: 0,
    };
  }, [center, radius]);

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    let time = 0;

    const draw = () => {
      ctx.clearRect(0, 0, size, size);

      // Draw background glow
      const gradient = ctx.createRadialGradient(center, center, 0, center, center, radius * 1.2);
      gradient.addColorStop(0, 'rgba(255, 107, 74, 0.1)');
      gradient.addColorStop(0.5, 'rgba(255, 107, 74, 0.02)');
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, size, size);

      // Draw connection rings
      for (let i = 1; i <= 3; i++) {
        const ringRadius = (radius * i) / 3;
        ctx.beginPath();
        ctx.arc(center, center, ringRadius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255, 107, 74, ${0.1 - i * 0.02})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Draw rotating scanner line
      const scanAngle = time * 0.5;
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.lineTo(
        center + Math.cos(scanAngle) * radius * 1.1,
        center + Math.sin(scanAngle) * radius * 1.1
      );
      const scanGradient = ctx.createLinearGradient(
        center,
        center,
        center + Math.cos(scanAngle) * radius,
        center + Math.sin(scanAngle) * radius
      );
      scanGradient.addColorStop(0, 'rgba(255, 107, 74, 0.5)');
      scanGradient.addColorStop(1, 'rgba(255, 107, 74, 0)');
      ctx.strokeStyle = scanGradient;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw connections from sources to center
      sources.forEach((source) => {
        const rad = (source.angle * Math.PI) / 180;
        const x = center + Math.cos(rad) * radius;
        const y = center + Math.sin(rad) * radius;

        // Connection line
        ctx.beginPath();
        ctx.moveTo(center, center);
        ctx.lineTo(x, y);
        ctx.strokeStyle = source.active
          ? `rgba(255, 107, 74, 0.3)`
          : `rgba(100, 100, 100, 0.1)`;
        ctx.lineWidth = source.active ? 2 : 1;
        ctx.stroke();

        // Source node
        ctx.beginPath();
        ctx.arc(x, y, source.active ? 8 : 5, 0, Math.PI * 2);
        ctx.fillStyle = source.active ? source.color : 'hsl(var(--muted-foreground))';
        ctx.fill();

        // Pulse effect for active sources
        if (source.active) {
          const pulseSize = 8 + Math.sin(time * 3 + source.angle) * 3;
          ctx.beginPath();
          ctx.arc(x, y, pulseSize, 0, Math.PI * 2);
          ctx.strokeStyle = `${source.color}66`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });

      // Draw center core
      const coreGlow = ctx.createRadialGradient(center, center, 0, center, center, 30);
      coreGlow.addColorStop(0, 'rgba(255, 107, 74, 0.8)');
      coreGlow.addColorStop(0.5, 'rgba(255, 107, 74, 0.3)');
      coreGlow.addColorStop(1, 'transparent');
      ctx.fillStyle = coreGlow;
      ctx.fillRect(center - 30, center - 30, 60, 60);

      // Core circle with pulsing effect
      const corePulse = 15 + Math.sin(time * 2) * 3;
      ctx.beginPath();
      ctx.arc(center, center, corePulse, 0, Math.PI * 2);
      ctx.fillStyle = 'var(--error)';
      ctx.fill();

      // Inner core
      ctx.beginPath();
      ctx.arc(center, center, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'hsl(var(--foreground))';
      ctx.fill();

      // Draw data pulses traveling to center
      setPulses((currentPulses) =>
        currentPulses
          .map((pulse) => ({
            ...pulse,
            progress: pulse.progress + 0.02,
          }))
          .filter((pulse) => pulse.progress < 1)
      );

      pulses.forEach((pulse) => {
        const x = pulse.x + (pulse.targetX - pulse.x) * pulse.progress;
        const y = pulse.y + (pulse.targetY - pulse.y) * pulse.progress;
        const opacity = 1 - pulse.progress * 0.5;
        const pulseSize = 4 * (1 - pulse.progress * 0.5);

        ctx.beginPath();
        ctx.arc(x, y, pulseSize, 0, Math.PI * 2);
        ctx.fillStyle = pulse.color + Math.round(opacity * 255).toString(16).padStart(2, '0');
        ctx.fill();

        // Trail effect
        for (let t = 1; t <= 3; t++) {
          const trailProgress = Math.max(0, pulse.progress - t * 0.05);
          const tx = pulse.x + (pulse.targetX - pulse.x) * trailProgress;
          const ty = pulse.y + (pulse.targetY - pulse.y) * trailProgress;
          ctx.beginPath();
          ctx.arc(tx, ty, pulseSize * (1 - t * 0.2), 0, Math.PI * 2);
          ctx.fillStyle = pulse.color + Math.round(opacity * 0.3 * 255).toString(16).padStart(2, '0');
          ctx.fill();
        }
      });

      time += 0.016;
      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [size, center, radius, sources, pulses]);

  // Simulate data flow
  useEffect(() => {
    const interval = setInterval(() => {
      const activeSources = sources.filter((s) => s.active);
      if (activeSources.length === 0) return;

      const randomSource = activeSources[Math.floor(Math.random() * activeSources.length)];
      const newPulse = createPulse(randomSource);

      setPulses((prev) => [...prev, newPulse]);
      setTotalProcessed((prev) => prev + 1);
      setSources((prev) =>
        prev.map((s) =>
          s.name === randomSource.name ? { ...s, count: s.count + 1 } : s
        )
      );
    }, 500 + Math.random() * 1000);

    return () => clearInterval(interval);
  }, [sources, createPulse]);

  // Update active connections count
  useEffect(() => {
    setActiveConnections(sources.filter((s) => s.active).length);
  }, [sources]);

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      <canvas ref={canvasRef} className="absolute inset-0" />

      {/* Source Labels */}
      {showLabels && (
        <div className="absolute inset-0 pointer-events-none">
          {sources.map((source) => {
            const rad = (source.angle * Math.PI) / 180;
            const labelRadius = radius + 35;
            const x = center + Math.cos(rad) * labelRadius;
            const y = center + Math.sin(rad) * labelRadius;

            return (
              <motion.div
                key={source.name}
                className="absolute text-xs font-medium"
                style={{
                  left: x,
                  top: y,
                  transform: 'translate(-50%, -50%)',
                  color: source.active ? source.color : 'hsl(var(--muted-foreground))',
                }}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: source.angle / 360 }}
              >
                <span className="mr-1">{source.icon}</span>
                <span className="hidden sm:inline">{source.name}</span>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Center Label */}
      <div
        className="absolute text-center pointer-events-none"
        style={{
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      >
        <motion.div
          className="text-[10px] font-bold text-foreground/80 mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          TAJINE
        </motion.div>
      </div>

      {/* Stats Overlay */}
      <div className="absolute bottom-2 left-2 right-2 flex justify-between text-[10px] text-foreground/60">
        <span>{activeConnections} sources actives</span>
        <span>{totalProcessed.toLocaleString()} requêtes</span>
      </div>
    </div>
  );
});

export default IntelligenceHub;
