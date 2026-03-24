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

export interface AdapterHealth {
  name: string;
  status: 'online' | 'degraded' | 'offline';
  latency_ms: number | null;
  last_success: string | null;
  error: string | null;
  category: 'enterprises' | 'territorial' | 'signals' | 'news';
}

export interface SourcesHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  total: number;
  online: number;
  degraded: number;
  offline: number;
  adapters: AdapterHealth[];
  checked_at: string;
}

export interface AdapterInfo {
  name: string;
  description: string;
  category: string;
  api_url: string | null;
  requires_auth: boolean;
  rate_limited: boolean;
  cache_ttl_seconds: number;
}

export interface AdaptersListResponse {
  adapters: AdapterInfo[];
  total: number;
}

export interface CategoryInfo {
  name: string;
  count: number;
  adapters: string[];
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Get health status of all data source adapters
 *
 * @param options.category - Filter by category (enterprises, territorial, signals, news)
 * @param options.quick - Quick check (cached) vs full check (live test)
 * @param config - SWR configuration
 */
export function useSourcesHealth(
  options?: {
    category?: 'enterprises' | 'territorial' | 'signals' | 'news';
    quick?: boolean;
  },
  config?: SWRConfiguration
) {
  const params = new URLSearchParams();
  if (options?.category) params.set('category', options.category);
  if (options?.quick !== undefined) params.set('quick', String(options.quick));

  const queryString = params.toString();
  const url = `${API_BASE}/api/v1/sources/health${queryString ? `?${queryString}` : ''}`;

  return useSWR<SourcesHealthResponse>(url, fetcher, {
    refreshInterval: 30000, // Auto-refresh every 30 seconds
    revalidateOnFocus: true,
    dedupingInterval: 10000, // Dedupe within 10 seconds
    ...config,
  });
}

/**
 * Get list of all available adapters with metadata
 *
 * @param category - Filter by category
 * @param config - SWR configuration
 */
export function useAdaptersList(
  category?: 'enterprises' | 'territorial' | 'signals' | 'news',
  config?: SWRConfiguration
) {
  const url = category
    ? `${API_BASE}/api/v1/sources/?category=${category}`
    : `${API_BASE}/api/v1/sources/`;

  return useSWR<AdaptersListResponse>(url, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 600000, // 10 minutes - rarely changes
    ...config,
  });
}

/**
 * Get list of adapter categories with counts
 */
export function useAdapterCategories(config?: SWRConfiguration) {
  return useSWR<{ categories: CategoryInfo[] }>(
    `${API_BASE}/api/v1/sources/categories`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 600000, // 10 minutes
      ...config,
    }
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get status color based on adapter status
 */
export function getStatusColor(status: AdapterHealth['status']): string {
  switch (status) {
    case 'online':
      return '#A3BE8C'; // Green
    case 'degraded':
      return '#EBCB8B'; // Yellow
    case 'offline':
      return '#BF616A'; // Red
    default:
      return '#4C566A'; // Gray
  }
}

/**
 * Get status icon based on adapter status
 */
export function getStatusIcon(status: AdapterHealth['status']): string {
  switch (status) {
    case 'online':
      return '🟢';
    case 'degraded':
      return '🟡';
    case 'offline':
      return '🔴';
    default:
      return '⚪';
  }
}

/**
 * Get category label in French
 */
export function getCategoryLabel(
  category: AdapterHealth['category']
): string {
  const labels: Record<AdapterHealth['category'], string> = {
    enterprises: 'Entreprises',
    territorial: 'Territorial',
    signals: 'Signaux faibles',
    news: 'Actualites',
  };
  return labels[category] || category;
}

/**
 * Get category icon
 */
export function getCategoryIcon(category: AdapterHealth['category']): string {
  const icons: Record<AdapterHealth['category'], string> = {
    enterprises: '🏢',
    territorial: '🗺️',
    signals: '📊',
    news: '📰',
  };
  return icons[category] || '📦';
}

/**
 * Calculate overall health percentage
 */
export function calculateHealthPercentage(
  health: SourcesHealthResponse
): number {
  if (health.total === 0) return 0;
  // online = 100%, degraded = 50%, offline = 0%
  const score =
    (health.online * 100 + health.degraded * 50) / health.total;
  return Math.round(score);
}
