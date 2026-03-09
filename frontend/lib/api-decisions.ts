'use client';

import useSWR from 'swr';

const API_BASE = '/api/v1/decisions';

const fetcher = (url: string) => fetch(url).then(r => {
  if (!r.ok) throw new Error(`API error: ${r.status}`);
  return r.json();
});

// Types
export interface Stakeholder {
  id: string;
  name: string;
  role: string;
  organization: string;
  type: 'collectivite' | 'entreprise' | 'institution' | 'association';
  domains: string[];
  territory_dept: string;
  territory_scope: string;
  influence_level: number;
  contact_email: string | null;
  tags: string[];
  avatar_url: string | null;
  active: boolean;
  created_at: string;
}

export interface StakeholderRelation {
  id: string;
  from_id: string;
  to_id: string;
  from_name: string | null;
  to_name: string | null;
  type: 'collaboration' | 'hierarchie' | 'financement' | 'opposition' | 'consultation';
  strength: number;
  description: string | null;
  bidirectional: boolean;
}

export interface DecisionStakeholder {
  stakeholder_id: string;
  stakeholder_name: string;
  stakeholder_role: string;
  stakeholder_org: string;
  role_in_decision: 'decideur' | 'consulte' | 'informe' | 'executant';
  recommendation: string;
  notified: boolean;
}

export interface Recommendation {
  id: string;
  target_role: string;
  action: string;
  reasoning: string;
  data_points: string[];
  confidence: number;
}

export interface Decision {
  id: string;
  title: string;
  description: string;
  status: 'draft' | 'en_consultation' | 'validee' | 'en_cours' | 'terminee';
  priority: 'basse' | 'moyenne' | 'haute' | 'urgente';
  dept: string;
  source_type: string;
  source_id: string | null;
  deadline: string | null;
  created_at: string;
  stakeholders: DecisionStakeholder[];
  recommendations: Recommendation[];
}

export interface DecisionStats {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

// SWR Hooks

export function useStakeholders(dept?: string) {
  const params = new URLSearchParams();
  if (dept) params.set('dept', dept);
  const url = `${API_BASE}/stakeholders${params.toString() ? '?' + params.toString() : ''}`;
  return useSWR<Stakeholder[]>(url, fetcher, { refreshInterval: 30000 });
}

export function useStakeholder(id: string | null) {
  return useSWR<Stakeholder>(id ? `${API_BASE}/stakeholders/${id}` : null, fetcher);
}

export function useRelations(dept?: string) {
  const params = new URLSearchParams();
  if (dept) params.set('dept', dept);
  const url = `${API_BASE}/relations${params.toString() ? '?' + params.toString() : ''}`;
  return useSWR<StakeholderRelation[]>(url, fetcher, { refreshInterval: 30000 });
}

export function useDecisions(dept?: string, status?: string) {
  const params = new URLSearchParams();
  if (dept) params.set('dept', dept);
  if (status) params.set('status', status);
  const url = `${API_BASE}/${params.toString() ? '?' + params : ''}`;
  return useSWR<Decision[]>(url, fetcher, { refreshInterval: 15000 });
}

export function useDecision(id: string | null) {
  return useSWR<Decision>(id ? `${API_BASE}/${id}` : null, fetcher);
}

export function useDecisionStats(dept?: string) {
  const params = new URLSearchParams();
  if (dept) params.set('dept', dept);
  const url = `${API_BASE}/stats/summary${params.toString() ? '?' + params : ''}`;
  return useSWR<DecisionStats>(url, fetcher, { refreshInterval: 30000 });
}

// Mutation helpers

export async function createStakeholder(data: Partial<Stakeholder>) {
  const res = await fetch(`${API_BASE}/stakeholders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create stakeholder: ${res.status}`);
  return res.json();
}

export async function updateStakeholder(id: string, data: Partial<Stakeholder>) {
  const res = await fetch(`${API_BASE}/stakeholders/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update stakeholder: ${res.status}`);
  return res.json();
}

export async function deleteStakeholder(id: string) {
  const res = await fetch(`${API_BASE}/stakeholders/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete stakeholder: ${res.status}`);
}

export async function createRelation(data: {
  from_id: string;
  to_id: string;
  type: string;
  strength?: number;
  description?: string;
  bidirectional?: boolean;
}) {
  const res = await fetch(`${API_BASE}/relations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create relation: ${res.status}`);
  return res.json();
}

export async function deleteRelation(id: string) {
  const res = await fetch(`${API_BASE}/relations/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete relation: ${res.status}`);
}

export async function createDecision(data: {
  title: string;
  description?: string;
  priority?: string;
  dept: string;
  source_type?: string;
  stakeholders?: { stakeholder_id: string; role_in_decision: string; recommendation?: string }[];
}) {
  const res = await fetch(`${API_BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create decision: ${res.status}`);
  return res.json();
}

export async function updateDecision(id: string, data: Partial<Decision>) {
  const res = await fetch(`${API_BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update decision: ${res.status}`);
  return res.json();
}

export async function updateDecisionStatus(id: string, status: string) {
  const res = await fetch(`${API_BASE}/${id}/status?status=${status}`, {
    method: 'PUT',
  });
  if (!res.ok) throw new Error(`Failed to update status: ${res.status}`);
  return res.json();
}
