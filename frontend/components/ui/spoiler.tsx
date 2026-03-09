'use client';

import { cn } from '@/lib/utils';

interface SpoilerProps {
  children: string;
  revealed?: boolean;
  className?: string;
}

export function Spoiler({
  children,
  revealed = false,
  className,
}: SpoilerProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden transition-all duration-700 cursor-pointer',
        !revealed && 'blur-sm select-none',
        className
      )}
    >
      {!revealed && (
        <div className="absolute inset-0 bg-gradient-to-r from-muted/80 via-muted/40 to-muted/80 animate-shimmer" />
      )}
      <span className={cn(!revealed && 'opacity-30')}>{children}</span>
    </div>
  );
}

/**
 * Animation de "pensee" magique
 * Orbe central pulsant + anneaux concentriques + particules orbitales
 */
export function ThinkingAnimation({
  text = 'Analyse en cours...',
  className,
}: {
  text?: string;
  className?: string;
}) {
  return (
    <div className={cn('flex items-start gap-4', className)}>
      {/* Magic orb with concentric rings */}
      <div className="relative w-10 h-10 flex-shrink-0">
        {/* Outer pulse rings */}
        <div className="absolute inset-0 rounded-full border border-primary/20 animate-ring-expand" />
        <div className="absolute inset-0 rounded-full border border-primary/15 animate-ring-expand" style={{ animationDelay: '700ms' }} />
        <div className="absolute inset-0 rounded-full border border-primary/10 animate-ring-expand" style={{ animationDelay: '1400ms' }} />

        {/* Core orb */}
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-primary/30 to-primary/10 animate-orb-breathe">
          <div className="absolute inset-0 rounded-full bg-primary/20 blur-sm" />
        </div>

        {/* Orbiting particles */}
        <div className="absolute inset-0 animate-orbit-slow">
          <span className="absolute top-0 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary/80" />
        </div>
        <div className="absolute inset-0 animate-orbit-medium">
          <span className="absolute bottom-0 right-0 w-1 h-1 rounded-full bg-primary/60" />
        </div>
        <div className="absolute inset-0 animate-orbit-fast">
          <span className="absolute top-1/2 left-0 w-0.5 h-0.5 rounded-full bg-primary/50" />
        </div>
      </div>

      {/* Text + shimmer bars */}
      <div className="flex-1 pt-1">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-medium text-foreground/80">{text}</span>
          <span className="flex items-center gap-0.5">
            <span className="h-1 w-1 rounded-full bg-primary animate-thinking-dot" />
            <span className="h-1 w-1 rounded-full bg-primary animate-thinking-dot" style={{ animationDelay: '200ms' }} />
            <span className="h-1 w-1 rounded-full bg-primary animate-thinking-dot" style={{ animationDelay: '400ms' }} />
          </span>
        </div>

        {/* Shimmer skeleton bars */}
        <div className="flex flex-col gap-2">
          <div className="h-2.5 rounded-full bg-muted/40 overflow-hidden w-[90%]">
            <div className="h-full w-full thinking-shimmer" />
          </div>
          <div className="h-2.5 rounded-full bg-muted/40 overflow-hidden w-[70%]">
            <div className="h-full w-full thinking-shimmer" style={{ animationDelay: '300ms' }} />
          </div>
          <div className="h-2.5 rounded-full bg-muted/40 overflow-hidden w-[50%]">
            <div className="h-full w-full thinking-shimmer" style={{ animationDelay: '600ms' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export const SpoilerFallback = Spoiler;
