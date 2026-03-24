export type ActorType = 'enterprise' | 'territory' | 'institution' | 'sector' | 'association' | 'formation' | 'financial';
export type RelationType = 'structural' | 'inferred' | 'hypothetical';

export interface GraphNode {
  id: string;
  label: string;
  type: ActorType;
  external_id: string;
  department_code: string | null;
  size: number;
  metadata: Record<string, any> | null;
}

export interface GraphLink {
  source: string;
  target: string;
  relation_type: RelationType;
  subtype: string;
  confidence: number;
  weight: number;
}

export interface RelationGraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  total_actors: number;
  total_relations: number;
  total_relations_unfiltered?: number;
}

export interface CoverageScore {
  total_relations: number;
  structural_count: number;
  structural_pct: number;
  inferred_count: number;
  inferred_pct: number;
  hypothetical_count: number;
  hypothetical_pct: number;
  coverage_score: number;
}

export interface GapItem {
  gap_type: string;
  description: string;
  affected_actors: number;
  potential_source: string;
  priority: 'high' | 'medium' | 'low';
}

export interface AlgorithmicHonestyItem {
  relation_subtype: string;
  relation_type: RelationType;
  count: number;
  avg_confidence: number;
  min_confidence: number;
  max_confidence: number;
  method: string;
  limitation: string;
  data_source: string;
}

export interface CapabilityItem {
  capability: string;
  level: number;
  missing: string;
  source?: string;
  method?: string;
}

export interface GapsReport {
  department_code: string;
  total_gaps: number;
  gaps: GapItem[];
  capability_matrix: CapabilityItem[];
  algorithmic_honesty?: AlgorithmicHonestyItem[];
}

export interface DiscoverResult {
  department_code: string;
  actors_upserted: number;
  relations_upserted: number;
  l1_relations: number;
  l2_relations: number;
  l3_relations: number;
  sources_run: string[];
  inferrers_run: string[];
  predictors_run: string[];
}

export interface CascadePathItem {
  actor_external_id: string;
  actor_name: string;
  actor_type: string;
  depth: number;
  cascade_probability: number;
  impact_score: number;
  estimated_headcount: number;
  via_relation: string;
  via_confidence: number;
}

export interface WhatIfResponse {
  source_actor: {
    external_id: string;
    name: string;
    estimated_headcount: number;
  };
  department_code: string;
  cascade_depth: number;
  affected_actors: number;
  cascade_paths: CascadePathItem[];
  total_impact_score: number;
  employment_at_risk: number;
}

export const ACTOR_COLORS: Record<ActorType, string> = {
  enterprise: '#88C0D0',
  territory: '#A3BE8C',
  institution: '#EBCB8B',
  sector: '#B48EAD',
  association: '#D08770',
  formation: '#5E81AC',
  financial: '#BF616A',
};

export const ACTOR_SHAPES: Record<ActorType, string> = {
  enterprise: 'circle',
  territory: 'hexagon',
  institution: 'diamond',
  sector: 'square',
  association: 'triangle',
  formation: 'pentagon',
  financial: 'star',
};

export const RELATION_STYLES: Record<RelationType, { dasharray: string; opacity: number }> = {
  structural: { dasharray: '0', opacity: 1.0 },
  inferred: { dasharray: '6,3', opacity: 0.7 },
  hypothetical: { dasharray: '2,4', opacity: 0.4 },
};

export interface NetworkAnalytics {
  department_code: string;
  graph_summary: {
    total_nodes: number;
    total_edges: number;
    density: number;
    avg_clustering: number;
    connected_components: number;
    type_distribution: Record<string, number>;
  };
  resilience: {
    score: number;
    diversity: number;
    clustering: number;
    density: number;
    robustness: number;
    components_after_removal: number;
    removed_hubs: string[];
  };
  communities: {
    id: number;
    size: number;
    composition: Record<string, number>;
    dominant_type: string;
  }[];
  critical_actors: {
    actor_external_id: string;
    actor_name: string;
    actor_type: string;
    betweenness: number;
    pagerank: number;
    degree: number;
  }[];
  structural_holes: {
    actor_external_id: string;
    actor_name: string;
    actor_type: string;
    constraint: number;
    brokerage_potential: number;
  }[];
  node_metrics: Record<string, {
    betweenness: number;
    pagerank: number;
    degree: number;
    eigenvector: number;
    shapley?: number;
    risk_score?: number;
    community_id: number;
  }>;
  shapley_top?: ShapleyEntry[];
  risk_ranking?: RiskEntry[];
}

// Cascade Graph types (investigation module)
export interface CascadeGraphNode {
  id: string;
  label: string;
  depth: number;
  isSource: boolean;
  impactScore: number;
  cascadeProbability: number;
  headcount: number;
}

export interface CascadeGraphLink {
  source: string;
  target: string;
  probability: number;
}

export interface CascadeGraphData {
  nodes: CascadeGraphNode[];
  links: CascadeGraphLink[];
}

// Ecosystem Score types
export interface EcosystemDimension {
  name: string;
  label: string;
  score: number;
  weight: number;
  indicators: Record<string, number | string>;
}

export interface EcosystemScore {
  department_code: string;
  overall_score: number;
  total_actors: number;
  total_relations: number;
  dimensions: EcosystemDimension[];
  recommendations: string[];
}

// Network Analytics sub-types
export interface ShapleyEntry {
  actor_external_id: string;
  actor_name: string;
  actor_type: string;
  shapley_value: number;
}

export interface RiskEntry {
  actor_external_id: string;
  actor_name: string;
  actor_type: string;
  risk_score: number;
}

export interface NodeMetrics {
  betweenness: number;
  pagerank: number;
  degree: number;
  community_id: number;
  shapley?: number;
  risk_score?: number;
}
