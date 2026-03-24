'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Minus, Activity, BarChart3,
  RefreshCw, Clock, Filter, ChevronDown, ChevronUp,
} from 'lucide-react';
import { DEPT_NAMES } from '@/lib/departments';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const METRIC_LABELS: Record<string, { label: string; color: string }> = {
  'bodacc_creation': { label: 'Creations entreprises', color: 'var(--success)' },
  'bodacc_liquidation': { label: 'Liquidations', color: 'var(--error)' },
  'bodacc_radiation': { label: 'Radiations', color: 'var(--warning)' },
  'ft_cdi': { label: 'Offres CDI', color: 'var(--chart-2)' },
  'ft_cdd': { label: 'Offres CDD', color: 'var(--chart-3)' },
  'transaction_immobiliere': { label: 'Transactions immo', color: 'var(--chart-4)' },
};

interface Prediction {
  department: string;
  source: string;
  metric: string;
  label: string;
  trend: string;
  change_pct: number;
  data_points: number;
  forecast: string;
  last_actual: string;
  changepoints: string;
  date: string;
}

interface ForecastPoint {
  date: string;
  predicted: number;
  lower: number;
  upper: number;
}

function parseForecast(raw: string): ForecastPoint[] {
  try { return JSON.parse(raw); } catch { return []; }
}

function parseLastActual(raw: string): { date: string; value: number } | null {
  try { return JSON.parse(raw); } catch { return null; }
}

function TrendIcon({ trend, size = 16 }: { trend: string; size?: number }) {
  if (trend === 'up') return <TrendingUp style={{ width: size, height: size, color: 'var(--success)' }} />;
  if (trend === 'down') return <TrendingDown style={{ width: size, height: size, color: 'var(--error)' }} />;
  return <Minus style={{ width: size, height: size, color: 'var(--muted-foreground)' }} />;
}

function trendColor(trend: string) {
  if (trend === 'up') return 'var(--success)';
  if (trend === 'down') return 'var(--error)';
  return 'var(--muted-foreground)';
}

export default function ForecastTab() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedMetric, setSelectedMetric] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const predRes = await fetch(`${API_BASE}/api/v1/signals/predictions?limit=200`);
      if (predRes.ok) {
        const d = await predRes.json();
        setPredictions(d.predictions || []);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Unique metrics
  const metrics = [...new Set(predictions.map(p => p.metric))];

  // Filtered predictions
  const filtered = selectedMetric
    ? predictions.filter(p => p.metric === selectedMetric)
    : predictions;

  // Sort by absolute change
  const sorted = [...filtered].sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));

  // Summary stats
  const nbUp = predictions.filter(p => p.trend === 'up').length;
  const nbDown = predictions.filter(p => p.trend === 'down').length;
  const nbStable = predictions.filter(p => p.trend === 'stable').length;
  const avgChange = predictions.length
    ? predictions.reduce((s, p) => s + p.change_pct, 0) / predictions.length
    : 0;

  // Top movers chart data
  const topMovers = sorted.slice(0, 15).map(p => ({
    name: `${p.department} ${p.label.substring(0, 12)}`,
    change: p.change_pct,
    trend: p.trend,
  }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard>
          <GlassCardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Tendances haussiere</p>
                <p className="text-2xl font-bold text-[var(--success)]">{nbUp}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-[var(--success)]/30" />
            </div>
          </GlassCardContent>
        </GlassCard>
        <GlassCard>
          <GlassCardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Tendances baissiere</p>
                <p className="text-2xl font-bold text-[var(--error)]">{nbDown}</p>
              </div>
              <TrendingDown className="h-8 w-8 text-[var(--error)]/30" />
            </div>
          </GlassCardContent>
        </GlassCard>
        <GlassCard>
          <GlassCardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Stables</p>
                <p className="text-2xl font-bold">{nbStable}</p>
              </div>
              <Minus className="h-8 w-8 text-muted-foreground/30" />
            </div>
          </GlassCardContent>
        </GlassCard>
        <GlassCard>
          <GlassCardContent className="pt-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Variation moyenne</p>
                <p className="text-2xl font-bold" style={{ color: avgChange >= 0 ? 'var(--success)' : 'var(--error)' }}>
                  {avgChange >= 0 ? '+' : ''}{avgChange.toFixed(1)}%
                </p>
              </div>
              <Activity className="h-8 w-8 text-primary/30" />
            </div>
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* Top Movers Chart */}
      <GlassCard>
        <GlassCardHeader className="pb-2">
          <GlassCardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4 text-primary" />
            Top 15 Variations Prevues
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          {topMovers.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topMovers} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <Tooltip
                  formatter={(v: number) => [`${v >= 0 ? '+' : ''}${v.toFixed(1)}%`, 'Variation']}
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
                />
                <Bar dataKey="change" radius={[0, 4, 4, 0]}>
                  {topMovers.map((entry, i) => (
                    <Cell key={i} fill={trendColor(entry.trend)} fillOpacity={0.7} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
              {loading ? 'Chargement...' : 'Aucune prediction disponible'}
            </div>
          )}
        </GlassCardContent>
      </GlassCard>

      {/* Filter + List */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={selectedMetric}
            onChange={e => setSelectedMetric(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-muted/30 border border-border text-sm"
          >
            <option value="">Toutes les metriques</option>
            {metrics.map(m => (
              <option key={m} value={m}>
                {METRIC_LABELS[m]?.label || m.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
        <span className="text-xs text-muted-foreground">
          {sorted.length} predictions
        </span>
        <Button variant="ghost" size="sm" onClick={fetchData} disabled={loading} className="ml-auto">
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </Button>
      </div>

      {/* Prediction Cards */}
      <div className="space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full" />
          </div>
        ) : sorted.length === 0 ? (
          <GlassCard>
            <GlassCardContent className="py-12 text-center text-muted-foreground">
              Aucune prediction disponible. Lancez le script Prophet.
            </GlassCardContent>
          </GlassCard>
        ) : (
          sorted.map((pred) => {
            const key = `${pred.department}-${pred.metric}`;
            const isExpanded = expandedId === key;
            const forecast = parseForecast(pred.forecast);
            const lastActual = parseLastActual(pred.last_actual);
            const metaColor = METRIC_LABELS[pred.metric]?.color || 'var(--primary)';

            // Build chart data: actual + forecast
            const chartData: any[] = [];
            if (lastActual) {
              chartData.push({
                date: new Date(lastActual.date).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' }),
                actual: lastActual.value,
              });
            }
            forecast.forEach(f => {
              chartData.push({
                date: new Date(f.date).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' }),
                predicted: f.predicted,
                lower: f.lower,
                upper: f.upper,
              });
            });

            return (
              <GlassCard key={key} className="transition-all hover:border-primary/30">
                <div
                  className="px-4 py-3 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : key)}
                >
                  <div className="flex items-center gap-3">
                    <TrendIcon trend={pred.trend} size={20} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs bg-primary/15 px-1.5 py-0.5 rounded">
                          {pred.department}
                        </span>
                        <span className="text-sm font-medium">
                          {DEPT_NAMES[pred.department] || pred.department}
                        </span>
                        <span
                          className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                          style={{
                            color: metaColor,
                            backgroundColor: `color-mix(in srgb, ${metaColor} 12%, transparent)`,
                          }}
                        >
                          {pred.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span>{pred.data_points} points de donnees</span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(pred.date).toLocaleDateString('fr-FR')}
                        </span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div
                        className="text-lg font-bold font-mono"
                        style={{ color: trendColor(pred.trend) }}
                      >
                        {pred.change_pct >= 0 ? '+' : ''}{pred.change_pct.toFixed(1)}%
                      </div>
                      <div className="text-[10px] text-muted-foreground">variation prevue</div>
                    </div>
                    <div className="shrink-0">
                      {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </div>
                  </div>
                </div>

                {isExpanded && chartData.length > 1 && (
                  <div className="px-4 pb-4 border-t border-border/50">
                    <div className="pt-3">
                      <p className="text-xs text-muted-foreground mb-2">
                        Prevision a 3 mois avec intervalle de confiance
                      </p>
                      <ResponsiveContainer width="100%" height={200}>
                        <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                          <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                          <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                          <Tooltip
                            contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
                          />
                          {/* Confidence interval */}
                          <Area
                            type="monotone"
                            dataKey="upper"
                            stroke="none"
                            fill={trendColor(pred.trend)}
                            fillOpacity={0.1}
                          />
                          <Area
                            type="monotone"
                            dataKey="lower"
                            stroke="none"
                            fill="hsl(var(--background))"
                            fillOpacity={1}
                          />
                          {/* Prediction line */}
                          <Area
                            type="monotone"
                            dataKey="predicted"
                            stroke={trendColor(pred.trend)}
                            fill={trendColor(pred.trend)}
                            fillOpacity={0.15}
                            strokeWidth={2}
                            strokeDasharray="5 5"
                          />
                          {/* Actual */}
                          <Area
                            type="monotone"
                            dataKey="actual"
                            stroke="hsl(var(--primary))"
                            fill="hsl(var(--primary))"
                            fillOpacity={0.2}
                            strokeWidth={2}
                          />
                        </AreaChart>
                      </ResponsiveContainer>

                      {/* Forecast values */}
                      <div className="grid grid-cols-3 gap-2 mt-3">
                        {forecast.map((f, i) => (
                          <div key={i} className="bg-muted/20 rounded p-2 text-center">
                            <p className="text-[10px] text-muted-foreground">
                              {new Date(f.date).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })}
                            </p>
                            <p className="text-sm font-bold font-mono" style={{ color: trendColor(pred.trend) }}>
                              {f.predicted.toFixed(1)}
                            </p>
                            <p className="text-[10px] text-muted-foreground">
                              [{f.lower.toFixed(1)} - {f.upper.toFixed(1)}]
                            </p>
                          </div>
                        ))}
                      </div>

                      {/* Changepoints */}
                      {pred.changepoints && pred.changepoints !== '[]' && (
                        <div className="mt-2">
                          <p className="text-[10px] text-muted-foreground">
                            Points de rupture detectes : {
                              JSON.parse(pred.changepoints).map((cp: string) =>
                                new Date(cp).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })
                              ).join(', ')
                            }
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </GlassCard>
            );
          })
        )}
      </div>
    </div>
  );
}
