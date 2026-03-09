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
  HiOutlineChartBarSquare,
} from 'react-icons/hi2';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { getCollectorSignals, type CollectorSignal } from '@/lib/api';

interface DayData {
  date: string;
  france_travail: number;
  sirene_creation: number;
  sirene_fermeture: number;
  presse: number;
}

/**
 * Signals Timeline Chart
 * Shows signal volume evolution over time by source
 */
export function SignalsTimelineChart({ days = 14 }: { days?: number }) {
  const [data, setData] = useState<DayData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const result = await getCollectorSignals({ days, limit: 5000 });
    if (!result?.signals) {
      setLoading(false);
      return;
    }

    // Group by date
    const byDate: Record<string, DayData> = {};
    for (const signal of result.signals) {
      const d = signal.event_date?.slice(0, 10) || 'unknown';
      if (!byDate[d]) {
        byDate[d] = { date: d, france_travail: 0, sirene_creation: 0, sirene_fermeture: 0, presse: 0 };
      }
      if (signal.source === 'france_travail') byDate[d].france_travail += (signal.metric_value || 0);
      else if (signal.source === 'sirene' && signal.metric_name === 'creation_entreprise') byDate[d].sirene_creation += (signal.metric_value || 0);
      else if (signal.source === 'sirene' && signal.metric_name === 'fermeture_entreprise') byDate[d].sirene_fermeture += (signal.metric_value || 0);
      else if (signal.source === 'presse_locale') byDate[d].presse += 1;
    }

    const sorted = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
    setData(sorted);
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 120000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBarSquare className="h-5 w-5 text-primary" />
          Évolution des Signaux
        </GlassCardTitle>
        <GlassCardDescription>{days} derniers jours</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse h-[250px] bg-muted/50 rounded" />
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">Aucune donnée</p>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <defs>
                <linearGradient id="colorFT" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--info)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--info)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorSC" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--success)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--success)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorSF" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--error)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--error)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorP" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--chart-3)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--chart-3)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(30,30,46,0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  color: 'hsl(var(--foreground))',
                  fontSize: 12,
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.6)' }}
              />
              <Area
                type="monotone" dataKey="france_travail" name="Offres emploi"
                stroke="var(--info)" fill="url(#colorFT)" strokeWidth={2}
              />
              <Area
                type="monotone" dataKey="sirene_creation" name="Créations"
                stroke="var(--success)" fill="url(#colorSC)" strokeWidth={2}
              />
              <Area
                type="monotone" dataKey="sirene_fermeture" name="Fermetures"
                stroke="var(--error)" fill="url(#colorSF)" strokeWidth={2}
              />
              <Area
                type="monotone" dataKey="presse" name="Presse"
                stroke="var(--chart-3)" fill="url(#colorP)" strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
