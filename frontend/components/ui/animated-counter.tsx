'use client';

import { useEffect, useRef, useState } from 'react';

interface AnimatedCounterProps {
  value: number | string;
  duration?: number;
  className?: string;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}

// Easing function for smooth deceleration
function easeOutQuart(t: number): number {
  return 1 - Math.pow(1 - t, 4);
}

export function AnimatedCounter({
  value,
  duration = 1000,
  className = '',
  prefix = '',
  suffix = '',
  decimals = 0,
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState('0');
  const startTimeRef = useRef<number | null>(null);
  const startValueRef = useRef<number>(0);
  const frameRef = useRef<number | null>(null);
  const currentValueRef = useRef<number>(0);

  // Parse the target value (handles strings like "12.4M")
  const parseValue = (val: number | string): { num: number; suffix: string } => {
    if (typeof val === 'number') {
      return { num: val, suffix: '' };
    }
    const match = val.match(/^([\d.]+)(.*)$/);
    if (match) {
      return { num: parseFloat(match[1]), suffix: match[2] };
    }
    return { num: 0, suffix: val };
  };

  const { num: targetValue, suffix: valueSuffix } = parseValue(value);

  useEffect(() => {
    const animate = (timestamp: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeOutQuart(progress);

      const currentValue = startValueRef.current + (targetValue - startValueRef.current) * easedProgress;
      currentValueRef.current = currentValue;

      if (decimals > 0) {
        setDisplayValue(currentValue.toFixed(decimals));
      } else {
        setDisplayValue(Math.round(currentValue).toString());
      }

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        // Ensure we end at the exact target value
        currentValueRef.current = targetValue;
        setDisplayValue(decimals > 0 ? targetValue.toFixed(decimals) : targetValue.toString());
      }
    };

    // Reset animation - use ref to avoid re-triggering effect
    startTimeRef.current = null;
    startValueRef.current = currentValueRef.current;
    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [targetValue, duration, decimals]);

  return (
    <span className={className}>
      {prefix}{displayValue}{valueSuffix}{suffix}
    </span>
  );
}

// Sparkline component for showing trends
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

export function Sparkline({
  data,
  width = 80,
  height = 24,
  color = 'currentColor',
  className = '',
}: SparklineProps) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  // Generate SVG path
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  });

  const pathD = `M${points.join(' L')}`;

  // Area path for gradient fill
  const areaD = `${pathD} L${width},${height} L0,${height} Z`;

  return (
    <svg width={width} height={height} className={className}>
      <defs>
        <linearGradient id="sparkline-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d={areaD}
        fill="url(#sparkline-gradient)"
      />
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Status indicator with pulse animation
interface StatusDotProps {
  status: 'online' | 'offline' | 'degraded' | 'loading';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const STATUS_COLORS = {
  online: 'bg-[var(--success)]',
  degraded: 'bg-[var(--warning)]',
  offline: 'bg-[var(--error)]',
  loading: 'bg-[var(--info)]',
};

const SIZE_CLASSES = {
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
};

export function StatusDot({ status, size = 'md', className = '' }: StatusDotProps) {
  const shouldPulse = status === 'online' || status === 'loading';

  return (
    <div className={`relative ${SIZE_CLASSES[size]} ${className}`}>
      <div className={`absolute inset-0 rounded-full ${STATUS_COLORS[status]} ${shouldPulse ? 'animate-pulse-dot' : ''}`} />
      {shouldPulse && (
        <div className={`absolute inset-0 rounded-full ${STATUS_COLORS[status]} animate-ping opacity-75`} />
      )}
    </div>
  );
}
