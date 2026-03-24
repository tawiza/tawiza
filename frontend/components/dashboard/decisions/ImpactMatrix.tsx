'use client';

import { useMemo } from 'react';
import type { Decision, Stakeholder } from '@/lib/api-decisions';
import { GlassCard } from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { LayoutGrid } from 'lucide-react';

const PRIORITY_WEIGHT: Record<string, number> = {
  urgente: 4,
  haute: 3,
  moyenne: 2,
  basse: 1,
};

const STATUS_PROGRESS: Record<string, number> = {
  draft: 0,
  en_consultation: 25,
  validee: 50,
  en_cours: 75,
  terminee: 100,
};

const ROLE_LABEL: Record<string, string> = {
  decideur: 'D',
  consulte: 'C',
  informe: 'I',
  executant: 'E',
};

const ROLE_COLORS: Record<string, string> = {
  decideur: 'bg-red-500/15 text-red-400 border-red-500/30',
  consulte: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  informe: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  executant: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
};

interface Props {
  decisions: Decision[];
  stakeholders: Stakeholder[];
  isLoading: boolean;
}

export function ImpactMatrix({ decisions, stakeholders, isLoading }: Props) {
  const matrix = useMemo(() => {
    if (decisions.length === 0 || stakeholders.length === 0) return null;

    const involvedIds = new Set<string>();
    for (const d of decisions) {
      for (const sh of d.stakeholders) {
        involvedIds.add(sh.stakeholder_id);
      }
    }

    const involvedStakeholders = stakeholders.filter(s => involvedIds.has(s.id));
    if (involvedStakeholders.length === 0) return null;

    return { stakeholders: involvedStakeholders, decisions };
  }, [decisions, stakeholders]);

  if (isLoading) {
    return (
      <div className="space-y-4 p-2">
        <Skeleton className="h-8 w-64 rounded-md" />
        <Skeleton className="h-48 rounded-xl" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (!matrix) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <LayoutGrid className="w-12 h-12 text-muted-foreground/20 mb-4" />
        <p className="text-sm font-medium text-muted-foreground">Matrice d&apos;impact</p>
        <p className="text-xs text-muted-foreground/70 mt-2 max-w-sm">
          La matrice RACI apparaitra automatiquement lorsque des acteurs seront assignes a des decisions.
          Creez des decisions et assignez-leur des parties prenantes dans l&apos;onglet Decisions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Legend */}
      <div className="flex items-center gap-4 text-xs">
        <span className="text-section-label">Roles RACI:</span>
        {Object.entries(ROLE_LABEL).map(([role, label]) => (
          <Badge
            key={role}
            variant="outline"
            className={`gap-1 ${ROLE_COLORS[role]}`}
          >
            <span className="font-bold">{label}</span>
            <span className="capitalize">{role}</span>
          </Badge>
        ))}
      </div>

      {/* Matrix table */}
      <GlassCard noPadding>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left p-3 font-medium text-muted-foreground sticky left-0 bg-card min-w-[180px]">
                  Decision
                </th>
                <th className="p-3 font-medium text-muted-foreground text-center min-w-[60px]">Priorite</th>
                <th className="p-3 font-medium text-muted-foreground text-center min-w-[80px]">Avancement</th>
                {matrix.stakeholders.map(s => (
                  <th key={s.id} className="p-3 font-medium text-center min-w-[80px]">
                    <div className="flex flex-col items-center gap-1">
                      <div className="w-7 h-7 rounded-full bg-primary/15 text-primary flex items-center justify-center text-[10px] font-bold">
                        {s.name.split(' ').map(w => w[0]).join('').slice(0, 2)}
                      </div>
                      <span className="text-[10px] text-muted-foreground truncate max-w-[70px]">
                        {s.name.split(' ').pop()}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.decisions.map((d, i) => {
                const priorityW = PRIORITY_WEIGHT[d.priority] || 2;
                const progress = STATUS_PROGRESS[d.status] || 0;

                return (
                  <tr
                    key={d.id}
                    className={`border-b border-border/30 hover:bg-muted/20 transition-colors ${
                      i % 2 === 0 ? 'bg-muted/5' : ''
                    }`}
                  >
                    <td className="p-3 sticky left-0 bg-card">
                      <span className="font-medium line-clamp-1">{d.title}</span>
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex justify-center gap-0.5">
                        {Array.from({ length: 4 }).map((_, j) => (
                          <div
                            key={j}
                            className={`w-1.5 h-4 rounded-sm ${
                              j < priorityW
                                ? priorityW >= 4
                                  ? 'bg-red-400'
                                  : priorityW >= 3
                                    ? 'bg-amber-400'
                                    : 'bg-blue-400'
                                : 'bg-muted/30'
                            }`}
                          />
                        ))}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-muted/30 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              progress === 100
                                ? 'bg-emerald-400'
                                : progress >= 50
                                  ? 'bg-blue-400'
                                  : 'bg-muted-foreground/40'
                            }`}
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground w-7 text-right tabular-nums">{progress}%</span>
                      </div>
                    </td>
                    {matrix.stakeholders.map(s => {
                      const link = d.stakeholders.find(sh => sh.stakeholder_id === s.id);
                      if (!link) {
                        return (
                          <td key={s.id} className="p-3 text-center">
                            <span className="text-muted-foreground/20"> - </span>
                          </td>
                        );
                      }
                      return (
                        <td key={s.id} className="p-3 text-center">
                          <span
                            className={`inline-flex items-center justify-center w-7 h-7 rounded border text-xs font-bold ${
                              ROLE_COLORS[link.role_in_decision] || 'bg-muted/20 text-muted-foreground border-border'
                            }`}
                            title={`${link.stakeholder_name}: ${link.role_in_decision}${link.recommendation ? '  -  ' + link.recommendation : ''}`}
                          >
                            {ROLE_LABEL[link.role_in_decision] || '?'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <GlassCard className="p-4 text-center">
          <div className="text-data-value">{decisions.length}</div>
          <div className="text-caption mt-1">Decisions</div>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <div className="text-data-value">{matrix.stakeholders.length}</div>
          <div className="text-caption mt-1">Acteurs impliques</div>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <div className="text-data-value">
            {decisions.filter(d => d.status === 'terminee').length}
          </div>
          <div className="text-caption mt-1">Terminees</div>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <div className="text-data-value text-amber-400">
            {decisions.filter(d => d.priority === 'urgente' || d.priority === 'haute').length}
          </div>
          <div className="text-caption mt-1">Haute priorite</div>
        </GlassCard>
      </div>
    </div>
  );
}
