/**
 * API hooks for News Intelligence features.
 * Endpoints: sentiments, focal-points, enriched articles, department health, spikes, scheduler
 */

import useSWR from 'swr';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Types ────────────────────────────────────────────────────────

export interface SentimentData {
  sentiment_distribution: Record<string, number>;
  total_articles: number;
}

export interface FocalPoint {
  entity: string;
  score: number;
  source_count: number;
  mention_count: number;
  sources: string[];
  articles: {
    id: number;
    title: string;
    url: string;
    source: string;
    feed: string;
    published_at: string | null;
  }[];
  is_known_actor: boolean;
  actor?: {
    actor_id: string;
    actor_type: string;
    actor_name: string;
    external_id: string;
    department: string;
  };
}

export interface FocalPointsResponse {
  focal_points: FocalPoint[];
  count: number;
  params: Record<string, unknown>;
}

export interface EnrichedArticle {
  id: number;
  title: string;
  url: string;
  source: string;
  feed_name: string;
  feed_category: string;
  published_at: string | null;
  ai_summary: string;
  sentiment: string;
  domain: string;
}

export interface NewsArticle {
  id: number;
  title: string;
  url: string;
  source: string;
  feed_name: string;
  feed_category: string;
  published_at: string | null;
  domain: string;
  summary?: string;
  ai_summary?: string;
  sentiment?: string;
  author?: string;
  tags?: string[];
}

export interface DepartmentHealth {
  department: string;
  score: number;
  grade: string;
  computed_at?: string;
  components: {
    baseline: {
      score: number;
      actor_count: number;
      type_count: number;
      relation_count: number;
      density_score: number;
      diversity_score: number;
      connectivity_score: number;
    };
    events: {
      score: number;
      news_48h: number;
      news_7d: number;
      bodacc_7d: number;
      acceleration: number;
      news_score: number;
      bodacc_score: number;
      accel_score: number;
    };
    boosts: {
      total: number;
      details: unknown[];
    };
  };
}

export interface DepartmentHealthResponse {
  departments: DepartmentHealth[];
  count: number;
  computed_at: string;
}

export interface SpikeInfo {
  stream: string;
  current_value: number;
  mean: number;
  std_dev: number;
  z_score: number;
  severity: string;
  detected_at: string;
}

export interface SpikesResponse {
  active_spikes: SpikeInfo[];
  spike_count: number;
  streams_monitored: number;
  streams: Record<string, unknown>;
}

export interface SchedulerStatus {
  running: boolean;
  interval_hours: number;
  run_count: number;
  last_run: string | null;
  last_result: Record<string, unknown> | null;
}

export interface NewsStats {
  total_articles: number;
  last_24h: number;
  by_category: Record<string, number>;
  hourly_distribution: { hour: string; count: number }[];
  sentiment_distribution: Record<string, number>;
  feeds_active: number;
  breakers_open: number;
}

// ── SWR Hooks ────────────────────────────────────────────────────

export function useSentiments() {
  return useSWR<SentimentData>(
    '/api/v1/sources/feeds/db/sentiments',
    fetcher,
    { refreshInterval: 60_000 }
  );
}

export function useFocalPoints(hours = 48, limit = 20) {
  return useSWR<FocalPointsResponse>(
    `/api/v1/sources/focal-points?hours=${hours}&limit=${limit}`,
    fetcher,
    { refreshInterval: 120_000 }
  );
}

interface EnrichedResponse {
  articles: EnrichedArticle[];
  total: number;
  filter: Record<string, unknown>;
}

export function useEnrichedArticles(sentiment?: string, limit = 30) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sentiment) params.set('sentiment', sentiment);
  const { data, ...rest } = useSWR<EnrichedResponse>(
    `/api/v1/sources/feeds/db/enriched?${params}`,
    fetcher,
    { refreshInterval: 60_000 }
  );
  return { data: data?.articles, ...rest };
}

export function useArticleSearch(keywords?: string, category?: string, limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (keywords) params.set('keywords', keywords);
  if (category) params.set('feed_category', category);
  const key = keywords || category
    ? `/api/v1/sources/feeds/db/latest?${params}`
    : null;
  const { data, ...rest } = useSWR<{ articles: NewsArticle[]; total: number }>(
    key,
    fetcher,
    { refreshInterval: 60_000 }
  );
  return { data: data?.articles, total: data?.total, ...rest };
}

export function useDepartmentHealth() {
  return useSWR<DepartmentHealthResponse>(
    '/api/v1/sources/departments/health',
    fetcher,
    { refreshInterval: 300_000 }
  );
}

export function useSpikes() {
  return useSWR<SpikesResponse>(
    '/api/v1/sources/spikes',
    fetcher,
    { refreshInterval: 30_000 }
  );
}

export function useSchedulerStatus() {
  return useSWR<SchedulerStatus>(
    '/api/v1/sources/intelligence/status',
    fetcher,
    { refreshInterval: 10_000 }
  );
}

export function useNewsStats() {
  return useSWR<NewsStats>(
    '/api/v1/sources/feeds/db/stats',
    fetcher,
    { refreshInterval: 60_000 }
  );
}

// ── Phase 2: Analytical Types ────────────────────────────────────

export interface SentimentTrendDay {
  date: string;
  positif: number;
  negatif: number;
  neutre: number;
}

export interface SentimentTrendsResponse {
  trends: SentimentTrendDay[];
  days: number;
}

export interface HeatmapFeed {
  feed_name: string;
  feed_category: string;
  total: number;
  positif: number;
  negatif: number;
  neutre: number;
}

export interface HeatmapResponse {
  feeds: HeatmapFeed[];
  count: number;
  days: number;
}

// ── Phase 2: Analytical Hooks ───────────────────────────────────

export function useSentimentTrends(days = 7) {
  return useSWR<SentimentTrendsResponse>(
    `/api/v1/sources/feeds/db/sentiments/trends?days=${days}`,
    fetcher,
    { refreshInterval: 120_000 }
  );
}

export function useSentimentHeatmap(days = 30) {
  return useSWR<HeatmapResponse>(
    `/api/v1/sources/feeds/db/sentiments/heatmap?days=${days}`,
    fetcher,
    { refreshInterval: 120_000 }
  );
}

// ── Actions (non-SWR) ────────────────────────────────────────────

export async function triggerIntelligenceRun(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/sources/intelligence/run`, { method: 'POST' });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export async function startScheduler(intervalHours = 6): Promise<void> {
  await fetch(`${API_BASE}/api/v1/sources/intelligence/start?interval_hours=${intervalHours}`, {
    method: 'POST',
  });
}

export async function stopScheduler(): Promise<void> {
  await fetch(`${API_BASE}/api/v1/sources/intelligence/stop`, { method: 'POST' });
}
