/**
 * API client for Tawiza/TAJINE backend
 */

// Use relative URLs so Next.js rewrites can proxy to backend
// This ensures same-origin cookies work correctly (no cross-site issues)
const API_BASE = '';

export interface DataSourceStatus {
  name: string;
  status: 'online' | 'offline' | 'degraded';
  latency: number;
  lastSync: string;
  requestCount24h: number;
  successRate: number;
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'offline';
  version: string;
  uptime: number;
  dataSources: DataSourceStatus[];
}

export interface AnalyticsData {
  totalAnalyses: number;
  analysesThisMonth: number;
  successRate: number;
  avgDuration: number;
  cognitiveDistribution: {
    level: string;
    count: number;
  }[];
  topDepartments: {
    code: string;
    name: string;
    count: number;
    change: string;
  }[];
  recentAnalyses: {
    id: string;
    query: string;
    department: string;
    status: 'completed' | 'error';
    time: string;
    duration: string;
  }[];
}

/**
 * Fetch with timeout and error handling
 */
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    clearTimeout(timeout);

    if (!response.ok) {
      console.error(`API error: ${response.status} ${response.statusText}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeout);
    if (error instanceof Error && error.name === 'AbortError') {
      console.warn('API request timed out');
    } else {
      console.error('API request failed:', error);
    }
    return null;
  }
}

/**
 * Get system status including data sources
 */
export async function getSystemStatus(): Promise<SystemStatus | null> {
  return fetchAPI<SystemStatus>('/api/v1/system/status');
}

/**
 * Get analytics data from TAJINE stats endpoint
 */
export async function getAnalytics(): Promise<AnalyticsData | null> {
  return fetchAPI<AnalyticsData>('/api/v1/tajine/stats');
}

/**
 * Get data sources status from watcher status endpoint (detailed metrics)
 */
interface WatcherStatusResponse {
  running: boolean;
  sources: Record<string, {
    last_poll: string | null;
    next_poll: string | null;
    polls_count: number;
    last_error: string | null;
  }>;
}

// Source name mapping for display
const SOURCE_DISPLAY_NAMES: Record<string, string> = {
  bodacc: 'BODACC',
  boamp: 'BOAMP',
  gdelt: 'GDELT (News)',
  sirene: 'SIRENE (INSEE)',
  ban: 'API Geo (BAN)',
};

// Estimate latency based on source type (ms)
const SOURCE_LATENCY_ESTIMATES: Record<string, number> = {
  bodacc: 250,
  boamp: 300,
  gdelt: 180,
  sirene: 120,
  ban: 80,
};

// Response from /api/v1/sources/health endpoint
interface SourcesHealthResponse {
  status: string;
  checked_at: string;
  total: number;
  online: number;
  degraded: number;
  offline: number;
  adapters: {
    name: string;
    status: 'online' | 'degraded' | 'offline';
    latency_ms: number;
    last_success: string;
    error: string | null;
    category: string;
  }[];
}

export async function getDataSourcesStatus(): Promise<DataSourceStatus[] | null> {
  // Fetch both watcher status and real API health concurrently
  const [watcherResponse, sourcesHealth] = await Promise.all([
    fetchAPI<WatcherStatusResponse>('/api/v1/watcher/status'),
    fetchAPI<SourcesHealthResponse>('/api/v1/sources/health'),
  ]);

  const results: DataSourceStatus[] = [];

  // Add watcher sources (BODACC, BOAMP, GDELT)
  if (watcherResponse?.sources) {
    for (const [source, data] of Object.entries(watcherResponse.sources)) {
      const hasError = !!data.last_error;
      const hasPolled = !!data.last_poll;

      // Determine status based on error and poll state
      let status: 'online' | 'offline' | 'degraded' = 'offline';
      if (watcherResponse.running && hasPolled && !hasError) {
        status = 'online';
      } else if (watcherResponse.running && hasError) {
        status = 'degraded';
      }

      // Format last sync time
      let lastSync = 'Jamais';
      if (data.last_poll) {
        const lastPollDate = new Date(data.last_poll);
        const now = new Date();
        const diffMs = now.getTime() - lastPollDate.getTime();
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 60) {
          lastSync = `Il y a ${diffMins}min`;
        } else if (diffMins < 1440) {
          lastSync = `Il y a ${Math.floor(diffMins / 60)}h`;
        } else {
          lastSync = lastPollDate.toLocaleDateString('fr-FR');
        }
      }

      // Estimate success rate
      const successRate = hasError ? 50 : (hasPolled ? 100 : 0);

      results.push({
        name: SOURCE_DISPLAY_NAMES[source] || source.toUpperCase(),
        status,
        latency: SOURCE_LATENCY_ESTIMATES[source] || 200,
        lastSync,
        requestCount24h: data.polls_count * 10,
        successRate,
      });
    }
  }

  // Add real API health sources from /api/v1/sources/health
  if (sourcesHealth?.adapters) {
    for (const adapter of sourcesHealth.adapters) {
      // Map status (API returns 'online', 'degraded', 'offline')
      const status: 'online' | 'offline' | 'degraded' = adapter.status;

      // Format last sync time
      let lastSync = 'Temps reel';
      if (adapter.last_success) {
        const lastDate = new Date(adapter.last_success);
        const now = new Date();
        const diffMs = now.getTime() - lastDate.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        if (diffMins < 60) {
          lastSync = `Il y a ${diffMins}min`;
        } else if (diffMins < 1440) {
          lastSync = `Il y a ${Math.floor(diffMins / 60)}h`;
        } else {
          lastSync = lastDate.toLocaleDateString('fr-FR');
        }
      }

      results.push({
        name: adapter.name.replace('Adapter', ''),
        status,
        latency: adapter.latency_ms || 0,
        lastSync: status === 'online' ? lastSync : (adapter.error || 'Indisponible'),
        requestCount24h: 0,
        successRate: status === 'online' ? 100 : (status === 'degraded' ? 50 : 0),
      });
    }
  }

  return results.length > 0 ? results : null;
}

/**
 * Check if backend is available
 */
export async function isBackendAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'HEAD',
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get cognitive levels status
 */
export interface CognitiveLevelStatus {
  name: string;
  active: boolean;
  level: number;
}

// Backend response format
interface BackendCognitiveLevel {
  level: number;
  name: string;
  description: string;
  outputs: string[];
}

interface BackendCognitiveLevelsResponse {
  levels: BackendCognitiveLevel[];
}

export async function getCognitiveLevels(): Promise<CognitiveLevelStatus[] | null> {
  const response = await fetchAPI<BackendCognitiveLevelsResponse>('/api/v1/tajine/cognitive/levels');
  if (!response?.levels) return null;

  // Transform backend format to frontend format
  // Mark levels 1-3 as active (available), 4-5 as inactive (advanced)
  return response.levels.map(level => ({
    name: level.name,
    active: level.level <= 3,
    level: level.level,
  }));
}

/**
 * Get recent analyses
 */
export interface RecentAnalysis {
  id: string;
  query: string;
  department: string;
  status: 'completed' | 'error' | 'pending';
  time: string;
  duration: string;
}

export async function getRecentAnalyses(limit: number = 5): Promise<RecentAnalysis[] | null> {
  return fetchAPI<RecentAnalysis[]>(`/api/v1/tajine/analyses/recent?limit=${limit}`);
}

/**
 * Get dashboard metrics from TAJINE health
 */
export interface DashboardMetrics {
  totalDepartments: number;
  totalEnterprises: string;
  enterpriseGrowth: string;
  analysesThisMonth: number;
  llmModel: string;
  llmParams: string;
}

interface TajineHealthResponse {
  status: string;
  agent: string;
  version: string;
  capabilities: string[];
  running_tasks: number;
}

export async function getDashboardMetrics(): Promise<DashboardMetrics | null> {
  const response = await fetchAPI<TajineHealthResponse>('/api/v1/tajine/health');
  if (!response) return null;

  // Return metrics derived from TAJINE health + static values
  return {
    totalDepartments: 101,
    totalEnterprises: '12.4M',
    enterpriseGrowth: '+2.3%',
    analysesThisMonth: response.running_tasks,
    llmModel: 'Qwen3',
    llmParams: `${response.capabilities.length} capacites`,
  };
}

// ============================================================================
// Stealth Browser API
// ============================================================================

export type StealthBrowserType = 'auto' | 'nodriver' | 'camoufox' | 'playwright';

export interface StealthFetchRequest {
  url: string;
  browser?: StealthBrowserType;
  territory?: string;
  headless?: boolean;
  max_retries?: number;
  take_screenshot?: boolean;
}

export interface StealthFetchResponse {
  success: boolean;
  url?: string;
  content?: string;
  screenshot_b64?: string;
  browser_used?: string;
  duration_ms?: number;
  retries?: number;
  error?: string;
}

export interface StealthBrowserStatus {
  nodriver_available: boolean;
  camoufox_available: boolean;
  recommended: string;
  domain_preferences: Record<string, string>;
}

/**
 * Fetch URL using stealth browser (nodriver/Camoufox)
 */
export async function stealthFetch(request: StealthFetchRequest): Promise<StealthFetchResponse | null> {
  return fetchAPI<StealthFetchResponse>('/api/v1/browser/stealth/fetch', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get stealth browser availability status
 */
export async function getStealthBrowserStatus(): Promise<StealthBrowserStatus | null> {
  return fetchAPI<StealthBrowserStatus>('/api/v1/browser/stealth/status');
}

/**
 * Batch fetch multiple URLs using stealth browsers
 */
export async function stealthBatchFetch(
  urls: string[],
  browser: StealthBrowserType = 'auto',
  territory?: string
): Promise<StealthFetchResponse[] | null> {
  const params = new URLSearchParams();
  if (browser) params.append('browser', browser);
  if (territory) params.append('territory', territory);

  return fetchAPI<StealthFetchResponse[]>(`/api/v1/browser/stealth/batch?${params}`, {
    method: 'POST',
    body: JSON.stringify(urls),
  });
}

// ============================================
// CRAWLER API
// ============================================

export interface CrawlerStats {
  total_sources: number;
  results_cached: number;
  is_running: boolean;
}

export interface CrawlResult {
  source_id: string;
  url: string;
  data: any;
  quality_score: number;
  timestamp: string;
}

export async function getCrawlerStats(): Promise<CrawlerStats | null> {
  return fetchAPI<CrawlerStats>('/crawler/stats');
}

export async function startCrawler(): Promise<{ status: string } | null> {
  return fetchAPI<{ status: string }>('/crawler/start', { method: 'POST' });
}

export async function stopCrawler(): Promise<{ status: string } | null> {
  return fetchAPI<{ status: string }>('/crawler/stop', { method: 'POST' });
}

export async function triggerCrawl(sourceId?: string): Promise<{ success: boolean; results_count: number } | null> {
  return fetchAPI<{ success: boolean; results_count: number }>('/crawler/crawl', {
    method: 'POST',
    body: sourceId ? JSON.stringify({ source_id: sourceId }) : undefined,
  });
}

export async function getCrawlResults(limit: number = 100): Promise<CrawlResult[] | null> {
  return fetchAPI<CrawlResult[]>(`/crawler/results?limit=${limit}`);
}

// ============================================
// ALERTS API
// ============================================

export interface Alert {
  id: string;
  type: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  description: string;
  territory: string | null;
  sector: string | null;
  created_at: string;
  status: 'new' | 'read' | 'archived';
}

export interface AlertsResponse {
  alerts: Alert[];
  total: number;
}

export interface AlertStats {
  total: number;
  new: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  rules_count: number;
}

export async function getAlerts(params?: {
  status?: string;
  alert_type?: string;
  territory?: string;
  limit?: number;
}): Promise<AlertsResponse | null> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.alert_type) searchParams.set('alert_type', params.alert_type);
  if (params?.territory) searchParams.set('territory', params.territory);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  
  const query = searchParams.toString();
  return fetchAPI<AlertsResponse>(`/alerts/${query ? '?' + query : ''}`);
}

export async function getAlertStats(): Promise<AlertStats | null> {
  return fetchAPI<AlertStats>('/alerts/stats');
}

export async function markAlertRead(alertId: string): Promise<{ success: boolean } | null> {
  return fetchAPI<{ success: boolean }>(`/alerts/${alertId}/read`, { method: 'POST' });
}

export async function archiveAlert(alertId: string): Promise<{ success: boolean } | null> {
  return fetchAPI<{ success: boolean }>(`/alerts/${alertId}/archive`, { method: 'POST' });
}

// ============================================================================
// Collector - Micro-signals
// ============================================================================

export interface CollectorSignal {
  id: number;
  source: string;
  event_date: string | null;
  code_commune: string | null;
  code_dept: string | null;
  metric_name: string;
  metric_value: number | null;
  signal_type: string | null;
  confidence: number | null;
  raw_data: Record<string, any> | null;
}

export interface CollectorSummary {
  total: number;
  period_days: number;
  by_source: Record<string, number>;
  by_metric: Record<string, number>;
  by_type: Record<string, number>;
  by_department: Record<string, number>;
}

export interface CollectorHealth {
  status: 'ok' | 'degraded';
  database: 'connected' | 'disconnected';
  collectors: string[];
}

export async function getCollectorHealth(): Promise<CollectorHealth | null> {
  return fetchAPI<CollectorHealth>('/api/collector/health');
}

export async function getCollectorSummary(days: number = 30, codeDept?: string): Promise<CollectorSummary | null> {
  const params = new URLSearchParams({ days: days.toString() });
  if (codeDept) params.set('code_dept', codeDept);
  return fetchAPI<CollectorSummary>(`/api/collector/signals/summary?${params}`);
}

export async function getCollectorSignals(
  options: { codeDept?: string; source?: string; metric?: string; days?: number; limit?: number } = {}
): Promise<{ count: number; signals: CollectorSignal[] } | null> {
  const params = new URLSearchParams();
  if (options.codeDept) params.set('code_dept', options.codeDept);
  if (options.source) params.set('source', options.source);
  if (options.metric) params.set('metric', options.metric);
  if (options.days) params.set('days', options.days.toString());
  if (options.limit) params.set('limit', options.limit.toString());
  return fetchAPI<{ count: number; signals: CollectorSignal[] }>(`/api/collector/signals?${params}`);
}

export async function runCollector(name: string, codeDept?: string): Promise<{ signals_stored: number } | null> {
  const params = codeDept ? `?code_dept=${codeDept}` : '';
  return fetchAPI<{ signals_stored: number }>(`/api/collector/run/${name}${params}`, { method: 'POST' });
}

// New API interfaces for Phase 2 features

export interface TerritorialRanking {
  code: string;
  name: string;
  score: number;
  confidence: number;
  population: number;
  factors: {
    sante: number;
    declin: number;
    emploi: number;
    immo: number;
    construction: number;
    presse: number;
  };
}

export interface SourcesSummary {
  sources: {
    source: string;
    count: number;
    last_collected: string | null;
    status: 'online' | 'degraded' | 'offline';
  }[];
  total_signals: number;
  total_sources: number;
}

export interface GoogleTrendsData {
  trends: {
    keyword: string;
    department: string;
    avg_value: number;
    count: number;
    latest: string | null;
  }[];
  top_keywords: {
    keyword: string;
    total_value: number;
    department_count: number;
    latest: string | null;
  }[];
  total_trends: number;
}

// New API functions

export async function getTerritorialRanking(): Promise<{ ranking: TerritorialRanking[]; total_departments: number } | null> {
  return fetchAPI<{ ranking: TerritorialRanking[]; total_departments: number }>('/api/collector/ranking');
}

export async function getSourcesSummary(): Promise<SourcesSummary | null> {
  return fetchAPI<SourcesSummary>('/api/collector/sources-summary');
}

export async function getGoogleTrendsData(limit: number = 20): Promise<GoogleTrendsData | null> {
  const params = new URLSearchParams({ limit: limit.toString() });
  return fetchAPI<GoogleTrendsData>(`/api/collector/trends?${params}`);
}

// ============================================================================
// Territorial Health Scores
// ============================================================================

export interface DepartmentScore {
  code_dept: string;
  composite_score: number;
  category: string;
  factors: Record<string, number>;
  factor_coverage: number;
  population: number;
}

export async function fetchDepartmentScores(): Promise<DepartmentScore[]> {
  const res = await fetch('/api/collector/departments/scores');
  if (!res.ok) return [];
  const data = await res.json();
  return data.departments || [];
}

// ============================================================================
// ML Analysis API
// ============================================================================

export interface MLAnomaly {
  code_dept: string;
  department_name: string;
  anomaly_score: number;
  method: 'isolation_forest' | 'hdbscan';
  cluster_label?: number;
  confidence: number;
  factors?: Record<string, number>;
  summary?: string;
}

export interface MLCluster {
  cluster_id: number;
  name: string;
  description: string;
  departments: string[];
  department_count: number;
  characteristics: Record<string, number>;
  color?: string;
}

export interface MLFactors {
  factors: {
    feature_name: string;
    importance: number;
    correlation: number;
    description?: string;
  }[];
  method: string;
  computed_at: string;
}

export interface MLAnomaliesResponse {
  anomalies: MLAnomaly[];
  outliers_count: number;
  clusters_count: number;
  isolation_forest_outliers: MLAnomaly[];
  hdbscan_outliers: MLAnomaly[];
  last_analysis: string;
  summary?: {
    feature_importance: { feature: string; importance: number }[];
    method: string;
  };
}

export interface MLClustersResponse {
  clusters: MLCluster[];
  noise_departments: string[];
  cluster_count: number;
  total_departments: number;
  silhouette_score: number;
  method: string;
  computed_at: string;
}

/**
 * Get ML anomalies and outliers detection results
 */
export async function getMLAnomalies(): Promise<MLAnomaliesResponse | null> {
  return fetchAPI<MLAnomaliesResponse>('/api/collector/ml/anomalies');
}

/**
 * Get economic clustering results
 */
export async function getMLClusters(): Promise<MLClustersResponse | null> {
  return fetchAPI<MLClustersResponse>('/api/collector/ml/clusters');
}

/**
 * Get feature importance factors
 */
export async function getMLFactors(): Promise<MLFactors | null> {
  // This endpoint may be slow, so use a longer timeout
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000); // 15s timeout

  try {
    const response = await fetch(`${API_BASE}/api/collector/ml/factors`, {
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
    });

    clearTimeout(timeout);

    if (!response.ok) {
      console.error(`ML Factors API error: ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeout);
    if (error instanceof Error && error.name === 'AbortError') {
      console.warn('ML Factors request timed out (expected for slow computation)');
    } else {
      console.error('ML Factors request failed:', error);
    }
    return null;
  }
}

/**
 * Trigger ML detection run
 */
export async function runMLDetection(): Promise<{ success: boolean; message?: string } | null> {
  return fetchAPI<{ success: boolean; message?: string }>('/api/collector/ml/run-detection', {
    method: 'POST',
  });
}
