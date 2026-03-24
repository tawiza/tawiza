'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineFunnel,
  HiOutlineCalendarDays,
  HiOutlineCheckCircle,
  HiOutlineClock,
  HiOutlineExclamationCircle,
  HiOutlineXMark,
  HiOutlineChevronDown,
  HiOutlineAcademicCap,
} from 'react-icons/hi2';

// Filter types
export interface FilterState {
  dateRange: 'all' | 'today' | 'week' | 'month' | 'custom';
  status: ('completed' | 'pending' | 'error')[];
  cognitiveLevel: ('tactical' | 'strategic' | 'theoretical')[];
  sortBy: 'date' | 'department' | 'status' | 'level';
  sortOrder: 'asc' | 'desc';
}

interface AdvancedFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  className?: string;
}

const STATUS_OPTIONS = [
  { value: 'completed', label: 'Termine', icon: HiOutlineCheckCircle, color: 'text-[var(--success)] bg-[var(--success)]/20' },
  { value: 'pending', label: 'En cours', icon: HiOutlineClock, color: 'text-[var(--warning)] bg-[var(--warning)]/20' },
  { value: 'error', label: 'Erreur', icon: HiOutlineExclamationCircle, color: 'text-[var(--error)] bg-[var(--error)]/20' },
] as const;

const COGNITIVE_LEVELS = [
  { value: 'tactical', label: 'Tactique', description: 'Analyses rapides' },
  { value: 'strategic', label: 'Strategique', description: 'Analyses approfondies' },
  { value: 'theoretical', label: 'Theorique', description: 'Modelisation avancee' },
] as const;

const DATE_RANGES = [
  { value: 'all', label: 'Tout' },
  { value: 'today', label: "Aujourd'hui" },
  { value: 'week', label: 'Cette semaine' },
  { value: 'month', label: 'Ce mois' },
] as const;

export const defaultFilters: FilterState = {
  dateRange: 'all',
  status: [],
  cognitiveLevel: [],
  sortBy: 'date',
  sortOrder: 'desc',
};

export default function AdvancedFilters({ filters, onFiltersChange, className = '' }: AdvancedFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Count active filters
  const activeFilterCount =
    (filters.dateRange !== 'all' ? 1 : 0) +
    filters.status.length +
    filters.cognitiveLevel.length;

  const toggleStatus = useCallback((status: FilterState['status'][number]) => {
    const newStatus = filters.status.includes(status)
      ? filters.status.filter(s => s !== status)
      : [...filters.status, status];
    onFiltersChange({ ...filters, status: newStatus });
  }, [filters, onFiltersChange]);

  const toggleCognitiveLevel = useCallback((level: FilterState['cognitiveLevel'][number]) => {
    const newLevels = filters.cognitiveLevel.includes(level)
      ? filters.cognitiveLevel.filter(l => l !== level)
      : [...filters.cognitiveLevel, level];
    onFiltersChange({ ...filters, cognitiveLevel: newLevels });
  }, [filters, onFiltersChange]);

  const setDateRange = useCallback((range: FilterState['dateRange']) => {
    onFiltersChange({ ...filters, dateRange: range });
  }, [filters, onFiltersChange]);

  const clearFilters = useCallback(() => {
    onFiltersChange(defaultFilters);
  }, [onFiltersChange]);

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Filter toggle button */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`flex items-center gap-2 px-3 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm transition-all ${
            isExpanded || activeFilterCount > 0
              ? 'glass border border-primary/50 text-primary'
              : 'glass hover:bg-white/5'
          }`}
        >
          <HiOutlineFunnel className="w-3.5 sm:w-4 h-3.5 sm:h-4" />
          <span className="hidden sm:inline">Filtres</span>
          {activeFilterCount > 0 && (
            <span className="flex items-center justify-center w-4 sm:w-5 h-4 sm:h-5 rounded-full bg-primary text-primary-foreground text-[10px] sm:text-xs font-medium">
              {activeFilterCount}
            </span>
          )}
          <HiOutlineChevronDown
            className={`w-3 sm:w-4 h-3 sm:h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        {/* Quick filter chips for date */}
        <div className="hidden sm:flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
          {DATE_RANGES.map(range => (
            <button
              key={range.value}
              onClick={() => setDateRange(range.value as FilterState['dateRange'])}
              className={`px-2 py-1 rounded-full text-xs transition-all whitespace-nowrap ${
                filters.dateRange === range.value
                  ? 'bg-primary/20 text-primary'
                  : 'glass hover:bg-white/5 text-muted-foreground'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>

        {/* Clear button */}
        {activeFilterCount > 0 && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <HiOutlineXMark className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Effacer</span>
          </button>
        )}
      </div>

      {/* Expanded filters panel */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="glass rounded-lg p-3 sm:p-4 space-y-3 sm:space-y-4">
              {/* Date range - mobile */}
              <div className="sm:hidden">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <HiOutlineCalendarDays className="w-3.5 h-3.5" />
                  Periode
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {DATE_RANGES.map(range => (
                    <button
                      key={range.value}
                      onClick={() => setDateRange(range.value as FilterState['dateRange'])}
                      className={`px-2.5 py-1 rounded-full text-[11px] transition-all ${
                        filters.dateRange === range.value
                          ? 'bg-primary/20 text-primary'
                          : 'glass hover:bg-white/5 text-muted-foreground'
                      }`}
                    >
                      {range.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status filters */}
              <div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <HiOutlineCheckCircle className="w-3.5 h-3.5" />
                  Statut
                </div>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                  {STATUS_OPTIONS.map(option => {
                    const Icon = option.icon;
                    const isActive = filters.status.includes(option.value);
                    return (
                      <button
                        key={option.value}
                        onClick={() => toggleStatus(option.value)}
                        className={`flex items-center gap-1.5 px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs transition-all ${
                          isActive
                            ? option.color
                            : 'glass hover:bg-white/5 text-muted-foreground'
                        }`}
                      >
                        <Icon className="w-3 sm:w-3.5 h-3 sm:h-3.5" />
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Cognitive level filters */}
              <div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <HiOutlineAcademicCap className="w-3.5 h-3.5" />
                  Niveau cognitif
                </div>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                  {COGNITIVE_LEVELS.map(level => {
                    const isActive = filters.cognitiveLevel.includes(level.value);
                    return (
                      <button
                        key={level.value}
                        onClick={() => toggleCognitiveLevel(level.value)}
                        className={`flex flex-col items-start px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-left transition-all ${
                          isActive
                            ? 'bg-[var(--chart-1)]/20 text-[var(--chart-1)]'
                            : 'glass hover:bg-white/5 text-muted-foreground'
                        }`}
                      >
                        <span className="text-[11px] sm:text-xs font-medium">{level.label}</span>
                        <span className="text-[9px] sm:text-[10px] opacity-70 hidden sm:block">{level.description}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
