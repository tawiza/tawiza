'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import {
  HiOutlineExclamationTriangle,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineBolt,
} from 'react-icons/hi2';

interface MicroSignal {
  signal_type: string;
  code_dept: string;
  score: number;
  sources: string[];
  metrics: Record<string, number>;
  description: string;
  detected_at: string;
}

interface AnomaliesResponse {
  count: number;
  window_days: number;
  micro_signals: MicroSignal[];
}

const SIGNAL_CONFIG: Record<string, { icon: typeof HiOutlineBolt; color: string; label: string }> = {
  dynamisme_territorial: { icon: HiOutlineArrowTrendingUp, color: 'text-[var(--success)]', label: 'Dynamisme' },
  declin_territorial: { icon: HiOutlineArrowTrendingDown, color: 'text-[var(--error)]', label: 'Déclin' },
  tension_emploi: { icon: HiOutlineBolt, color: 'text-warning', label: 'Tension emploi' },
  crise_sectorielle: { icon: HiOutlineExclamationTriangle, color: 'text-[var(--error)]', label: 'Crise' },
  attractivite: { icon: HiOutlineArrowTrendingUp, color: 'text-success', label: 'Attractivité' },
  desertification: { icon: HiOutlineArrowTrendingDown, color: 'text-[var(--chart-5)]', label: 'Désertification' },
  renouvellement: { icon: HiOutlineBolt, color: 'text-info', label: 'Renouvellement' },
};

const SOURCE_NAMES: Record<string, string> = {
  sirene: 'SIRENE',
  france_travail: 'France Travail',
  presse_locale: 'Presse',
};

/**
 * Anomalies / Micro-Signals Detection Widget
 */
export function AnomaliesWidget({ days = 3650 }: { days?: number }) {
  const [data, setData] = useState<AnomaliesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(`/api/collector/anomalies?days=${days}`);
      if (resp.ok) {
        setData(await resp.json());
      }
    } catch {
      // ignore
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // every 5 min
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <GlassCard glow={data && data.count > 0 ? 'red' : 'cyan'} hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineExclamationTriangle className="h-5 w-5 text-primary" />
          Micro-Signaux Détectés
        </GlassCardTitle>
        <GlassCardDescription>
          Croisement multi-sources • {days}j
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-12 bg-muted/50 rounded" />
            <div className="h-12 bg-muted/50 rounded" />
          </div>
        ) : !data || data.count === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-muted-foreground">
              Aucune anomalie multi-sources détectée
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Le détecteur croise SIRENE + France Travail + Presse
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl font-bold">{data.count}</span>
              <span className="text-xs text-muted-foreground">anomalies détectées</span>
            </div>
            {data.micro_signals.slice(0, 5).map((ms, i) => {
              const config = SIGNAL_CONFIG[ms.signal_type] || SIGNAL_CONFIG.tension_emploi;
              const Icon = config.icon;
              return (
                <div
                  key={i}
                  className="flex items-start gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <Icon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{config.label}</span>
                      <span className="text-xs font-mono text-muted-foreground">
                        Dept {ms.code_dept}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {ms.description}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      {ms.sources.map((s) => (
                        <span
                          key={s}
                          className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/80 text-muted-foreground"
                        >
                          {SOURCE_NAMES[s] || s}
                        </span>
                      ))}
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        Score: {(ms.score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
