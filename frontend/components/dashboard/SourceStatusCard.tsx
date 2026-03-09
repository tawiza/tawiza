'use client';

import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardDescription
} from '@/components/ui/glass-card';
import { Sparkline } from '@/components/ui/sparkline';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface SourceStatusCardProps {
  name: string;
  description: string;
  status: 'online' | 'offline' | 'degraded';
  latency: number; // ms
  latencyHistory: number[];
  requests24h: number;
  requestHistory: number[];
  successRate: number; // percentage
  lastSync: string;
  icon: React.ReactNode;
}

export function SourceStatusCard({
  name,
  description,
  status,
  latency,
  latencyHistory,
  requests24h,
  requestHistory,
  successRate,
  lastSync,
  icon
}: SourceStatusCardProps) {
  const statusConfig = {
    online: {
      label: 'En ligne',
      color: 'bg-[var(--success)]',
      glow: 'glow-green' as const,
      textColor: 'text-[var(--success)]'
    },
    offline: {
      label: 'Hors ligne',
      color: 'bg-[var(--error)]',
      glow: 'glow-red' as const,
      textColor: 'text-[var(--error)]'
    },
    degraded: {
      label: 'Degrade',
      color: 'bg-[var(--warning)]',
      glow: '' as const,
      textColor: 'text-[var(--warning)]'
    }
  };

  const config = statusConfig[status];
  const glowClass = status === 'online' ? 'green' : status === 'offline' ? 'red' : 'none';

  return (
    <GlassCard glow={glowClass} hoverGlow>
      <GlassCardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-primary">{icon}</div>
            <div>
              <GlassCardTitle className="text-lg">{name}</GlassCardTitle>
              <GlassCardDescription>{description}</GlassCardDescription>
            </div>
          </div>
          <Badge
            className={cn(
              'font-medium',
              status === 'online' && 'bg-[var(--success)]/20 text-[var(--success)] border-[var(--success)]/30',
              status === 'offline' && 'bg-[var(--error)]/20 text-[var(--error)] border-[var(--error)]/30',
              status === 'degraded' && 'bg-[var(--warning)]/20 text-[var(--warning)] border-[var(--warning)]/30'
            )}
          >
            <span className={cn(
              'w-2 h-2 rounded-full mr-2',
              config.color,
              status === 'online' && 'animate-pulse-dot'
            )} />
            {config.label}
          </Badge>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Latency */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Latence</span>
              <span className="font-medium">{latency}ms</span>
            </div>
            <Sparkline
              data={latencyHistory}
              width={120}
              height={24}
              color="hsl(var(--primary))"
              showArea
            />
          </div>

          {/* Requests */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Requetes/24h</span>
              <span className="font-medium">{requests24h.toLocaleString()}</span>
            </div>
            <Sparkline
              data={requestHistory}
              width={120}
              height={24}
              color="hsl(var(--accent))"
              showArea
            />
          </div>
        </div>

        {/* Success rate */}
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Taux de succes</span>
            <span className={cn(
              'font-medium',
              successRate >= 95 ? 'text-[var(--success)]' :
              successRate >= 80 ? 'text-[var(--warning)]' : 'text-[var(--error)]'
            )}>
              {successRate}%
            </span>
          </div>
          <Progress
            value={successRate}
            className="h-2"
          />
        </div>

        {/* Last sync */}
        <div className="mt-4 pt-3 border-t border-border/50">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Derniere sync</span>
            <span className="text-muted-foreground">{lastSync}</span>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
