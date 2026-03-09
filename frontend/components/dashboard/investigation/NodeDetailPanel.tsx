'use client';

import type { GraphNode, GraphLink, RelationGraphData, NetworkAnalytics, ShapleyEntry, RiskEntry } from '@/types/relations';
import { ACTOR_COLORS } from '@/types/relations';
import { X, Target, AlertTriangle, Sparkles, Link2, Info } from 'lucide-react';

interface NodeDetailPanelProps {
  node: GraphNode;
  graphData: RelationGraphData;
  analytics: NetworkAnalytics | null;
  onClose: () => void;
  onCenter?: (nodeId: string) => void;
}

function getRiskColor(score: number): string {
  if (score >= 0.7) return '#BF616A';
  if (score >= 0.4) return '#EBCB8B';
  return '#A3BE8C';
}

function getRiskLabel(score: number): string {
  if (score >= 0.7) return 'Eleve';
  if (score >= 0.4) return 'Moyen';
  return 'Faible';
}

export default function NodeDetailPanel({
  node,
  graphData,
  analytics,
  onClose,
  onCenter,
}: NodeDetailPanelProps) {
  // Find direct relations (where this node is source or target)
  const directRelations = graphData.links.filter(
    (l) => l.source === node.id || l.target === node.id,
  );
  // Sort by confidence descending
  const sortedRelations = [...directRelations].sort((a, b) => b.confidence - a.confidence);

  // Find the node label for a given id
  const nodeLabel = (id: string): string => {
    const n = graphData.nodes.find((nd) => nd.id === id);
    return n?.label || id.slice(0, 12);
  };

  // Get node metrics from analytics (keyed by external_id, not UUID)
  const metrics = analytics?.node_metrics?.[node.external_id] ?? analytics?.node_metrics?.[node.id] ?? null;

  // Find Shapley entry for this node (check top list first, then fallback to node_metrics)
  let shapleyEntry: ShapleyEntry | undefined = analytics?.shapley_top?.find(
    (s) => s.actor_external_id === node.external_id,
  );
  // If not in top list, synthesize from node_metrics
  if (!shapleyEntry && metrics && typeof metrics.shapley === 'number') {
    const sv = metrics.shapley;
    if (sv > 0) {
      shapleyEntry = {
        actor_external_id: node.external_id,
        actor_name: node.label,
        actor_type: node.type,
        shapley_value: sv,
      };
    }
  }

  // Find risk entry for this node (check top ranking first, then fallback to node_metrics)
  let riskEntry: RiskEntry | undefined = analytics?.risk_ranking?.find(
    (r) => r.actor_external_id === node.external_id,
  );
  // If not in top ranking, synthesize from node_metrics
  if (!riskEntry && metrics && typeof metrics.risk_score === 'number') {
    riskEntry = {
      actor_external_id: node.external_id,
      actor_name: node.label,
      actor_type: node.type,
      risk_score: metrics.risk_score,
    };
  }

  // Compute Shapley rank if in the top list
  const shapleyRank = shapleyEntry
    ? (analytics?.shapley_top?.findIndex(
        (s) => s.actor_external_id === node.external_id,
      ) ?? -1) + 1
    : null;

  const typeColor = ACTOR_COLORS[node.type] || '#88C0D0';

  return (
    <div className="absolute top-0 right-0 h-full w-[350px] bg-black/80 backdrop-blur-xl border-l border-white/10 overflow-y-auto z-40 animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="sticky top-0 bg-black/90 backdrop-blur-sm border-b border-white/10 p-4 flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: typeColor }}
            />
            <h3 className="text-sm font-semibold text-white truncate">{node.label}</h3>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
              style={{ backgroundColor: `${typeColor}20`, color: typeColor }}
            >
              {node.type}
            </span>
            <span className="text-[10px] text-white/40 font-mono">{node.external_id}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {onCenter && (
            <button
              onClick={() => onCenter(node.id)}
              className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors"
              title="Centrer sur ce noeud"
            >
              <Target className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Risk Score */}
        {riskEntry && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs text-white/60">
              <AlertTriangle className="w-3.5 h-3.5" />
              Score de risque
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${riskEntry.risk_score * 100}%`,
                    backgroundColor: getRiskColor(riskEntry.risk_score),
                  }}
                />
              </div>
              <span
                className="text-xs font-mono font-medium"
                style={{ color: getRiskColor(riskEntry.risk_score) }}
              >
                {(riskEntry.risk_score * 100).toFixed(0)}%
              </span>
            </div>
            <span
              className="text-[10px] font-medium"
              style={{ color: getRiskColor(riskEntry.risk_score) }}
            >
              Risque {getRiskLabel(riskEntry.risk_score)}
            </span>
          </div>
        )}

        {/* Shapley Value */}
        {shapleyEntry && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs text-white/60">
              <Sparkles className="w-3.5 h-3.5" />
              Valeur de Shapley
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-violet-500 transition-all"
                  style={{ width: `${shapleyEntry.shapley_value * 100}%` }}
                />
              </div>
              <span className="text-xs font-mono font-medium text-violet-400">
                {shapleyEntry.shapley_value.toFixed(3)}
              </span>
            </div>
            {shapleyRank && shapleyRank > 0 && (
              <span className="text-[10px] text-violet-400/70">
                #{shapleyRank} contribution au reseau
              </span>
            )}
          </div>
        )}

        {/* Network Metrics */}
        {metrics && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs text-white/60">
              <Info className="w-3.5 h-3.5" />
              Metriques reseau
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 rounded-lg bg-white/5">
                <div className="text-[10px] text-white/40">Betweenness</div>
                <div className="text-sm font-mono text-white/80">
                  {metrics.betweenness.toFixed(4)}
                </div>
              </div>
              <div className="p-2 rounded-lg bg-white/5">
                <div className="text-[10px] text-white/40">PageRank</div>
                <div className="text-sm font-mono text-white/80">
                  {metrics.pagerank.toFixed(4)}
                </div>
              </div>
              <div className="p-2 rounded-lg bg-white/5">
                <div className="text-[10px] text-white/40">Degre</div>
                <div className="text-sm font-mono text-white/80">{metrics.degree}</div>
              </div>
              <div className="p-2 rounded-lg bg-white/5">
                <div className="text-[10px] text-white/40">Communaute</div>
                <div className="text-sm font-mono text-white/80">#{metrics.community_id}</div>
              </div>
            </div>
          </div>
        )}

        {/* Direct Relations */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs text-white/60">
            <Link2 className="w-3.5 h-3.5" />
            Relations directes ({sortedRelations.length})
          </div>
          {sortedRelations.length === 0 ? (
            <p className="text-[10px] text-white/30 py-2">Aucune relation directe</p>
          ) : (
            <div className="space-y-1 max-h-[300px] overflow-y-auto">
              {sortedRelations.map((rel, i) => {
                const isSource = rel.source === node.id;
                const otherId = isSource ? rel.target : rel.source;
                const otherLabel = nodeLabel(otherId);
                const arrow = isSource ? '\u2192' : '\u2190';
                const confColor =
                  rel.confidence >= 0.7
                    ? 'text-emerald-400'
                    : rel.confidence >= 0.4
                      ? 'text-amber-400'
                      : 'text-red-400';

                return (
                  <div
                    key={`${rel.source}-${rel.target}-${rel.subtype}-${i}`}
                    className="flex items-center gap-2 p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                  >
                    <span className="text-[10px] text-white/30">{arrow}</span>
                    <span className="text-xs text-white/70 truncate flex-1">{otherLabel}</span>
                    <span className="text-[9px] text-white/40 shrink-0">{rel.subtype}</span>
                    <span className={`text-[10px] font-mono shrink-0 ${confColor}`}>
                      {(rel.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Metadata */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs text-white/60">Metadata</div>
            <div className="space-y-1">
              {Object.entries(node.metadata).map(([key, value]) => (
                <div key={key} className="flex items-start gap-2 text-[10px]">
                  <span className="text-white/40 shrink-0">{key}:</span>
                  <span className="text-white/60 break-all">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
