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
import { AnimatedCounter } from '@/components/ui/animated-counter';
import { HiOutlineArrowTrendingUp, HiOutlineArrowPath, HiOutlineMapPin } from 'react-icons/hi2';
import { getGoogleTrendsData, type GoogleTrendsData } from '@/lib/api';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Cell } from 'recharts';

// Colors for bars
const COLORS = [
  'var(--info)', // blue
  'var(--success)', // green
  'var(--warning)', // yellow
  'var(--error)', // red
  'var(--chart-3)', // purple
  'var(--chart-2)', // cyan
  'var(--success)', // lime
  'var(--chart-5)', // orange
];

function TrendSparkline({ value, maxValue }: { value: number; maxValue: number }) {
  const width = Math.max(10, (value / maxValue) * 80);
  const intensity = value / maxValue;
  const color = intensity > 0.7 ? 'bg-red-500' : intensity > 0.4 ? 'bg-yellow-500' : 'bg-blue-500';

  return (
    <div className="w-20 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
      <div
        className={`h-2 rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

export function GoogleTrendsWidget() {
  const [data, setData] = useState<GoogleTrendsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const result = await getGoogleTrendsData(15);
      if (result) {
        setData(result);
      } else {
        setError('Impossible de charger les données Google Trends');
      }
    } catch (err) {
      setError('Erreur lors du chargement');
      console.error('Error fetching Google Trends:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineArrowTrendingUp className="h-5 w-5 text-primary" />
              Google Trends
            </GlassCardTitle>
            <GlassCardDescription>
              Mots-clés les plus recherchés
            </GlassCardDescription>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3 animate-pulse">
                <div className="flex-1 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="w-20 h-2 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="w-8 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
              </div>
            ))}
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (error || !data || data.top_keywords.length === 0) {
    return (
      <GlassCard glow="red" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineArrowTrendingUp className="h-5 w-5 text-primary" />
              Google Trends
            </GlassCardTitle>
            <GlassCardDescription>
              Mots-clés les plus recherchés
            </GlassCardDescription>
          </div>
          <Button size="sm" variant="ghost" onClick={fetchData}>
            <HiOutlineArrowPath className="h-4 w-4" />
          </Button>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="text-center py-6 text-muted-foreground">
            <p>{error || 'Aucune donnée Google Trends disponible'}</p>
            <Button size="sm" onClick={fetchData} className="mt-2">
              Réessayer
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  const maxValue = Math.max(...data.top_keywords.map(k => k.total_value));
  const topKeywords = data.top_keywords.slice(0, 8);

  // Prepare chart data
  const chartData = topKeywords.map(keyword => ({
    keyword: keyword.keyword.length > 12 ? keyword.keyword.substring(0, 12) + '...' : keyword.keyword,
    value: keyword.total_value,
  }));

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between">
        <div className="space-y-1">
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineArrowTrendingUp className="h-5 w-5 text-primary" />
            Google Trends
          </GlassCardTitle>
          <GlassCardDescription>
            <AnimatedCounter value={data.total_trends} suffix=" recherches" /> dans <AnimatedCounter value={data.top_keywords.length} suffix=" mots-clés" />
          </GlassCardDescription>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant={showDetails ? "default" : "ghost"}
            onClick={() => setShowDetails(!showDetails)}
          >
            <HiOutlineMapPin className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="ghost" onClick={fetchData}>
            <HiOutlineArrowPath className="h-4 w-4" />
          </Button>
        </div>
      </GlassCardHeader>
      <GlassCardContent>
        {!showDetails ? (
          <>
            {/* Mini Bar Chart */}
            <div className="h-32 mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                  <XAxis
                    dataKey="keyword"
                    tick={{ fontSize: 10 }}
                    interval={0}
                    angle={-45}
                    textAnchor="end"
                    height={40}
                  />
                  <YAxis hide />
                  <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                    {chartData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Top Keywords List */}
            <div className="space-y-2">
              {topKeywords.slice(0, 5).map((keyword, index) => (
                <div
                  key={keyword.keyword}
                  className="flex items-center justify-between text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 py-1 transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <span className="text-xs text-muted-foreground w-4">
                      {index + 1}
                    </span>
                    <span className="text-sm truncate">
                      {keyword.keyword}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <TrendSparkline value={keyword.total_value} maxValue={maxValue} />
                    <span className="text-xs font-mono text-muted-foreground w-8 text-right">
                      <AnimatedCounter value={Math.round(keyword.total_value)} />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            {/* Detailed view by department */}
            <div className="space-y-3">
              <div className="text-sm font-medium text-muted-foreground">
                Détails par département
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {data.trends.slice(0, 15).map((trend, index) => (
                  <div
                    key={`${trend.keyword}-${trend.department}`}
                    className="flex items-center justify-between text-xs hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-2 py-1 transition-colors"
                  >
                    <div className="flex-1 truncate">
                      <span className="font-medium">{trend.keyword}</span>
                      {trend.department && (
                        <span className="text-muted-foreground ml-1">({trend.department})</span>
                      )}
                    </div>
                    <div className="text-muted-foreground">
                      <AnimatedCounter value={Math.round(trend.avg_value)} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Footer */}
        <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div>
              Tendances de recherche Google
            </div>
            <div>
              {showDetails ? 'Par département' : 'Top mots-clés'}
            </div>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}