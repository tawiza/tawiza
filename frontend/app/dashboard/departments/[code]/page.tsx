'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout';
import {
  GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle, GlassCardDescription
} from '@/components/ui/glass-card';
import {
  Factory, Briefcase, Home, Coins, BarChart3, Newspaper,
  ArrowLeft, Zap, AlertTriangle, Flame, TrendingDown, TrendingUp,
  Activity, Radio, Users, MapPin, ChevronRight, Eye, MessageSquare
} from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  AreaChart, Area, CartesianGrid, Legend,
} from 'recharts';
import { Clock, Database, FileText } from 'lucide-react';
import { DEPT_NAMES } from '@/lib/departments';

// ─── Types ───────────────────────────────────────────────────
interface DeptScore {
  code_dept: string;
  score_composite: number;
  alpha1_sante_entreprises: number;
  alpha2_tension_emploi: number;
  alpha3_dynamisme_immo: number;
  alpha4_sante_financiere: number;
  alpha5_declin_ratio: number;
  alpha6_sentiment: number;
  population: number;
}

interface RadarData {
  code_dept: string;
  population: number;
  nb_signals: number;
  nb_microsignals: number;
  metrics: Record<string, { avg: number; count: number }>;
  microsignals: Array<{
    type: string;
    score: number;
    dimensions: string[];
    description: string;
  }>;
}

// ─── Constants ───────────────────────────────────────────────
const FACTORS = [
  { key: 'alpha1_sante_entreprises' as const, label: 'Santé Entreprises', color: 'var(--success)', Icon: Factory },
  { key: 'alpha2_tension_emploi' as const, label: 'Tension Emploi', color: 'var(--chart-1)', Icon: Briefcase },
  { key: 'alpha3_dynamisme_immo' as const, label: 'Dynamisme Immobilier', color: 'var(--chart-3)', Icon: Home },
  { key: 'alpha4_sante_financiere' as const, label: 'Santé Financière', color: 'var(--chart-5)', Icon: Coins },
  { key: 'alpha5_declin_ratio' as const, label: 'Ratio Déclin', color: 'var(--error)', Icon: BarChart3 },
  { key: 'alpha6_sentiment' as const, label: 'Sentiment Presse', color: 'var(--chart-2)', Icon: Newspaper },
];

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--success)';
  if (score >= 55) return 'var(--chart-4)';
  if (score >= 45) return 'var(--warning)';
  if (score >= 35) return 'var(--chart-5)';
  return 'var(--error)';
}

const TYPE_ICONS: Record<string, typeof AlertTriangle> = {
  anomaly: AlertTriangle, convergence: Flame, alert: Zap,
  trend_degradation: TrendingDown, trend_amelioration: TrendingUp,
};

// ─── Metric categorization ───────────────────────────────────
function categorizeMetrics(metrics: Record<string, { avg: number; count: number }>) {
  const categories: Record<string, Array<{ name: string; avg: number; count: number }>> = {
    'Entreprises (BODACC)': [],
    'Emploi (France Travail)': [],
    'Immobilier (DVF)': [],
    'Économie (SIRENE)': [],
    'Finances (OFGL)': [],
    'Presse locale': [],
    'Tendances (Google)': [],
    'Démographie (INSEE)': [],
    'Auto-entrepreneurs (URSSAF)': [],
  };

  for (const [key, val] of Object.entries(metrics)) {
    const cleanName = key.replace(/_/g, ' ').replace(/^(bodacc|france_travail|dvf|sirene|ofgl|presse_locale|google_trends|insee|urssaf)\s+/, '');
    if (key.startsWith('bodacc')) categories['Entreprises (BODACC)'].push({ name: cleanName, ...val });
    else if (key.startsWith('france_travail')) categories['Emploi (France Travail)'].push({ name: cleanName, ...val });
    else if (key.startsWith('dvf')) categories['Immobilier (DVF)'].push({ name: cleanName, ...val });
    else if (key.startsWith('sirene')) categories['Économie (SIRENE)'].push({ name: cleanName, ...val });
    else if (key.startsWith('ofgl')) categories['Finances (OFGL)'].push({ name: cleanName, ...val });
    else if (key.startsWith('presse')) categories['Presse locale'].push({ name: cleanName, ...val });
    else if (key.startsWith('google')) categories['Tendances (Google)'].push({ name: cleanName, ...val });
    else if (key.startsWith('insee')) categories['Démographie (INSEE)'].push({ name: cleanName, ...val });
    else if (key.startsWith('urssaf')) categories['Auto-entrepreneurs (URSSAF)'].push({ name: cleanName, ...val });
  }

  // Remove empty categories
  return Object.fromEntries(Object.entries(categories).filter(([_, v]) => v.length > 0));
}

// ─── Component ───────────────────────────────────────────────
export default function DepartmentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const code = params.code as string;

  const [deptScore, setDeptScore] = useState<DeptScore | null>(null);
  const [radarData, setRadarData] = useState<RadarData | null>(null);
  const [timeline, setTimeline] = useState<{ sources: string[]; timeline: any[] } | null>(null);
  const [recentSignals, setRecentSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    const fetchData = async () => {
      try {
        const [scoresRes, radarRes, timelineRes, recentRes] = await Promise.all([
          fetch('/api/v1/signals/departments/scores'),
          fetch(`/api/v1/signals/radar/${code}`),
          fetch(`/api/v1/signals/department/${code}/timeline?days=180`).catch(() => null),
          fetch(`/api/v1/signals/department/${code}/signals/recent?limit=15`).catch(() => null),
        ]);
        if (!scoresRes.ok || !radarRes.ok) throw new Error(`API error: scores=${scoresRes.status}, radar=${radarRes.status}`);
        const scores: DeptScore[] = await scoresRes.json();
        const radar: RadarData = await radarRes.json();
        setDeptScore((Array.isArray(scores) ? scores : []).find(d => d.code_dept === code) || null);
        setRadarData(radar);
        if (timelineRes?.ok) {
          const tlData = await timelineRes.json();
          setTimeline(tlData);
        }
        if (recentRes?.ok) {
          const rcData = await recentRes.json();
          setRecentSignals(Array.isArray(rcData) ? rcData : []);
        }
      } catch (e) {
        console.error('Error fetching department detail:', e);
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [code]);

  const name = DEPT_NAMES[code] || code;
  const score = deptScore?.score_composite ?? 0;

  // Radar chart data
  const radarChartData = deptScore ? FACTORS.map(f => ({
    axis: f.label.replace('Santé ', '').replace('Dynamisme ', '').replace('Tension ', '').replace('Ratio ', '').replace('Sentiment ', ''),
    value: (deptScore[f.key] as number) ?? 0,
    fullMark: 100,
  })) : [];

  // Categorized metrics
  const metricCategories = radarData ? categorizeMetrics(radarData.metrics) : {};

  if (loading) {
    return (
      <DashboardLayout title="Chargement..." description="">
        <div className="space-y-4">
          <GlassCard className="h-40 animate-pulse bg-muted/10" />
          <div className="grid grid-cols-2 gap-4">
            <GlassCard className="h-80 animate-pulse bg-muted/10" />
            <GlassCard className="h-80 animate-pulse bg-muted/10" />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout title={`${name} (${code})`} description="Fiche territoriale détaillée">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3 md:gap-4">
          <button
            onClick={() => router.push('/dashboard/departments')}
            className="p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors shrink-0"
          >
            <ArrowLeft className="h-5 w-5 text-muted-foreground" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-primary">{name}</h1>
            <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
              <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> Département {code}</span>
              {radarData?.population && (
                <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {Math.round(radarData.population).toLocaleString('fr-FR')} hab.</span>
              )}
              {radarData && (
                <span className="flex items-center gap-1"><Activity className="h-3.5 w-3.5" /> {radarData.nb_signals} signaux</span>
              )}
              {radarData && radarData.nb_microsignals > 0 && (
                <span className="flex items-center gap-1 text-red-400"><Zap className="h-3.5 w-3.5" /> {radarData.nb_microsignals} micro-signaux</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={`/dashboard/signals?dept=${code}`}
              onClick={(e) => { e.preventDefault(); router.push(`/dashboard/signals?dept=${code}`); }}
              className="flex items-center gap-2 px-3 md:px-4 py-2 bg-muted/30 hover:bg-muted/50 text-foreground rounded-lg text-sm font-medium transition-colors"
            >
              <FileText className="h-4 w-4" />
              <span className="hidden sm:inline">Voir les signaux</span>
              <span className="sm:hidden">Signaux</span>
            </a>
            <a
              href={`/dashboard/ai-chat`}
              onClick={(e) => { e.preventDefault(); router.push(`/dashboard/ai-chat`); }}
              className="flex items-center gap-2 px-3 md:px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg text-sm font-medium transition-colors"
            >
              <MessageSquare className="h-4 w-4" />
              <span className="hidden sm:inline">Analyser avec TAJINE</span>
              <span className="sm:hidden">TAJINE</span>
            </a>
            {deptScore && (
              <div className="text-right">
                <div className="text-4xl font-bold" style={{ color: scoreColor(score) }}>
                  {score.toFixed(1)}
                </div>
                <div className="text-xs text-muted-foreground">Score /100</div>
              </div>
            )}
          </div>
        </div>

        {/* Row 1: Radar + Factors */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Radar Chart */}
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-primary" />
                Radar 6 Dimensions
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarChartData}>
                    <PolarGrid stroke="rgba(255,255,255,0.1)" />
                    <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar name="Score" dataKey="value" stroke="var(--chart-5)" fill="var(--chart-5)" fillOpacity={0.25} strokeWidth={2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Factor detail cards */}
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                Détail des 6 Facteurs
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-4">
                {deptScore && FACTORS.map(f => {
                  const val = (deptScore[f.key] as number) ?? 0;
                  return (
                    <div key={f.key} className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <f.Icon className="h-4 w-4" style={{ color: f.color }} />
                          <span className="text-sm text-muted-foreground">{f.label}</span>
                        </div>
                        <span className="text-sm font-bold" style={{ color: val >= 60 ? f.color : val >= 40 ? 'hsl(var(--muted-foreground))' : 'var(--error)' }}>
                          {val.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-2 bg-muted/50 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${val}%`, backgroundColor: f.color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Row 2: Micro-signals */}
        {radarData && radarData.microsignals.length > 0 && (
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-red-500" />
                Micro-Signaux Actifs ({radarData.microsignals.length})
              </GlassCardTitle>
              <GlassCardDescription>Anomalies et alertes détectées sur ce territoire</GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {radarData.microsignals.map((m, i) => {
                  const TypeIcon = TYPE_ICONS[m.type] || AlertTriangle;
                  return (
                    <div key={i} className="p-4 rounded-xl bg-muted/30 border-l-4 transition-colors hover:bg-muted/50" style={{
                      borderColor: m.score >= 0.8 ? 'var(--error)' : m.score >= 0.5 ? 'var(--warning)' : 'var(--chart-5)'
                    }}>
                      <div className="flex items-center gap-2 mb-2">
                        <TypeIcon className="h-4 w-4" style={{ color: m.score >= 0.8 ? 'var(--error)' : 'var(--warning)' }} />
                        <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full" style={{
                          backgroundColor: m.score >= 0.8 ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                          color: m.score >= 0.8 ? 'var(--error)' : 'var(--warning)'
                        }}>
                          {m.type.replace('_', ' ')}
                        </span>
                        <span className="ml-auto font-bold text-sm" style={{ color: m.score >= 0.8 ? 'var(--error)' : 'var(--warning)' }}>
                          {(m.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {(m.description || '').replace(/^[^\w]*\d+:\s*/i, '')}
                      </p>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {m.dimensions.map(d => (
                          <span key={d} className="text-[10px] bg-muted/30 text-muted-foreground px-2 py-0.5 rounded-full">
                            {d}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCardContent>
          </GlassCard>
        )}

        {/* Row 3: Timeline Evolution */}
        {timeline && timeline.timeline.length > 0 && (
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Evolution temporelle (6 mois)
              </GlassCardTitle>
              <GlassCardDescription>Nombre de signaux par semaine et par source</GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={timeline.timeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="week"
                    tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    tickFormatter={(v) => new Date(v).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
                  />
                  <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                  <Tooltip
                    contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, color: 'hsl(var(--foreground))', fontSize: 12 }}
                    labelFormatter={(v) => new Date(v).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {timeline.sources.slice(0, 6).map((src, i) => {
                    const colors = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)', 'var(--error)'];
                    return (
                      <Area
                        key={src}
                        type="monotone"
                        dataKey={src}
                        stroke={colors[i % colors.length]}
                        fill={colors[i % colors.length]}
                        fillOpacity={0.1}
                        strokeWidth={2}
                        name={src.replace('_', ' ')}
                      />
                    );
                  })}
                </AreaChart>
              </ResponsiveContainer>
            </GlassCardContent>
          </GlassCard>
        )}

        {/* Row 3b: Recent Signals */}
        {recentSignals.length > 0 && (
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary" />
                Signaux recents
              </GlassCardTitle>
              <GlassCardDescription>Les {recentSignals.length} derniers signaux collectes</GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-1">
                {recentSignals.map((sig, i) => {
                  const srcColor: Record<string, string> = {
                    bodacc: 'text-blue-400 bg-blue-500/10', france_travail: 'text-indigo-400 bg-indigo-500/10',
                    dvf: 'text-purple-400 bg-purple-500/10', sirene: 'text-green-400 bg-green-500/10',
                    presse_locale: 'text-pink-400 bg-pink-500/10', google_trends: 'text-cyan-400 bg-cyan-500/10',
                    insee: 'text-blue-400 bg-blue-500/10', ofgl: 'text-blue-400 bg-blue-500/10',
                    urssaf: 'text-teal-400 bg-teal-500/10', sitadel: 'text-violet-400 bg-violet-500/10',
                  };
                  return (
                    <div key={sig.id || i} className="flex items-center gap-3 py-1.5 px-3 rounded-lg bg-muted/20 hover:bg-muted/30 transition text-sm">
                      <span className="text-xs text-muted-foreground min-w-[4rem]">
                        {sig.date ? new Date(sig.date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '\u2014'}
                      </span>
                      <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded min-w-[5.5rem] text-center ${srcColor[sig.source] || 'text-gray-400 bg-gray-500/10'}`}>
                        {sig.source.replace('_', ' ')}
                      </span>
                      <span className="text-xs text-muted-foreground flex-1 truncate">
                        {(sig.metric || '').replace(/_/g, ' ')}
                      </span>
                      {sig.value != null && (
                        <span className="text-xs font-mono text-foreground">
                          {sig.value >= 1000 ? `${(sig.value / 1000).toFixed(1)}k` : sig.value.toFixed(sig.value < 1 ? 2 : 0)}
                        </span>
                      )}
                      <span className="text-[10px] bg-muted/30 px-1.5 py-0.5 rounded text-muted-foreground capitalize">
                        {sig.type}
                      </span>
                    </div>
                  );
                })}
              </div>
            </GlassCardContent>
          </GlassCard>
        )}

        {/* Row 4: Metrics by category */}
        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle className="flex items-center gap-2">
              <Radio className="h-5 w-5 text-primary" />
              Métriques Collectées ({Object.keys(radarData?.metrics || {}).length} indicateurs)
            </GlassCardTitle>
            <GlassCardDescription>Données brutes par source — valeurs moyennes et occurrences</GlassCardDescription>
          </GlassCardHeader>
          <GlassCardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Object.entries(metricCategories).map(([category, items]) => (
                <div key={category} className="rounded-xl bg-muted/20 p-4">
                  <h4 className="text-xs font-medium text-primary uppercase tracking-wider mb-3">
                    {category}
                  </h4>
                  <div className="space-y-2">
                    {items.sort((a, b) => b.count - a.count).map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-[11px]">
                        <span className="text-muted-foreground truncate flex-1 mr-2" title={item.name}>
                          {item.name}
                        </span>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span className="text-foreground font-mono">
                            {item.avg >= 1000 ? `${(item.avg / 1000).toFixed(1)}k` :
                             item.avg >= 1 ? item.avg.toFixed(1) :
                             item.avg.toFixed(2)}
                          </span>
                          <span className="text-muted-foreground/60 text-[10px] min-w-[3rem] text-right">
                            ×{item.count}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </GlassCardContent>
        </GlassCard>
      </div>
    </DashboardLayout>
  );
}
