/**
 * TAJINE API hooks with SWR for data fetching
 */

import useSWR from 'swr';

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

// Fetcher with error handling
async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

// Types
export interface DepartmentStats {
  code: string;
  name: string;
  enterprises: number;
  growth: number;
  analyses: number;
  // Extended fields for territorial analysis
  unemployment?: number;
  population?: number;
  prix_m2?: number;
  health_score?: number;
  budget?: number;
  dette?: number;
  region_code?: string;
  // Collector data fields
  signal_count?: number;
  total_signals?: number;
  anomalies?: number;
  latest_signal?: string;
  sources?: Record<string, number>;
}

export interface TimeseriesPoint {
  date: string;
  value: number;
  department?: string;
}

export interface SectorData {
  sector: string;
  count: number;
  growth: number;
  color?: string;
}

export interface SimulationResult {
  percentile5: number;
  percentile50: number;
  percentile95: number;
  histogram: { bin: number; count: number }[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'enterprise' | 'sector' | 'territory';
  size?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface Conversation {
  id: string;
  created_at: string;
  department_code: string | null;
  cognitive_level: string;
  status: 'completed' | 'error' | 'pending';
  query_preview: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    sources?: string[];
    confidence?: number;
    duration_ms?: number;
  };
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

// SWR Hooks

/**
 * Fetch department statistics for the map (enriched with collector data)
 */
export function useDepartmentStats() {
  // Fetch TAJINE stats
  const { data: tajineData, error: tajineError, isLoading: tajineLoading, mutate } = useSWR<{ departments: DepartmentStats[] }>(
    '/api/v1/tajine/departments/stats',
    fetcher,
    { refreshInterval: 60000 } // Refresh every minute
  );

  // Fetch collector heatmap data
  const { data: collectorData, error: collectorError, isLoading: collectorLoading } = useSWR<{
    departments: Array<{
      code: string;
      total_signals: number;
      sources: Record<string, number>;
      anomalies: number;
      latest_signal?: string;
    }>;
  }>(
    '/api/collector/departments/heatmap',
    async (url: string) => {
      try {
        return await fetcher(url);
      } catch (err) {
        // Fallback if collector is down - return empty data
        console.warn('Collector API unavailable:', err);
        return { departments: [] };
      }
    },
    { refreshInterval: 60000, dedupingInterval: 30000 }
  );

  // Merge the data
  const mergedDepartments = (tajineData?.departments || []).map((tajineDept) => {
    const collectorDept = collectorData?.departments?.find(
      (c) => c.code === tajineDept.code
    );

    return {
      ...tajineDept,
      // Add collector fields with fallbacks
      signal_count: collectorDept?.total_signals || 0,
      total_signals: collectorDept?.total_signals || 0,
      anomalies: collectorDept?.anomalies || 0,
      latest_signal: collectorDept?.latest_signal,
      sources: collectorDept?.sources || {},
    };
  });

  return {
    departments: mergedDepartments,
    isLoading: tajineLoading || collectorLoading,
    isError: !!tajineError, // Only fail if TAJINE fails (collector is optional)
    mutate,
  };
}

/**
 * Fetch timeseries data for growth charts
 */
export function useTimeseries(dept: string | null, period: string = '12m') {
  const { data, error, isLoading } = useSWR<{ data: TimeseriesPoint[] }>(
    dept ? `/api/v1/tajine/analytics/timeseries?dept=${dept}&period=${period}` : null,
    fetcher
  );

  return {
    timeseries: data?.data || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch sector distribution data
 */
export function useSectors(dept: string | null) {
  const { data, error, isLoading } = useSWR<{ sectors: SectorData[] }>(
    dept ? `/api/v1/tajine/analytics/sectors?dept=${dept}` : null,
    fetcher
  );

  return {
    sectors: data?.sectors || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch Monte Carlo simulation results
 */
export function useSimulation(dept: string | null, runs: number = 1000) {
  const { data, error, isLoading } = useSWR<SimulationResult>(
    dept ? `/api/v1/tajine/analytics/simulation?dept=${dept}&runs=${runs}` : null,
    fetcher
  );

  return {
    simulation: data,
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch relation graph data
 */
export function useRelationGraph(dept: string | null, depth: number = 2) {
  const { data, error, isLoading } = useSWR<GraphData>(
    dept ? `/api/v1/tajine/analytics/graph?dept=${dept}&depth=${depth}` : null,
    fetcher
  );

  return {
    graph: data,
    isLoading,
    isError: !!error,
  };
}

// ============================================================================
// New Chart Data Hooks
// ============================================================================

export interface RadarMetric {
  metric: string;
  value: number;
  fullMark: number;
  benchmark?: number;
}

export interface TreemapNode {
  name: string;
  size?: number;
  children?: TreemapNode[];
  growth?: number;
}

export interface HeatmapCell {
  x: string;
  y: string;
  value: number;
}

export interface SankeyNode {
  id: string;
  name: string;
  category: 'source' | 'sector' | 'destination';
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  type?: 'growth' | 'creation' | 'transfer' | 'cessation' | 'investment';
}

/**
 * Fetch radar chart data for multi-metric comparison
 */
export function useRadarData(dept: string | null) {
  const { data, error, isLoading } = useSWR<{ data: RadarMetric[] }>(
    dept ? `/api/v1/tajine/analytics/radar?dept=${dept}` : null,
    fetcher
  );

  return {
    radarData: data?.data || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch treemap data for hierarchical sector visualization
 */
export function useTreemapData(dept: string | null) {
  const { data, error, isLoading } = useSWR<{ data: TreemapNode[] }>(
    dept ? `/api/v1/tajine/analytics/treemap?dept=${dept}` : null,
    fetcher
  );

  return {
    treemapData: data?.data || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch heatmap data for sector activity over time
 */
export function useHeatmapData(dept: string | null, periods: number = 5) {
  const { data, error, isLoading } = useSWR<{
    data: HeatmapCell[];
    xLabels: string[];
    yLabels: string[];
  }>(
    dept ? `/api/v1/tajine/analytics/heatmap?dept=${dept}&periods=${periods}` : null,
    fetcher
  );

  return {
    heatmapData: data?.data || [],
    xLabels: data?.xLabels || [],
    yLabels: data?.yLabels || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch Sankey flow data for enterprise dynamics
 */
export function useSankeyData(dept: string | null) {
  const { data, error, isLoading } = useSWR<{
    nodes: SankeyNode[];
    links: SankeyLink[];
  }>(
    dept ? `/api/v1/tajine/analytics/sankey?dept=${dept}` : null,
    fetcher
  );

  return {
    sankeyNodes: data?.nodes || [],
    sankeyLinks: data?.links || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch conversation history
 */
export function useConversations(dept: string | null, page: number = 0, limit: number = 20) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(page * limit) });
  if (dept) params.set('dept', dept);

  const { data, error, isLoading, mutate } = useSWR<Conversation[]>(
    `/api/v1/tajine/conversations?${params}`,
    fetcher
  );

  return {
    conversations: data || [],
    isLoading,
    isError: !!error,
    mutate,
  };
}

/**
 * Fetch single conversation with messages
 */
export function useConversation(id: string | null) {
  const { data, error, isLoading } = useSWR<ConversationDetail>(
    id ? `/api/v1/tajine/conversations/${id}` : null,
    fetcher
  );

  return {
    conversation: data,
    isLoading,
    isError: !!error,
  };
}

// Mutation functions (non-SWR)

/**
 * Create a new conversation
 */
export async function createConversation(
  departmentCode: string | null,
  cognitiveLevel: string
): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/api/v1/tajine/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ department_code: departmentCode, cognitive_level: cognitiveLevel }),
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

/**
 * Add message to conversation
 */
export async function addMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  metadata?: Message['metadata']
): Promise<Message> {
  const res = await fetch(`${API_BASE}/api/v1/tajine/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role, content, metadata }),
  });
  if (!res.ok) throw new Error('Failed to add message');
  return res.json();
}

/**
 * Delete a conversation
 */
export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/tajine/conversations/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete conversation');
}

// ============================================================================
// Territorial Analyzer Types
// ============================================================================

export type AttractiveAxis =
  | 'infrastructure'
  | 'capital_humain'
  | 'environnement_eco'
  | 'qualite_vie'
  | 'accessibilite'
  | 'innovation';

export interface AxisScore {
  score: number;
  trend: number;
  components: Record<string, number>;
}

export interface AttractivenessScore {
  territory_code: string;
  territory_name: string;
  global_score: number;
  rank: number;
  axes: Record<AttractiveAxis, AxisScore>;
  computed_at: string;
}

export interface TerritoryComparison {
  code: string;
  name: string;
  global_score: number;
  distance_km?: number;
  category?: string;
}

export interface CompetitorAnalysis {
  territory_code: string;
  territory_name: string;
  gap_vs_neighbors: number;
  gap_vs_similar: number;
  ranking: TerritoryComparison[];
  neighbors: TerritoryComparison[];
  similar: TerritoryComparison[];
}

export interface PolicyChange {
  type: string;
  target: string;
  value: number;
  description: string;
}

export interface WhatIfScenario {
  id: string;
  name: string;
  description: string;
  duration_months: number;
  changes: PolicyChange[];
}

export interface SimulationSnapshot {
  month: number;
  enterprises: number;
  employment: number;
  attractiveness: number;
}

export interface TerritorialSimulationResult {
  territory_code: string;
  territory_name: string;
  scenario: WhatIfScenario | null;
  duration_months: number;
  computed_at: string;
  summary: {
    net_enterprise_change: number;
    net_employment_change: number;
    net_household_change: number;
    attractiveness_change: number;
  };
  initial_state: SimulationSnapshot;
  final_state: SimulationSnapshot;
  timeline: SimulationSnapshot[];
  positive_effects: string[];
  negative_effects: string[];
  roi_estimate: number | null;
  recommendation: string;
}

export interface TerritorialAnalysis {
  territory_code: string;
  territory_name: string;
  attractiveness?: AttractivenessScore;
  competitors?: CompetitorAnalysis;
  simulation?: TerritorialSimulationResult;
  swot: {
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    threats: string[];
  };
  recommendation: string;
}

// ============================================================================
// Territorial Analyzer Hooks
// ============================================================================

/**
 * Fetch attractiveness score for a department
 */
export function useAttractiveness(code: string | null) {
  const { data, error, isLoading } = useSWR<AttractivenessScore>(
    code ? `/api/v1/tajine/territorial/attractiveness/${code}` : null,
    fetcher,
  );

  return {
    attractiveness: data,
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch competitor analysis for a department
 */
export function useCompetitors(code: string | null) {
  const { data, error, isLoading } = useSWR<CompetitorAnalysis>(
    code ? `/api/v1/tajine/territorial/compare` : null,
    async (url: string) => {
      const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    },
  );

  return {
    competitors: data,
    isLoading,
    isError: !!error,
  };
}

/**
 * Fetch available What-If scenarios
 */
export function useScenarios() {
  const { data, error, isLoading } = useSWR<{ scenarios: WhatIfScenario[] }>(
    '/api/v1/tajine/territorial/scenarios',
    fetcher,
  );

  return {
    scenarios: data?.scenarios || [],
    isLoading,
    isError: !!error,
  };
}

/**
 * Run territorial simulation with optional scenario
 */
export async function runSimulation(
  code: string,
  scenarioId?: string,
  durationMonths: number = 36
): Promise<TerritorialSimulationResult> {
  const res = await fetch(`${API_BASE}/api/v1/tajine/territorial/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code,
      scenario: scenarioId,
      duration_months: durationMonths,
    }),
  });
  if (!res.ok) throw new Error('Simulation failed');
  return res.json();
}

/**
 * Run complete territorial analysis (attractiveness + competitors + simulation)
 */
export async function analyzeTerritoryComplete(
  code: string,
  options?: {
    aspects?: ('attractiveness' | 'competitors' | 'simulation')[];
    scenario?: string;
    simulationMonths?: number;
  }
): Promise<TerritorialAnalysis> {
  const res = await fetch(`${API_BASE}/api/v1/tajine/territorial/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code,
      aspects: options?.aspects || ['attractiveness', 'competitors', 'simulation'],
      scenario: options?.scenario,
      simulation_months: options?.simulationMonths || 36,
    }),
  });
  if (!res.ok) throw new Error('Analysis failed');
  return res.json();
}

/**
 * Hook for complete territorial analysis with caching
 */
export function useTerritorialAnalysis(
  code: string | null,
  aspects: ('attractiveness' | 'competitors' | 'simulation')[] = ['attractiveness']
) {
  const aspectsKey = aspects.sort().join(',');

  const { data, error, isLoading, mutate } = useSWR<TerritorialAnalysis>(
    code ? `/api/v1/tajine/territorial/analyze?code=${code}&aspects=${aspectsKey}` : null,
    async () => {
      if (!code) throw new Error('No code provided');
      return analyzeTerritoryComplete(code, { aspects });
    },
  );

  return {
    analysis: data,
    isLoading,
    isError: !!error,
    mutate,
  };
}
