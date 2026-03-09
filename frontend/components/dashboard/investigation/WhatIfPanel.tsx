'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { GraphNode, WhatIfResponse, CascadePathItem, CascadeGraphData } from '@/types/relations';
import CascadeGraph from './CascadeGraph';

interface WhatIfPanelProps {
  nodes: GraphNode[];
  whatIfResult: WhatIfResponse | null;
  simulating: boolean;
  onSimulate: (actorExternalId: string, maxDepth: number) => void;
  onExport: (format: 'json' | 'csv' | 'graphml') => void;
}

function DepthBadge({ depth }: { depth: number }) {
  const colors = [
    'bg-red-500/20 text-red-400 border-red-500/30',
    'bg-amber-500/20 text-amber-400 border-amber-500/30',
    'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  ];
  return (
    <span className={cn('text-[10px] font-mono px-1.5 py-0.5 rounded border', colors[Math.min(depth - 1, 2)])}>
      D{depth}
    </span>
  );
}

function CascadeRow({ item }: { item: CascadePathItem }) {
  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg bg-muted/10 hover:bg-muted/20 transition-colors">
      <DepthBadge depth={item.depth} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">{item.actor_name}</span>
          <span className="text-[10px] text-muted-foreground/50 font-mono">{item.actor_external_id}</span>
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground/60">
          <span>via <span className="text-muted-foreground/80">{item.via_relation.replace(/_/g, ' ')}</span></span>
          <span className="font-mono">{(item.cascade_probability * 100).toFixed(0)}% proba</span>
          {item.estimated_headcount > 0 && (
            <span>{item.estimated_headcount} emplois</span>
          )}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className={cn(
          'text-sm font-mono font-bold',
          item.impact_score >= 0.5 ? 'text-red-400' : item.impact_score >= 0.2 ? 'text-amber-400' : 'text-muted-foreground'
        )}>
          {item.impact_score.toFixed(2)}
        </div>
        <div className="text-[10px] text-muted-foreground/40">impact</div>
      </div>
    </div>
  );
}

export default function WhatIfPanel({ nodes, whatIfResult, simulating, onSimulate, onExport }: WhatIfPanelProps) {
  const [selectedActor, setSelectedActor] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [searchFilter, setSearchFilter] = useState('');

  const cascadeGraphData = useMemo<CascadeGraphData | null>(() => {
    if (!whatIfResult) return null;
    const sourceNode = {
      id: whatIfResult.source_actor.external_id,
      label: whatIfResult.source_actor.name,
      type: 'enterprise',
      depth: 0,
      cascadeProbability: 1.0,
      impactScore: 1.0,
      headcount: whatIfResult.source_actor.estimated_headcount,
      isSource: true,
    };
    const cascadeNodes = whatIfResult.cascade_paths.map((p) => ({
      id: p.actor_external_id,
      label: p.actor_name,
      type: p.actor_type,
      depth: p.depth,
      cascadeProbability: p.cascade_probability,
      impactScore: p.impact_score,
      headcount: p.estimated_headcount,
      isSource: false,
    }));
    const links = whatIfResult.cascade_paths.map((p) => ({
      source: whatIfResult.source_actor.external_id,
      target: p.actor_external_id,
      viaRelation: p.via_relation,
      confidence: p.via_confidence,
      probability: p.cascade_probability,
    }));
    return { nodes: [sourceNode, ...cascadeNodes], links };
  }, [whatIfResult]);

  const enterprises = nodes.filter(n => n.type === 'enterprise');
  const filtered = searchFilter
    ? enterprises.filter(n =>
        n.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
        n.external_id.toLowerCase().includes(searchFilter.toLowerCase())
      )
    : enterprises.slice(0, 20);

  return (
    <div className="rounded-xl border border-border/50 bg-card/50 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Simulation What-If</h3>
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">
            Simulez la defaillance d&apos;une entreprise et visualisez l&apos;effet cascade
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onExport('json')}
            className="text-[11px] px-2 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
          >
            Export JSON
          </button>
          <button
            onClick={() => onExport('csv')}
            className="text-[11px] px-2 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
          >
            Export CSV
          </button>
          <button
            onClick={() => onExport('graphml')}
            className="text-[11px] px-2 py-1 rounded border border-violet-500/30 text-violet-400 hover:text-violet-300 hover:bg-violet-500/10 transition-colors"
            title="Exporter au format GraphML pour Gephi"
          >
            Export Gephi
          </button>
        </div>
      </div>

      {/* Actor selector */}
      <div className="p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Rechercher une entreprise..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full px-3 py-1.5 text-sm rounded-lg border border-border/50 bg-background/50 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-violet-500/30"
            />
          </div>
          <select
            value={maxDepth}
            onChange={(e) => setMaxDepth(Number(e.target.value))}
            className="px-2 py-1.5 text-sm rounded-lg border border-border/50 bg-background/50 focus:outline-none focus:ring-1 focus:ring-violet-500/30"
          >
            <option value={1}>Profondeur 1</option>
            <option value={2}>Profondeur 2</option>
            <option value={3}>Profondeur 3</option>
          </select>
          <button
            onClick={() => selectedActor && onSimulate(selectedActor, maxDepth)}
            disabled={!selectedActor || simulating}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-lg transition-all',
              selectedActor && !simulating
                ? 'bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25'
                : 'bg-muted/20 text-muted-foreground/40 border border-border/30 cursor-not-allowed'
            )}
          >
            {simulating ? (
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 border-2 border-red-400/30 border-t-red-400 rounded-full animate-spin" />
                Simulation...
              </span>
            ) : (
              'Simuler la defaillance'
            )}
          </button>
        </div>

        {/* Enterprise list */}
        {enterprises.length > 0 && (
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {filtered.map((n) => (
              <button
                key={n.id}
                onClick={() => setSelectedActor(n.external_id)}
                className={cn(
                  'text-[11px] px-2 py-1 rounded-md border transition-all truncate max-w-[200px]',
                  selectedActor === n.external_id
                    ? 'bg-red-500/15 text-red-400 border-red-500/30'
                    : 'bg-muted/10 text-muted-foreground/70 border-border/30 hover:bg-muted/20 hover:text-foreground'
                )}
                title={`${n.label} (${n.external_id})`}
              >
                {n.label}
              </button>
            ))}
            {enterprises.length > filtered.length && !searchFilter && (
              <span className="text-[10px] text-muted-foreground/40 px-2 py-1">
                +{enterprises.length - filtered.length} autres
              </span>
            )}
          </div>
        )}
      </div>

      {/* Results */}
      {whatIfResult && (
        <div className="border-t border-border/30">
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border/20">
            <div className="bg-card/50 p-3 text-center">
              <div className="text-lg font-mono font-bold text-foreground">
                {whatIfResult.source_actor.name}
              </div>
              <div className="text-[10px] text-muted-foreground/50 mt-0.5">Entreprise source</div>
            </div>
            <div className="bg-card/50 p-3 text-center">
              <div className={cn(
                'text-lg font-mono font-bold',
                whatIfResult.affected_actors > 5 ? 'text-red-400' : whatIfResult.affected_actors > 0 ? 'text-amber-400' : 'text-emerald-400'
              )}>
                {whatIfResult.affected_actors}
              </div>
              <div className="text-[10px] text-muted-foreground/50 mt-0.5">Acteurs impactes</div>
            </div>
            <div className="bg-card/50 p-3 text-center">
              <div className={cn(
                'text-lg font-mono font-bold',
                whatIfResult.total_impact_score >= 1.0 ? 'text-red-400' : 'text-amber-400'
              )}>
                {whatIfResult.total_impact_score.toFixed(2)}
              </div>
              <div className="text-[10px] text-muted-foreground/50 mt-0.5">Score impact total</div>
            </div>
            <div className="bg-card/50 p-3 text-center">
              <div className={cn(
                'text-lg font-mono font-bold',
                whatIfResult.employment_at_risk > 50 ? 'text-red-400' : 'text-amber-400'
              )}>
                {whatIfResult.employment_at_risk}
              </div>
              <div className="text-[10px] text-muted-foreground/50 mt-0.5">Emplois a risque</div>
            </div>
          </div>

          {/* Cascade graph */}
          {cascadeGraphData && cascadeGraphData.nodes.length > 1 && (
            <div className="p-3">
              <CascadeGraph data={cascadeGraphData} />
            </div>
          )}

          {/* Cascade paths */}
          {whatIfResult.cascade_paths.length > 0 ? (
            <div className="p-3 space-y-1.5">
              <div className="text-xs text-muted-foreground/60 uppercase tracking-wider font-medium mb-2">
                Chemin de cascade ({whatIfResult.cascade_paths.length} acteurs)
              </div>
              {whatIfResult.cascade_paths
                .sort((a, b) => a.depth - b.depth || b.impact_score - a.impact_score)
                .map((item, i) => (
                  <CascadeRow key={i} item={item} />
                ))}
            </div>
          ) : (
            <div className="p-6 text-center">
              <div className="text-sm text-muted-foreground/60">
                Aucun effet cascade detecte pour cette entreprise
              </div>
              <div className="text-[11px] text-muted-foreground/40 mt-1">
                L&apos;entreprise a peu de connexions dans le graphe relationnel
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
