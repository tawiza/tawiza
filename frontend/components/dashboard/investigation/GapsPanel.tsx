'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  HiExclamationTriangle,
  HiCircleStack,
  HiCpuChip,
  HiLink,
  HiChevronDown,
  HiShieldCheck,
  HiEye,
  HiBeaker,
} from 'react-icons/hi2';
import type { GapsReport, AlgorithmicHonestyItem } from '@/types/relations';

interface GapsPanelProps {
  gaps: GapsReport | null;
  isLoading?: boolean;
}

const gapIcons: Record<string, typeof HiExclamationTriangle> = {
  missing_source: HiCircleStack,
  missing_model: HiCpuChip,
  low_coverage: HiEye,
  stale_data: HiExclamationTriangle,
};

const priorityColors: Record<string, string> = {
  high: 'text-red-400 bg-red-500/10 border-red-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  low: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
};

const relationTypeColors: Record<string, string> = {
  structural: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  inferred: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  hypothetical: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const subtypeLabels: Record<string, string> = {
  headquarter_in: 'Siege social',
  belongs_to_sector: 'Secteur NAF',
  sector_present_in: 'Secteur present',
  sector_dominance: 'Concentration sectorielle',
  employment_anchor: 'Ancre emploi',
  cluster_member: 'Cluster geographique',
  event_creation: 'Creation',
  event_vente: 'Cession',
  event_liquidation: 'Liquidation',
  event_redressement: 'Redressement',
  event_procedure_collective: 'Procedure collective',
  event_radiation: 'Radiation',
  event_cloture_insuffisance: 'Cloture insuffisance',
  event_plan_cession: 'Plan de cession',
  event_plan_continuation: 'Plan de continuation',
};

export default function GapsPanel({ gaps, isLoading }: GapsPanelProps) {
  const [honestyExpanded, setHonestyExpanded] = useState(false);

  if (isLoading || !gaps) return null;

  const honesty = gaps.algorithmic_honesty || [];
  const structuralItems = honesty.filter(h => h.relation_type === 'structural');
  const inferredItems = honesty.filter(h => h.relation_type === 'inferred');

  return (
    <div className="space-y-3">
      {/* Gaps list */}
      <div className="rounded-xl border border-border/50 bg-card/50 p-4">
        <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-3 flex items-center gap-2">
          <HiExclamationTriangle className="h-3.5 w-3.5 text-amber-400" />
          Ce qu&apos;on ne sait pas encore ({gaps.total_gaps} lacunes)
        </h4>
        <div className="space-y-2">
          {gaps.gaps.map((gap, i) => {
            const Icon = gapIcons[gap.gap_type] || HiExclamationTriangle;
            return (
              <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-muted/20 border border-border/20">
                <Icon className="h-3.5 w-3.5 text-muted-foreground/60 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-foreground/80 leading-relaxed">{gap.description}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded border font-medium',
                      priorityColors[gap.priority]
                    )}>
                      {gap.priority}
                    </span>
                    <span className="text-[10px] text-muted-foreground/50">
                      Source potentielle : {gap.potential_source}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Capability matrix */}
      <div className="rounded-xl border border-border/50 bg-card/50 p-4">
        <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-3 flex items-center gap-2">
          <HiBeaker className="h-3.5 w-3.5 text-primary" />
          Matrice de capacite algorithmique
        </h4>
        <div className="space-y-1.5">
          {gaps.capability_matrix.map((cap, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[12px] text-foreground/70 w-44 shrink-0 truncate" title={cap.capability}>
                {cap.capability}
              </span>
              <div className="flex-1 h-2 rounded-full bg-muted/30 overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    cap.level >= 5 ? 'bg-emerald-500/80' :
                    cap.level >= 3 ? 'bg-amber-500/80' :
                    cap.level >= 1 ? 'bg-red-500/60' :
                    'bg-muted-foreground/10'
                  )}
                  style={{ width: `${(cap.level / 8) * 100}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-muted-foreground/50 w-5 text-right">
                {cap.level}
              </span>
              {cap.source && (
                <span className="text-[9px] text-muted-foreground/40 w-20 shrink-0 truncate text-right" title={cap.source}>
                  {cap.source}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Algorithmic honesty table */}
      {honesty.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-card/50 p-4">
          <button
            onClick={() => setHonestyExpanded(!honestyExpanded)}
            className="w-full flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground font-medium"
          >
            <HiShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            <span>Honnetete algorithmique ({honesty.length} types de relations)</span>
            <HiChevronDown className={cn(
              'h-3.5 w-3.5 ml-auto transition-transform duration-200',
              honestyExpanded && 'rotate-180'
            )} />
          </button>

          {honestyExpanded && (
            <div className="mt-3 space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* Structural relations */}
              {structuralItems.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                      L1 — Structurelles ({structuralItems.reduce((s, h) => s + h.count, 0)})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {structuralItems.map((item, i) => (
                      <HonestyRow key={i} item={item} />
                    ))}
                  </div>
                </div>
              )}

              {/* Inferred relations */}
              {inferredItems.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-2 w-2 rounded-full bg-amber-500" />
                    <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">
                      L2 — Inferees ({inferredItems.reduce((s, h) => s + h.count, 0)})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {inferredItems.map((item, i) => (
                      <HonestyRow key={i} item={item} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HonestyRow({ item }: { item: AlgorithmicHonestyItem }) {
  const [expanded, setExpanded] = useState(false);
  const label = subtypeLabels[item.relation_subtype] || item.relation_subtype;

  return (
    <div className="rounded-lg border border-border/20 bg-muted/10 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/20 transition-colors"
      >
        <span className="text-[12px] font-medium text-foreground/80 flex-1">
          {label}
        </span>
        <span className="text-[10px] font-mono text-muted-foreground/60">
          {item.count}x
        </span>
        {/* Confidence bar */}
        <div className="w-16 h-1.5 rounded-full bg-muted/30 overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full',
              item.avg_confidence >= 0.8 ? 'bg-emerald-500' :
              item.avg_confidence >= 0.5 ? 'bg-amber-500' :
              'bg-red-500'
            )}
            style={{ width: `${item.avg_confidence * 100}%` }}
          />
        </div>
        <span className="text-[10px] font-mono text-muted-foreground/50 w-10 text-right">
          {Math.round(item.avg_confidence * 100)}%
        </span>
        <HiChevronDown className={cn(
          'h-3 w-3 text-muted-foreground/40 transition-transform duration-200',
          expanded && 'rotate-180'
        )} />
      </button>

      {expanded && (
        <div className="px-3 pb-2.5 space-y-1.5 border-t border-border/10 pt-2 animate-in fade-in duration-150">
          <div className="flex items-start gap-1.5">
            <span className="text-[10px] text-muted-foreground/50 w-20 shrink-0 pt-0.5">Methode</span>
            <span className="text-[11px] text-foreground/70">{item.method}</span>
          </div>
          <div className="flex items-start gap-1.5">
            <span className="text-[10px] text-muted-foreground/50 w-20 shrink-0 pt-0.5">Limitation</span>
            <span className="text-[11px] text-amber-400/80">{item.limitation}</span>
          </div>
          <div className="flex items-start gap-1.5">
            <span className="text-[10px] text-muted-foreground/50 w-20 shrink-0 pt-0.5">Source</span>
            <span className="text-[11px] text-foreground/60">{item.data_source}</span>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-muted-foreground/40">
              Confiance: {Math.round(item.min_confidence * 100)}% — {Math.round(item.max_confidence * 100)}%
            </span>
            <span className={cn(
              'text-[9px] px-1.5 py-0.5 rounded border font-medium',
              relationTypeColors[item.relation_type]
            )}>
              {item.relation_type === 'structural' ? 'L1' : item.relation_type === 'inferred' ? 'L2' : 'L3'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
