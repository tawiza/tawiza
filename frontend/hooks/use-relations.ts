'use client';

import { useState, useCallback } from 'react';
import type {
  RelationGraphData,
  CoverageScore,
  GapsReport,
  DiscoverResult,
  WhatIfResponse,
  NetworkAnalytics,
  EcosystemScore,
} from '@/types/relations';

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

/** Default timeout for quick GET endpoints (graph, coverage, gaps, analytics). */
const DEFAULT_TIMEOUT_MS = 30_000;

/** Long timeout for heavy endpoints (discover pipeline, what-if simulation). */
const LONG_TIMEOUT_MS = 120_000;

/**
 * Fetch JSON with configurable timeout and error handling.
 */
async function fetchJSON<T>(
  url: string,
  options?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    });

    clearTimeout(timeout);

    if (!res.ok) {
      console.error(`Relations API error: ${res.status} ${res.statusText}`);
      return null;
    }

    return await res.json();
  } catch (error) {
    clearTimeout(timeout);
    if (error instanceof Error && error.name === 'AbortError') {
      console.warn(`Relations API request timed out after ${timeoutMs}ms: ${url}`);
    } else {
      console.error('Relations API request failed:', error);
    }
    return null;
  }
}

/**
 * Hook for managing relation graph data, coverage scores, and gap analysis
 * for a given department.
 *
 * @param departmentCode - The department code (e.g. '75', '13') or null
 */
export function useRelations(departmentCode: string | null) {
  const [graph, setGraph] = useState<RelationGraphData | null>(null);
  const [coverage, setCoverage] = useState<CoverageScore | null>(null);
  const [gaps, setGaps] = useState<GapsReport | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null);
  const [analytics, setAnalytics] = useState<NetworkAnalytics | null>(null);
  const [ecosystemScore, setEcosystemScore] = useState<EcosystemScore | null>(null);
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [simulating, setSimulating] = useState(false);

  const fetchGraph = useCallback(async (minConfidence = 0.4, types?: string) => {
    if (!departmentCode) return;
    setLoading(true);
    const params = new URLSearchParams({ min_confidence: String(minConfidence) });
    if (types) params.set('types', types);
    const url = departmentCode === 'all'
      ? `${API_BASE}/api/v1/investigation/relations/all?${params}`
      : `${API_BASE}/api/v1/investigation/relations/${departmentCode}?${params}`;
    const data = await fetchJSON<RelationGraphData>(url);
    setGraph(data);
    setLoading(false);
  }, [departmentCode]);

  const fetchCoverage = useCallback(async () => {
    if (!departmentCode || departmentCode === 'all') {
      setCoverage(null);
      return;
    }
    const data = await fetchJSON<CoverageScore>(
      `${API_BASE}/api/v1/investigation/relations/coverage/${departmentCode}`
    );
    setCoverage(data);
  }, [departmentCode]);

  const fetchGaps = useCallback(async () => {
    if (!departmentCode || departmentCode === 'all') {
      setGaps(null);
      return;
    }
    const data = await fetchJSON<GapsReport>(
      `${API_BASE}/api/v1/investigation/relations/gaps/${departmentCode}`
    );
    setGaps(data);
  }, [departmentCode]);

  const discover = useCallback(async (sources = ['sirene', 'bodacc']) => {
    if (!departmentCode) return null;
    setDiscovering(true);
    const result = await fetchJSON<DiscoverResult>(
      `${API_BASE}/api/v1/investigation/relations/discover`,
      {
        method: 'POST',
        body: JSON.stringify({ department_code: departmentCode, sources, depth: 2 }),
      },
      LONG_TIMEOUT_MS,
    );
    setDiscovering(false);
    // Always try to load the graph after discover (data may exist even if discover timed out)
    await Promise.all([fetchGraph(), fetchCoverage(), fetchGaps()]);
    return result;
  }, [departmentCode, fetchGraph, fetchCoverage, fetchGaps]);

  const whatif = useCallback(async (actorExternalId: string, maxDepth = 3) => {
    if (!departmentCode) return null;
    setSimulating(true);
    setWhatIfResult(null);
    const result = await fetchJSON<WhatIfResponse>(
      `${API_BASE}/api/v1/investigation/relations/what-if`,
      {
        method: 'POST',
        body: JSON.stringify({
          actor_external_id: actorExternalId,
          department_code: departmentCode,
          max_depth: maxDepth,
        }),
      },
      LONG_TIMEOUT_MS,
    );
    setWhatIfResult(result);
    setSimulating(false);
    return result;
  }, [departmentCode]);

  const exportGraph = useCallback(async (format: 'json' | 'csv' | 'graphml' = 'json') => {
    if (!departmentCode) return null;
    const url = `${API_BASE}/api/v1/investigation/relations/export/${departmentCode}?format=${format}`;

    // GraphML returns XML (blob download), not JSON
    if (format === 'graphml') {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
      try {
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeout);
        if (!res.ok) {
          console.error(`Relations API error: ${res.status} ${res.statusText}`);
          return null;
        }
        const blob = await res.blob();
        const anchor = document.createElement('a');
        anchor.href = URL.createObjectURL(blob);
        anchor.download = `relations-${departmentCode}.graphml`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(anchor.href);
        return null;
      } catch (error) {
        clearTimeout(timeout);
        console.error('GraphML export failed:', error);
        return null;
      }
    }

    return fetchJSON<Record<string, unknown>>(url);
  }, [departmentCode]);

  const fetchAnalytics = useCallback(async () => {
    if (!departmentCode) return;
    const endpoint = departmentCode === 'all'
      ? `${API_BASE}/api/v1/investigation/relations/analytics/cross-dept`
      : `${API_BASE}/api/v1/investigation/relations/analytics/${departmentCode}`;
    const data = await fetchJSON<NetworkAnalytics>(endpoint);
    setAnalytics(data);
  }, [departmentCode]);

  const fetchEcosystemScore = useCallback(async () => {
    if (!departmentCode || departmentCode === 'all') {
      setEcosystemScore(null);
      return;
    }
    const data = await fetchJSON<EcosystemScore>(
      `${API_BASE}/api/v1/investigation/relations/ecosystem/${departmentCode}`
    );
    setEcosystemScore(data);
  }, [departmentCode]);

  return {
    graph, coverage, gaps, whatIfResult, analytics, ecosystemScore,
    loading, discovering, simulating,
    fetchGraph, fetchCoverage, fetchGaps, discover, whatif, exportGraph, fetchAnalytics, fetchEcosystemScore,
  };
}
