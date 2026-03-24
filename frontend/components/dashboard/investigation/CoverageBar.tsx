'use client';

import { cn } from '@/lib/utils';
import type { CoverageScore } from '@/types/relations';

interface CoverageBarProps {
  coverage: CoverageScore | null;
  isLoading?: boolean;
}

export default function CoverageBar({ coverage, isLoading }: CoverageBarProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card/50 p-4 animate-pulse">
        <div className="h-4 bg-muted/30 rounded w-1/3 mb-2" />
        <div className="h-6 bg-muted/30 rounded" />
      </div>
    );
  }

  if (!coverage || coverage.total_relations === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card/50 p-4 text-muted-foreground text-sm text-center">
        Aucune relation detectee  -  lancez une decouverte pour commencer
      </div>
    );
  }

  const scoreColor = coverage.coverage_score >= 0.7
    ? 'text-emerald-400'
    : coverage.coverage_score >= 0.4
      ? 'text-amber-400'
      : 'text-red-400';

  return (
    <div className="rounded-xl border border-border/50 bg-card/50 p-4">
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium">
          Couverture relationnelle
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-muted-foreground/60">
            {coverage.total_relations} relations
          </span>
          <span className={cn('text-sm font-mono font-bold', scoreColor)}>
            {Math.round(coverage.coverage_score * 100)}%
          </span>
        </div>
      </div>

      {/* Segmented bar */}
      <div className="w-full h-3 rounded-full overflow-hidden flex bg-muted/20">
        {coverage.structural_pct > 0 && (
          <div
            className="h-full bg-emerald-500/80 transition-all duration-700 ease-out"
            style={{ width: `${coverage.structural_pct}%` }}
            title={`L1 Structurel: ${coverage.structural_count} (${coverage.structural_pct}%)`}
          />
        )}
        {coverage.inferred_pct > 0 && (
          <div
            className="h-full bg-amber-500/80 transition-all duration-700 ease-out"
            style={{ width: `${coverage.inferred_pct}%` }}
            title={`L2 Infere: ${coverage.inferred_count} (${coverage.inferred_pct}%)`}
          />
        )}
        {coverage.hypothetical_pct > 0 && (
          <div
            className="h-full bg-red-500/50 transition-all duration-700 ease-out"
            style={{ width: `${coverage.hypothetical_pct}%` }}
            title={`L3 Hypothetique: ${coverage.hypothetical_count} (${coverage.hypothetical_pct}%)`}
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2.5 text-[11px] text-muted-foreground/60">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500/80" />
          L1 Structurel
          <span className="font-mono">{coverage.structural_count}</span>
          <span className="text-muted-foreground/40">({coverage.structural_pct}%)</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-500/80" />
          L2 Infere
          <span className="font-mono">{coverage.inferred_count}</span>
          <span className="text-muted-foreground/40">({coverage.inferred_pct}%)</span>
        </span>
        {coverage.hypothetical_count > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500/50" />
            L3 Hypothetique
            <span className="font-mono">{coverage.hypothetical_count}</span>
          </span>
        )}
      </div>
    </div>
  );
}
