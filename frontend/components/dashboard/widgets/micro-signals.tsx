'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import {
  HiOutlineSignal,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineMinusSmall,
  HiOutlineCircleStack,
  HiOutlinePlay,
} from 'react-icons/hi2';
import {
  getCollectorSummary,
  getCollectorHealth,
  getCollectorSignals,
  type CollectorSummary,
  type CollectorHealth,
  type CollectorSignal,
} from '@/lib/api';

// Signal type to icon/color mapping
const SIGNAL_ICONS: Record<string, { icon: typeof HiOutlineArrowTrendingUp; color: string }> = {
  positif: { icon: HiOutlineArrowTrendingUp, color: 'text-[var(--success)]' },
  negatif: { icon: HiOutlineArrowTrendingDown, color: 'text-[var(--error)]' },
  neutre: { icon: HiOutlineMinusSmall, color: 'text-muted-foreground' },
};

// Source display names
const SOURCE_NAMES: Record<string, string> = {
  sirene: 'SIRENE (INSEE)',
  france_travail: 'France Travail',
  presse_locale: 'Presse locale',
  bodacc: 'BODACC',
  dvf: 'DVF (Immobilier)',
  test: 'Test',
};

// Metric display names
const METRIC_NAMES: Record<string, string> = {
  creation_entreprise: 'Créations entreprises',
  fermeture_entreprise: 'Fermetures entreprises',
  offres_emploi: 'Offres emploi',
  presse_positif: 'Presse positive',
  presse_negatif: 'Presse négative',
  test_signal: 'Test',
};

/**
 * Micro-Signals Summary Widget
 * Shows overview of collected signals with source breakdown
 */
export function MicroSignalsSummaryWidget() {
  const [summary, setSummary] = useState<CollectorSummary | null>(null);
  const [health, setHealth] = useState<CollectorHealth | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const [summaryData, healthData] = await Promise.all([
      getCollectorSummary(3650),
      getCollectorHealth(),
    ]);
    setSummary(summaryData);
    setHealth(healthData);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineSignal className="h-5 w-5 text-primary animate-pulse" />
            Micro-Signaux
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-8 bg-muted/50 rounded" />
            <div className="h-4 bg-muted/50 rounded w-3/4" />
            <div className="h-4 bg-muted/50 rounded w-1/2" />
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  const dbConnected = health?.database === 'connected';

  return (
    <GlassCard glow={dbConnected ? 'green' : 'red'} hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineSignal className="h-5 w-5 text-primary" />
          Micro-Signaux
        </GlassCardTitle>
        <GlassCardDescription>
          Collecte multi-sources • {summary?.period_days || 30}j
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {!dbConnected ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            Base de données non connectée
          </p>
        ) : (
          <div className="space-y-4">
            {/* Total signals */}
            <div className="flex items-center justify-between">
              <span className="text-3xl font-bold">{summary?.total || 0}</span>
              <span className="text-xs text-muted-foreground">signaux collectés</span>
            </div>

            {/* By type breakdown */}
            {summary?.by_type && (
              <div className="flex gap-3">
                {Object.entries(summary.by_type).map(([type, count]) => {
                  const config = SIGNAL_ICONS[type] || SIGNAL_ICONS.neutre;
                  const Icon = config.icon;
                  return (
                    <div key={type} className="flex items-center gap-1">
                      <Icon className={`h-4 w-4 ${config.color}`} />
                      <span className="text-sm font-medium">{count}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* By source */}
            {summary?.by_source && Object.keys(summary.by_source).length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Sources</p>
                {Object.entries(summary.by_source).slice(0, 5).map(([source, count]) => (
                  <div key={source} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <HiOutlineCircleStack className="h-3 w-3 text-muted-foreground" />
                      <span className="text-sm">{SOURCE_NAMES[source] || source}</span>
                    </div>
                    <span className="text-sm font-mono">{count}</span>
                  </div>
                ))}
              </div>
            )}

            {/* By department */}
            {summary?.by_department && Object.keys(summary.by_department).length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">
                  Top départements
                </p>
                {Object.entries(summary.by_department).slice(0, 3).map(([dept, count]) => (
                  <div key={dept} className="flex items-center justify-between">
                    <span className="text-sm font-mono">{dept}</span>
                    <span className="text-sm">{count} signaux</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

/**
 * Recent Signals Widget
 * Shows the latest collected signals with details
 */
export function RecentSignalsWidget({ limit = 5 }: { limit?: number }) {
  const [signals, setSignals] = useState<CollectorSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      const data = await getCollectorSignals({ days: 7, limit });
      setSignals(data?.signals || []);
      setLoading(false);
    }
    fetch();
  }, [limit]);

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineArrowTrendingUp className="h-5 w-5 text-primary" />
          Signaux Récents
        </GlassCardTitle>
        <GlassCardDescription>Derniers 7 jours</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-muted/50 rounded" />
            ))}
          </div>
        ) : signals.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            Aucun signal récent
          </p>
        ) : (
          <div className="space-y-2">
            {signals.map((signal) => {
              const config = SIGNAL_ICONS[signal.signal_type || 'neutre'] || SIGNAL_ICONS.neutre;
              const Icon = config.icon;
              return (
                <div
                  key={signal.id}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <Icon className={`h-4 w-4 flex-shrink-0 ${config.color}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">
                      {METRIC_NAMES[signal.metric_name] || signal.metric_name}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{SOURCE_NAMES[signal.source] || signal.source}</span>
                      {signal.code_dept && (
                        <>
                          <span>•</span>
                          <span>Dept {signal.code_dept}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {signal.metric_value !== null && (
                    <span className="text-sm font-mono">{signal.metric_value}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
