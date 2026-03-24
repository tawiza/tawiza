'use client';

import { useEffect, useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import {
  Database,
  AlertTriangle,
  Radio,
  TrendingUp,
  TrendingDown,
  PieChart as PieChartIcon,
  Clock,
  ArrowUp,
  ArrowDown,
  Zap,
  Radar as RadarIcon,
  Flame,
  Target,
  Shield,
  Activity,
  Eye,
  MapPin,
  Layers
} from 'lucide-react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardDescription
} from '@/components/ui/glass-card';
// Carousel removed - using grid layout
import DashboardLayout from '@/components/layout';
import { AnimatedCounter } from '@/components/ui/animated-counter';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar
} from 'recharts';

const FranceMap = dynamic(() => import('./FranceMap'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center bg-muted/30 rounded-lg">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
        <p className="text-sm text-muted-foreground">Chargement de la carte...</p>
      </div>
    </div>
  )
});

// ─── Types ───────────────────────────────────────────────────
interface SignalsSummary {
  by_source: Record<string, number>;
  by_department?: Record<string, number>;
  by_metric?: Record<string, number>;
  total: number;
  period_days?: number;
}

interface MicroSignal {
  id: number;
  territory_code: string;
  signal_type: string;
  sources: string[];
  dimensions: string[];
  score: number;
  confidence: number;
  impact: number;
  novelty: number;
  description: string;
  detected_at: string;
}

interface Convergence {
  territory_code: string;
  score: number;
  dimensions: string[];
  sources: string[];
  description: string;
  detected_at: string;
}

interface DepartmentScore {
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

interface SourceStatus {
  source: string;
  count: number;
  last_collected: string;
  status: string;
}

interface TimelineData {
  semaine: string;
  liquidations: number;
  creations: number;
  fermetures: number;
  [key: string]: number | string;
}

interface RecentSignal {
  id: number;
  source: string;
  code_dept: string;
  metric_name: string;
  signal_type: string;
  event_date: string;
  confidence: number;
}

// ─── Helpers ─────────────────────────────────────────────────
const DEPT_NAMES: Record<string, string> = {
  '01':'Ain','02':'Aisne','03':'Allier','04':'Alpes-de-Hte-Provence','05':'Hautes-Alpes',
  '06':'Alpes-Maritimes','07':'Ardèche','08':'Ardennes','09':'Ariège','10':'Aube',
  '11':'Aude','12':'Aveyron','13':'Bouches-du-Rhône','14':'Calvados','15':'Cantal',
  '16':'Charente','17':'Charente-Maritime','18':'Cher','19':'Corrèze','2A':'Corse-du-Sud',
  '2B':'Haute-Corse','21':"Côte-d'Or",'22':"Côtes-d'Armor",'23':'Creuse','24':'Dordogne',
  '25':'Doubs','26':'Drôme','27':'Eure','28':'Eure-et-Loir','29':'Finistère',
  '30':'Gard','31':'Haute-Garonne','32':'Gers','33':'Gironde','34':'Hérault',
  '35':'Ille-et-Vilaine','36':'Indre','37':'Indre-et-Loire','38':'Isère','39':'Jura',
  '40':'Landes','41':'Loir-et-Cher','42':'Loire','43':'Haute-Loire','44':'Loire-Atlantique',
  '45':'Loiret','46':'Lot','47':'Lot-et-Garonne','48':'Lozère','49':'Maine-et-Loire',
  '50':'Manche','51':'Marne','52':'Haute-Marne','53':'Mayenne','54':'Meurthe-et-Moselle',
  '55':'Meuse','56':'Morbihan','57':'Moselle','58':'Nièvre','59':'Nord',
  '60':'Oise','61':'Orne','62':'Pas-de-Calais','63':'Puy-de-Dôme','64':'Pyrénées-Atlantiques',
  '65':'Hautes-Pyrénées','66':'Pyrénées-Orientales','67':'Bas-Rhin','68':'Haut-Rhin','69':'Rhône',
  '70':'Haute-Saône','71':'Saône-et-Loire','72':'Sarthe','73':'Savoie','74':'Haute-Savoie',
  '75':'Paris','76':'Seine-Maritime','77':'Seine-et-Marne','78':'Yvelines','79':'Deux-Sèvres',
  '80':'Somme','81':'Tarn','82':'Tarn-et-Garonne','83':'Var','84':'Vaucluse',
  '85':'Vendée','86':'Vienne','87':'Haute-Vienne','88':'Vosges','89':'Yonne',
  '90':'Belfort','91':'Essonne','92':'Hauts-de-Seine','93':'Seine-Saint-Denis','94':'Val-de-Marne',
  '95':"Val-d'Oise",'971':'Guadeloupe','972':'Martinique','973':'Guyane','974':'Réunion',
  '976':'Mayotte'
};

function deptName(code: string): string {
  return DEPT_NAMES[code] || code;
}

async function fetchAPI<T>(endpoint: string): Promise<T | null> {
  try {
    const response = await fetch(`/api/collector${endpoint}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error(`Error fetching ${endpoint}:`, error);
    return null;
  }
}

async function fetchV1<T>(endpoint: string): Promise<T | null> {
  try {
    const response = await fetch(`/api/v1/signals${endpoint}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error(`Error fetching v1 ${endpoint}:`, error);
    return null;
  }
}

function timeAgo(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays > 0) return `${diffDays}j`;
  if (diffHours > 0) return `${diffHours}h`;
  return `${diffMins}min`;
}

const SOURCE_COLORS: Record<string, string> = {
  bodacc: 'var(--chart-1)', france_travail: 'var(--chart-2)', dvf: 'var(--chart-3)',
  sirene: 'var(--chart-4)', presse_locale: 'var(--chart-5)', google_trends: 'var(--info)',
  insee: 'hsl(var(--primary))', ofgl: 'var(--chart-5)', urssaf: 'var(--chart-4)',
};

// ─── Main Dashboard Component ────────────────────────────────
export default function Main() {
  const [signalsSummary, setSignalsSummary] = useState<SignalsSummary | null>(null);
  const [microSignals, setMicroSignals] = useState<MicroSignal[]>([]);
  const [convergences, setConvergences] = useState<Convergence[]>([]);
  const [deptScores, setDeptScores] = useState<DepartmentScore[]>([]);
  const [sourcesStatus, setSourcesStatus] = useState<SourceStatus[]>([]);
  const [timelineData, setTimelineData] = useState<TimelineData[]>([]);
  const [recentSignals, setRecentSignals] = useState<RecentSignal[]>([]);
  const [anomaliesV2, setAnomaliesV2] = useState<Array<{ department: string; risk_score: number; isolation_forest: string; cluster: string; convergence_score: number; nb_micro_signals: number }>>([]);
  const [clusters, setClusters] = useState<{ nb_clusters: number; nb_outliers: number; clusters: Array<{ id: number; departments: Array<{ code: string; risk_score: number }>; is_outlier_group: boolean; profile?: Record<string, number> }> } | null>(null);
  const [selectedDept, setSelectedDept] = useState('05');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [
          summaryRes,
          microRes,
          convRes,
          scoresRes,
          sourcesRes,
          timelineRes,
          signalsRes,
          anomV2Res,
          clustersRes,
        ] = await Promise.all([
          fetchAPI<SignalsSummary>('/signals/summary?period_days=30'),
          fetchV1<MicroSignal[]>('/microsignals'),
          fetchV1<Convergence[]>('/convergences'),
          fetchV1<DepartmentScore[]>('/departments/scores'),
          fetchAPI<{ sources: SourceStatus[] }>('/sources-summary'),
          fetchAPI<{ timeline: TimelineData[] }>('/timeline?days=30'),
          fetchAPI<{ signals: RecentSignal[] }>('/signals?limit=10'),
          fetchV1<{ count: number; results: typeof anomaliesV2 }>('/anomalies/v2?limit=20&min_risk=0.3'),
          fetchV1<typeof clusters>('/clusters'),
        ]);

        setSignalsSummary(summaryRes);
        setMicroSignals(Array.isArray(microRes) ? microRes : []);
        setConvergences(Array.isArray(convRes) ? convRes : []);
        setDeptScores(Array.isArray(scoresRes) ? scoresRes : []);
        setSourcesStatus(sourcesRes?.sources || []);
        setTimelineData(timelineRes?.timeline || []);
        setRecentSignals(signalsRes?.signals || []);
        setAnomaliesV2((anomV2Res as any)?.results || []);
        setClusters(clustersRes as any);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Derived data
  const signalDistribution = useMemo(() => {
    if (!signalsSummary?.by_source) return [];
    return Object.entries(signalsSummary.by_source)
      .map(([name, value]) => ({ name: name.replace('_', ' '), value, color: SOURCE_COLORS[name] || 'hsl(var(--muted-foreground))' }))
      .sort((a, b) => b.value - a.value);
  }, [signalsSummary]);

  const criticalCount = microSignals.filter(s => s.score >= 0.8).length;
  const totalSignals = signalsSummary?.total || 0;
  const sourcesOnline = sourcesStatus.filter(s => s.status === 'online').length;
  const totalSources = sourcesStatus.length || 9;

  // Top/bottom departments
  const sortedDepts = useMemo(() =>
    [...deptScores].sort((a, b) => b.score_composite - a.score_composite),
    [deptScores]
  );
  const top5 = sortedDepts.slice(0, 5);
  const bottom5 = sortedDepts.slice(-5).reverse();

  const scoreColor = (score: number) => {
    if (score >= 70) return 'text-green-400';
    if (score >= 50) return 'text-blue-400';
    if (score >= 30) return 'text-primary';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <DashboardLayout
        title="Tableau de bord"
        description="Intelligence territoriale"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => (
              <GlassCard key={i} className="h-24 skeleton" />
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <GlassCard className="lg:col-span-7 h-[400px] skeleton" />
            <GlassCard className="lg:col-span-5 h-[400px] skeleton" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <GlassCard className="h-[400px] skeleton" />
            <GlassCard className="h-[400px] skeleton" />
          </div>
          <GlassCard className="h-48 skeleton" />
        </div>
      </DashboardLayout>
    );
  }

  const selectedDeptData = deptScores.find(d => d.code_dept === selectedDept);
  const radarData = selectedDeptData ? [
    { axis: 'Santé Entrep.', value: selectedDeptData.alpha1_sante_entreprises ?? 0, fullMark: 100 },
    { axis: 'Tension Emploi', value: selectedDeptData.alpha2_tension_emploi ?? 0, fullMark: 100 },
    { axis: 'Dynamisme Immo', value: selectedDeptData.alpha3_dynamisme_immo ?? 0, fullMark: 100 },
    { axis: 'Santé Fin.', value: selectedDeptData.alpha4_sante_financiere ?? 0, fullMark: 100 },
    { axis: 'Ratio Déclin', value: selectedDeptData.alpha5_declin_ratio ?? 0, fullMark: 100 },
    { axis: 'Sentiment', value: selectedDeptData.alpha6_sentiment ?? 0, fullMark: 100 },
  ] : [];

  const tooltipStyle = {
    backgroundColor: 'hsl(var(--card))',
    border: '1px solid hsl(var(--border))',
    borderRadius: '8px',
    color: 'hsl(var(--foreground))',
    fontSize: '12px',
  };

  const srcColor: Record<string, string> = {
    bodacc: 'text-blue-400 bg-blue-500/10',
    france_travail: 'text-indigo-400 bg-indigo-500/10',
    dvf: 'text-purple-400 bg-purple-500/10',
    sirene: 'text-green-400 bg-green-500/10',
    presse_locale: 'text-pink-400 bg-pink-500/10',
    google_trends: 'text-cyan-400 bg-cyan-500/10',
    insee: 'text-blue-400 bg-blue-500/10',
    ofgl: 'text-blue-400 bg-blue-500/10',
    urssaf: 'text-teal-400 bg-teal-500/10',
  };

  return (
    <DashboardLayout
      title="Tableau de bord"
      description="Intelligence territoriale"
    >
      <div className="space-y-4">

        {/* ── KPI Strip ──────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Signaux', value: <AnimatedCounter value={totalSignals} />, icon: Database, color: 'text-primary', bg: 'bg-primary/10', sub: `${signalsSummary?.period_days || 30}j` },
            { label: 'Sources', value: <>{sourcesOnline}<span className="text-base text-muted-foreground">/{totalSources}</span></>, icon: Radio, color: 'text-green-500', bg: 'bg-green-500/10', sub: sourcesOnline === totalSources ? 'Toutes actives' : `${totalSources - sourcesOnline} hors ligne` },
            { label: 'Micro-signaux', value: <AnimatedCounter value={microSignals.length} />, icon: Zap, color: criticalCount > 0 ? 'text-red-500' : 'text-amber-500', bg: criticalCount > 0 ? 'bg-red-500/10' : 'bg-amber-500/10', sub: criticalCount > 0 ? `${criticalCount} critiques` : 'Aucun critique' },
            { label: 'Départements', value: '101', icon: Layers, color: 'text-primary', bg: 'bg-primary/10', sub: `${deptScores.length} analysés` },
          ].map(({ label, value, icon: Icon, color, bg, sub }) => (
            <GlassCard key={label} className="p-4">
              <div className="flex items-center gap-3">
                <div className={`h-10 w-10 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
                  <Icon className={`h-5 w-5 ${color}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
                  <p className="text-2xl font-bold text-foreground leading-tight">{value}</p>
                  <p className="text-[10px] text-muted-foreground">{sub}</p>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>

        {/* ── Anomaly Banner ──────────────────────────────────── */}
        {anomaliesV2.filter(a => a.risk_score >= 0.5).length > 0 && (
          <GlassCard className="border-red-500/30 bg-red-500/5">
            <GlassCardContent className="py-3 px-4">
              <div className="flex items-center gap-3 mb-2">
                <Shield className="h-5 w-5 text-red-400" />
                <span className="text-sm font-semibold text-red-400">Anomalies detectees</span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {anomaliesV2.filter(a => a.risk_score >= 0.5).length} departement{anomaliesV2.filter(a => a.risk_score >= 0.5).length > 1 ? 's' : ''}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {anomaliesV2.filter(a => a.risk_score >= 0.5).slice(0, 8).map(a => {
                  let contributing: Array<{ feature: string; z_score: number }> = [];
                  try { contributing = JSON.parse(a.isolation_forest)?.contributing || []; } catch {}
                  return (
                    <div key={a.department} className="flex items-center gap-1.5 bg-red-500/10 border border-red-500/20 rounded-lg px-2.5 py-1.5">
                      <span className="font-mono text-xs font-bold text-red-400">{a.department}</span>
                      <span className="text-xs text-muted-foreground">{deptName(a.department)}</span>
                      <span className="text-[10px] font-bold text-red-300 ml-1">{(a.risk_score * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </GlassCardContent>
          </GlassCard>
        )}

        {/* ── Row 1: Area Chart (7/12) + Pie Chart (5/12) ──── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <GlassCard className="lg:col-span-7">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-primary" />
                Evolution hebdomadaire
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="h-[340px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timelineData}>
                    <defs>
                      <linearGradient id="gradLiquidations" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--error)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--error)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradCreations" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--chart-4)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--chart-4)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradFermetures" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5} />
                    <XAxis
                      dataKey="semaine"
                      stroke="rgb(107,114,128)"
                      fontSize={11}
                      tickFormatter={(v) => new Date(v).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}
                    />
                    <YAxis stroke="rgb(107,114,128)" fontSize={11} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }} />
                    <Area type="monotone" dataKey="liquidations" stroke="var(--error)" fill="url(#gradLiquidations)" name="Liquidations" strokeWidth={2} />
                    <Area type="monotone" dataKey="creations" stroke="var(--chart-4)" fill="url(#gradCreations)" name="Creations" strokeWidth={2} />
                    <Area type="monotone" dataKey="fermetures" stroke="var(--chart-1)" fill="url(#gradFermetures)" name="Fermetures" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </GlassCardContent>
          </GlassCard>

          <GlassCard className="lg:col-span-5">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <PieChartIcon className="h-4 w-4 text-primary" />
                Repartition par source
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="h-[340px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={signalDistribution}
                      cx="50%"
                      cy="45%"
                      innerRadius={65}
                      outerRadius={105}
                      paddingAngle={3}
                      dataKey="value"
                      strokeWidth={0}
                    >
                      {signalDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(value: number) => value.toLocaleString('fr-FR')} />
                    <Legend verticalAlign="bottom" height={36} wrapperStyle={{ color: 'rgb(156, 163, 175)', fontSize: '11px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* ── Row 2: France Map (6/12) + Ranking (6/12) ────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GlassCard>
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <MapPin className="h-4 w-4 text-primary" />
                Carte des scores departementaux
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent className="h-[400px]">
              <FranceMap />
            </GlassCardContent>
          </GlassCard>

          <GlassCard>
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <RadarIcon className="h-4 w-4 text-primary" />
                Classement territorial
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 h-[370px]">
                {/* Radar */}
                <div className="flex flex-col">
                  <select
                    className="bg-muted/40 border border-border rounded-lg px-2 py-1.5 text-xs text-foreground mb-2 focus:outline-none focus:border-primary"
                    value={selectedDept}
                    onChange={(e) => setSelectedDept(e.target.value)}
                  >
                    {deptScores.map(d => (
                      <option key={d.code_dept} value={d.code_dept}>
                        {d.code_dept} — {deptName(d.code_dept)}
                      </option>
                    ))}
                  </select>
                  {selectedDeptData && (
                    <div className="text-center mb-1">
                      <span className={`text-3xl font-bold ${scoreColor(selectedDeptData.score_composite)}`}>
                        {selectedDeptData.score_composite.toFixed(1)}
                      </span>
                      <span className="text-xs text-muted-foreground">/100</span>
                    </div>
                  )}
                  <div className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="65%" data={radarData}>
                        <PolarGrid stroke="hsl(var(--border))" />
                        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 9, fill: 'rgb(156,163,175)' }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                        <Radar name="Score" dataKey="value" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} strokeWidth={2} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Top 5 */}
                <div className="overflow-y-auto">
                  <h4 className="text-xs font-medium text-green-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <ArrowUp className="h-3 w-3" /> Meilleurs
                  </h4>
                  <div className="space-y-1">
                    {top5.map((d, i) => (
                      <button
                        key={d.code_dept}
                        onClick={() => setSelectedDept(d.code_dept)}
                        className={`w-full flex items-center gap-2 p-2 rounded-lg text-left transition-colors ${
                          d.code_dept === selectedDept ? 'bg-primary/15 border border-primary/30' : 'bg-muted/20 hover:bg-muted/30'
                        }`}
                      >
                        <span className="text-[10px] text-muted-foreground w-4">{i + 1}</span>
                        <span className="font-mono text-[11px] text-primary w-7">{d.code_dept}</span>
                        <span className="text-xs text-foreground flex-1 truncate">{deptName(d.code_dept)}</span>
                        <span className={`text-xs font-bold ${scoreColor(d.score_composite)}`}>
                          {d.score_composite.toFixed(1)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Bottom 5 */}
                <div className="overflow-y-auto">
                  <h4 className="text-xs font-medium text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <ArrowDown className="h-3 w-3" /> Plus faibles
                  </h4>
                  <div className="space-y-1">
                    {bottom5.map((d, i) => (
                      <button
                        key={d.code_dept}
                        onClick={() => setSelectedDept(d.code_dept)}
                        className={`w-full flex items-center gap-2 p-2 rounded-lg text-left transition-colors ${
                          d.code_dept === selectedDept ? 'bg-primary/15 border border-primary/30' : 'bg-muted/20 hover:bg-muted/30'
                        }`}
                      >
                        <span className="text-[10px] text-muted-foreground w-4">{sortedDepts.length - bottom5.length + i + 1}</span>
                        <span className="font-mono text-[11px] text-primary w-7">{d.code_dept}</span>
                        <span className="text-xs text-foreground flex-1 truncate">{deptName(d.code_dept)}</span>
                        <span className={`text-xs font-bold ${scoreColor(d.score_composite)}`}>
                          {d.score_composite.toFixed(1)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* ── Row 3: Clusters (5/12) + Activity (7/12) ───────── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <GlassCard className="lg:col-span-5">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <Target className="h-4 w-4 text-primary" />
                Clusters economiques
              </GlassCardTitle>
              <GlassCardDescription>DBSCAN — profils similaires</GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="h-[280px] overflow-y-auto space-y-2 pr-1">
                {clusters ? (
                  <>
                    <div className="flex gap-2 mb-3">
                      <div className="bg-primary/10 border border-primary/20 rounded-lg px-3 py-2 text-center flex-1">
                        <p className="text-lg font-bold text-primary">{clusters.nb_clusters}</p>
                        <p className="text-[10px] text-muted-foreground">Clusters</p>
                      </div>
                      <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg px-3 py-2 text-center flex-1">
                        <p className="text-lg font-bold text-orange-400">{clusters.nb_outliers}</p>
                        <p className="text-[10px] text-muted-foreground">Outliers</p>
                      </div>
                    </div>
                    {clusters.clusters.map(cluster => (
                      <div key={cluster.id} className={`border rounded-lg p-2.5 ${cluster.is_outlier_group ? 'border-orange-500/30 bg-orange-500/5' : 'border-border bg-muted/10'}`}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={`text-xs font-bold ${cluster.is_outlier_group ? 'text-orange-400' : 'text-primary'}`}>
                            {cluster.is_outlier_group ? 'Outliers' : `Cluster ${cluster.id}`}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {cluster.departments.length} dept{cluster.departments.length > 1 ? 's' : ''}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {cluster.departments.slice(0, 15).map(d => (
                            <span key={d.code} className={`font-mono text-[10px] px-1.5 py-0.5 rounded ${
                              d.risk_score > 0.3 ? 'bg-red-500/15 text-red-400' : 'bg-muted/30 text-muted-foreground'
                            }`}>
                              {d.code}
                            </span>
                          ))}
                          {cluster.departments.length > 15 && (
                            <span className="text-[10px] text-muted-foreground">+{cluster.departments.length - 15}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <Target className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Clusters non disponibles</p>
                  </div>
                )}
              </div>
            </GlassCardContent>
          </GlassCard>

          <GlassCard className="lg:col-span-7">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4 text-primary" />
                Activite recente
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="h-[280px] overflow-y-auto space-y-1 pr-1">
                {recentSignals.slice(0, 10).map((signal, index) => (
                  <div key={signal.id || index} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-muted/10 hover:bg-muted/20 transition-colors text-sm">
                    <span className="text-xs text-muted-foreground min-w-[3rem]">
                      {signal.event_date ? new Date(signal.event_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '\u2014'}
                    </span>
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded min-w-[5rem] text-center ${srcColor[signal.source] || 'text-gray-400 bg-gray-500/10'}`}>
                      {signal.source.replace('_', ' ')}
                    </span>
                    <span className="font-mono text-xs text-primary min-w-[2rem]">
                      {signal.code_dept}
                    </span>
                    <span className="text-xs text-muted-foreground flex-1 truncate">
                      {signal.metric_name?.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[10px] bg-muted/30 px-1.5 py-0.5 rounded text-muted-foreground capitalize">
                      {signal.signal_type}
                    </span>
                  </div>
                ))}
                {recentSignals.length === 0 && (
                  <div className="text-center py-12 text-muted-foreground">
                    <Clock className="h-6 w-6 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Aucun signal recent</p>
                  </div>
                )}
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>

      </div>
    </DashboardLayout>
  );
}
