'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  HiOutlineChartBar,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
} from 'react-icons/hi2';

interface TrendData {
  current: number;
  change: number;
  data: number[];
}

interface TrendsResponse {
  creations: TrendData;
  prix_m2: TrendData;
  emploi: TrendData;
  population: TrendData;
}

const TREND_CONFIG = {
  creations: {
    label: 'Créations',
    unit: 'k',
    color: 'var(--success)',
    format: (v: number) => `${(v / 1000).toFixed(1)}k`,
  },
  prix_m2: {
    label: 'Prix m²',
    unit: '€',
    color: 'var(--chart-1)',
    format: (v: number) => `${v.toLocaleString('fr-FR')} €`,
  },
  emploi: {
    label: 'Emploi',
    unit: '%',
    color: 'var(--warning)',
    format: (v: number) => `${v.toFixed(1)}%`,
  },
  population: {
    label: 'Population',
    unit: 'M',
    color: 'var(--chart-3)',
    format: (v: number) => `${(v / 1000000).toFixed(2)}M`,
  },
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function Sparkline({
  data,
  color,
  width = 80,
  height = 24,
}: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(' L ')}`;

  // Create area path for gradient fill
  const areaD = `${pathD} L ${width},${height} L 0,${height} Z`;

  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#gradient-${color})`} />
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Current value dot */}
      <circle
        cx={width}
        cy={height - ((data[data.length - 1] - min) / range) * height}
        r={2}
        fill={color}
      />
    </svg>
  );
}

function TrendRow({
  trendKey,
  trend,
}: {
  trendKey: keyof typeof TREND_CONFIG;
  trend: TrendData;
}) {
  const config = TREND_CONFIG[trendKey];
  const isPositive = trend.change >= 0;

  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <div className="flex items-center gap-3">
        <div className="w-20">
          <Sparkline data={trend.data} color={config.color} />
        </div>
        <div>
          <div className="text-sm font-medium">{config.label}</div>
          <div className="text-xs text-muted-foreground">
            {config.format(trend.current)}
          </div>
        </div>
      </div>
      <div
        className={`flex items-center gap-1 text-sm ${
          isPositive ? 'text-green-400' : 'text-red-400'
        }`}
      >
        {isPositive ? (
          <HiOutlineArrowTrendingUp className="h-4 w-4" />
        ) : (
          <HiOutlineArrowTrendingDown className="h-4 w-4" />
        )}
        <span>
          {isPositive ? '+' : ''}
          {trend.change.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export function TrendsWidget() {
  const [period, setPeriod] = useState('12m');

  const { data, error, isLoading } = useSWR<TrendsResponse | { detail?: string }>(
    `/api/v1/territorial/trends?period=${period}`,
    fetcher,
    {
      refreshInterval: 300000, // Refresh every 5 minutes
      revalidateOnFocus: false,
    }
  );

  // Validate response has expected properties (not an error object)
  const trends = data && 'creations' in data ? (data as TrendsResponse) : null;

  if (error) {
    return (
      <GlassCard glow="red">
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineChartBar className="h-5 w-5 text-red-400" />
            Tendances Nationales
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground">Erreur de chargement</p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between pb-2">
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBar className="h-5 w-5 text-primary" />
          Tendances Nationales
        </GlassCardTitle>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-[80px] h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="3m">3 mois</SelectItem>
            <SelectItem value="6m">6 mois</SelectItem>
            <SelectItem value="12m">12 mois</SelectItem>
            <SelectItem value="24m">24 mois</SelectItem>
          </SelectContent>
        </Select>
      </GlassCardHeader>
      <GlassCardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-12 bg-muted/20 rounded animate-pulse" />
            ))}
          </div>
        ) : trends ? (
          <div className="space-y-1">
            <TrendRow trendKey="creations" trend={trends.creations} />
            <TrendRow trendKey="prix_m2" trend={trends.prix_m2} />
            <TrendRow trendKey="emploi" trend={trends.emploi} />
            <TrendRow trendKey="population" trend={trends.population} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            Aucune donnée disponible
          </p>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

export default TrendsWidget;
