'use client';

import useSWR, { SWRConfiguration } from 'swr';

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

// Generic fetcher with error handling
const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    const error = new Error('API request failed');
    (error as any).status = res.status;
    (error as any).info = await res.json().catch(() => ({}));
    throw error;
  }
  return res.json();
};

// ============================================================================
// Types
// ============================================================================

export interface DepartmentStats {
  code: string;
  name: string;
  region: string;
  enterprises: number;
  growth: number;
  unemployment: number;
}

export interface DepartmentDetail {
  code: string;
  name: string;
  region: string;
  region_code: string;
  population: number;
  area_km2: number;
  enterprises: number;
  growth: number;
  price_m2: number;
  unemployment_rate: number;
  budget_per_capita: number;
  debt_per_capita: number;
  health_score: number;
  sector_distribution: Record<string, number>;
  recent_analyses: number;
}

export interface Alert {
  code: string;
  name: string;
  severity: 'critical' | 'warning' | 'info';
  type: string;
  message: string;
  value: number;
  threshold: number;
}

export interface TrendData {
  current: number;
  change: number;
  data: number[];
}

export interface Trends {
  creations: TrendData;
  prix_m2: TrendData;
  emploi: TrendData;
  population: TrendData;
}

export interface HealthScore {
  code: string;
  name: string;
  score: number;
  components: {
    emploi: number;
    dynamisme: number;
    finances: number;
    immobilier: number;
    demographie: number;
  };
  trend: 'up' | 'down' | 'stable';
}

export interface DepartmentComparison {
  code: string;
  name: string;
  region: string;
  enterprises: number;
  growth: number;
  price_m2: number;
  unemployment_rate: number;
  budget_per_capita: number;
  debt_per_capita: number;
  error?: string;
}

export interface FilterOptions {
  regions: { code: string; name: string }[];
  territories: string[];
  size_range: { min: number; max: number };
  growth_range: { min: number; max: number };
  unemployment_range: { min: number; max: number };
  price_range: { min: number; max: number };
  population_range: { min: number; max: number };
}

export interface IndicatorData {
  indicator: string;
  unit: string;
  data: Record<string, number>;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Get complete details for a single department
 */
export function useDepartmentDetails(
  code: string | null,
  config?: SWRConfiguration
) {
  return useSWR<DepartmentDetail>(
    code ? `${API_BASE}/api/v1/territorial/department/${code}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000, // 1 minute
      ...config,
    }
  );
}

/**
 * Get filtered list of departments
 */
export function useDepartmentStats(
  filters?: {
    region?: string;
    territory?: 'metropole' | 'dom_tom';
    size_min?: number;
    size_max?: number;
    growth_min?: number;
    growth_max?: number;
    unemployment_min?: number;
    unemployment_max?: number;
    limit?: number;
    offset?: number;
  },
  config?: SWRConfiguration
) {
  const params = new URLSearchParams();
  if (filters?.region) params.set('region', filters.region);
  if (filters?.territory) params.set('territory', filters.territory);
  if (filters?.size_min !== undefined)
    params.set('size_min', String(filters.size_min));
  if (filters?.size_max !== undefined)
    params.set('size_max', String(filters.size_max));
  if (filters?.growth_min !== undefined)
    params.set('growth_min', String(filters.growth_min));
  if (filters?.growth_max !== undefined)
    params.set('growth_max', String(filters.growth_max));
  if (filters?.unemployment_min !== undefined)
    params.set('unemployment_min', String(filters.unemployment_min));
  if (filters?.unemployment_max !== undefined)
    params.set('unemployment_max', String(filters.unemployment_max));
  if (filters?.limit) params.set('limit', String(filters.limit));
  if (filters?.offset) params.set('offset', String(filters.offset));

  const queryString = params.toString();
  const url = `${API_BASE}/api/v1/territorial/departments${queryString ? `?${queryString}` : ''}`;

  return useSWR<{
    departments: DepartmentStats[];
    total: number;
    limit: number;
    offset: number;
  }>(url, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30000,
    ...config,
  });
}

/**
 * Get territorial alerts (anomalies)
 */
export function useAlerts(limit: number = 10, config?: SWRConfiguration) {
  return useSWR<Alert[]>(
    `${API_BASE}/api/v1/territorial/alerts?limit=${limit}`,
    fetcher,
    {
      refreshInterval: 60000, // Refresh every minute
      revalidateOnFocus: true,
      ...config,
    }
  );
}

/**
 * Get national trends for sparklines
 */
export function useTrends(
  period: '3m' | '6m' | '12m' | '24m' = '12m',
  config?: SWRConfiguration
) {
  return useSWR<Trends>(
    `${API_BASE}/api/v1/territorial/trends?period=${period}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 300000, // 5 minutes
      ...config,
    }
  );
}

/**
 * Get department health scores
 */
export function useHealthScores(
  options?: { limit?: number; bottom?: boolean },
  config?: SWRConfiguration
) {
  const params = new URLSearchParams();
  if (options?.limit) params.set('limit', String(options.limit));
  if (options?.bottom) params.set('bottom', 'true');

  return useSWR<HealthScore[]>(
    `${API_BASE}/api/v1/territorial/health-scores?${params.toString()}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

/**
 * Compare 2-3 departments side by side
 */
export function useCompareDepartments(
  codes: string[],
  config?: SWRConfiguration
) {
  const codesString = codes.join(',');
  return useSWR<DepartmentComparison[]>(
    codes.length > 0
      ? `${API_BASE}/api/v1/territorial/compare?codes=${codesString}`
      : null,
    fetcher,
    {
      revalidateOnFocus: false,
      ...config,
    }
  );
}

/**
 * Get indicator data for map visualization
 */
export function useIndicator(
  indicator:
    | 'growth'
    | 'enterprises'
    | 'prix_m2'
    | 'chomage'
    | 'population'
    | 'health_score',
  codes?: string[],
  config?: SWRConfiguration
) {
  const params = new URLSearchParams();
  if (codes && codes.length > 0) params.set('codes', codes.join(','));

  return useSWR<IndicatorData>(
    `${API_BASE}/api/v1/territorial/indicators/${indicator}${params.toString() ? `?${params.toString()}` : ''}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

/**
 * Get available filter options
 */
export function useFilterOptions(config?: SWRConfiguration) {
  return useSWR<FilterOptions>(
    `${API_BASE}/api/v1/territorial/filter-options`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 600000, // 10 minutes - rarely changes
      ...config,
    }
  );
}

// ============================================================================
// Analytics Hooks
// ============================================================================

export interface AnalysisRecord {
  id: string;
  query: string;
  territory: string;
  mode: 'fast' | 'complete';
  cognitive_level: string;
  confidence: number;
  created_at: string;
}

/**
 * Get recent analyses history
 */
export function useAnalyticsHistory(
  options?: { limit?: number; territory?: string },
  config?: SWRConfiguration
) {
  const params = new URLSearchParams();
  if (options?.limit) params.set('limit', String(options.limit));
  if (options?.territory) params.set('territory', options.territory);

  return useSWR<{ analyses: AnalysisRecord[]; total: number }>(
    `${API_BASE}/api/v1/tajine/analyses/recent?${params.toString()}`,
    fetcher,
    {
      refreshInterval: 30000, // Refresh every 30 seconds
      revalidateOnFocus: true,
      ...config,
    }
  );
}
