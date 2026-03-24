'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

/**
 * ReasoningDisplay - Claude-style AI reasoning indicator
 *
 * Design:
 * - Amber pulsing orb (#EBCB8B)
 * - PPDSL progress bars with Nord theme colors
 * - Sources summary display
 */

export type ReasoningStep = {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'done';
};

export interface ReasoningDisplayProps {
  steps: ReasoningStep[];
  progress: number; // 0-100
  currentMessage?: string;
  sources?: { name: string; count: number }[];
  className?: string;
}

// PPDSL phases with Nord theme colors
const PPDSL_COLORS: Record<string, string> = {
  perceive: 'var(--info)',
  plan: 'var(--chart-2)',
  delegate: 'var(--chart-4)',
  synthesize: 'var(--success)',
  learn: 'var(--chart-3)',
};

// Amber orb component
function AmberOrb({ isActive = true }: { isActive?: boolean }) {
  return (
    <div className="relative flex items-center justify-center w-10 h-10">
      {/* Glow effect */}
      <motion.div
        className="absolute inset-0 rounded-full bg-warning/30 blur-md"
        animate={isActive ? {
          scale: [1, 1.2, 1],
          opacity: [0.5, 0.8, 0.5],
        } : {}}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
      {/* Core orb */}
      <motion.div
        className="relative z-10 w-6 h-6 rounded-full bg-gradient-to-br from-warning to-[var(--chart-5)]"
        animate={isActive ? {
          scale: [0.95, 1.05, 0.95],
        } : {}}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        {/* Inner highlight */}
        <div className="absolute top-1 left-1.5 w-2 h-2 rounded-full bg-white/40" />
      </motion.div>
    </div>
  );
}

// Progress bar component
function ProgressBar({
  step,
  color,
}: {
  step: ReasoningStep;
  color: string;
}) {
  const widthMap = {
    pending: '0%',
    active: '60%',
    done: '100%',
  };

  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-24 text-muted-foreground uppercase tracking-wide">
        {step.label}
      </span>
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: '0%' }}
          animate={{ width: widthMap[step.status] }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span className="w-16 text-right text-muted-foreground text-[10px]">
        {step.status === 'done'
          ? 'Termine'
          : step.status === 'active'
          ? 'En cours'
          : 'En attente'}
      </span>
    </div>
  );
}

export function ReasoningDisplay({
  steps,
  progress,
  currentMessage,
  sources,
  className,
}: ReasoningDisplayProps) {
  return (
    <div
      className={cn(
        'p-4 rounded-xl border border-border bg-card',
        className
      )}
    >
      {/* Header with amber orb */}
      <div className="flex items-center gap-3 mb-4">
        <AmberOrb isActive={progress < 100} />
        <div>
          <p className="font-medium text-foreground">
            {progress < 100 ? 'Analyse en cours' : 'Analyse terminee'}
          </p>
          {currentMessage && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {currentMessage}
            </p>
          )}
        </div>
      </div>

      {/* PPDSL Progress bars */}
      <div className="space-y-2">
        {steps.map((step) => (
          <ProgressBar
            key={step.id}
            step={step}
            color={PPDSL_COLORS[step.id] || 'var(--success)'}
          />
        ))}
      </div>

      {/* Sources summary */}
      {sources && sources.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/50">
          <p className="text-xs text-muted-foreground">
            <span className="text-foreground font-medium">Sources: </span>
            {sources.map((s, i) => (
              <span key={s.name}>
                {s.name} ({s.count})
                {i < sources.length - 1 && ', '}
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  );
}

// Compact version for inline use
export function ReasoningIndicator({
  phase,
  message,
}: {
  phase: string;
  message?: string;
}) {
  const color = PPDSL_COLORS[phase] || 'var(--success)';

  return (
    <div className="flex items-center gap-2 text-xs">
      {/* Mini amber dot */}
      <motion.div
        className="w-2 h-2 rounded-full bg-warning"
        animate={{
          scale: [0.95, 1.1, 0.95],
          opacity: [0.7, 1, 0.7],
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />
      {/* Phase indicator */}
      <span
        className="px-2 py-0.5 rounded text-[10px] font-medium uppercase"
        style={{ backgroundColor: `${color}20`, color }}
      >
        {phase}
      </span>
      {message && (
        <span className="text-muted-foreground">{message}</span>
      )}
    </div>
  );
}

export default ReasoningDisplay;
