'use client';

import { useState, useMemo, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import DashboardLayout from '@/components/layout';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle } from '@/components/ui/glass-card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  HiOutlineGlobeEuropeAfrica,
  HiOutlineChartBar,
  HiOutlineChatBubbleLeftRight,
  HiOutlinePlus,
  HiOutlineArrowPath,
  HiOutlineArrowTrendingUp,
  HiOutlineBuildingOffice2,
  HiOutlineMap,
  HiOutlineMapPin,
  HiOutlineSquares2X2,
  HiOutlineViewfinderCircle,
} from 'react-icons/hi2';

// Dynamic import for immersive layout (heavy component)
const ImmersiveLayout = dynamic(
  () => import('@/components/dashboard/tajine/ImmersiveLayout'),
  { ssr: false }
);
import FranceMap, { IndicatorType, INDICATORS } from '@/components/dashboard/tajine/FranceMap';
import FranceMapLeaflet from '@/components/dashboard/tajine/FranceMapLeaflet';
import IndicatorDrawer, { ExtendedIndicatorType } from '@/components/dashboard/tajine/IndicatorDrawer';
import TerritorialFilters, {
  TerritorialFilterState,
  defaultTerritorialFilters,
} from '@/components/dashboard/tajine/TerritorialFilters';
import { HiOutlineAdjustmentsHorizontal } from 'react-icons/hi2';
import {
  GrowthLineChart,
  SectorBarChart,
  MonteCarloChart,
  RelationGraph,
  RadarChart,
  TreemapChart,
  HeatmapChart,
  SankeyChart,
} from '@/components/dashboard/tajine/charts';
import UnifiedSynthesisDisplay from '@/components/dashboard/tajine/UnifiedSynthesisDisplay';
import ConversationHistory from '@/components/dashboard/tajine/ConversationHistory';
import PPDSLProgress from '@/components/dashboard/tajine/PPDSLProgress';
import { TajinePageSkeleton } from '@/components/skeletons';
import {
  useDepartmentStats,
  useTimeseries,
  useSectors,
  useSimulation,
  useRelationGraph,
  useRadarData,
  useTreemapData,
  useHeatmapData,
  useSankeyData,
} from '@/lib/api-tajine';

type MapType = 'svg' | 'leaflet';
type LayoutMode = 'classic' | 'immersive';

function TAJINEPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>('75'); // Default Paris
  const [mapIndicator, setMapIndicator] = useState<IndicatorType>('growth');
  const [mapType, setMapType] = useState<MapType>('leaflet'); // Default to Leaflet for satellite

  // Layout mode - check URL param or localStorage
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => {
    if (typeof window !== 'undefined') {
      const savedMode = localStorage.getItem('tajine-layout-mode');
      return (savedMode as LayoutMode) || 'classic';
    }
    return 'classic';
  });

  // Persist layout mode and reload to apply wrapper change
  const toggleLayoutMode = () => {
    const newMode = layoutMode === 'classic' ? 'immersive' : 'classic';
    if (typeof window !== 'undefined') {
      localStorage.setItem('tajine-layout-mode', newMode);
      // Force reload to properly switch DashboardLayout wrapper
      window.location.reload();
    }
  };

  // Indicator drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [biIndicatorMode, setBiIndicatorMode] = useState(false);
  const [secondaryIndicator, setSecondaryIndicator] = useState<ExtendedIndicatorType | null>(null);

  // Territorial filters state
  const [filters, setFilters] = useState<TerritorialFilterState>(defaultTerritorialFilters);

  // Get analysis results from context (from Chat page analyses)
  const { latestAnalysis, analysisHistory } = useTAJINE();

  // Fetch base data from API using SWR hooks
  const { departments, isLoading: loadingDepts, isError: errorDepts, mutate: refreshDepts } = useDepartmentStats();
  const { timeseries, isLoading: loadingTimeseries } = useTimeseries(selectedDepartment);
  const { sectors, isLoading: loadingSectors } = useSectors(selectedDepartment);
  const { simulation, isLoading: loadingSimulation } = useSimulation(selectedDepartment);
  const { graph, isLoading: loadingGraph } = useRelationGraph(selectedDepartment);

  // Fetch chart data from API (fallback)
  const { radarData: apiRadarData, isLoading: loadingRadar } = useRadarData(selectedDepartment);
  const { treemapData: apiTreemapData, isLoading: loadingTreemap } = useTreemapData(selectedDepartment);
  const { heatmapData: apiHeatmapData, xLabels: apiHeatmapXLabels, yLabels: apiHeatmapYLabels, isLoading: loadingHeatmap } = useHeatmapData(selectedDepartment);
  const { sankeyNodes: apiSankeyNodes, sankeyLinks: apiSankeyLinks, isLoading: loadingSankey } = useSankeyData(selectedDepartment);

  // Prefer context data over API data when available
  // This allows charts to show real analysis results from Chat
  // Add fullMark (100) if missing from context data
  const radarData = latestAnalysis?.radarData?.length
    ? latestAnalysis.radarData.map(d => ({ ...d, fullMark: d.fullMark ?? 100 }))
    : apiRadarData;
  const treemapData = latestAnalysis?.treemapData?.length ? latestAnalysis.treemapData : apiTreemapData;
  const heatmapData = latestAnalysis?.heatmapData?.data?.length ? latestAnalysis.heatmapData.data : apiHeatmapData;
  const heatmapXLabels = latestAnalysis?.heatmapData?.xLabels?.length ? latestAnalysis.heatmapData.xLabels : apiHeatmapXLabels;
  const heatmapYLabels = latestAnalysis?.heatmapData?.yLabels?.length ? latestAnalysis.heatmapData.yLabels : apiHeatmapYLabels;
  const sankeyNodes = latestAnalysis?.sankeyData?.nodes?.length ? latestAnalysis.sankeyData.nodes : apiSankeyNodes;
  const sankeyLinks = latestAnalysis?.sankeyData?.links?.length ? latestAnalysis.sankeyData.links : apiSankeyLinks;

  // Check if we're using real analysis data
  const usingRealData = !!(latestAnalysis?.radarData?.length || latestAnalysis?.heatmapData?.data?.length);

  // Filter departments based on territorial filters
  const filteredDepartments = useMemo(() => {
    if (!departments) return [];

    return departments.filter((dept) => {
      // Territory filter (metropole vs DOM-TOM)
      if (filters.territory !== 'all') {
        const code = parseInt(dept.code, 10);
        const isDomTom = isNaN(code) || code > 95; // DOM-TOM codes are > 95 or alphanumeric
        if (filters.territory === 'metropole' && isDomTom) return false;
        if (filters.territory === 'dom_tom' && !isDomTom) return false;
      }

      // Size range filter (enterprises count)
      const enterprises = dept.enterprises || 0;
      if (enterprises < filters.sizeRange[0] || enterprises > filters.sizeRange[1]) {
        return false;
      }

      // Growth range filter
      const growth = dept.growth || 0;
      if (growth < filters.growthRange[0] || growth > filters.growthRange[1]) {
        return false;
      }

      // Unemployment range filter
      const unemployment = dept.unemployment || 0;
      if (unemployment < filters.unemploymentRange[0] || unemployment > filters.unemploymentRange[1]) {
        return false;
      }

      // Population range filter
      const population = dept.population || 0;
      if (population < filters.populationRange[0] || population > filters.populationRange[1]) {
        return false;
      }

      return true;
    });
  }, [departments, filters]);

  // Handle department selection from map
  const handleDepartmentSelect = (code: string) => {
    setSelectedDepartment(code);
  };

  if (loadingDepts) {
    return <TajinePageSkeleton />;
  }

  // Render immersive layout if selected
  if (layoutMode === 'immersive') {
    return (
      <ImmersiveLayout
        departments={filteredDepartments}
        isLoading={loadingDepts}
      />
    );
  }

  // Get selected department name
  const selectedDeptName = departments.find(d => d.code === selectedDepartment)?.name || selectedDepartment;

  return (
    <div className="h-full w-full space-y-6">
      {/* Unified Synthesis Display - Shows only when data is available */}
      {latestAnalysis?.unifiedSynthesis && (
        <div className="opacity-0 animate-fade-in stagger-0">
          <UnifiedSynthesisDisplay 
            data={latestAnalysis.unifiedSynthesis} 
          />
        </div>
      )}

      {/* Top row: Map + Charts - stack on mobile */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 lg:grid-cols-2">
        {/* France Map */}
        <div className="opacity-0 animate-fade-in stagger-1">
          <GlassCard glow="cyan" hoverGlow className="h-full">
            <GlassCardHeader className="flex flex-row items-center justify-between flex-wrap gap-2">
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineGlobeEuropeAfrica className="h-5 w-5 text-primary" />
                Carte de France
                {selectedDepartment && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    | {selectedDeptName}
                  </span>
                )}
              </GlassCardTitle>
              <div className="flex items-center gap-2">
                {/* Layout Mode Toggle */}
                <button
                  onClick={toggleLayoutMode}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs glass hover:bg-primary/10 transition-all"
                  title="Mode immersif"
                >
                  <HiOutlineViewfinderCircle className="h-4 w-4 text-primary" />
                  <span className="hidden md:inline">Immersif</span>
                </button>

                {/* Map Type Toggle - SVG vs Leaflet */}
                <div className="glass rounded-lg p-1 flex gap-1">
                  <button
                    onClick={() => setMapType('svg')}
                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all ${
                      mapType === 'svg'
                        ? 'bg-primary/20 text-primary'
                        : 'hover:bg-muted/50 text-muted-foreground'
                    }`}
                    title="Carte vectorielle"
                  >
                    <HiOutlineMap className="h-3.5 w-3.5" />
                    <span className="hidden md:inline">SVG</span>
                  </button>
                  <button
                    onClick={() => setMapType('leaflet')}
                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all ${
                      mapType === 'leaflet'
                        ? 'bg-primary/20 text-primary'
                        : 'hover:bg-muted/50 text-muted-foreground'
                    }`}
                    title="Carte satellite/terrain"
                  >
                    <HiOutlineGlobeEuropeAfrica className="h-3.5 w-3.5" />
                    <span className="hidden md:inline">Satellite</span>
                  </button>
                </div>
                {/* Quick Indicator Selector - dropdown menu for SVG mode */}
                {mapType === 'svg' && (
                  <Select
                    value={mapIndicator}
                    onValueChange={(v) => setMapIndicator(v as IndicatorType)}
                  >
                    <SelectTrigger className="w-[140px] h-8 text-xs glass border-0">
                      <div className="flex items-center gap-1.5">
                        {INDICATORS[mapIndicator]?.icon}
                        <SelectValue placeholder="Indicateur" />
                      </div>
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(INDICATORS) as IndicatorType[]).map((key) => {
                        const ind = INDICATORS[key];
                        return (
                          <SelectItem key={key} value={key}>
                            <div className="flex items-center gap-2">
                              {ind.icon}
                              <span>{ind.label}</span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                )}
                {/* Advanced Indicator Drawer button */}
                <button
                  onClick={() => setDrawerOpen(true)}
                  className={`p-2 glass rounded-lg transition-colors ${
                    biIndicatorMode ? 'bg-primary/20 text-primary' : 'hover:bg-primary/10'
                  }`}
                  title="Indicateurs avances"
                >
                  <HiOutlineAdjustmentsHorizontal className="h-4 w-4" />
                </button>
                {/* Refresh button */}
                <button
                  onClick={() => refreshDepts()}
                  className="p-2 glass rounded-lg hover:bg-primary/10 transition-colors"
                  title="Rafraichir les donnees"
                >
                  <HiOutlineArrowPath className="h-4 w-4" />
                </button>
              </div>
            </GlassCardHeader>
            <GlassCardContent className="space-y-4">
              {/* Territorial Filters */}
              <TerritorialFilters
                filters={filters}
                onFiltersChange={setFilters}
              />

              {/* Filtered department count */}
              {filteredDepartments.length !== departments.length && (
                <div className="text-xs text-muted-foreground">
                  {filteredDepartments.length} / {departments.length} départements affichés
                </div>
              )}

              {mapType === 'svg' ? (
                <FranceMap
                  data={filteredDepartments}
                  selectedDepartment={selectedDepartment}
                  onDepartmentSelect={handleDepartmentSelect}
                  activeIndicator={mapIndicator}
                  onIndicatorChange={setMapIndicator}
                />
              ) : (
                <FranceMapLeaflet
                  data={filteredDepartments}
                  selectedDepartment={selectedDepartment}
                  onDepartmentSelect={handleDepartmentSelect}
                  activeIndicator={mapIndicator}
                  onIndicatorChange={setMapIndicator}
                />
              )}
              {errorDepts && (
                <div className="mt-2 text-sm text-amber-500">
                  Données en cache (erreur de connexion API)
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Charts with tabs */}
        <div className="opacity-0 animate-fade-in stagger-2">
          <GlassCard glow="cyan" hoverGlow className="h-full">
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineChartBar className="h-5 w-5 text-primary" />
                Analyses Graphiques
                {selectedDepartment && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    | {selectedDeptName}
                  </span>
                )}
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <Tabs defaultValue="growth" className="w-full">
                <TabsList className="flex w-full overflow-x-auto glass scrollbar-hide">
                  <TabsTrigger value="growth" className="flex-1 min-w-[80px] text-xs sm:text-sm">Croissance</TabsTrigger>
                  <TabsTrigger value="sectors" className="flex-1 min-w-[80px] text-xs sm:text-sm">Secteurs</TabsTrigger>
                  <TabsTrigger value="monte" className="flex-1 min-w-[80px] text-xs sm:text-sm">Monte Carlo</TabsTrigger>
                  <TabsTrigger value="graph" className="flex-1 min-w-[80px] text-xs sm:text-sm">Relations</TabsTrigger>
                </TabsList>
                <TabsContent value="growth" className="mt-4">
                  <GrowthLineChart
                    data={timeseries}
                    isLoading={loadingTimeseries}
                  />
                </TabsContent>
                <TabsContent value="sectors" className="mt-4">
                  <SectorBarChart
                    data={sectors}
                    isLoading={loadingSectors}
                  />
                </TabsContent>
                <TabsContent value="monte" className="mt-4">
                  <MonteCarloChart
                    data={simulation?.histogram}
                    percentile5={simulation?.percentile5}
                    percentile50={simulation?.percentile50}
                    percentile95={simulation?.percentile95}
                    isLoading={loadingSimulation}
                  />
                </TabsContent>
                <TabsContent value="graph" className="mt-4">
                  <RelationGraph
                    nodes={graph?.nodes}
                    links={graph?.links}
                    isLoading={loadingGraph}
                  />
                </TabsContent>
              </Tabs>
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>

      {/* Advanced Analytics - Second row of charts */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Radar & Treemap */}
        <div className="opacity-0 animate-fade-in stagger-3">
          <GlassCard glow="cyan" hoverGlow className="h-full">
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineChartBar className="h-5 w-5 text-primary" />
                Analyses Avancees
                {selectedDepartment && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    | {selectedDeptName}
                  </span>
                )}
                {usingRealData && (
                  <span className="ml-2 px-2 py-0.5 text-[10px] font-medium rounded bg-green-500/20 text-green-500 border border-green-500/30">
                    ANALYSE REELLE
                  </span>
                )}
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <Tabs defaultValue="radar" className="w-full">
                <TabsList className="flex w-full glass">
                  <TabsTrigger value="radar" className="flex-1 text-xs sm:text-sm">Radar</TabsTrigger>
                  <TabsTrigger value="treemap" className="flex-1 text-xs sm:text-sm">Treemap</TabsTrigger>
                </TabsList>
                <TabsContent value="radar" className="mt-4">
                  <RadarChart data={radarData} isLoading={loadingRadar} />
                </TabsContent>
                <TabsContent value="treemap" className="mt-4">
                  <TreemapChart data={treemapData} isLoading={loadingTreemap} />
                </TabsContent>
              </Tabs>
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Heatmap & Sankey */}
        <div className="opacity-0 animate-fade-in stagger-4">
          <GlassCard glow="cyan" hoverGlow className="h-full">
            <GlassCardHeader>
              <GlassCardTitle className="flex items-center gap-2">
                <HiOutlineChartBar className="h-5 w-5 text-primary" />
                Flux & Tendances
                {selectedDepartment && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    | {selectedDeptName}
                  </span>
                )}
                {usingRealData && (
                  <span className="ml-2 px-2 py-0.5 text-[10px] font-medium rounded bg-green-500/20 text-green-500 border border-green-500/30">
                    ANALYSE REELLE
                  </span>
                )}
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <Tabs defaultValue="heatmap" className="w-full">
                <TabsList className="flex w-full glass">
                  <TabsTrigger value="heatmap" className="flex-1 text-xs sm:text-sm">Heatmap</TabsTrigger>
                  <TabsTrigger value="sankey" className="flex-1 text-xs sm:text-sm">Sankey</TabsTrigger>
                </TabsList>
                <TabsContent value="heatmap" className="mt-4">
                  <HeatmapChart
                    data={heatmapData}
                    xLabels={heatmapXLabels}
                    yLabels={heatmapYLabels}
                    isLoading={loadingHeatmap}
                  />
                </TabsContent>
                <TabsContent value="sankey" className="mt-4">
                  <SankeyChart
                    nodes={sankeyNodes}
                    links={sankeyLinks}
                    isLoading={loadingSankey}
                  />
                </TabsContent>
              </Tabs>
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>

      {/* PPDSL Progress Indicator - shows during active analysis */}
      <PPDSLProgress className="opacity-0 animate-fade-in stagger-5" />

      {/* Bottom row: History */}
      <div className="opacity-0 animate-fade-in stagger-6">
        <GlassCard glow="cyan" hoverGlow>
          <GlassCardHeader className="flex flex-row items-center justify-between">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineChatBubbleLeftRight className="h-5 w-5 text-primary" />
              Historique des Analyses
            </GlassCardTitle>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Rechercher..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="px-3 py-1.5 text-sm glass rounded-lg border-0 focus:ring-2 focus:ring-primary/30"
              />
              <button
                onClick={() => router.push('/dashboard/ai-chat')}
                className="px-4 py-1.5 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity flex items-center gap-1"
              >
                <HiOutlinePlus className="w-4 h-4" />
                Nouvelle Analyse
              </button>
            </div>
          </GlassCardHeader>
          <GlassCardContent>
            <ConversationHistory
              searchQuery={searchQuery}
              onConversationSelect={(id) => {
                // Navigate to chat with selected conversation
                router.push(`/dashboard/ai-chat?conversation=${id}`);
              }}
            />
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* Indicator Drawer for advanced indicator selection */}
      <IndicatorDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        primaryIndicator={mapIndicator as ExtendedIndicatorType}
        secondaryIndicator={secondaryIndicator}
        onPrimaryChange={(ind) => {
          // FranceMap now supports all extended indicators
          setMapIndicator(ind as IndicatorType);
        }}
        onSecondaryChange={setSecondaryIndicator}
        biIndicatorMode={biIndicatorMode}
        onBiIndicatorModeChange={setBiIndicatorMode}
      />
    </div>
  );
}

export default function TAJINEPage() {
  // Check layout mode on client side
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('classic');
  const [isClient, setIsClient] = useState(false);

  // Hydrate layout mode from localStorage
  useEffect(() => {
    setIsClient(true);
    const savedMode = localStorage.getItem('tajine-layout-mode');
    if (savedMode === 'immersive') {
      setLayoutMode('immersive');
    }
  }, []);

  // Listen for layout mode changes
  useEffect(() => {
    const handleStorage = () => {
      const savedMode = localStorage.getItem('tajine-layout-mode');
      setLayoutMode(savedMode === 'immersive' ? 'immersive' : 'classic');
    };
    window.addEventListener('storage', handleStorage);
    // Also check periodically for same-tab changes
    const interval = setInterval(handleStorage, 500);
    return () => {
      window.removeEventListener('storage', handleStorage);
      clearInterval(interval);
    };
  }, []);

  // Show loading while hydrating
  if (!isClient) {
    return <TajinePageSkeleton />;
  }

  // Full-screen immersive mode - no DashboardLayout wrapper
  if (layoutMode === 'immersive') {
    return <TAJINEPageContent />;
  }

  // Classic mode with DashboardLayout
  return (
    <DashboardLayout
      title="TAJINE"
      description="Intelligence Territoriale"
    >
      <TAJINEPageContent />
    </DashboardLayout>
  );
}
