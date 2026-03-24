'use client';

import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import {
  Loader2,
  TrendingUp,
  Building2,
  Landmark,
  GraduationCap,
  Briefcase,
  MapPin,
  Layers,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import type { EcosystemScore, EcosystemDimension } from '@/types/relations';

interface EcosystemScorePanelProps {
  data: EcosystemScore | null;
  isLoading: boolean;
}

/* -- Helpers ----------------------------------------------------------- */

const DIMENSION_ICONS: Record<string, typeof TrendingUp> = {
  tissu_economique: Building2,
  structures_support: Layers,
  maillage_institutionnel: Landmark,
  formation_recherche: GraduationCap,
  emploi_competences: Briefcase,
  foncier_infrastructure: MapPin,
};

const DIMENSION_COLORS: Record<string, string> = {
  tissu_economique: 'from-sky-500 to-sky-400',
  structures_support: 'from-violet-500 to-violet-400',
  maillage_institutionnel: 'from-amber-500 to-amber-400',
  formation_recherche: 'from-blue-500 to-blue-400',
  emploi_competences: 'from-rose-500 to-rose-400',
  foncier_infrastructure: 'from-emerald-500 to-emerald-400',
};

const DIMENSION_BG_COLORS: Record<string, string> = {
  tissu_economique: 'bg-sky-500/10 border-sky-500/20',
  structures_support: 'bg-violet-500/10 border-violet-500/20',
  maillage_institutionnel: 'bg-amber-500/10 border-amber-500/20',
  formation_recherche: 'bg-blue-500/10 border-blue-500/20',
  emploi_competences: 'bg-rose-500/10 border-rose-500/20',
  foncier_infrastructure: 'bg-emerald-500/10 border-emerald-500/20',
};

function overallScoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-400';
  if (score >= 40) return 'text-amber-400';
  return 'text-red-400';
}

function overallScoreGradient(score: number): string {
  if (score >= 70) return 'from-emerald-500 to-emerald-400';
  if (score >= 40) return 'from-amber-500 to-amber-400';
  return 'from-red-500 to-red-400';
}

function overallScoreBg(score: number): string {
  if (score >= 70) return 'bg-emerald-500/10 border-emerald-500/30';
  if (score >= 40) return 'bg-amber-500/10 border-amber-500/30';
  return 'bg-red-500/10 border-red-500/30';
}

function dimensionBarColor(score: number): string {
  if (score >= 70) return 'bg-emerald-500/80';
  if (score >= 40) return 'bg-amber-500/80';
  return 'bg-red-500/60';
}

function scoreLabel(score: number): string {
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Bon';
  if (score >= 40) return 'Moyen';
  if (score >= 20) return 'Faible';
  return 'Critique';
}

/* -- Circular gauge (SVG) ---------------------------------------------- */

function CircularGauge({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const fillPct = Math.min(score / 100, 1);
  const strokeDashoffset = circumference * (1 - fillPct);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={8}
          className="text-muted/20"
        />
        {/* Filled arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className={cn(
            'transition-all duration-1000 ease-out',
            score >= 70 ? 'stroke-emerald-500' : score >= 40 ? 'stroke-amber-500' : 'stroke-red-500',
          )}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('text-2xl font-bold tabular-nums', overallScoreColor(score))}>
          {score.toFixed(0)}
        </span>
        <span className="text-[10px] text-muted-foreground/70">/100</span>
      </div>
    </div>
  );
}

/* -- Dimension row ----------------------------------------------------- */

function DimensionRow({ dim }: { dim: EcosystemDimension }) {
  const Icon = DIMENSION_ICONS[dim.name] || TrendingUp;
  const barGradient = DIMENSION_COLORS[dim.name] || 'from-gray-500 to-gray-400';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn('p-1 rounded border', DIMENSION_BG_COLORS[dim.name] || 'bg-muted/20 border-muted/30')}>
            <Icon className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-medium">{dim.label}</span>
          <span className="text-[10px] text-muted-foreground/60">({(dim.weight * 100).toFixed(0)}%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={cn('text-sm font-semibold tabular-nums', overallScoreColor(dim.score))}>
            {dim.score.toFixed(0)}
          </span>
          <span className="text-[10px] text-muted-foreground/50">/100</span>
        </div>
      </div>
      <div className="h-2 rounded-full bg-muted/20 overflow-hidden">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r transition-all duration-700 ease-out', barGradient)}
          style={{ width: `${Math.min(dim.score, 100)}%` }}
        />
      </div>
      {/* Indicators (compact inline) */}
      <div className="flex flex-wrap gap-1.5 mt-1">
        {Object.entries(dim.indicators).map(([key, val]) => (
          <span key={key} className="text-[10px] text-muted-foreground/60">
            {key.replace(/_/g, ' ')}: <span className="text-foreground/80 font-medium">{val}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* -- Main component ---------------------------------------------------- */

export default function EcosystemScorePanel({ data, isLoading }: EcosystemScorePanelProps) {
  if (isLoading) {
    return (
      <GlassCard>
        <GlassCardContent className="flex items-center justify-center gap-3 py-12">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Calcul du score ecosysteme...</span>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (!data) return null;

  return (
    <GlassCard>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary" />
          Score Ecosysteme - Dept {data.department_code}
        </GlassCardTitle>
      </GlassCardHeader>
      <GlassCardContent className="space-y-6">
        {/* Top: overall gauge + summary */}
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <CircularGauge score={data.overall_score} size={130} />
          <div className="flex-1 space-y-3">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={cn('text-xs font-semibold', overallScoreBg(data.overall_score))}
              >
                {scoreLabel(data.overall_score)}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {data.total_actors} acteurs / {data.total_relations} relations
              </span>
            </div>
            {/* Mini summary bars */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {data.dimensions.map((d) => (
                <div key={d.name} className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground/70 w-24 truncate">{d.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all duration-500', dimensionBarColor(d.score))}
                      style={{ width: `${Math.min(d.score, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Detailed dimension breakdown */}
        <div className="space-y-4 pt-2 border-t border-border/30">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Detail des dimensions
          </h4>
          <div className="space-y-4">
            {data.dimensions.map((dim) => (
              <DimensionRow key={dim.name} dim={dim} />
            ))}
          </div>
        </div>

        {/* Recommendations */}
        {data.recommendations.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border/30">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recommandations
            </h4>
            <div className="space-y-1.5">
              {data.recommendations.map((rec, i) => {
                const isPriority = rec.startsWith('Priorite haute');
                return (
                  <div
                    key={i}
                    className={cn(
                      'flex items-start gap-2 p-2 rounded-md text-xs',
                      isPriority
                        ? 'bg-red-500/5 border border-red-500/15 text-red-300'
                        : rec.startsWith('Bon niveau')
                          ? 'bg-emerald-500/5 border border-emerald-500/15 text-emerald-300'
                          : 'bg-amber-500/5 border border-amber-500/15 text-amber-300',
                    )}
                  >
                    {isPriority ? (
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    ) : rec.startsWith('Bon niveau') ? (
                      <CheckCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    ) : (
                      <TrendingUp className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    )}
                    <span>{rec}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
