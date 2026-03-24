'use client';

import { useState } from 'react';
import type { Decision } from '@/lib/api-decisions';
import { createDecision, updateDecisionStatus } from '@/lib/api-decisions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle,
} from '@/components/ui/glass-card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Plus, Clock, CheckCircle2, AlertTriangle, Sparkles,
  ChevronRight, Users, ClipboardList,
} from 'lucide-react';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  draft: { label: 'Brouillon', color: 'text-muted-foreground', icon: <Clock className="w-3.5 h-3.5" /> },
  en_consultation: { label: 'Consultation', color: 'text-blue-400', icon: <Clock className="w-3.5 h-3.5" /> },
  validee: { label: 'Validee', color: 'text-emerald-400', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  en_cours: { label: 'En cours', color: 'text-amber-400', icon: <Clock className="w-3.5 h-3.5" /> },
  terminee: { label: 'Terminee', color: 'text-emerald-400', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  basse: { label: 'Basse', color: 'text-muted-foreground' },
  moyenne: { label: 'Moyenne', color: 'text-blue-400' },
  haute: { label: 'Haute', color: 'text-amber-400' },
  urgente: { label: 'Urgente', color: 'text-red-400' },
};

const ROLE_COLORS: Record<string, string> = {
  decideur: 'bg-red-500/15 text-red-400 border-red-500/30',
  consulte: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  informe: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  executant: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
};

interface Props {
  decisions: Decision[];
  stakeholders: import('@/lib/api-decisions').Stakeholder[];
  isLoading: boolean;
  onMutate: () => void;
  dept: string;
}

export function DecisionBoard({ decisions, stakeholders, isLoading, onMutate, dept }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPriority, setNewPriority] = useState('moyenne');
  const [creating, setCreating] = useState(false);

  const selected = decisions.find(d => d.id === selectedId);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      await createDecision({ title: newTitle, description: newDesc, priority: newPriority, dept });
      setNewTitle('');
      setNewDesc('');
      setShowCreate(false);
      onMutate();
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await updateDecisionStatus(id, status);
      onMutate();
    } catch (e) {
      console.error(e);
    }
  };

  if (isLoading) {
    return (
      <div className="flex gap-4 p-2">
        <div className="w-80 space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
        <Skeleton className="flex-1 h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="flex gap-4 min-h-[500px]">
      {/* Left: Decision list */}
      <div className="w-80 shrink-0 flex flex-col gap-2 max-h-[calc(100vh-200px)] overflow-y-auto pr-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowCreate(!showCreate)}
          className="justify-start gap-2 border-dashed"
        >
          <Plus className="w-4 h-4" />
          Nouvelle decision
        </Button>

        {/* Create form */}
        {showCreate && (
          <GlassCard className="p-3 space-y-2">
            <Input
              placeholder="Titre de la decision..."
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              className="h-9"
            />
            <textarea
              placeholder="Description..."
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md bg-background border border-input text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="flex items-center gap-2">
              <select
                value={newPriority}
                onChange={e => setNewPriority(e.target.value)}
                className="flex-1 h-9 px-2 rounded-md bg-background border border-input text-sm"
              >
                <option value="basse">Basse</option>
                <option value="moyenne">Moyenne</option>
                <option value="haute">Haute</option>
                <option value="urgente">Urgente</option>
              </select>
              <Button
                size="sm"
                onClick={handleCreate}
                disabled={creating || !newTitle.trim()}
              >
                {creating ? '...' : 'Creer'}
              </Button>
            </div>
          </GlassCard>
        )}

        {/* Decision cards */}
        {decisions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <ClipboardList className="w-10 h-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">Aucune decision</p>
            <p className="text-xs text-muted-foreground/70 mt-1 max-w-[200px]">
              Creez votre premiere decision ou lancez une analyse TAJINE pour en generer automatiquement
            </p>
            <Button size="sm" className="mt-4 gap-2" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4" />
              Premiere decision
            </Button>
          </div>
        ) : (
          decisions.map(d => {
            const statusCfg = STATUS_CONFIG[d.status] || STATUS_CONFIG.draft;
            const priorityCfg = PRIORITY_CONFIG[d.priority] || PRIORITY_CONFIG.moyenne;
            const isSelected = d.id === selectedId;

            return (
              <button
                key={d.id}
                onClick={() => setSelectedId(isSelected ? null : d.id)}
                className={`text-left w-full p-3 rounded-xl border transition-all duration-150 ${
                  isSelected
                    ? 'border-primary bg-primary/5 shadow-sm'
                    : 'border-border bg-card hover:border-zinc-600'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-medium line-clamp-2">{d.title}</h3>
                  <ChevronRight className={`w-4 h-4 shrink-0 mt-0.5 text-muted-foreground transition-transform ${isSelected ? 'rotate-90' : ''}`} />
                </div>
                <div className="flex items-center gap-2 mt-2 text-xs">
                  <Badge variant="secondary" className={`gap-1 ${statusCfg.color}`}>
                    {statusCfg.icon} {statusCfg.label}
                  </Badge>
                  <Badge variant="secondary" className={priorityCfg.color}>
                    {priorityCfg.label}
                  </Badge>
                </div>
                {d.stakeholders.length > 0 && (
                  <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                    <Users className="w-3.5 h-3.5" />
                    {d.stakeholders.length} acteur{d.stakeholders.length > 1 ? 's' : ''}
                  </div>
                )}
                {d.source_type === 'tajine_analysis' && (
                  <div className="flex items-center gap-1 mt-1 text-xs text-emerald-400">
                    <Sparkles className="w-3 h-3" />
                    Auto TAJINE
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Right: Detail panel */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        {selected ? (
          <GlassCard className="p-5 space-y-5">
            <div>
              <h2 className="text-lg font-semibold">{selected.title}</h2>
              {selected.description && (
                <p className="text-sm text-muted-foreground mt-2">{selected.description}</p>
              )}
            </div>

            {/* Status workflow */}
            <div>
              <p className="text-section-label mb-2">Statut</p>
              <div className="flex gap-1.5 flex-wrap">
                {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                  <Button
                    key={key}
                    variant={selected.status === key ? 'secondary' : 'ghost'}
                    size="sm"
                    onClick={() => handleStatusChange(selected.id, key)}
                    className={`gap-1 text-xs ${cfg.color} ${
                      selected.status === key ? 'ring-1 ring-current font-medium' : 'opacity-50 hover:opacity-100'
                    }`}
                  >
                    {cfg.icon} {cfg.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Stakeholders RACI */}
            {selected.stakeholders.length > 0 && (
              <div>
                <p className="text-section-label mb-2">Parties prenantes</p>
                <div className="space-y-2">
                  {selected.stakeholders.map(sh => (
                    <div key={sh.stakeholder_id} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                      <div className="w-8 h-8 rounded-full bg-primary/15 text-primary flex items-center justify-center text-xs font-bold shrink-0">
                        {sh.stakeholder_name.charAt(0)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{sh.stakeholder_name}</span>
                          <Badge variant="outline" className={`text-[10px] uppercase font-semibold ${ROLE_COLORS[sh.role_in_decision] || ''}`}>
                            {sh.role_in_decision}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{sh.stakeholder_role} — {sh.stakeholder_org}</p>
                        {sh.recommendation && (
                          <p className="text-xs mt-1 text-foreground/80 italic">
                            &laquo; {sh.recommendation} &raquo;
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t border-border">
              <span>Cree le {new Date(selected.created_at).toLocaleDateString('fr-FR')}</span>
              {selected.deadline && (
                <span>Echeance: {new Date(selected.deadline).toLocaleDateString('fr-FR')}</span>
              )}
              <span>Dept. {selected.dept}</span>
            </div>
          </GlassCard>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-20" />
              <p className="text-sm">Selectionnez une decision</p>
              <p className="text-xs mt-1 text-muted-foreground/70">ou creez-en une nouvelle</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
