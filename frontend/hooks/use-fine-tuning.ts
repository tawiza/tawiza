'use client';

import useSWR, { SWRConfiguration, mutate } from 'swr';
import { useState, useCallback } from 'react';

// Use relative URLs for Next.js proxy
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

export interface FineTuningJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  project_id: string;
  base_model: string;
  model_name: string;
  training_examples: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  error?: string;
  test_result?: Record<string, any>;
}

export interface FineTunedModel {
  name: string;
  base_model: string;
  created_at: string;
  size?: number;
  parameters?: Record<string, any>;
}

export interface TrainingDataStats {
  total_interactions: number;
  success_traces: number;
  preference_pairs: number;
  positive_feedback: number;
  negative_feedback: number;
  avg_quality_score: number;
  last_collected: string | null;
}

export interface FineTuningHealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  ollama_url: string;
  ollama_connected: boolean;
  error?: string;
}

export interface StartFineTuningRequest {
  project_id: string;
  base_model: string;
  task_type?: string;
  model_name?: string;
  annotations?: any[];
}

export interface OumiTrainingConfig {
  base_model: string;
  use_lora: boolean;
  lora_rank: number;
  learning_rate: number;
  num_epochs: number;
  batch_size: number;
  use_coalm: boolean;
  coalm_agents: number;
  territory_code?: string;
  quantization: '4bit' | '8bit' | 'none';
}

export interface LabelStudioProject {
  id: string;
  name: string;
  description: string;
  total_tasks: number;
  annotated_tasks: number;
}

export interface StartFromLabelStudioRequest {
  project_id: string;
  base_model: string;
  task_type?: string;
  model_name?: string;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Get fine-tuning service health status
 */
export function useFineTuningHealth(config?: SWRConfiguration) {
  return useSWR<FineTuningHealthStatus>(
    `${API_BASE}/api/v1/fine-tuning/health`,
    fetcher,
    {
      refreshInterval: 30000, // Check every 30s
      revalidateOnFocus: false,
      ...config,
    }
  );
}

/**
 * List all fine-tuning jobs
 */
export function useFineTuningJobs(projectId?: string, config?: SWRConfiguration) {
  const url = projectId
    ? `${API_BASE}/api/v1/fine-tuning/jobs?project_id=${projectId}`
    : `${API_BASE}/api/v1/fine-tuning/jobs`;

  return useSWR<FineTuningJob[]>(url, fetcher, {
    refreshInterval: 5000, // Refresh every 5s for active jobs
    revalidateOnFocus: true,
    ...config,
  });
}

/**
 * Get a specific job status
 */
export function useFineTuningJob(jobId: string | null, config?: SWRConfiguration) {
  return useSWR<FineTuningJob>(
    jobId ? `${API_BASE}/api/v1/fine-tuning/jobs/${jobId}` : null,
    fetcher,
    {
      refreshInterval: 2000, // Refresh every 2s for active monitoring
      revalidateOnFocus: true,
      ...config,
    }
  );
}

/**
 * List fine-tuned models
 */
export function useFineTunedModels(config?: SWRConfiguration) {
  return useSWR<{ models: FineTunedModel[]; total: number }>(
    `${API_BASE}/api/v1/fine-tuning/models`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
      ...config,
    }
  );
}

/**
 * Get job logs
 */
export function useJobLogs(jobId: string | null, lines: number = 100, config?: SWRConfiguration) {
  return useSWR<{ job_id: string; content: string; lines: number }>(
    jobId ? `${API_BASE}/api/v1/fine-tuning/jobs/${jobId}/logs?lines=${lines}` : null,
    fetcher,
    {
      refreshInterval: 3000,
      revalidateOnFocus: true,
      ...config,
    }
  );
}

/**
 * Get training data statistics
 */
export function useTrainingDataStats(config?: SWRConfiguration) {
  return useSWR<TrainingDataStats>(
    `${API_BASE}/api/v1/training/stats`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      fallbackData: {
        total_interactions: 0,
        success_traces: 0,
        preference_pairs: 0,
        positive_feedback: 0,
        negative_feedback: 0,
        avg_quality_score: 0,
        last_collected: null,
      },
      ...config,
    }
  );
}

/**
 * Hook for starting a fine-tuning job
 */
export function useStartFineTuning() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startFineTuning = useCallback(async (request: StartFineTuningRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/fine-tuning/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to start fine-tuning');
      }

      const job = await res.json();
      // Invalidate jobs cache
      mutate(`${API_BASE}/api/v1/fine-tuning/jobs`);
      return job;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { startFineTuning, isLoading, error };
}

/**
 * Hook for cancelling a job
 */
export function useCancelJob() {
  const [isLoading, setIsLoading] = useState(false);

  const cancelJob = useCallback(async (jobId: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/fine-tuning/jobs/${jobId}/cancel`, {
        method: 'POST',
      });

      if (!res.ok) {
        throw new Error('Failed to cancel job');
      }

      const result = await res.json();
      mutate(`${API_BASE}/api/v1/fine-tuning/jobs`);
      mutate(`${API_BASE}/api/v1/fine-tuning/jobs/${jobId}`);
      return result;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { cancelJob, isLoading };
}

/**
 * Hook for deleting a model
 */
export function useDeleteModel() {
  const [isLoading, setIsLoading] = useState(false);

  const deleteModel = useCallback(async (modelName: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/fine-tuning/models/${encodeURIComponent(modelName)}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        throw new Error('Failed to delete model');
      }

      const result = await res.json();
      mutate(`${API_BASE}/api/v1/fine-tuning/models`);
      return result;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { deleteModel, isLoading };
}

/**
 * List Label Studio projects
 */
export function useLabelStudioProjects(config?: SWRConfiguration) {
  return useSWR<LabelStudioProject[]>(
    `${API_BASE}/api/v1/annotations/projects`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
      fallbackData: [],
      ...config,
    }
  );
}

/**
 * Check Label Studio health
 */
export function useLabelStudioHealth(config?: SWRConfiguration) {
  return useSWR<{ status: string; connected: boolean }>(
    `${API_BASE}/api/v1/annotations/health`,
    fetcher,
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      fallbackData: { status: 'unknown', connected: false },
      ...config,
    }
  );
}

/**
 * Hook for starting fine-tuning from Label Studio project
 */
export function useStartFromLabelStudio() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startFromLabelStudio = useCallback(async (request: StartFromLabelStudioRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        project_id: request.project_id,
        base_model: request.base_model,
        task_type: request.task_type || 'classification',
      });
      if (request.model_name) {
        params.append('model_name', request.model_name);
      }

      const res = await fetch(`${API_BASE}/api/v1/fine-tuning/from-label-studio?${params}`, {
        method: 'POST',
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to start fine-tuning from Label Studio');
      }

      const job = await res.json();
      // Invalidate jobs cache
      mutate(`${API_BASE}/api/v1/fine-tuning/jobs`);
      return job;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { startFromLabelStudio, isLoading, error, clearError: () => setError(null) };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get status badge color (Nord theme)
 */
export function getJobStatusColor(status: FineTuningJob['status']): string {
  const colors: Record<string, string> = {
    pending: 'var(--warning)',    // Yellow
    running: 'var(--info)',    // Cyan
    completed: '#A3BE8C',  // Green
    failed: 'var(--error)',     // Red
    cancelled: '#4C566A',  // Gray
  };
  return colors[status] || '#4C566A';
}

/**
 * Get status label (French)
 */
export function getJobStatusLabel(status: FineTuningJob['status']): string {
  const labels: Record<string, string> = {
    pending: 'En attente',
    running: 'En cours',
    completed: 'Termine',
    failed: 'Echoue',
    cancelled: 'Annule',
  };
  return labels[status] || status;
}

/**
 * Format model size
 */
export function formatModelSize(bytes?: number): string {
  if (!bytes) return 'N/A';
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)} GB`;
}

/**
 * Format duration
 */
export function formatDuration(startedAt?: string, completedAt?: string): string {
  if (!startedAt) return 'N/A';

  const start = new Date(startedAt);
  const end = completedAt ? new Date(completedAt) : new Date();
  const seconds = Math.floor((end.getTime() - start.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
