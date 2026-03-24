'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  HiChevronDown,
  HiShieldCheck,
  HiUserGroup,
  HiArrowsPointingOut,
  HiStar,
} from 'react-icons/hi2';
import type { NetworkAnalytics, ActorType } from '@/types/relations';
import { ACTOR_COLORS } from '@/types/relations';

interface NetworkAnalyticsPanelProps {
  analytics: NetworkAnalytics | null;
  isLoading: boolean;
}

/* ── Helpers ────────────────────────────────────────────────── */

function scoreColor(score: number): string {
  if (score > 0.6) return 'text-emerald-400';
  if (score >= 0.3) return 'text-amber-400';
  return 'text-red-400';
}

function barColor(score: number): string {
  if (score > 0.6) return 'bg-emerald-500/80';
  if (score >= 0.3) return 'bg-amber-500/80';
  return 'bg-red-500/60';
}

function scoreBgColor(score: number): string {
  if (score > 0.6) return 'bg-emerald-500/10 border-emerald-500/20';
  if (score >= 0.3) return 'bg-amber-500/10 border-amber-500/20';
  return 'bg-red-500/10 border-red-500/20';
}

const actorTypeBadge: Record<string, string> = {
  enterprise: 'bg-[#88C0D0]/15 text-[#88C0D0] border-[#88C0D0]/25',
  territory: 'bg-[#A3BE8C]/15 text-[#A3BE8C] border-[#A3BE8C]/25',
  institution: 'bg-[#EBCB8B]/15 text-[#EBCB8B] border-[#EBCB8B]/25',
  sector: 'bg-[#B48EAD]/15 text-[#B48EAD] border-[#B48EAD]/25',
  association: 'bg-[#D08770]/15 text-[#D08770] border-[#D08770]/25',
  formation: 'bg-[#5E81AC]/15 text-[#5E81AC] border-[#5E81AC]/25',
  financial: 'bg-[#BF616A]/15 text-[#BF616A] border-[#BF616A]/25',
};

/* ── Sub-metric bar ─────────────────────────────────────────── */

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-muted-foreground/70 w-24 shrink-0">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-muted/20 overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700 ease-out', barColor(value))}
          style={{ width: `${Math.min(value * 100, 100)}%` }}
        />
      </div>
      <span className={cn('text-[11px] font-mono w-10 text-right', scoreColor(value))}>
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

/* ── Composition bar for communities ────────────────────────── */

function CompositionBar({ composition }: { composition: Record<string, number> }) {
  const total = Object.values(composition).reduce((s, v) => s + v, 0);
  if (total === 0) return null;

  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-muted/20">
      {Object.entries(composition).map(([type, count]) => {
        const pct = (count / total) * 100;
        const color = ACTOR_COLORS[type as ActorType] || '#666';
        return (
          <div
            key={type}
            className="h-full transition-all duration-500"
            style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.8 }}
            title={`${type}: ${count} (${pct.toFixed(0)}%)`}
          />
        );
      })}
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────── */

export default function NetworkAnalyticsPanel({ analytics, isLoading }: NetworkAnalyticsPanelProps) {
  const [communitiesExpanded, setCommunitiesExpanded] = useState(true);
  const [holesExpanded, setHolesExpanded] = useState(true);

  if (isLoading && !analytics) {
    return (
      <div className="space-y-3">
        <div className="rounded-xl border border-border/50 bg-card/50 p-4 animate-pulse">
          <div className="h-4 bg-muted/30 rounded w-1/3 mb-3" />
          <div className="h-6 bg-muted/30 rounded mb-2" />
          <div className="h-3 bg-muted/30 rounded w-2/3 mb-1" />
          <div className="h-3 bg-muted/30 rounded w-1/2" />
        </div>
        <div className="rounded-xl border border-border/50 bg-card/50 p-4 animate-pulse">
          <div className="h-4 bg-muted/30 rounded w-1/4 mb-3" />
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-muted/30 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!analytics) return null;

  const { resilience, critical_actors, communities, structural_holes, graph_summary } = analytics;

  return (
    <div className="space-y-3">
      {/* ── Section 1: Resilience Score ────────────────────── */}
      <div className="rounded-xl border border-border/50 bg-card/50 p-4">
        <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-3 flex items-center gap-2">
          <HiShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          Resilience du reseau
        </h4>

        {/* Main score */}
        <div className="flex items-center gap-4 mb-4">
          <div className={cn(
            'flex items-center justify-center w-16 h-16 rounded-xl border',
            scoreBgColor(resilience.score)
          )}>
            <span className={cn('text-2xl font-mono font-bold', scoreColor(resilience.score))}>
              {(resilience.score * 100).toFixed(0)}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1">
              <span className={cn('text-sm font-semibold', scoreColor(resilience.score))}>
                {resilience.score > 0.6 ? 'Reseau resilient' :
                 resilience.score >= 0.3 ? 'Resilience moderee' :
                 'Reseau fragile'}
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground/60">
              {graph_summary.total_nodes} noeuds, {graph_summary.total_edges} aretes,{' '}
              {graph_summary.connected_components} composante{graph_summary.connected_components > 1 ? 's' : ''}
            </div>
            {resilience.removed_hubs.length > 0 && (
              <div className="text-[10px] text-muted-foreground/40 mt-1">
                Hubs retires pour test: {resilience.removed_hubs.join(', ')}
              </div>
            )}
          </div>
        </div>

        {/* Sub-metrics */}
        <div className="space-y-1.5">
          <MetricBar label="Diversite" value={resilience.diversity} />
          <MetricBar label="Clustering" value={resilience.clustering} />
          <MetricBar label="Densite" value={resilience.density} />
          <MetricBar label="Robustesse" value={resilience.robustness} />
        </div>
      </div>

      {/* ── Section 2: Critical Actors ────────────────────── */}
      {critical_actors.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-card/50 p-4">
          <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-3 flex items-center gap-2">
            <HiStar className="h-3.5 w-3.5 text-amber-400" />
            Acteurs critiques ({critical_actors.length})
          </h4>

          {/* Table header */}
          <div className="grid grid-cols-[1fr_80px_80px_70px_60px] gap-2 px-3 py-1.5 text-[10px] text-muted-foreground/50 uppercase tracking-wider font-medium border-b border-border/20">
            <span>Nom</span>
            <span className="text-right">Type</span>
            <span className="text-right">Betweenness</span>
            <span className="text-right">PageRank</span>
            <span className="text-right">Degre</span>
          </div>

          {/* Table rows */}
          <div className="divide-y divide-border/10">
            {critical_actors
              .sort((a, b) => b.betweenness - a.betweenness)
              .map((actor, i) => (
                <div
                  key={actor.actor_external_id}
                  className="grid grid-cols-[1fr_80px_80px_70px_60px] gap-2 px-3 py-2 items-center hover:bg-muted/10 transition-colors"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{actor.actor_name}</div>
                    <div className="text-[10px] text-muted-foreground/40 font-mono">{actor.actor_external_id}</div>
                  </div>
                  <div className="text-right">
                    <Badge
                      variant="outline"
                      className={cn('text-[9px]', actorTypeBadge[actor.actor_type] || '')}
                    >
                      {actor.actor_type}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <span className={cn(
                      'text-sm font-mono',
                      i === 0 ? 'font-bold text-amber-400' : 'text-foreground/80'
                    )}>
                      {actor.betweenness.toFixed(3)}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-mono text-foreground/70">
                      {actor.pagerank.toFixed(4)}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-mono text-foreground/70">
                      {actor.degree}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── Section 3: Communities ─────────────────────────── */}
      {communities.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-card/50 p-4">
          <button
            onClick={() => setCommunitiesExpanded(!communitiesExpanded)}
            className="w-full flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground font-medium"
          >
            <HiUserGroup className="h-3.5 w-3.5 text-violet-400" />
            <span>Communautes detectees ({communities.length})</span>
            <HiChevronDown className={cn(
              'h-3.5 w-3.5 ml-auto transition-transform duration-200',
              communitiesExpanded && 'rotate-180'
            )} />
          </button>

          {communitiesExpanded && (
            <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
              {communities
                .sort((a, b) => b.size - a.size)
                .map((community) => {
                  const dominantColor = ACTOR_COLORS[community.dominant_type as ActorType] || '#666';
                  return (
                    <div
                      key={community.id}
                      className="rounded-lg border border-border/20 bg-muted/10 p-3"
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: dominantColor, opacity: 0.8 }}
                        />
                        <span className="text-[13px] font-medium text-foreground/80">
                          Communaute {community.id + 1}
                        </span>
                        <span className="text-[11px] text-muted-foreground/60">
                          {community.size} acteur{community.size > 1 ? 's' : ''}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn('text-[9px] ml-auto', actorTypeBadge[community.dominant_type] || '')}
                        >
                          {community.dominant_type}
                        </Badge>
                      </div>
                      <CompositionBar composition={community.composition} />
                      <div className="flex flex-wrap gap-2 mt-1.5">
                        {Object.entries(community.composition).map(([type, count]) => (
                          <span key={type} className="text-[10px] text-muted-foreground/50">
                            <span
                              className="inline-block w-1.5 h-1.5 rounded-full mr-1"
                              style={{ backgroundColor: ACTOR_COLORS[type as ActorType] || '#666' }}
                            />
                            {type}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      )}

      {/* ── Section 4: Structural Holes ───────────────────── */}
      {structural_holes.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-card/50 p-4">
          <button
            onClick={() => setHolesExpanded(!holesExpanded)}
            className="w-full flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground font-medium"
          >
            <HiArrowsPointingOut className="h-3.5 w-3.5 text-sky-400" />
            <span>Trous structurels ({structural_holes.length} opportunites)</span>
            <HiChevronDown className={cn(
              'h-3.5 w-3.5 ml-auto transition-transform duration-200',
              holesExpanded && 'rotate-180'
            )} />
          </button>

          {holesExpanded && (
            <div className="mt-3 animate-in fade-in slide-in-from-top-2 duration-200">
              {/* Table header */}
              <div className="grid grid-cols-[1fr_80px_90px_100px] gap-2 px-3 py-1.5 text-[10px] text-muted-foreground/50 uppercase tracking-wider font-medium border-b border-border/20">
                <span>Nom</span>
                <span className="text-right">Type</span>
                <span className="text-right">Contrainte</span>
                <span className="text-right">Potentiel courtage</span>
              </div>

              {/* Table rows */}
              <div className="divide-y divide-border/10">
                {structural_holes
                  .sort((a, b) => b.brokerage_potential - a.brokerage_potential)
                  .map((hole) => {
                    const potentialColor = hole.brokerage_potential > 0.6
                      ? 'text-emerald-400'
                      : hole.brokerage_potential > 0.3
                        ? 'text-amber-400'
                        : 'text-muted-foreground/70';

                    return (
                      <div
                        key={hole.actor_external_id}
                        className="grid grid-cols-[1fr_80px_90px_100px] gap-2 px-3 py-2 items-center hover:bg-muted/10 transition-colors"
                      >
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{hole.actor_name}</div>
                          <div className="text-[10px] text-muted-foreground/40 font-mono">{hole.actor_external_id}</div>
                        </div>
                        <div className="text-right">
                          <Badge
                            variant="outline"
                            className={cn('text-[9px]', actorTypeBadge[hole.actor_type] || '')}
                          >
                            {hole.actor_type}
                          </Badge>
                        </div>
                        <div className="text-right">
                          <span className="text-sm font-mono text-foreground/70">
                            {hole.constraint.toFixed(3)}
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-12 h-1.5 rounded-full bg-muted/30 overflow-hidden">
                              <div
                                className={cn('h-full rounded-full', barColor(hole.brokerage_potential))}
                                style={{ width: `${hole.brokerage_potential * 100}%` }}
                              />
                            </div>
                            <span className={cn('text-sm font-mono font-medium', potentialColor)}>
                              {(hole.brokerage_potential * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
