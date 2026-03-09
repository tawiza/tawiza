'use client';

import useSWR from 'swr';
import { useState, useCallback } from 'react';

// Use relative URLs for Next.js proxy
const API_BASE = '';

// ============================================================================
// Types
// ============================================================================

export interface ProxyConfig {
  url: string;
  name: string;
  enabled: boolean;
  country: string;
}

export interface ProxyPoolConfig {
  enabled: boolean;
  strategy: 'round_robin' | 'random' | 'weighted';
  max_failures: number;
  recovery_time_seconds: number;
  health_check_interval: number;
  proxies: ProxyConfig[];
}

export interface CaptchaConfig {
  enabled: boolean;
  provider: '2captcha' | 'anticaptcha';
  api_key_2captcha: string;
  api_key_anticaptcha: string;
  timeout_seconds: number;
  max_retries: number;
}

export interface HeadersConfig {
  rotate_user_agent: boolean;
  browsers: string[];
  languages: string[];
  include_dnt: boolean;
  custom_headers: Record<string, string>;
}

export interface RateLimitConfig {
  enabled: boolean;
  requests_per_second: number;
  burst_size: number;
  per_domain_limits: Record<string, number>;
}

export interface StealthConfig {
  enabled: boolean;
  prefer_nodriver: boolean;
  prefer_camoufox_for: string[];
  headless: boolean;
  screenshot_on_error: boolean;
  max_concurrent_browsers: number;
}

export interface CrawlerConfig {
  proxy_pool: ProxyPoolConfig;
  captcha: CaptchaConfig;
  headers: HeadersConfig;
  rate_limit: RateLimitConfig;
  stealth: StealthConfig;
  timeout_seconds: number;
  max_retries: number;
  respect_robots_txt: boolean;
  cache_enabled: boolean;
  cache_ttl_seconds: number;
}

export interface CrawlerStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  avg_response_time_ms: number;
  requests_by_source: Record<string, number>;
  captcha_solved: number;
  proxies_used: number;
  stealth_requests: number;
}

export interface CrawlerStatus {
  status: string;
  config: {
    proxies_enabled: boolean;
    proxies_count: number;
    captcha_enabled: boolean;
    captcha_provider: string | null;
    stealth_enabled: boolean;
    rate_limit_rps: number;
  };
  stealth_browsers: {
    nodriver: boolean;
    camoufox: boolean;
  };
  stats_summary: {
    total_requests: number;
    success_rate: number;
  };
}

export interface ProxyTestResult {
  status: 'success' | 'error';
  origin_ip?: string;
  response_time_ms?: number;
  message?: string;
  code?: number;
}

export interface CaptchaTestResult {
  status: 'success' | 'error';
  balance?: string | number;
  message?: string;
}

// ============================================================================
// Fetcher
// ============================================================================

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    const error = new Error('API error');
    throw error;
  }
  return res.json();
};

// ============================================================================
// Hook: useCrawlerConfig
// ============================================================================

export function useCrawlerConfig() {
  const { data, error, isLoading, mutate } = useSWR<CrawlerConfig>(
    `${API_BASE}/api/v1/crawler/config`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  const updateConfig = useCallback(async (config: CrawlerConfig): Promise<CrawlerConfig> => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error('Failed to update config');
    const updated = await res.json();
    mutate(updated, false);
    return updated;
  }, [mutate]);

  return {
    config: data,
    error,
    isLoading,
    updateConfig,
    refresh: () => mutate(),
  };
}

// ============================================================================
// Hook: useCrawlerStats
// ============================================================================

export function useCrawlerStats(refreshInterval = 30000) {
  const { data, error, isLoading, mutate } = useSWR<CrawlerStats>(
    `${API_BASE}/api/v1/crawler/stats`,
    fetcher,
    {
      refreshInterval,
      revalidateOnFocus: true,
    }
  );

  const resetStats = useCallback(async () => {
    await fetch(`${API_BASE}/api/v1/crawler/stats/reset`, { method: 'POST' });
    mutate();
  }, [mutate]);

  return {
    stats: data,
    error,
    isLoading,
    resetStats,
    refresh: () => mutate(),
  };
}

// ============================================================================
// Hook: useCrawlerStatus
// ============================================================================

export function useCrawlerStatus(refreshInterval = 15000) {
  const { data, error, isLoading, mutate } = useSWR<CrawlerStatus>(
    `${API_BASE}/api/v1/crawler/status`,
    fetcher,
    {
      refreshInterval,
      revalidateOnFocus: true,
    }
  );

  return {
    status: data,
    error,
    isLoading,
    refresh: () => mutate(),
  };
}

// ============================================================================
// Hook: useProxyManager
// ============================================================================

export function useProxyManager() {
  const { config, updateConfig, refresh } = useCrawlerConfig();
  const [testResult, setTestResult] = useState<ProxyTestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const addProxy = useCallback(async (proxy: ProxyConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/proxy/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(proxy),
    });
    if (!res.ok) throw new Error('Failed to add proxy');
    refresh();
    return res.json();
  }, [refresh]);

  const removeProxy = useCallback(async (index: number) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/proxy/${index}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to remove proxy');
    refresh();
    return res.json();
  }, [refresh]);

  const testProxy = useCallback(async (proxy: ProxyConfig): Promise<ProxyTestResult> => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/crawler/config/proxy/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proxy),
      });
      const result = await res.json();
      setTestResult(result);
      return result;
    } finally {
      setIsTesting(false);
    }
  }, []);

  const updateProxyPool = useCallback(async (proxyPool: ProxyPoolConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/proxy`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(proxyPool),
    });
    if (!res.ok) throw new Error('Failed to update proxy pool');
    refresh();
    return res.json();
  }, [refresh]);

  return {
    proxyPool: config?.proxy_pool,
    addProxy,
    removeProxy,
    testProxy,
    testResult,
    isTesting,
    updateProxyPool,
  };
}

// ============================================================================
// Hook: useCaptchaConfig
// ============================================================================

export function useCaptchaConfig() {
  const { config, refresh } = useCrawlerConfig();
  const [testResult, setTestResult] = useState<CaptchaTestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const updateCaptcha = useCallback(async (captchaConfig: CaptchaConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/captcha`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(captchaConfig),
    });
    if (!res.ok) throw new Error('Failed to update captcha config');
    refresh();
    return res.json();
  }, [refresh]);

  const testCaptchaApi = useCallback(async (provider: '2captcha' | 'anticaptcha'): Promise<CaptchaTestResult> => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/crawler/config/captcha/test?provider=${provider}`, {
        method: 'POST',
      });
      const result = await res.json();
      setTestResult(result);
      return result;
    } finally {
      setIsTesting(false);
    }
  }, []);

  return {
    captcha: config?.captcha,
    updateCaptcha,
    testCaptchaApi,
    testResult,
    isTesting,
  };
}

// ============================================================================
// Hook: useStealthConfig
// ============================================================================

export function useStealthConfig() {
  const { config, refresh } = useCrawlerConfig();

  const updateStealth = useCallback(async (stealthConfig: StealthConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/stealth`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stealthConfig),
    });
    if (!res.ok) throw new Error('Failed to update stealth config');
    refresh();
    return res.json();
  }, [refresh]);

  return {
    stealth: config?.stealth,
    updateStealth,
  };
}

// ============================================================================
// Hook: useHeadersConfig
// ============================================================================

export function useHeadersConfig() {
  const { config, refresh } = useCrawlerConfig();

  const updateHeaders = useCallback(async (headersConfig: HeadersConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/headers`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(headersConfig),
    });
    if (!res.ok) throw new Error('Failed to update headers config');
    refresh();
    return res.json();
  }, [refresh]);

  return {
    headers: config?.headers,
    updateHeaders,
  };
}

// ============================================================================
// Hook: useRateLimitConfig
// ============================================================================

export function useRateLimitConfig() {
  const { config, refresh } = useCrawlerConfig();

  const updateRateLimit = useCallback(async (rateLimitConfig: RateLimitConfig) => {
    const res = await fetch(`${API_BASE}/api/v1/crawler/config/rate-limit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rateLimitConfig),
    });
    if (!res.ok) throw new Error('Failed to update rate limit config');
    refresh();
    return res.json();
  }, [refresh]);

  return {
    rateLimit: config?.rate_limit,
    updateRateLimit,
  };
}
