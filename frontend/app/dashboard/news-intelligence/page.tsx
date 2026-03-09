'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import DashboardLayout from '@/components/layout';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet';
import {
  GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle, GlassCardDescription,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Newspaper, Target, Activity, HeartPulse, Zap, Play, Square,
  RefreshCw, ExternalLink, Clock, TrendingUp, TrendingDown, Minus,
  AlertTriangle, CheckCircle2, Users, BarChart3, Layers,
  Search, X, LayoutDashboard, MapPin, ChevronDown, ChevronUp,
  Rss, Globe, Shield, Building2, Rocket, Monitor,
} from 'lucide-react';
import {
  useSentiments, useFocalPoints, useEnrichedArticles, useDepartmentHealth,
  useSpikes, useSchedulerStatus, useNewsStats, useArticleSearch,
  useSentimentTrends, useSentimentHeatmap,
  triggerIntelligenceRun, startScheduler, stopScheduler,
  type FocalPoint, type EnrichedArticle, type NewsArticle,
  type DepartmentHealth, type SpikeInfo,
  type SentimentTrendDay, type HeatmapFeed,
} from '@/lib/api-news';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  Tooltip as RTooltip, ResponsiveContainer, Cell,
} from 'recharts';

// ── Constants ────────────────────────────────────────────────────

const SENTIMENT_CFG: Record<string, { label: string; color: string; bg: string; Icon: typeof TrendingUp }> = {
  positif: { label: 'Positif', color: 'text-emerald-400', bg: 'bg-emerald-500/10', Icon: TrendingUp },
  negatif: { label: 'Negatif', color: 'text-red-400', bg: 'bg-red-500/10', Icon: TrendingDown },
  neutre:  { label: 'Neutre',  color: 'text-zinc-400', bg: 'bg-zinc-500/10', Icon: Minus },
};

const SEVERITY_CFG: Record<string, { color: string; bg: string }> = {
  low:      { color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  medium:   { color: 'text-orange-400', bg: 'bg-orange-500/10' },
  high:     { color: 'text-red-400', bg: 'bg-red-500/10' },
  critical: { color: 'text-red-500', bg: 'bg-red-500/20' },
};

const GRADE_COLORS: Record<string, string> = {
  A: 'text-emerald-400 bg-emerald-500/10', B: 'text-green-400 bg-green-500/10',
  C: 'text-yellow-400 bg-yellow-500/10', D: 'text-orange-400 bg-orange-500/10',
  E: 'text-red-400 bg-red-500/10', F: 'text-red-500 bg-red-500/20',
};

const CATEGORIES = [
  { value: 'eco_national', label: 'Eco National', icon: TrendingUp },
  { value: 'eco_regional', label: 'Eco Regional', icon: MapPin },
  { value: 'startups', label: 'Startups', icon: Rocket },
  { value: 'tech', label: 'Tech', icon: Monitor },
  { value: 'international', label: 'International', icon: Globe },
  { value: 'institutions', label: 'Institutions', icon: Building2 },
  { value: 'security', label: 'Securite', icon: Shield },
] as const;

const CAT_COLORS: Record<string, string> = {
  international: 'hsl(200, 80%, 55%)', eco_national: 'hsl(160, 70%, 50%)',
  startups: 'hsl(45, 90%, 55%)', eco_regional: 'hsl(280, 60%, 60%)',
  tech: 'hsl(330, 70%, 55%)', institutions: 'hsl(220, 60%, 55%)',
  security: 'hsl(0, 70%, 55%)',
};

const DEPT_NAMES: Record<string, string> = {
  '13': 'Bouches-du-Rhone', '59': 'Nord', '75': 'Paris', '69': 'Rhone',
  '31': 'Haute-Garonne', '33': 'Gironde', '34': 'Herault',
  '06': 'Alpes-Maritimes', '44': 'Loire-Atlantique', '67': 'Bas-Rhin',
};

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}j`;
}

// ── Main Page ────────────────────────────────────────────────────

export default function NewsIntelligencePage() {
  // ─ State
  const [tab, setTab] = useState('overview');
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [category, setCategory] = useState('all');
  const [sentiment, setSentiment] = useState('all');
  const [selectedFocal, setSelectedFocal] = useState<FocalPoint | null>(null);
  const [schedulerOpen, setSchedulerOpen] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  // ─ SWR hooks
  const { data: stats } = useNewsStats();
  const { data: sentiments, isLoading: loadingSentiments } = useSentiments();
  const { data: focalData, isLoading: loadingFocal } = useFocalPoints(48, 20);
  const { data: healthData, isLoading: loadingHealth } = useDepartmentHealth();
  const { data: spikesData } = useSpikes();
  const { data: scheduler, mutate: mutateScheduler } = useSchedulerStatus();

  const { data: trendsData } = useSentimentTrends(7);
  const { data: heatmapData } = useSentimentHeatmap(30);

  const isSearching = !!debounced;
  const sentimentParam = !isSearching && sentiment !== 'all' ? sentiment : undefined;
  const { data: enrichedArticles, isLoading: loadingEnriched } = useEnrichedArticles(sentimentParam, 50);
  const { data: searchArticles, isLoading: loadingSearch } = useArticleSearch(
    isSearching ? debounced : undefined, undefined, 50,
  );

  const rawArticles = (isSearching ? searchArticles : enrichedArticles) || [];
  const displayedArticles = useMemo(() => {
    let items = [...rawArticles];
    if (category !== 'all') items = items.filter(a => a.feed_category === category);
    if (isSearching && sentiment !== 'all') {
      items = items.filter(a => (a as EnrichedArticle).sentiment === sentiment);
    }
    return items;
  }, [rawArticles, category, sentiment, isSearching]);
  const loadingArticles = isSearching ? loadingSearch : loadingEnriched;

  // ─ Derived
  const sentimentDist = sentiments?.sentiment_distribution || {};
  const totalAnalyzed = Object.values(sentimentDist).reduce((a, b) => a + b, 0);
  const focalPoints = focalData?.focal_points || [];
  const departments = healthData?.departments || [];
  const spikes = spikesData?.active_spikes || [];

  // ─ Actions
  const handleRunOnce = useCallback(async () => {
    setRunning(true);
    try { await triggerIntelligenceRun(); mutateScheduler(); }
    finally { setRunning(false); }
  }, [mutateScheduler]);

  const handleToggleScheduler = useCallback(async () => {
    if (scheduler?.running) await stopScheduler(); else await startScheduler(6);
    mutateScheduler();
  }, [scheduler, mutateScheduler]);

  const goToArticles = useCallback((cat?: string, sent?: string) => {
    if (cat) setCategory(cat);
    if (sent) setSentiment(sent);
    setTab('articles');
  }, []);

  const clearFilters = useCallback(() => {
    setSearch(''); setDebounced(''); setCategory('all'); setSentiment('all');
  }, []);

  const hasFilters = search || category !== 'all' || sentiment !== 'all';

  // ─ Header
  const headerActions = (
    <div className="flex items-center gap-2">
      <Badge variant={scheduler?.running ? 'default' : 'outline'} className="hidden sm:flex gap-1 text-[10px]">
        {scheduler?.running ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
        {scheduler?.running ? 'Scheduler actif' : 'Scheduler arrete'}
      </Badge>
      <Button variant="outline" size="sm" onClick={handleRunOnce} disabled={running}>
        {running ? <RefreshCw className="h-4 w-4 mr-1.5 animate-spin" /> : <Play className="h-4 w-4 mr-1.5" />}
        {running ? 'Cycle...' : 'Lancer'}
      </Button>
      <Button variant={scheduler?.running ? 'destructive' : 'default'} size="sm" onClick={handleToggleScheduler}>
        {scheduler?.running ? <><Square className="h-4 w-4 mr-1.5" />Stop</> : <><Play className="h-4 w-4 mr-1.5" />Start</>}
      </Button>
    </div>
  );

  return (
    <DashboardLayout
      title="News Intelligence"
      description="Pipeline : RSS → IA → Focal Points → Alertes"
      headerActions={headerActions}
    >
      <div className="space-y-4">
        {/* ── Filter Bar ─────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher dans les articles..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-[160px] h-9">
              <SelectValue placeholder="Categorie" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes categories</SelectItem>
              {CATEGORIES.map(c => (
                <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sentiment} onValueChange={setSentiment}>
            <SelectTrigger className="w-[140px] h-9">
              <SelectValue placeholder="Sentiment" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous sentiments</SelectItem>
              {Object.entries(SENTIMENT_CFG).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2">
              <X className="h-4 w-4 mr-1" />Effacer
            </Button>
          )}
        </div>

        {/* ── KPI Row ────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPICard title="Articles" value={stats?.total_articles ?? '—'}
            sub={`${stats?.last_24h ?? 0} dernières 24h`} icon={Newspaper} glow="cyan" />
          <KPICard title="Analyses" value={totalAnalyzed || '—'}
            sub={stats?.total_articles ? `${Math.round((totalAnalyzed / stats.total_articles) * 100)}% couverture` : 'Aucun'}
            icon={BarChart3} glow={totalAnalyzed > 0 ? 'green' : 'yellow'} />
          <KPICard title="Focal Points" value={focalData?.count ?? '—'}
            sub={focalPoints[0] ? `Top: ${focalPoints[0].entity}` : 'Aucun detecte'}
            icon={Target} glow="cyan" />
          <KPICard title="Sources" value={stats?.feeds_active ?? '—'}
            sub={`${stats?.breakers_open ?? 0} circuit-breakers ouverts`}
            icon={Rss} glow={stats?.breakers_open ? 'yellow' : 'green'} />
        </div>

        {/* ── Spike Alert ────────────────────────────────── */}
        {spikes.length > 0 && (
          <GlassCard glow="red">
            <div className="flex items-center gap-3 p-1">
              <Zap className="h-5 w-5 text-red-400 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium">{spikes.length} spike{spikes.length > 1 ? 's' : ''} detecte{spikes.length > 1 ? 's' : ''}</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {spikes.map((s: SpikeInfo, i: number) => {
                    const cfg = SEVERITY_CFG[s.severity] || SEVERITY_CFG.low;
                    return (
                      <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                        {s.stream.replace('news_', '')}: z={s.z_score.toFixed(1)}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          </GlassCard>
        )}

        {/* ── Tabs ───────────────────────────────────────── */}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-card border">
            <TabsTrigger value="overview" className="gap-1.5 text-xs">
              <LayoutDashboard className="h-3.5 w-3.5" />Vue d&apos;ensemble
            </TabsTrigger>
            <TabsTrigger value="articles" className="gap-1.5 text-xs">
              <Newspaper className="h-3.5 w-3.5" />Articles
              {displayedArticles.length > 0 && (
                <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{displayedArticles.length}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="focal" className="gap-1.5 text-xs">
              <Target className="h-3.5 w-3.5" />Points focaux
            </TabsTrigger>
            <TabsTrigger value="territories" className="gap-1.5 text-xs">
              <MapPin className="h-3.5 w-3.5" />Territoires
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4 space-y-4">
            <OverviewTab
              stats={stats}
              sentimentDist={sentimentDist}
              totalAnalyzed={totalAnalyzed}
              loadingSentiments={loadingSentiments}
              goToArticles={goToArticles}
              trends={trendsData?.trends}
              heatmapFeeds={heatmapData?.feeds}
            />
          </TabsContent>

          <TabsContent value="articles" className="mt-4">
            <ArticlesTab articles={displayedArticles} loading={loadingArticles} isSearching={isSearching} />
          </TabsContent>

          <TabsContent value="focal" className="mt-4">
            <FocalPointsTab
              focalPoints={focalPoints}
              loading={loadingFocal}
              onSelect={setSelectedFocal}
            />
          </TabsContent>

          <TabsContent value="territories" className="mt-4">
            <TerritoriesTab departments={departments} loading={loadingHealth} />
          </TabsContent>
        </Tabs>

        {/* ── Scheduler Panel (collapsible) ──────────────── */}
        <GlassCard>
          <button
            className="w-full flex items-center justify-between p-1"
            onClick={() => setSchedulerOpen(!schedulerOpen)}
          >
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">Pipeline d&apos;intelligence</span>
              {scheduler?.last_run && (
                <span className="text-xs text-muted-foreground">
                  Dernier cycle: {timeAgo(scheduler.last_run)} — #{scheduler.run_count}
                </span>
              )}
            </div>
            {schedulerOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {schedulerOpen && scheduler?.last_result && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries((scheduler.last_result.steps as Record<string, unknown>) || {}).map(([step, data]) => (
                  <div key={step} className="p-2.5 rounded-lg bg-muted/10 border border-border">
                    <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{step.replace(/_/g, ' ')}</p>
                    <div className="mt-1">
                      {typeof data === 'object' && data !== null ? (
                        (data as Record<string, unknown>).error ? (
                          <span className="text-red-400 text-xs">{String((data as Record<string, unknown>).error).slice(0, 80)}</span>
                        ) : (
                          <pre className="text-[11px] text-muted-foreground overflow-hidden whitespace-pre-wrap leading-relaxed">
                            {JSON.stringify(data, null, 1).slice(0, 200)}
                          </pre>
                        )
                      ) : <span className="text-xs">{String(data)}</span>}
                    </div>
                  </div>
                ))}
              </div>
              {(scheduler.last_result as Record<string, unknown>).elapsed_seconds && (
                <p className="text-xs text-muted-foreground mt-2">
                  Duree: {String((scheduler.last_result as Record<string, unknown>).elapsed_seconds)}s
                </p>
              )}
            </div>
          )}
        </GlassCard>
      </div>

      {/* ── Focal Point Detail Sheet ─────────────────── */}
      <Sheet open={!!selectedFocal} onOpenChange={open => !open && setSelectedFocal(null)}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          {selectedFocal && <FocalPointDetail fp={selectedFocal} />}
        </SheetContent>
      </Sheet>
    </DashboardLayout>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────

function KPICard({ title, value, sub, icon: Icon, glow }: {
  title: string; value: string | number; sub: string;
  icon: typeof Newspaper; glow?: 'cyan' | 'green' | 'yellow' | 'red' | 'none';
}) {
  return (
    <GlassCard glow={glow}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold mt-0.5">{value}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>
        </div>
        <div className="p-2 rounded-lg bg-muted/20">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
    </GlassCard>
  );
}

// ── Overview Tab ─────────────────────────────────────────────────

function OverviewTab({ stats, sentimentDist, totalAnalyzed, loadingSentiments, goToArticles, trends, heatmapFeeds }: {
  stats: ReturnType<typeof useNewsStats>['data'];
  sentimentDist: Record<string, number>;
  totalAnalyzed: number;
  loadingSentiments: boolean;
  goToArticles: (cat?: string, sent?: string) => void;
  trends?: SentimentTrendDay[];
  heatmapFeeds?: HeatmapFeed[];
}) {
  return (
    <div className="space-y-4">
      {/* Timeline */}
      <GlassCard>
        <GlassCardHeader className="pb-2">
          <GlassCardTitle className="text-sm flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />Timeline des publications (48h)
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <HourlyChart data={stats?.hourly_distribution} />
        </GlassCardContent>
      </GlassCard>

      {/* Sentiment Trend (Phase 2) */}
      <GlassCard>
        <GlassCardHeader className="pb-2">
          <GlassCardTitle className="text-sm flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />Evolution du sentiment (7 jours)
          </GlassCardTitle>
          <GlassCardDescription>
            Tendance positif / neutre / negatif par jour
          </GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <SentimentTrendChart data={trends} />
        </GlassCardContent>
      </GlassCard>

      {/* Categories + Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <GlassCard className="h-full">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="text-sm flex items-center gap-2">
                <Layers className="h-4 w-4 text-primary" />Repartition par categorie
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <CategoryChart data={stats?.by_category} onCategoryClick={cat => goToArticles(cat)} />
            </GlassCardContent>
          </GlassCard>
        </div>
        <div className="lg:col-span-2">
          <GlassCard className="h-full">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />Sentiment
              </GlassCardTitle>
              <GlassCardDescription>{totalAnalyzed} articles analyses</GlassCardDescription>
            </GlassCardHeader>
            <GlassCardContent>
              {loadingSentiments ? (
                <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-10" />)}</div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(SENTIMENT_CFG).map(([key, cfg]) => {
                    const count = sentimentDist[key] || 0;
                    const pct = totalAnalyzed > 0 ? (count / totalAnalyzed) * 100 : 0;
                    return (
                      <button
                        key={key}
                        onClick={() => goToArticles(undefined, key)}
                        className="w-full flex items-center gap-3 p-2.5 rounded-lg transition-colors hover:bg-muted/30"
                      >
                        <cfg.Icon className={`h-4 w-4 ${cfg.color} shrink-0`} />
                        <span className="text-sm flex-1 text-left">{cfg.label}</span>
                        <span className={`text-sm font-mono font-bold ${cfg.color}`}>{count}</span>
                        <div className="w-24 h-2 bg-muted/30 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-700 ${
                              key === 'positif' ? 'bg-emerald-500' : key === 'negatif' ? 'bg-red-500' : 'bg-zinc-500'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground w-8 text-right">{pct.toFixed(0)}%</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>

      {/* Source Heatmap (Phase 2) */}
      <GlassCard>
        <GlassCardHeader className="pb-2">
          <GlassCardTitle className="text-sm flex items-center gap-2">
            <Rss className="h-4 w-4 text-primary" />Heatmap Sources x Sentiment
          </GlassCardTitle>
          <GlassCardDescription>
            Tonalite par source (30 derniers jours)
          </GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <SourceHeatmap feeds={heatmapFeeds} />
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}

// ── Articles Tab ─────────────────────────────────────────────────

type DisplayArticle = (EnrichedArticle | NewsArticle) & { ai_summary?: string; sentiment?: string };

function ArticlesTab({ articles, loading, isSearching }: {
  articles: DisplayArticle[];
  loading: boolean;
  isSearching: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="text-center py-16">
        <Newspaper className="h-10 w-10 text-muted-foreground/30 mx-auto" />
        <p className="text-sm text-muted-foreground mt-3">
          {isSearching ? 'Aucun article trouve pour cette recherche.' : 'Aucun article enrichi. Lancez un cycle d\'intelligence.'}
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[calc(100vh-380px)]">
      <div className="space-y-2 pr-3">
        {articles.map((a: DisplayArticle) => {
          const sent = a.sentiment ? SENTIMENT_CFG[a.sentiment] : null;
          const summary = a.ai_summary || (a as NewsArticle).summary;
          return (
            <GlassCard key={a.id} hoverGlow>
              <div className="p-1">
                <div className="flex items-start justify-between gap-3">
                  <a href={a.url} target="_blank" rel="noopener noreferrer"
                    className="text-sm font-medium hover:text-primary transition-colors line-clamp-2 flex-1">
                    {a.title}
                  </a>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {sent ? (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${sent.bg} ${sent.color} font-medium`}>
                        {sent.label}
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted/30 text-muted-foreground">
                        Non analyse
                      </span>
                    )}
                    <a href={a.url} target="_blank" rel="noopener noreferrer"
                      className="p-1 rounded hover:bg-muted/30 transition-colors">
                      <ExternalLink className="h-3 w-3 text-muted-foreground" />
                    </a>
                  </div>
                </div>
                {summary && (
                  <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">{summary}</p>
                )}
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  {a.feed_category && (
                    <Badge variant="outline" className="text-[10px] py-0 h-5"
                      style={{ borderColor: CAT_COLORS[a.feed_category] || undefined,
                               color: CAT_COLORS[a.feed_category] || undefined }}>
                      {a.feed_category.replace(/_/g, ' ')}
                    </Badge>
                  )}
                  <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                    {a.feed_name || a.source}
                  </span>
                  {a.published_at && (
                    <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                      <Clock className="h-2.5 w-2.5" />{timeAgo(a.published_at)}
                    </span>
                  )}
                  {a.ai_summary && (
                    <Badge variant="secondary" className="text-[10px] py-0 h-5 gap-0.5">
                      <Zap className="h-2.5 w-2.5" />IA
                    </Badge>
                  )}
                </div>
              </div>
            </GlassCard>
          );
        })}
      </div>
    </ScrollArea>
  );
}

// ── Focal Points Tab ─────────────────────────────────────────────

function FocalPointsTab({ focalPoints, loading, onSelect }: {
  focalPoints: FocalPoint[];
  loading: boolean;
  onSelect: (fp: FocalPoint) => void;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-32 rounded-lg" />)}
      </div>
    );
  }

  if (focalPoints.length === 0) {
    return (
      <div className="text-center py-16">
        <Target className="h-10 w-10 text-muted-foreground/30 mx-auto" />
        <p className="text-sm text-muted-foreground mt-3">Aucun point focal detecte sur les dernieres 48h.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {focalPoints.map((fp, i) => (
        <GlassCard key={fp.entity} hoverGlow>
          <button className="w-full text-left p-1" onClick={() => onSelect(fp)}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-muted-foreground/60">#{i + 1}</span>
                  <span className="text-sm font-semibold truncate">{fp.entity}</span>
                  {fp.is_known_actor && (
                    <Badge variant="default" className="text-[10px] py-0 h-4 shrink-0">Graphe</Badge>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Users className="h-3 w-3" />{fp.source_count} sources</span>
                  <span>{fp.mention_count} mentions</span>
                </div>
                {fp.actor && (
                  <p className="text-xs text-primary/70 mt-1.5 truncate">{fp.actor.actor_name} ({fp.actor.actor_type})</p>
                )}
              </div>
              <div className="text-right shrink-0">
                <div className={`text-2xl font-bold ${
                  fp.score >= 80 ? 'text-red-400' : fp.score >= 50 ? 'text-yellow-400' : 'text-zinc-400'
                }`}>{fp.score}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">score</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {fp.sources.slice(0, 5).map(s => (
                <span key={s} className="text-[10px] px-2 py-0.5 bg-muted/30 rounded-full text-muted-foreground truncate max-w-[130px]">{s}</span>
              ))}
              {fp.sources.length > 5 && (
                <span className="text-[10px] text-muted-foreground">+{fp.sources.length - 5}</span>
              )}
            </div>
          </button>
        </GlassCard>
      ))}
    </div>
  );
}

// ── Focal Point Detail (Sheet) ───────────────────────────────────

function FocalPointDetail({ fp }: { fp: FocalPoint }) {
  return (
    <>
      <SheetHeader>
        <SheetTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          {fp.entity}
        </SheetTitle>
        <SheetDescription>
          Score: {fp.score} — {fp.source_count} sources, {fp.mention_count} mentions
        </SheetDescription>
      </SheetHeader>

      <div className="mt-6 space-y-6">
        {/* Score visual */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Score de convergence</span>
            <span className={`text-lg font-bold ${
              fp.score >= 80 ? 'text-red-400' : fp.score >= 50 ? 'text-yellow-400' : 'text-zinc-400'
            }`}>{fp.score}/100</span>
          </div>
          <div className="w-full h-2.5 bg-muted/30 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                fp.score >= 80 ? 'bg-red-500' : fp.score >= 50 ? 'bg-yellow-500' : 'bg-zinc-500'
              }`}
              style={{ width: `${fp.score}%` }}
            />
          </div>
        </div>

        {/* Actor link */}
        {fp.actor && (
          <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
            <p className="text-xs font-medium text-primary mb-1">Acteur lie au graphe</p>
            <p className="text-sm font-semibold">{fp.actor.actor_name}</p>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span>Type: {fp.actor.actor_type}</span>
              <span>Dept: {fp.actor.department}</span>
            </div>
          </div>
        )}

        {/* Sources */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Sources ({fp.source_count})</p>
          <div className="flex flex-wrap gap-1.5">
            {fp.sources.map(s => (
              <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
            ))}
          </div>
        </div>

        {/* Articles */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Articles lies ({fp.articles.length})</p>
          <div className="space-y-2">
            {fp.articles.map(a => (
              <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer"
                className="block p-2.5 rounded-lg border border-border hover:border-primary/30 transition-colors">
                <p className="text-sm font-medium line-clamp-2 hover:text-primary transition-colors">{a.title}</p>
                <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted-foreground">
                  <span>{a.feed}</span>
                  {a.published_at && <span className="flex items-center gap-0.5"><Clock className="h-2.5 w-2.5" />{timeAgo(a.published_at)}</span>}
                  <ExternalLink className="h-2.5 w-2.5 ml-auto" />
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Territories Tab ──────────────────────────────────────────────

function TerritoriesTab({ departments, loading }: {
  departments: DepartmentHealth[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1,2,3].map(i => <Skeleton key={i} className="h-48 rounded-lg" />)}
      </div>
    );
  }

  if (departments.length === 0) {
    return (
      <div className="text-center py-16">
        <MapPin className="h-10 w-10 text-muted-foreground/30 mx-auto" />
        <p className="text-sm text-muted-foreground mt-3">Aucun departement evalue.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {departments.map((d: DepartmentHealth) => {
        const gradeCls = GRADE_COLORS[d.grade] || 'text-zinc-400 bg-zinc-500/10';
        const b = d.components?.baseline;
        const e = d.components?.events;
        const bo = d.components?.boosts;
        return (
          <GlassCard key={d.department}>
            <div className="p-1">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-semibold">Dept {d.department}</p>
                  <p className="text-xs text-muted-foreground">{DEPT_NAMES[d.department] || ''}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-bold px-2.5 py-0.5 rounded-lg ${gradeCls}`}>{d.grade}</span>
                </div>
              </div>

              {/* Score bar */}
              <div className="flex items-center gap-2 mb-4">
                <div className="flex-1 h-2.5 bg-muted/30 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      d.score >= 70 ? 'bg-emerald-500' : d.score >= 50 ? 'bg-yellow-500' : d.score >= 30 ? 'bg-orange-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${d.score}%` }}
                  />
                </div>
                <span className="text-sm font-mono font-bold w-10 text-right">{d.score}</span>
              </div>

              {/* Component breakdown */}
              {b && e && bo && (
                <div className="space-y-2">
                  <ComponentBar label="Baseline" score={b.score} weight="40%" color="bg-blue-500" />
                  <ComponentBar label="Events" score={e.score} weight="60%" color="bg-amber-500" />
                  {bo.total > 0 && <ComponentBar label="Boosts" score={bo.total} weight="" color="bg-purple-500" />}
                </div>
              )}

              {/* Stats */}
              {b && e && (
                <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-border">
                  <MiniStat label="Acteurs" value={b.actor_count} />
                  <MiniStat label="Relations" value={b.relation_count} />
                  <MiniStat label="News 48h" value={e.news_48h} />
                </div>
              )}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}

function ComponentBar({ label, score, weight, color }: {
  label: string; score: number; weight: string; color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground w-16">{label} {weight && <span className="opacity-60">({weight})</span>}</span>
      <div className="flex-1 h-1.5 bg-muted/20 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(score, 100)}%` }} />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground w-8 text-right">{score.toFixed(0)}</span>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className="text-sm font-bold">{value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}

// ── Chart: Hourly Timeline ───────────────────────────────────────

function HourlyChart({ data }: { data?: { hour: string; count: number }[] }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.map(d => ({
      hour: new Date(d.hour).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
      date: new Date(d.hour).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
      articles: d.count,
    }));
  }, [data]);

  if (chartData.length === 0) {
    return <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">Pas de donnees</div>;
  }

  return (
    <div className="h-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 0, left: -15 }}>
          <defs>
            <linearGradient id="timelineGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(200, 80%, 55%)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(200, 80%, 55%)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} allowDecimals={false} />
          <RTooltip
            contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
            formatter={(value: number) => [`${value} articles`, 'Volume']}
            labelFormatter={(label: string, payload: unknown[]) => {
              const p = payload as { payload?: { date?: string } }[];
              return p[0]?.payload?.date ? `${p[0].payload.date} ${label}` : label;
            }}
          />
          <Area type="monotone" dataKey="articles" stroke="hsl(200, 80%, 55%)" strokeWidth={2} fill="url(#timelineGrad)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart: Sentiment Trend (Phase 2) ────────────────────────────

function SentimentTrendChart({ data }: { data?: SentimentTrendDay[] }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.map(d => ({
      date: new Date(d.date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
      Positif: d.positif,
      Negatif: d.negatif,
      Neutre: d.neutre,
    }));
  }, [data]);

  if (chartData.length === 0) {
    return <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">Pas de donnees de tendance</div>;
  }

  return (
    <div className="h-[220px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 0, left: -15 }}>
          <defs>
            <linearGradient id="gradPos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0.4} />
              <stop offset="100%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradNeg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0.4} />
              <stop offset="100%" stopColor="hsl(0, 72%, 51%)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradNeu" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(240, 5%, 65%)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(240, 5%, 65%)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} allowDecimals={false} />
          <RTooltip
            contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
          />
          <Area type="monotone" dataKey="Positif" stackId="1" stroke="hsl(160, 84%, 39%)" strokeWidth={2} fill="url(#gradPos)" />
          <Area type="monotone" dataKey="Neutre" stackId="1" stroke="hsl(240, 5%, 65%)" strokeWidth={1.5} fill="url(#gradNeu)" />
          <Area type="monotone" dataKey="Negatif" stackId="1" stroke="hsl(0, 72%, 51%)" strokeWidth={2} fill="url(#gradNeg)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart: Source Heatmap (Phase 2) ─────────────────────────────

function SourceHeatmap({ feeds }: { feeds?: HeatmapFeed[] }) {
  if (!feeds || feeds.length === 0) {
    return <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">Pas de donnees heatmap</div>;
  }

  const maxTotal = Math.max(...feeds.map(f => f.total));

  return (
    <div className="space-y-1">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] text-muted-foreground w-[140px] shrink-0">Source</span>
        <div className="flex-1 grid grid-cols-3 gap-1 text-center">
          <span className="text-[10px] text-emerald-400 font-medium">Positif</span>
          <span className="text-[10px] text-zinc-400 font-medium">Neutre</span>
          <span className="text-[10px] text-red-400 font-medium">Negatif</span>
        </div>
        <span className="text-[10px] text-muted-foreground w-10 text-right shrink-0">Total</span>
      </div>

      {/* Rows */}
      {feeds.slice(0, 15).map(f => {
        const posPct = f.total > 0 ? (f.positif / f.total) * 100 : 0;
        const neuPct = f.total > 0 ? (f.neutre / f.total) * 100 : 0;
        const negPct = f.total > 0 ? (f.negatif / f.total) * 100 : 0;
        const intensity = f.total / maxTotal;

        return (
          <div key={f.feed_name} className="flex items-center gap-2 py-1 group hover:bg-muted/10 rounded-md transition-colors">
            <span className="text-[11px] text-muted-foreground w-[140px] shrink-0 truncate" title={f.feed_name}>
              {f.feed_name}
            </span>
            <div className="flex-1 grid grid-cols-3 gap-1">
              <HeatCell value={f.positif} pct={posPct} color="emerald" intensity={intensity} />
              <HeatCell value={f.neutre} pct={neuPct} color="zinc" intensity={intensity} />
              <HeatCell value={f.negatif} pct={negPct} color="red" intensity={intensity} />
            </div>
            <span className="text-[11px] font-mono text-muted-foreground w-10 text-right shrink-0">{f.total}</span>
          </div>
        );
      })}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 pt-2 border-t border-border justify-end">
        <span className="text-[10px] text-muted-foreground">Intensite:</span>
        {[0.2, 0.5, 0.8, 1].map(v => (
          <div key={v} className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: `hsla(200, 80%, 55%, ${v * 0.6})` }} />
            <span className="text-[9px] text-muted-foreground">{Math.round(v * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeatCell({ value, pct, color, intensity }: {
  value: number; pct: number; color: 'emerald' | 'zinc' | 'red'; intensity: number;
}) {
  const hues = { emerald: '160, 84%, 39%', zinc: '240, 5%, 65%', red: '0, 72%, 51%' };
  const opacity = value > 0 ? Math.max(0.15, intensity * (pct / 100) * 0.8) : 0.03;
  return (
    <div
      className="h-7 rounded-sm flex items-center justify-center transition-colors"
      style={{ backgroundColor: `hsla(${hues[color]}, ${opacity})` }}
      title={`${value} articles (${pct.toFixed(0)}%)`}
    >
      {value > 0 && <span className="text-[10px] font-mono opacity-90">{value}</span>}
    </div>
  );
}

// ── Chart: Category Distribution ─────────────────────────────────

function CategoryChart({ data, onCategoryClick }: {
  data?: Record<string, number>;
  onCategoryClick?: (category: string) => void;
}) {
  const chartData = useMemo(() => {
    if (!data) return [];
    return Object.entries(data)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8)
      .map(([name, count]) => ({
        name: name.replace(/_/g, ' '),
        key: name,
        articles: count,
        fill: CAT_COLORS[name] || 'hsl(var(--muted-foreground))',
      }));
  }, [data]);

  if (chartData.length === 0) {
    return <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">Pas de donnees</div>;
  }

  return (
    <div className="h-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, bottom: 0, left: 0 }}
          onClick={(e) => e?.activePayload?.[0]?.payload?.key && onCategoryClick?.(e.activePayload[0].payload.key)}>
          <XAxis type="number" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false} axisLine={false} width={90} />
          <RTooltip
            contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
            formatter={(value: number) => [`${value} articles`, 'Volume']}
            cursor={{ fill: 'hsl(var(--muted) / 0.2)' }}
          />
          <Bar dataKey="articles" radius={[0, 4, 4, 0]} barSize={16} className="cursor-pointer">
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
