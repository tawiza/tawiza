'use client';

import useSWR, { SWRConfiguration } from 'swr';
import useSWRMutation from 'swr/mutation';

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

// POST fetcher for mutations
const postFetcher = async (url: string, { arg }: { arg: any }) => {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(arg),
  });
  if (!res.ok) {
    const error = new Error('API request failed');
    (error as any).status = res.status;
    (error as any).info = await res.json().catch(() => ({}));
    throw error;
  }
  return res.json();
};

// ============================================================================
// Types - Investigation
// ============================================================================

export type RiskLevel = 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'CRITICAL';

export interface Signal {
  code: string;
  name: string;
  category: 'BODACC' | 'SIRENE' | 'BOAMP' | 'DERIVED';
  value: any;
  likelihood_ratio: number;
  direction: 'positive' | 'negative' | 'neutral';
  description: string;
  source: string;
  detected_at: string;
}

export interface RiskAssessment {
  siren: string;
  denomination: string;
  prior_probability: number;
  posterior_probability: number;
  risk_level: RiskLevel;
  confidence: number;
  data_coverage: number;
  signals: Signal[];
  interpretation: string;
  computed_at: string;
}

export interface InvestigationResult {
  status: 'success' | 'error';
  assessment?: RiskAssessment;
  error?: string;
}

export interface InvestigationMarkdown {
  status: 'success' | 'error';
  siren: string;
  markdown: string;
  error?: string;
}

export interface SignalsResult {
  status: 'success' | 'error';
  siren: string;
  signals: Signal[];
  error?: string;
}

// ============================================================================
// Types - Risk Score
// ============================================================================

export type RiskScoreLevel = 'TRES_FAIBLE' | 'FAIBLE' | 'MODERE' | 'ELEVE' | 'TRES_ELEVE' | 'CRITIQUE';

export interface RiskFactor {
  name: string;
  value: any;
  impact: number;
  direction: 'positive' | 'negative' | 'critical' | 'neutral';
  description: string;
  recommendation: string | null;
}

export interface RiskScore {
  siren: string;
  denomination: string;
  score: number;
  risk_level: RiskScoreLevel;
  confidence: number;
  confidence_interval: [number, number];
  data_quality: number;
  computed_at: string;
  top_factors: RiskFactor[];
}

export interface RiskExplanation {
  siren: string;
  denomination: string;
  score: RiskScore;
  factors: RiskFactor[];
  summary: string;
  detailed_analysis: string;
  recommendations: string[];
  data_sources: string[];
  generated_at: string;
}

export interface RiskScoreResult {
  status: 'success' | 'error';
  score?: RiskScore;
  error?: string;
}

export interface RiskExplanationResult {
  status: 'success' | 'error';
  explanation?: RiskExplanation;
  error?: string;
}

export interface RiskMarkdownResult {
  status: 'success' | 'error';
  siren: string;
  markdown: string;
  error?: string;
}

// ============================================================================
// Investigation Hooks
// ============================================================================

/**
 * Get full investigation for an enterprise
 *
 * @param siren - SIREN number (9 digits)
 * @param config - SWR configuration
 */
export function useInvestigation(
  siren: string | null,
  config?: SWRConfiguration
) {
  return useSWR<InvestigationResult>(
    siren ? `${API_BASE}/api/v1/tajine/investigate/${siren}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000, // 1 minute cache
      ...config,
    }
  );
}

/**
 * Trigger a new investigation (POST)
 */
export function useInvestigateMutation() {
  return useSWRMutation(
    `${API_BASE}/api/v1/tajine/investigate`,
    postFetcher
  );
}

/**
 * Get investigation as markdown report
 *
 * @param siren - SIREN number (9 digits)
 * @param config - SWR configuration
 */
export function useInvestigationMarkdown(
  siren: string | null,
  config?: SWRConfiguration
) {
  return useSWR<InvestigationMarkdown>(
    siren ? `${API_BASE}/api/v1/tajine/investigate/${siren}/markdown` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

/**
 * Get raw signals for an enterprise
 *
 * @param siren - SIREN number (9 digits)
 * @param config - SWR configuration
 */
export function useInvestigationSignals(
  siren: string | null,
  config?: SWRConfiguration
) {
  return useSWR<SignalsResult>(
    siren ? `${API_BASE}/api/v1/tajine/investigate/${siren}/signals` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

// ============================================================================
// Risk Score Hooks
// ============================================================================

/**
 * Get risk score for an enterprise
 *
 * @param siren - SIREN number (9 digits)
 * @param style - Explanation style (technical, business, summary)
 * @param config - SWR configuration
 */
export function useRiskScore(
  siren: string | null,
  style: 'technical' | 'business' | 'summary' = 'business',
  config?: SWRConfiguration
) {
  return useSWR<RiskScoreResult>(
    siren ? `${API_BASE}/api/v1/tajine/risk/${siren}?style=${style}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

/**
 * Get full risk explanation with factors and recommendations
 */
export function useRiskExplanation(
  siren: string | null,
  style: 'technical' | 'business' | 'summary' = 'business',
  config?: SWRConfiguration
) {
  return useSWRMutation<RiskExplanationResult, Error, string, { siren: string; style: string }>(
    `${API_BASE}/api/v1/tajine/risk/score`,
    async (url, { arg }) => {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ siren: arg.siren, style: arg.style }),
      });
      if (!res.ok) {
        throw new Error('Risk score request failed');
      }
      return res.json();
    }
  );
}

/**
 * Get risk analysis as markdown
 */
export function useRiskMarkdown(
  siren: string | null,
  style: 'technical' | 'business' | 'summary' = 'business',
  config?: SWRConfiguration
) {
  return useSWR<RiskMarkdownResult>(
    siren ? `${API_BASE}/api/v1/tajine/risk/${siren}/markdown?style=${style}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
      ...config,
    }
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get color for risk level (Nord theme)
 */
export function getRiskLevelColor(level: RiskLevel | RiskScoreLevel): string {
  const colors: Record<string, string> = {
    // Investigation levels
    LOW: '#A3BE8C',      // Green
    MODERATE: '#EBCB8B', // Yellow
    ELEVATED: '#D08770', // Orange
    HIGH: '#BF616A',     // Red
    CRITICAL: '#B48EAD', // Purple (critical)
    // Risk score levels (French)
    TRES_FAIBLE: '#A3BE8C',
    FAIBLE: '#8FBCBB',
    MODERE: '#EBCB8B',
    ELEVE: '#D08770',
    TRES_ELEVE: '#BF616A',
    CRITIQUE: '#B48EAD',
  };
  return colors[level] || '#4C566A';
}

/**
 * Get label for risk level (French)
 */
export function getRiskLevelLabel(level: RiskLevel | RiskScoreLevel): string {
  const labels: Record<string, string> = {
    LOW: 'Faible',
    MODERATE: 'Modere',
    ELEVATED: 'Eleve',
    HIGH: 'Eleve',
    CRITICAL: 'Critique',
    TRES_FAIBLE: 'Tres faible',
    FAIBLE: 'Faible',
    MODERE: 'Modere',
    ELEVE: 'Eleve',
    TRES_ELEVE: 'Tres eleve',
    CRITIQUE: 'Critique',
  };
  return labels[level] || level;
}

/**
 * Get icon for risk level
 */
export function getRiskLevelIcon(level: RiskLevel | RiskScoreLevel): string {
  const icons: Record<string, string> = {
    LOW: '🟢',
    MODERATE: '🟡',
    ELEVATED: '🟠',
    HIGH: '🔴',
    CRITICAL: '🟣',
    TRES_FAIBLE: '🟢',
    FAIBLE: '🟢',
    MODERE: '🟡',
    ELEVE: '🟠',
    TRES_ELEVE: '🔴',
    CRITIQUE: '🟣',
  };
  return icons[level] || '⚪';
}

/**
 * Get signal category label (French)
 */
export function getSignalCategoryLabel(category: Signal['category']): string {
  const labels: Record<Signal['category'], string> = {
    BODACC: 'Annonces legales',
    SIRENE: 'Donnees INSEE',
    BOAMP: 'Marches publics',
    DERIVED: 'Calcule',
  };
  return labels[category] || category;
}

/**
 * Format probability as percentage
 */
export function formatProbability(prob: number): string {
  return `${Math.round(prob * 100)}%`;
}

/**
 * Format confidence as text
 */
export function formatConfidence(confidence: number): string {
  if (confidence >= 0.8) return 'Elevee';
  if (confidence >= 0.6) return 'Moderee';
  if (confidence >= 0.4) return 'Limitee';
  return 'Faible';
}

/**
 * Get factor direction color
 */
export function getFactorDirectionColor(direction: RiskFactor['direction']): string {
  switch (direction) {
    case 'positive':
      return '#A3BE8C'; // Green - reduces risk
    case 'negative':
      return '#D08770'; // Orange - increases risk
    case 'critical':
      return '#BF616A'; // Red - critical factor
    case 'neutral':
    default:
      return '#4C566A'; // Gray
  }
}
