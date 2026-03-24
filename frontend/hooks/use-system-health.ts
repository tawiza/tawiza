'use client';

import useSWR from 'swr';
import { useCallback } from 'react';

// Types
export type ServiceStatus = 'connected' | 'degraded' | 'disconnected' | 'checking';

export interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  latency_ms: number | null;
  message: string | null;
  details: Record<string, any> | null;
}

export interface DetailedHealth {
  overall: 'healthy' | 'degraded' | 'unhealthy';
  services: ServiceHealth[];
  checked_at: string;
}

export interface OllamaModel {
  name: string;
  size: number;
  size_gb: number;
  modified_at: string;
  digest: string | null;
  details: Record<string, any> | null;
}

export interface OllamaModelsResponse {
  models: OllamaModel[];
  default_model: string | null;
  total: number;
}

// Fetcher
const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
};

// ============================================================================
// System Health Hook
// ============================================================================

export function useSystemHealth(refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<DetailedHealth>(
    '/api/v1/health/detailed',
    fetcher,
    {
      refreshInterval,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
      errorRetryCount: 2,
    }
  );

  const refresh = useCallback(() => {
    mutate();
  }, [mutate]);

  // Helper to get specific service status
  const getService = useCallback(
    (name: string): ServiceHealth | undefined => {
      return data?.services.find((s) => s.name === name);
    },
    [data]
  );

  // Check if all critical services are connected
  const isCriticalHealthy = useCallback(() => {
    const critical = ['backend', 'ollama'];
    return critical.every((name) => getService(name)?.status === 'connected');
  }, [getService]);

  return {
    health: data,
    services: data?.services ?? [],
    overall: data?.overall ?? 'unhealthy',
    isLoading,
    error,
    refresh,
    getService,
    isCriticalHealthy,
  };
}

// ============================================================================
// Ollama Models Hook
// ============================================================================

export function useOllamaModels() {
  const { data, error, isLoading, mutate } = useSWR<OllamaModelsResponse>(
    '/api/v1/ollama/models',
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000, // 1 minute cache
    }
  );

  const refresh = useCallback(() => {
    mutate();
  }, [mutate]);

  const setDefaultModel = useCallback(
    async (modelName: string) => {
      try {
        const res = await fetch('/api/v1/ollama/models/default', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: modelName }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to set default model');
        }

        // Refresh the list
        await mutate();
        return true;
      } catch (err) {
        console.error('Failed to set default model:', err);
        throw err;
      }
    },
    [mutate]
  );

  const pullModel = useCallback(
    async (modelName: string) => {
      try {
        const res = await fetch('/api/v1/ollama/models/pull', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: modelName }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to pull model');
        }

        // Refresh the list
        await mutate();
        return true;
      } catch (err) {
        console.error('Failed to pull model:', err);
        throw err;
      }
    },
    [mutate]
  );

  const deleteModel = useCallback(
    async (modelName: string) => {
      try {
        const res = await fetch(`/api/v1/ollama/models/${encodeURIComponent(modelName)}`, {
          method: 'DELETE',
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to delete model');
        }

        // Refresh the list
        await mutate();
        return true;
      } catch (err) {
        console.error('Failed to delete model:', err);
        throw err;
      }
    },
    [mutate]
  );

  return {
    models: data?.models ?? [],
    defaultModel: data?.default_model ?? null,
    total: data?.total ?? 0,
    isLoading,
    error,
    refresh,
    setDefaultModel,
    pullModel,
    deleteModel,
  };
}

// ============================================================================
// Service Status Hook (Single Service)
// ============================================================================

export function useServiceHealth(serviceName: string, refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<ServiceHealth>(
    `/api/v1/health/services/${serviceName}`,
    fetcher,
    {
      refreshInterval,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  );

  return {
    service: data,
    status: data?.status ?? 'checking',
    latency: data?.latency_ms ?? null,
    message: data?.message ?? null,
    isLoading,
    error,
    refresh: () => mutate(),
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

export function getStatusColor(status: ServiceStatus): string {
  switch (status) {
    case 'connected':
      return '#A3BE8C'; // Nord green
    case 'degraded':
      return '#EBCB8B'; // Nord yellow
    case 'disconnected':
      return '#BF616A'; // Nord red
    case 'checking':
    default:
      return '#4C566A'; // Nord gray
  }
}

export function getStatusIcon(status: ServiceStatus): string {
  switch (status) {
    case 'connected':
      return '✓';
    case 'degraded':
      return '⚠';
    case 'disconnected':
      return '✗';
    case 'checking':
    default:
      return '○';
  }
}

export function getStatusLabel(status: ServiceStatus): string {
  switch (status) {
    case 'connected':
      return 'Connecte';
    case 'degraded':
      return 'Degrade';
    case 'disconnected':
      return 'Deconnecte';
    case 'checking':
    default:
      return 'Verification...';
  }
}

export function formatLatency(ms: number | null): string {
  if (ms === null) return '--';
  if (ms < 1) return '<1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
