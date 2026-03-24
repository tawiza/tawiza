'use client';

import React, { useState, useEffect, memo } from 'react';
import { motion, useSpring, useMotionValueEvent } from 'framer-motion';
import {
  HiOutlineBuildingOffice2,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineCpuChip,
  HiOutlineBolt,
  HiOutlineChartBar,
  HiOutlineUserGroup,
} from 'react-icons/hi2';

/**
 * AnimatedNumber - Smooth counting animation with spring physics
 */
const AnimatedNumber = memo(function AnimatedNumber({
  value,
  format = 'number',
  prefix = '',
  suffix = '',
  className = '',
}: {
  value: number;
  format?: 'number' | 'compact' | 'percent';
  prefix?: string;
  suffix?: string;
  className?: string;
}) {
  const spring = useSpring(0, { stiffness: 50, damping: 15 });
  const [display, setDisplay] = useState('0');

  const formatNumber = (current: number) => {
    if (format === 'compact') {
      if (current >= 1000000) return `${(current / 1000000).toFixed(1)}M`;
      if (current >= 1000) return `${(current / 1000).toFixed(1)}K`;
    }
    if (format === 'percent') return `${Math.round(current)}%`;
    return Math.round(current).toLocaleString('fr-FR');
  };

  useMotionValueEvent(spring, 'change', (current) => {
    setDisplay(formatNumber(current));
  });

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return (
    <motion.span className={className}>
      {prefix}
      {display}
      {suffix}
    </motion.span>
  );
});

interface StatItem {
  label: string;
  value: number;
  format?: 'number' | 'compact' | 'percent';
  suffix?: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  color: string;
  trend?: { value: number; isUp: boolean };
}

interface HeroStatsProps {
  className?: string;
  stats?: StatItem[];
}

const DEFAULT_STATS: StatItem[] = [
  {
    label: 'Entreprises analysées',
    value: 2847593,
    format: 'compact',
    icon: HiOutlineBuildingOffice2,
    color: 'var(--error)',
    trend: { value: 12.5, isUp: true },
  },
  {
    label: 'Territoires couverts',
    value: 101,
    icon: HiOutlineGlobeEuropeAfrica,
    color: 'var(--chart-4)',
  },
  {
    label: 'Requêtes TAJINE',
    value: 15847,
    format: 'compact',
    icon: HiOutlineCpuChip,
    color: 'var(--warning)',
    trend: { value: 23.8, isUp: true },
  },
  {
    label: 'Temps réponse moyen',
    value: 2.4,
    suffix: 's',
    icon: HiOutlineBolt,
    color: 'var(--success)',
  },
  {
    label: 'Précision analyse',
    value: 94,
    format: 'percent',
    icon: HiOutlineChartBar,
    color: 'var(--error)',
    trend: { value: 2.1, isUp: true },
  },
  {
    label: 'Utilisateurs actifs',
    value: 342,
    icon: HiOutlineUserGroup,
    color: 'var(--chart-3)',
  },
];

const HeroStats = memo(function HeroStats({
  className = '',
  stats = DEFAULT_STATS,
}: HeroStatsProps) {
  const [mounted, setMounted] = useState(false);
  const [liveStats, setLiveStats] = useState(stats);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Simulate live updates
  useEffect(() => {
    const interval = setInterval(() => {
      setLiveStats((prev) =>
        prev.map((stat) => {
          if (stat.label.includes('Requêtes')) {
            return { ...stat, value: stat.value + Math.floor(Math.random() * 5) };
          }
          if (stat.label.includes('Entreprises')) {
            return { ...stat, value: stat.value + Math.floor(Math.random() * 100) };
          }
          return stat;
        })
      );
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`w-full ${className}`}>
      {/* Gradient background */}
      <div className="relative overflow-hidden rounded-2xl">
        {/* Animated gradient background */}
        <div
          className="absolute inset-0 opacity-90"
          style={{
            background: `linear-gradient(135deg,
              rgba(255, 107, 74, 0.15) 0%,
              rgba(78, 205, 196, 0.1) 50%,
              rgba(170, 150, 218, 0.15) 100%)`,
          }}
        />

        {/* Grid pattern overlay */}
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
          }}
        />

        {/* Floating orbs */}
        <motion.div
          className="absolute w-64 h-64 rounded-full opacity-20"
          style={{
            background: 'radial-gradient(circle, rgba(255,107,74,0.4) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
          animate={{
            x: [0, 50, 0],
            y: [0, 30, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        <motion.div
          className="absolute right-0 bottom-0 w-48 h-48 rounded-full opacity-20"
          style={{
            background: 'radial-gradient(circle, rgba(78,205,196,0.4) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
          animate={{
            x: [0, -30, 0],
            y: [0, -20, 0],
          }}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />

        {/* Stats grid */}
        <div className="relative z-10 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 p-6">
          {liveStats.map((stat, index) => (
            <motion.div
              key={stat.label}
              className="flex flex-col items-center text-center p-4 rounded-xl bg-card border border-border hover:bg-muted transition-all"
              initial={{ opacity: 0, y: 20 }}
              animate={mounted ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: index * 0.1 }}
              whileHover={{ scale: 1.02, y: -2 }}
            >
              {/* Icon */}
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                style={{ backgroundColor: `${stat.color}20` }}
              >
                <stat.icon className="w-5 h-5" style={{ color: stat.color }} />
              </div>

              {/* Value */}
              <div className="text-2xl md:text-3xl font-bold text-foreground mb-1">
                {mounted ? (
                  <AnimatedNumber
                    value={stat.value}
                    format={stat.format}
                    suffix={stat.suffix || ''}
                  />
                ) : (
                  '...'
                )}
              </div>

              {/* Label */}
              <div className="text-xs text-foreground/60 mb-1">{stat.label}</div>

              {/* Trend */}
              {stat.trend && (
                <div
                  className={`text-xs flex items-center gap-1 ${
                    stat.trend.isUp ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  <span>{stat.trend.isUp ? '↑' : '↓'}</span>
                  <span>{stat.trend.value}%</span>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Live indicator */}
        <div className="absolute top-4 right-4 flex items-center gap-2 text-xs text-foreground/60">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
          </span>
          <span>LIVE</span>
        </div>
      </div>
    </div>
  );
});

export default HeroStats;
