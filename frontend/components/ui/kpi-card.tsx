import type { ComponentType } from 'react';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  title: string;
  value: string | number;
  icon: ComponentType<{ className?: string }>;
  trend?: { value: number; label?: string };
  className?: string;
}

export function KpiCard({ title, value, icon: Icon, trend, className }: KpiCardProps) {
  return (
    <div className={cn(
      'flex items-center gap-4 p-4 rounded-xl bg-card border border-border transition-colors hover:border-zinc-700 dark:hover:border-zinc-600',
      className
    )}>
      <div className="p-2.5 rounded-lg bg-primary/10 text-primary shrink-0">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold truncate">{value}</p>
        <p className="text-xs text-muted-foreground truncate">{title}</p>
        {trend && (
          <p className={cn(
            'text-xs font-medium mt-0.5',
            trend.value >= 0 ? 'text-[var(--success)]' : 'text-[var(--error)]'
          )}>
            {trend.value >= 0 ? '+' : ''}{trend.value}%{trend.label ? ` ${trend.label}` : ''}
          </p>
        )}
      </div>
    </div>
  );
}
