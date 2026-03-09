'use client';

import { useState } from 'react';
import type { Stakeholder } from '@/lib/api-decisions';
import { createStakeholder, deleteStakeholder } from '@/lib/api-decisions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { GlassCard } from '@/components/ui/glass-card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Plus, Trash2, Star, Building2, GraduationCap, Landmark, Users,
} from 'lucide-react';

const TYPE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  collectivite: { label: 'Collectivite', icon: <Landmark className="w-4 h-4" />, color: 'text-blue-400' },
  entreprise: { label: 'Entreprise', icon: <Building2 className="w-4 h-4" />, color: 'text-amber-400' },
  institution: { label: 'Institution', icon: <GraduationCap className="w-4 h-4" />, color: 'text-emerald-400' },
  association: { label: 'Association', icon: <Users className="w-4 h-4" />, color: 'text-purple-400' },
};

interface Props {
  stakeholders: Stakeholder[];
  isLoading: boolean;
  onMutate: () => void;
  dept: string;
}

export function StakeholderRegistry({ stakeholders, isLoading, onMutate, dept }: Props) {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: '', role: '', organization: '', type: 'institution' as const,
    domains: '', influence_level: 3, tags: '',
  });
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

  const filtered = filter
    ? stakeholders.filter(s => s.type === filter)
    : stakeholders;

  const handleCreate = async () => {
    if (!form.name.trim() || !form.role.trim()) return;
    setCreating(true);
    try {
      await createStakeholder({
        name: form.name,
        role: form.role,
        organization: form.organization,
        type: form.type,
        domains: form.domains.split(',').map(d => d.trim()).filter(Boolean),
        territory_dept: dept,
        influence_level: form.influence_level,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      });
      setForm({ name: '', role: '', organization: '', type: 'institution', domains: '', influence_level: 3, tags: '' });
      setShowCreate(false);
      onMutate();
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteStakeholder(id);
      onMutate();
    } catch (e) {
      console.error(e);
    }
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-2">
        {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-40 rounded-xl" />)}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="gap-2">
          <Plus className="w-4 h-4" />
          Nouvel acteur
        </Button>

        {/* Type filters */}
        <div className="flex gap-1">
          <Button
            variant={!filter ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setFilter(null)}
            className="text-xs"
          >
            Tous ({stakeholders.length})
          </Button>
          {Object.entries(TYPE_CONFIG).map(([key, cfg]) => {
            const count = stakeholders.filter(s => s.type === key).length;
            if (count === 0) return null;
            return (
              <Button
                key={key}
                variant={filter === key ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setFilter(filter === key ? null : key)}
                className={`gap-1 text-xs ${cfg.color}`}
              >
                {cfg.icon} {count}
              </Button>
            );
          })}
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <GlassCard className="p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input placeholder="Nom *" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="h-9" />
            <Input placeholder="Role/Titre *" value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="h-9" />
            <Input placeholder="Organisation" value={form.organization} onChange={e => setForm({ ...form, organization: e.target.value })} className="h-9" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value as any })} className="h-9 px-3 rounded-md bg-background border border-input text-sm">
              {Object.entries(TYPE_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <Input placeholder="Domaines (virgules)" value={form.domains} onChange={e => setForm({ ...form, domains: e.target.value })} className="h-9" />
            <Input placeholder="Tags (virgules)" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} className="h-9" />
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground whitespace-nowrap">Influence:</label>
              <input type="range" min={1} max={5} value={form.influence_level} onChange={e => setForm({ ...form, influence_level: +e.target.value })} className="flex-1" />
              <span className="text-sm font-medium w-4 tabular-nums">{form.influence_level}</span>
            </div>
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={handleCreate} disabled={creating || !form.name || !form.role}>
              {creating ? 'Creation...' : 'Creer'}
            </Button>
          </div>
        </GlassCard>
      )}

      {/* Stakeholder grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map(s => {
          const typeCfg = TYPE_CONFIG[s.type] || TYPE_CONFIG.institution;

          return (
            <GlassCard key={s.id} className="p-4 flex flex-col gap-2 group relative">
              {/* Delete button */}
              <button
                onClick={() => handleDelete(s.id)}
                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity p-1 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>

              {/* Header */}
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full bg-muted flex items-center justify-center text-sm font-bold shrink-0 ${typeCfg.color}`}>
                  {s.name.split(' ').map(w => w[0]).join('').slice(0, 2)}
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold truncate">{s.name}</h3>
                  <p className="text-xs text-muted-foreground truncate">{s.role}</p>
                </div>
              </div>

              {/* Organization */}
              <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                {typeCfg.icon}
                {s.organization}
              </p>

              {/* Influence */}
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={`w-3.5 h-3.5 ${i < s.influence_level ? 'text-amber-400 fill-amber-400' : 'text-muted-foreground/20'}`}
                  />
                ))}
              </div>

              {/* Domains + Tags */}
              <div className="flex flex-wrap gap-1 mt-1">
                {s.domains.slice(0, 3).map(d => (
                  <Badge key={d} variant="secondary" className="text-[10px] px-1.5 py-0 text-primary">
                    {d}
                  </Badge>
                ))}
                {s.tags.slice(0, 2).map(t => (
                  <Badge key={t} variant="outline" className="text-[10px] px-1.5 py-0">
                    {t}
                  </Badge>
                ))}
              </div>
            </GlassCard>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-8 text-muted-foreground text-sm">
          Aucun acteur enregistre
        </div>
      )}
    </div>
  );
}
