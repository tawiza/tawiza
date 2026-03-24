'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Database,
  RefreshCw,
  Activity,
  Clock,
  BarChart3,
  CheckCircle,
  XCircle,
  FileText,
  Briefcase,
  Home,
  Building2,
  Newspaper,
  Globe,
  TrendingUp,
  Coins,
  Shield,
  HardHat,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

// ─── Types ───────────────────────────────────────────────────
interface SourceInfo {
  source: string;
  count: number;
  last_collected: string;
  status: string;
  departments?: number;
}

interface SchedulerStatus {
  running: boolean;
  jobs?: Array<{
    name: string;
    schedule: string;
    last_run?: string;
    next_run?: string;
  }>;
}

// ─── Source metadata ─────────────────────────────────────────
const SOURCE_META: Record<string, { label: string; description: string; icon: typeof Database; color: string }> = {
  bodacc: { label: 'BODACC', description: 'Annonces legales officielles (creations, liquidations, radiations)', icon: FileText, color: 'var(--chart-1)' },
  france_travail: { label: 'France Travail', description: 'Offres emploi CDI, CDD, missions (ex-Pole Emploi)', icon: Briefcase, color: 'var(--chart-2)' },
  sitadel: { label: 'Sitadel', description: 'Permis de construire, logements autorises/commences (SDES)', icon: HardHat, color: 'var(--chart-3)' },
  dvf: { label: 'DVF', description: 'Demandes de valeurs foncieres - transactions immobilieres', icon: Home, color: 'var(--chart-3)' },
  sirene: { label: 'SIRENE', description: 'Base entreprises INSEE (immatriculations)', icon: Building2, color: 'var(--chart-4)' },
  presse_locale: { label: 'Presse locale', description: 'Flux RSS presse regionale (sentiment, mots-cles)', icon: Newspaper, color: 'var(--error)' },
  insee: { label: 'INSEE', description: 'Statistiques demographiques et economiques', icon: BarChart3, color: 'hsl(var(--primary))' },
  google_trends: { label: 'Google Trends', description: "Tendances de recherche par departement", icon: TrendingUp, color: 'var(--info)' },
  ofgl: { label: 'OFGL', description: 'Finances des collectivites locales', icon: Coins, color: 'var(--chart-5)' },
  urssaf: { label: 'URSSAF', description: 'Donnees sociales, effectifs salaries', icon: Shield, color: 'var(--success)' },
  gdelt: { label: 'GDELT', description: 'Actualites internationales georeferoncees', icon: Globe, color: 'var(--warning)' },
  banque_france: { label: 'Banque de France', description: 'Indicateurs financiers et statistiques', icon: Coins, color: 'var(--error)' },
  commoncrawl: { label: 'Common Crawl', description: 'Archives web - analyse temporelle des sites entreprises', icon: Globe, color: 'var(--info)' },
};

function getSourceMeta(source: string) {
  return SOURCE_META[source] || { label: source, description: 'Source de donnees', icon: Database, color: 'hsl(var(--muted-foreground))' };
}

function formatTimeAgo(dateStr: string): string {
  if (!dateStr) return 'Jamais';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays > 0) return `Il y a ${diffDays}j`;
  if (diffHours > 0) return `Il y a ${diffHours}h`;
  if (diffMins > 0) return `Il y a ${diffMins}min`;
  return 'A l\'instant';
}

// ─── Component ───────────────────────────────────────────────
export default function SourcesTab() {
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [sourcesRes, schedulerRes] = await Promise.all([
        fetch('/api/collector/sources-summary').then(r => r.ok ? r.json() : null),
        fetch('/api/collector/scheduler/status').then(r => r.ok ? r.json() : null),
      ]);
      if (sourcesRes?.sources) {
        setSources(sourcesRes.sources);
      }
      if (schedulerRes) {
        setScheduler(schedulerRes);
      }
    } catch (err) {
      console.error('Error fetching sources:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const totalSignals = sources.reduce((s, src) => s + src.count, 0);
  const onlineSources = sources.filter(s => s.status === 'online').length;

  // Chart data sorted by count
  const chartData = [...sources]
    .sort((a, b) => b.count - a.count)
    .map(s => ({
      name: getSourceMeta(s.source).label,
      count: s.count,
      color: getSourceMeta(s.source).color,
    }));

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Database className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Total signaux</p>
              <p className="text-2xl font-bold">{totalSignals.toLocaleString('fr-FR')}</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Activity className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Sources actives</p>
              <p className="text-2xl font-bold">
                <span className="text-[var(--success)]">{onlineSources}</span>
                <span className="text-base text-muted-foreground">/{sources.length}</span>
              </p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Clock className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Scheduler</p>
              <p className="text-2xl font-bold">
                {scheduler?.running ? (
                  <span className="text-[var(--success)]">Actif</span>
                ) : (
                  <span className="text-[var(--error)]">Inactif</span>
                )}
              </p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <BarChart3 className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Departements</p>
                <p className="text-2xl font-bold">101</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={fetchData} disabled={loading}>
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>
          </div>
        </GlassCard>
      </div>

      {/* Chart */}
      <GlassCard>
        <GlassCardHeader className="pb-2">
          <GlassCardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4 text-primary" />
            Volume par source
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 10 }}>
                <XAxis type="number" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, color: 'hsl(var(--foreground))', fontSize: 12 }}
                  formatter={(value: number) => value.toLocaleString('fr-FR')}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[280px] text-muted-foreground">
              Chargement...
            </div>
          )}
        </GlassCardContent>
      </GlassCard>

      {/* Source Cards Grid */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sources.map(src => {
          const meta = getSourceMeta(src.source);
          const Icon = meta.icon;
          const isOnline = src.status === 'online';
          return (
            <GlassCard key={src.source} className="group hover:shadow-md transition-shadow">
              <GlassCardContent className="pt-5 pb-4">
                <div className="flex items-start gap-3">
                  <div
                    className="h-10 w-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: meta.color + '15' }}
                  >
                    <Icon className="h-5 w-5" style={{ color: meta.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-sm">{meta.label}</h3>
                      <Badge
                        variant="outline"
                        className={cn(
                          'text-[10px] px-1.5 py-0',
                          isOnline
                            ? 'bg-green-500/10 text-green-500 border-green-500/30'
                            : 'bg-red-500/10 text-red-500 border-red-500/30'
                        )}
                      >
                        {isOnline ? (
                          <><CheckCircle className="h-2.5 w-2.5 mr-1" />En ligne</>
                        ) : (
                          <><XCircle className="h-2.5 w-2.5 mr-1" />Hors ligne</>
                        )}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{meta.description}</p>

                    <div className="flex items-center gap-4 mt-3">
                      <div>
                        <p className="text-lg font-bold" style={{ color: meta.color }}>
                          {src.count.toLocaleString('fr-FR')}
                        </p>
                        <p className="text-[10px] text-muted-foreground">signaux</p>
                      </div>
                      {src.departments && (
                        <div>
                          <p className="text-lg font-bold">{src.departments}</p>
                          <p className="text-[10px] text-muted-foreground">depts</p>
                        </div>
                      )}
                      <div className="ml-auto text-right">
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTimeAgo(src.last_collected)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </GlassCardContent>
            </GlassCard>
          );
        })}
      </div>

      {/* Scheduler Jobs */}
      {scheduler?.jobs && scheduler.jobs.length > 0 && (
        <GlassCard>
          <GlassCardHeader className="pb-2">
            <GlassCardTitle className="flex items-center gap-2 text-base">
              <Clock className="h-4 w-4 text-primary" />
              Jobs planifies
              <Badge variant="secondary" className="text-[10px]">
                {scheduler.running ? 'Actif' : 'Inactif'}
              </Badge>
            </GlassCardTitle>
          </GlassCardHeader>
          <GlassCardContent>
            <div className="space-y-2">
              {scheduler.jobs.map((job, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                  <Activity className="h-4 w-4 text-primary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{job.name}</p>
                    <p className="text-xs text-muted-foreground">{job.schedule}</p>
                  </div>
                  {job.last_run && (
                    <span className="text-xs text-muted-foreground">
                      Dernier: {formatTimeAgo(job.last_run)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </GlassCardContent>
        </GlassCard>
      )}
    </div>
  );
}
