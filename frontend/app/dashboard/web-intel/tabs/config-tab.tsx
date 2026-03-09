'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardDescription,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import {
  Play,
  RefreshCw,
  Database,
  Clock,
  Activity,
  Globe,
  Loader2,
  XCircle,
  Zap,
  Server,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// ── Types ────────────────────────────────────────────────────
interface Source {
  id: string;
  name: string;
  type: string;
  description: string;
  schedule: string;
  enabled: boolean;
}

interface CrawlerStats {
  total_signals: number;
  recent_24h: number;
  departments_covered: number;
  date_range: { min: string | null; max: string | null };
  by_source: { source: string; count: number; last_collected: string | null }[];
}

interface CrawlerStatus {
  is_running: boolean;
  current_source: string | null;
  started_at: string | null;
  last_run: string | null;
  error: string | null;
}

interface HistoryEntry {
  source: string;
  batch_time: string;
  count: number;
  departments: number;
}

// ── Helpers ──────────────────────────────────────────────────
function formatDate(iso: string | null): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('fr-FR');
}

const sourceTypeColors: Record<string, string> = {
  api: 'bg-primary/15 text-primary border-primary/25',
  rss: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/25',
  scraper: 'bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/25',
};

// ── Main Component ──────────────────────────────────────────
export default function ConfigTab() {
  const [sources, setSources] = useState<Source[]>([]);
  const [stats, setStats] = useState<CrawlerStats | null>(null);
  const [status, setStatus] = useState<CrawlerStatus | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningSource, setRunningSource] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [configRes, statsRes, statusRes, historyRes] = await Promise.all([
        fetch(`${API}/api/v1/crawler/config`),
        fetch(`${API}/api/v1/crawler/stats`),
        fetch(`${API}/api/v1/crawler/status`),
        fetch(`${API}/api/v1/crawler/history`),
      ]);
      if (configRes.ok) {
        const c = await configRes.json();
        setSources(c.sources || []);
      }
      if (statsRes.ok) setStats(await statsRes.json());
      if (statusRes.ok) setStatus(await statusRes.json());
      if (historyRes.ok) setHistory(await historyRes.json());
    } catch (e) {
      console.error('Failed to fetch crawler data', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const triggerRun = async (source?: string) => {
    setRunningSource(source || 'all');
    try {
      await fetch(`${API}/api/v1/crawler/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: source || null, days_back: 30 }),
      });
      setTimeout(fetchAll, 2000);
    } catch (e) {
      console.error('Failed to trigger run', e);
    }
  };

  const toggleSource = async (sourceId: string, enabled: boolean) => {
    await fetch(`${API}/api/v1/crawler/config/source/${sourceId}?enabled=${enabled}`, {
      method: 'PUT',
    });
    setSources((prev) => prev.map((s) => (s.id === sourceId ? { ...s, enabled } : s)));
  };

  const isRunning = status?.is_running || false;

  // Build source stats map
  const sourceStatsMap = new Map(
    stats?.by_source?.map((s) => [s.source, s]) || []
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">
            {sources.filter((s) => s.enabled).length} sources actives sur {sources.length}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
            Actualiser
          </Button>
          <Button
            size="sm"
            onClick={() => triggerRun()}
            disabled={isRunning}
          >
            {isRunning ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            {isRunning ? 'Collecte en cours...' : 'Lancer la collecte'}
          </Button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard>
          <GlassCardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Database className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Signaux totaux</p>
                <p className="text-xl font-bold">{stats ? formatNumber(stats.total_signals) : '-'}</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        <GlassCard>
          <GlassCardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-[var(--success)]/10">
                <Zap className="w-5 h-5 text-[var(--success)]" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Dernieres 24h</p>
                <p className="text-xl font-bold">{stats ? formatNumber(stats.recent_24h) : '-'}</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        <GlassCard>
          <GlassCardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-secondary/10">
                <Globe className="w-5 h-5 text-secondary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Departements</p>
                <p className="text-xl font-bold">{stats?.departments_covered ?? '-'}</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        <GlassCard>
          <GlassCardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-[var(--info)]/10">
                <Server className="w-5 h-5 text-[var(--info)]" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Statut</p>
                <p className="text-sm font-medium">
                  {isRunning ? (
                    <span className="text-[var(--warning)]">Collecte: {status?.current_source}</span>
                  ) : (
                    <span className="text-[var(--success)]">En attente</span>
                  )}
                </p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* Sources Grid */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Sources de Donnees
          </GlassCardTitle>
          <GlassCardDescription>
            Activez/desactivez les sources et lancez des collectes individuelles
          </GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {sources.map((source) => {
              const sStats = sourceStatsMap.get(source.id);
              const isThisRunning = isRunning && status?.current_source === source.id;
              return (
                <div
                  key={source.id}
                  className={cn(
                    'flex items-center gap-4 p-4 rounded-xl border transition-colors',
                    source.enabled
                      ? 'bg-card/50 border-border/50'
                      : 'bg-muted/30 border-border/30 opacity-60'
                  )}
                >
                  {/* Toggle */}
                  <Switch
                    checked={source.enabled}
                    onCheckedChange={(v) => toggleSource(source.id, v)}
                  />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-medium text-sm">{source.name}</span>
                      <Badge variant="outline" className={cn('text-[10px]', sourceTypeColors[source.type] || '')}>
                        {source.type}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] bg-muted/50 text-muted-foreground border-border/50">
                        {source.schedule}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{source.description}</p>
                  </div>

                  {/* Stats */}
                  <div className="hidden md:flex items-center gap-6 text-xs text-muted-foreground">
                    <div className="text-right">
                      <p className="font-medium text-foreground">
                        {sStats ? formatNumber(sStats.count) : '0'}
                      </p>
                      <p>signaux</p>
                    </div>
                    <div className="text-right min-w-[100px]">
                      <p className="font-medium text-foreground">
                        {sStats?.last_collected ? formatDate(sStats.last_collected) : '-'}
                      </p>
                      <p>derniere collecte</p>
                    </div>
                  </div>

                  {/* Run button */}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isRunning || !source.enabled}
                    onClick={() => triggerRun(source.id)}
                  >
                    {isThisRunning ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        </GlassCardContent>
      </GlassCard>

      {/* History */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Historique Recent
          </GlassCardTitle>
          <GlassCardDescription>Activite de collecte des 7 derniers jours</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Aucune activite recente
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium">Source</th>
                    <th className="text-left py-2 px-3 font-medium">Date</th>
                    <th className="text-right py-2 px-3 font-medium">Signaux</th>
                    <th className="text-right py-2 px-3 font-medium">Depts</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i} className="border-b border-border/30 hover:bg-muted/30 transition-colors">
                      <td className="py-2 px-3">
                        <Badge variant="outline" className="text-[10px]">
                          {h.source}
                        </Badge>
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">{formatDate(h.batch_time)}</td>
                      <td className="py-2 px-3 text-right font-medium">{formatNumber(h.count)}</td>
                      <td className="py-2 px-3 text-right text-muted-foreground">{h.departments}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCardContent>
      </GlassCard>

      {/* Error display */}
      {status?.error && (
        <GlassCard>
          <GlassCardContent className="p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-[var(--error)] shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-[var(--error)]">Erreur lors de la derniere collecte</p>
                <p className="text-xs text-muted-foreground mt-1 font-mono">{status.error}</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}
    </div>
  );
}
