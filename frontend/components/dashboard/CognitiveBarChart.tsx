'use client';

import { useEffect, useState } from 'react';
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardDescription, GlassCardContent } from '@/components/ui/glass-card';
import { HiOutlineCpuChip } from 'react-icons/hi2';
import { AnimatedCounter } from '@/components/ui/animated-counter';

interface CognitiveLevelData {
  level: string;
  count: number;
  color: string;
}

interface CognitiveBarChartProps {
  data?: CognitiveLevelData[];
  maxValue?: number;
  animated?: boolean;
}

// Default data with Nord Aurora colors
const defaultData: CognitiveLevelData[] = [
  { level: 'Reactif', count: 45, color: 'var(--info)' },      // nord9
  { level: 'Analytique', count: 32, color: 'var(--chart-2)' },   // nord8
  { level: 'Strategique', count: 18, color: 'var(--chart-4)' },  // nord7
  { level: 'Prospectif', count: 4, color: 'var(--success)' },    // nord14
  { level: 'Theorique', count: 1, color: 'var(--chart-3)' },     // nord15
];

export function CognitiveBarChart({ data = defaultData, maxValue, animated = true }: CognitiveBarChartProps) {
  const [isVisible, setIsVisible] = useState(!animated);
  const max = maxValue || Math.max(...data.map(d => d.count));
  const total = data.reduce((sum, d) => sum + d.count, 0);

  // Trigger animation on mount
  useEffect(() => {
    if (animated) {
      const timer = setTimeout(() => setIsVisible(true), 100);
      return () => clearTimeout(timer);
    }
  }, [animated]);

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineCpuChip className="h-5 w-5 text-primary" />
          Distribution Cognitive
        </GlassCardTitle>
        <GlassCardDescription>
          Repartition des analyses par niveau cognitif
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="space-y-4">
          {data.map((item, index) => {
            const percentage = max > 0 ? (item.count / max) * 100 : 0;
            const pct = total > 0 ? ((item.count / total) * 100).toFixed(0) : 0;
            const delay = index * 100; // Stagger animation

            return (
              <div
                key={index}
                className="space-y-1"
                style={{
                  opacity: isVisible ? 1 : 0,
                  transform: isVisible ? 'translateX(0)' : 'translateX(-10px)',
                  transition: `all 0.4s ease-out ${delay}ms`,
                }}
              >
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{item.level}</span>
                  <span className="text-muted-foreground">
                    {animated ? (
                      <AnimatedCounter value={item.count} duration={800 + delay} />
                    ) : (
                      item.count
                    )} ({pct}%)
                  </span>
                </div>
                <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: isVisible ? `${percentage}%` : '0%',
                      backgroundColor: item.color,
                      boxShadow: isVisible ? `0 0 8px ${item.color}40` : 'none',
                      transition: `all 0.6s cubic-bezier(0.4, 0, 0.2, 1) ${delay + 200}ms`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Total */}
        <div
          className="mt-4 pt-4 border-t border-border/50"
          style={{
            opacity: isVisible ? 1 : 0,
            transition: 'opacity 0.4s ease-out 600ms',
          }}
        >
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Total analyses</span>
            <span className="font-bold text-primary">
              {animated ? (
                <AnimatedCounter value={total} duration={1200} />
              ) : (
                total
              )}
            </span>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
