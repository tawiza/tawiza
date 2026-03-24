'use client';

import { useState } from 'react';
import { ACTOR_COLORS } from '@/types/relations';
import type { ActorType } from '@/types/relations';
import { Search, Palette } from 'lucide-react';

export type ColorMode = 'type' | 'risk' | 'community' | 'shapley';

interface GraphFiltersProps {
  actorTypes: string[];
  enabledTypes: Set<string>;
  onToggleType: (type: string) => void;
  enabledLevels: Set<string>;
  onToggleLevel: (level: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  communities: { id: number; size: number }[];
  selectedCommunity: number | null;
  onSelectCommunity: (id: number | null) => void;
  colorMode: ColorMode;
  onColorModeChange: (mode: ColorMode) => void;
}

const TYPE_LABELS: Record<string, string> = {
  enterprise: 'Entreprise',
  territory: 'Territoire',
  institution: 'Institution',
  sector: 'Secteur',
  association: 'Association',
  formation: 'Formation',
  financial: 'Financier',
};

const LEVEL_LABELS: Record<string, { label: string; color: string }> = {
  structural: { label: 'L1', color: '#A3BE8C' },
  inferred: { label: 'L2', color: '#EBCB8B' },
  hypothetical: { label: 'L3', color: '#BF616A' },
};

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  type: 'Par type',
  risk: 'Par risque',
  community: 'Par communaute',
  shapley: 'Par Shapley',
};

export default function GraphFilters({
  actorTypes,
  enabledTypes,
  onToggleType,
  enabledLevels,
  onToggleLevel,
  searchQuery,
  onSearchChange,
  communities,
  selectedCommunity,
  onSelectCommunity,
  colorMode,
  onColorModeChange,
}: GraphFiltersProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-2 p-3 rounded-xl bg-black/40 border border-white/10">
      {/* Row 1: Type checkboxes + search */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Actor type toggles */}
        <div className="flex flex-wrap gap-1.5">
          {actorTypes.map((t) => {
            const checked = enabledTypes.has(t);
            const color = ACTOR_COLORS[t as ActorType] || '#88C0D0';
            return (
              <button
                key={t}
                onClick={() => onToggleType(t)}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all border"
                style={{
                  backgroundColor: checked ? `${color}20` : 'transparent',
                  borderColor: checked ? `${color}50` : 'rgba(255,255,255,0.1)',
                  color: checked ? color : 'rgba(255,255,255,0.3)',
                }}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: color, opacity: checked ? 1 : 0.3 }}
                />
                {TYPE_LABELS[t] || t}
              </button>
            );
          })}
        </div>

        {/* Level toggles */}
        <div className="flex gap-1 border-l border-white/10 pl-3">
          {Object.entries(LEVEL_LABELS).map(([level, { label, color }]) => {
            const checked = enabledLevels.has(level);
            return (
              <button
                key={level}
                onClick={() => onToggleLevel(level)}
                className="px-2 py-1 rounded-md text-[10px] font-bold transition-all border"
                style={{
                  backgroundColor: checked ? `${color}20` : 'transparent',
                  borderColor: checked ? `${color}50` : 'rgba(255,255,255,0.1)',
                  color: checked ? color : 'rgba(255,255,255,0.3)',
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="flex items-center gap-1.5 flex-1 min-w-[140px] border-l border-white/10 pl-3">
          <Search className="w-3 h-3 text-white/30 shrink-0" />
          <input
            type="text"
            placeholder="Rechercher..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="bg-transparent text-xs text-white/80 placeholder:text-white/20 outline-none flex-1"
          />
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-white/40 hover:text-white/70 transition-colors"
        >
          {expanded ? 'Moins' : 'Plus'}
        </button>
      </div>

      {/* Row 2: Color mode + community (expandable) */}
      {expanded && (
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-white/5">
          {/* Color mode */}
          <div className="flex items-center gap-1.5">
            <Palette className="w-3 h-3 text-white/40" />
            <span className="text-[10px] text-white/40">Couleur:</span>
            <div className="flex gap-1">
              {(Object.keys(COLOR_MODE_LABELS) as ColorMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => onColorModeChange(mode)}
                  className={`px-2 py-0.5 rounded text-[10px] transition-all ${
                    colorMode === mode
                      ? 'bg-white/15 text-white/90 font-medium'
                      : 'text-white/30 hover:text-white/60'
                  }`}
                >
                  {COLOR_MODE_LABELS[mode]}
                </button>
              ))}
            </div>
          </div>

          {/* Community dropdown */}
          {communities.length > 0 && (
            <div className="flex items-center gap-1.5 border-l border-white/10 pl-3">
              <span className="text-[10px] text-white/40">Communaute:</span>
              <select
                value={selectedCommunity ?? ''}
                onChange={(e) =>
                  onSelectCommunity(e.target.value === '' ? null : Number(e.target.value))
                }
                className="bg-transparent text-[10px] text-white/70 border border-white/10 rounded px-1.5 py-0.5 outline-none"
              >
                <option value="">Toutes</option>
                {communities.map((c) => (
                  <option key={c.id} value={c.id}>
                    #{c.id} ({c.size} noeuds)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
