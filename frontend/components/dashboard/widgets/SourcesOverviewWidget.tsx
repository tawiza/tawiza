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
import { StatusDot, AnimatedCounter } from '@/components/ui/animated-counter';
import { HiOutlineCircleStack, HiOutlineArrowPath } from 'react-icons/hi2';
import { getSourcesSummary, type SourcesSummary } from '@/lib/api';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

// Source display names
const SOURCE_NAMES: Record<string, string> = {
  sirene: 'SIRENE (INSEE)',
  france_travail: 'France Travail',
  presse_locale: 'Presse locale',
  bodacc: 'BODACC',
  dvf: 'DVF (Immobilier)',
  sitadel: 'Sitadel (Construction)',
  google_trends: 'Google Trends',
  gdelt: 'GDELT (Actualités)',
  banque_france: 'Banque de France',
  test: 'Test',
};

// Colors for the pie chart
const COLORS = [
  'var(--info)', // blue
  'var(--success)', // green
  'var(--warning)', // yellow
  'var(--error)', // red
  'var(--chart-3)', // purple
  'var(--chart-2)', // cyan
  'var(--success)', // lime
  'var(--chart-5)', // orange
  'var(--chart-4)', // pink
  'hsl(var(--muted-foreground))', // gray
];

function StatusIndicator({ status }: { status: 'online' | 'degraded' | 'offline' }) {
  return <StatusDot status={status} size="sm" />;
}

export function SourcesOverviewWidget() {
  const [data, setData] = useState<SourcesSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const result = await getSourcesSummary();
      if (result) {
        setData(result);
      } else {
        setError('Impossible de charger les données des sources');
      }
    } catch (err) {
      setError('Erreur lors du chargement');
      console.error('Error fetching sources summary:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <GlassCard glow="green" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineCircleStack className="h-5 w-5 text-primary" />
              Sources de Données
            </GlassCardTitle>
            <GlassCardDescription>
              Vue d&apos;ensemble des 10 sources
            </GlassCardDescription>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3 animate-pulse">
                <div className="w-3 h-3 bg-gray-300 dark:bg-gray-600 rounded-full"></div>
                <div className="flex-1 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="w-16 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
              </div>
            ))}
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (error || !data) {
    return (
      <GlassCard glow="red" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineCircleStack className="h-5 w-5 text-primary" />
              Sources de Données
            </GlassCardTitle>
            <GlassCardDescription>
              Vue d&apos;ensemble des sources
            </GlassCardDescription>
          </div>
          <Button size="sm" variant="ghost" onClick={fetchData}>
            <HiOutlineArrowPath className="h-4 w-4" />
          </Button>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="text-center py-6 text-muted-foreground">
            <p>{error || 'Aucune donnée disponible'}</p>
            <Button size="sm" onClick={fetchData} className="mt-2">
              Réessayer
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Prepare chart data
  const chartData = data.sources.slice(0, 8).map((source, index) => ({
    name: SOURCE_NAMES[source.source] || source.source,
    value: source.count,
    color: COLORS[index % COLORS.length]
  }));

  return (
    <GlassCard glow="green" hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between">
        <div className="space-y-1">
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineCircleStack className="h-5 w-5 text-primary" />
            Sources de Données
          </GlassCardTitle>
          <GlassCardDescription>
            <AnimatedCounter value={data.total_sources} suffix=" sources" /> • <AnimatedCounter value={data.total_signals} suffix=" signaux" />
          </GlassCardDescription>
        </div>
        <Button size="sm" variant="ghost" onClick={fetchData}>
          <HiOutlineArrowPath className="h-4 w-4" />
        </Button>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Pie Chart */}
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={20}
                  outerRadius={50}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          
          {/* Sources List */}
          <div className="space-y-2">
            {data.sources.slice(0, 6).map((source) => (
              <div
                key={source.source}
                className="flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-2 flex-1">
                  <StatusIndicator status={source.status} />
                  <span className="text-xs truncate">
                    {SOURCE_NAMES[source.source] || source.source}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground font-mono">
                  <AnimatedCounter value={source.count} />
                </div>
              </div>
            ))}
            
            {data.sources.length > 6 && (
              <div className="text-xs text-muted-foreground text-center pt-1">
                +{data.sources.length - 6} autres sources
              </div>
            )}
          </div>
        </div>
        
        {/* Status Legend */}
        <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <StatusIndicator status="online" />
                <span>&lt;24h</span>
              </div>
              <div className="flex items-center gap-1">
                <StatusIndicator status="degraded" />
                <span>&lt;7j</span>
              </div>
              <div className="flex items-center gap-1">
                <StatusIndicator status="offline" />
                <span>&gt;7j</span>
              </div>
            </div>
            <div className="text-xs">
              Dernière collecte
            </div>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}