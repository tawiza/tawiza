'use client';

import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface ChartWrapperProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export function ChartWrapper({ title, subtitle, children, className }: ChartWrapperProps) {
  return (
    <div className={cn(
      'rounded-xl bg-card border border-border p-5 transition-colors hover:border-zinc-700 dark:hover:border-zinc-600',
      className
    )}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold">{title}</h3>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function useChartTheme() {
  return {
    text: 'hsl(var(--muted-foreground))',
    grid: 'hsl(var(--border))',
    tooltip: {
      bg: 'hsl(var(--card))',
      border: 'hsl(var(--border))',
      text: 'hsl(var(--foreground))',
    },
    series: [
      'hsl(var(--primary))',
      'hsl(var(--chart-2, 160 60% 45%))',
      'hsl(var(--chart-3, 30 80% 55%))',
      'hsl(var(--chart-4, 280 65% 60%))',
      'hsl(var(--chart-5, 340 75% 55%))',
    ],
  };
}
