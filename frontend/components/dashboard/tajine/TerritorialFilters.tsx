'use client';

import { useState, useCallback, useEffect } from 'react';
import useSWR from 'swr';
import {
  HiOutlineFunnel,
  HiOutlineXMark,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineBuildingOffice2,
  HiOutlineArrowTrendingUp,
  HiOutlineBriefcase,
  HiOutlineUsers,
  HiOutlineMapPin,
  HiOutlineCheck,
} from 'react-icons/hi2';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';

// Filter state for territorial data
export interface TerritorialFilterState {
  region: string | null;
  territory: 'all' | 'metropole' | 'dom_tom';
  sizeRange: [number, number];
  growthRange: [number, number];
  unemploymentRange: [number, number];
  populationRange: [number, number];
}

// Filter options from API
interface FilterOptions {
  regions: { code: string; name: string }[];
  territories: string[];
  size_range: { min: number; max: number };
  growth_range: { min: number; max: number };
  unemployment_range: { min: number; max: number };
  price_range: { min: number; max: number };
  population_range: { min: number; max: number };
}

interface TerritorialFiltersProps {
  filters: TerritorialFilterState;
  onFiltersChange: (filters: TerritorialFilterState) => void;
  className?: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

// Default filter options when API is unavailable
const DEFAULT_FILTER_OPTIONS: FilterOptions = {
  regions: [
    { code: '11', name: 'Ile-de-France' },
    { code: '84', name: 'Auvergne-Rhone-Alpes' },
    { code: '93', name: 'Provence-Alpes-Cote d\'Azur' },
    { code: '75', name: 'Nouvelle-Aquitaine' },
    { code: '76', name: 'Occitanie' },
    { code: '32', name: 'Hauts-de-France' },
    { code: '44', name: 'Grand Est' },
    { code: '28', name: 'Normandie' },
    { code: '52', name: 'Pays de la Loire' },
    { code: '53', name: 'Bretagne' },
    { code: '24', name: 'Centre-Val de Loire' },
    { code: '27', name: 'Bourgogne-Franche-Comte' },
    { code: '94', name: 'Corse' },
  ],
  territories: ['metropole', 'dom_tom'],
  size_range: { min: 0, max: 500000 },
  growth_range: { min: -10, max: 10 },
  unemployment_range: { min: 0, max: 20 },
  price_range: { min: 0, max: 15000 },
  population_range: { min: 0, max: 15000000 },
};

export const defaultTerritorialFilters: TerritorialFilterState = {
  region: null,
  territory: 'all',
  sizeRange: [0, 500000],
  growthRange: [-10, 10],
  unemploymentRange: [0, 20],
  populationRange: [0, 15000000],
};

// Type guard to check if response has expected structure
function isValidFilterOptions(data: unknown): data is FilterOptions {
  return (
    typeof data === 'object' &&
    data !== null &&
    'size_range' in data &&
    typeof (data as FilterOptions).size_range?.min === 'number'
  );
}

export default function TerritorialFilters({
  filters,
  onFiltersChange,
  className = '',
}: TerritorialFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Fetch filter options from API
  const { data: rawOptions, isLoading } = useSWR<FilterOptions | { detail?: string }>(
    '/api/v1/territorial/filter-options',
    fetcher,
    { revalidateOnFocus: false }
  );

  // Use validated options or fallback to defaults
  const options: FilterOptions = isValidFilterOptions(rawOptions)
    ? rawOptions
    : DEFAULT_FILTER_OPTIONS;

  // Count active filters
  const activeFilterCount =
    (filters.region ? 1 : 0) +
    (filters.territory !== 'all' ? 1 : 0) +
    (options &&
    (filters.sizeRange[0] !== options.size_range.min ||
      filters.sizeRange[1] !== options.size_range.max)
      ? 1
      : 0) +
    (options &&
    (filters.growthRange[0] !== options.growth_range.min ||
      filters.growthRange[1] !== options.growth_range.max)
      ? 1
      : 0) +
    (options &&
    (filters.unemploymentRange[0] !== options.unemployment_range.min ||
      filters.unemploymentRange[1] !== options.unemployment_range.max)
      ? 1
      : 0);

  const clearFilters = useCallback(() => {
    onFiltersChange({
      region: null,
      territory: 'all',
      sizeRange: [options.size_range.min, options.size_range.max],
      growthRange: [options.growth_range.min, options.growth_range.max],
      unemploymentRange: [
        options.unemployment_range.min,
        options.unemployment_range.max,
      ],
      populationRange: [
        options.population_range.min,
        options.population_range.max,
      ],
    });
  }, [options, onFiltersChange]);

  const formatNumber = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
    return n.toString();
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Single unified filter dropdown */}
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <button
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
              activeFilterCount > 0 || filters.territory !== 'all' || filters.region
                ? 'bg-primary/20 text-primary border border-primary/30'
                : 'glass hover:bg-white/10 text-muted-foreground'
            }`}
          >
            <HiOutlineFunnel className="w-4 h-4" />
            <span>
              {filters.territory === 'all' ? 'France' : filters.territory === 'metropole' ? 'Metropole' : 'DOM-TOM'}
              {filters.region && ` - ${options.regions.find(r => r.code === filters.region)?.name?.slice(0, 10)}`}
            </span>
            {activeFilterCount > 0 && (
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-[10px]">
                {activeFilterCount}
              </span>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-4" align="start">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-sm">Filtres territoriaux</h4>
              {(activeFilterCount > 0 || filters.territory !== 'all' || filters.region) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="h-7 px-2 text-xs"
                >
                  <HiOutlineXMark className="w-3.5 h-3.5 mr-1" />
                  Effacer
                </Button>
              )}
            </div>

            {/* Territory quick pills - now inside popover */}
            <div className="space-y-2">
              <span className="text-xs text-muted-foreground">Zone</span>
              <div className="flex items-center gap-1">
                {['all', 'metropole', 'dom_tom'].map((t) => (
                  <button
                    key={t}
                    onClick={() =>
                      onFiltersChange({
                        ...filters,
                        territory: t as TerritorialFilterState['territory'],
                      })
                    }
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      filters.territory === t
                        ? 'bg-primary text-primary-foreground'
                        : 'glass hover:bg-white/10 text-muted-foreground'
                    }`}
                  >
                    {t === 'all' ? 'France' : t === 'metropole' ? 'Metropole' : 'DOM-TOM'}
                  </button>
                ))}
              </div>
            </div>

            {/* Region select - now inside popover */}
            <div className="space-y-2">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <HiOutlineMapPin className="w-3.5 h-3.5" />
                Region
              </span>
              <Select
                value={filters.region || 'all'}
                onValueChange={(v) =>
                  onFiltersChange({
                    ...filters,
                    region: v === 'all' ? null : v,
                  })
                }
              >
                <SelectTrigger className="w-full h-9 text-xs glass border-0">
                  <SelectValue placeholder="Toutes regions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes regions</SelectItem>
                  {options?.regions.map((region) => (
                    <SelectItem key={region.code} value={region.code}>
                      {region.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Divider */}
            <div className="border-t border-border/50" />

            {isLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-12 bg-muted/20 rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <>
                {/* Size range */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <HiOutlineBuildingOffice2 className="w-3.5 h-3.5" />
                      Entreprises
                    </span>
                    <span className="text-xs font-medium text-primary">
                      {formatNumber(filters.sizeRange[0])} - {formatNumber(filters.sizeRange[1])}
                    </span>
                  </div>
                  <Slider
                    value={filters.sizeRange}
                    onValueChange={(v) =>
                      onFiltersChange({
                        ...filters,
                        sizeRange: v as [number, number],
                      })
                    }
                    min={options.size_range.min}
                    max={options.size_range.max}
                    step={5000}
                    className="w-full"
                  />
                </div>

                {/* Growth range */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <HiOutlineArrowTrendingUp className="w-3.5 h-3.5" />
                      Croissance
                    </span>
                    <span className="text-xs font-medium text-primary">
                      {filters.growthRange[0].toFixed(1)}% - {filters.growthRange[1].toFixed(1)}%
                    </span>
                  </div>
                  <Slider
                    value={filters.growthRange}
                    onValueChange={(v) =>
                      onFiltersChange({
                        ...filters,
                        growthRange: v as [number, number],
                      })
                    }
                    min={options.growth_range.min}
                    max={options.growth_range.max}
                    step={0.5}
                    className="w-full"
                  />
                </div>

                {/* Unemployment range */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <HiOutlineBriefcase className="w-3.5 h-3.5" />
                      Chomage
                    </span>
                    <span className="text-xs font-medium text-primary">
                      {filters.unemploymentRange[0].toFixed(1)}% - {filters.unemploymentRange[1].toFixed(1)}%
                    </span>
                  </div>
                  <Slider
                    value={filters.unemploymentRange}
                    onValueChange={(v) =>
                      onFiltersChange({
                        ...filters,
                        unemploymentRange: v as [number, number],
                      })
                    }
                    min={options.unemployment_range.min}
                    max={options.unemployment_range.max}
                    step={0.5}
                    className="w-full"
                  />
                </div>

                {/* Population range */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <HiOutlineUsers className="w-3.5 h-3.5" />
                      Population
                    </span>
                    <span className="text-xs font-medium text-primary">
                      {formatNumber(filters.populationRange[0])} - {formatNumber(filters.populationRange[1])}
                    </span>
                  </div>
                  <Slider
                    value={filters.populationRange}
                    onValueChange={(v) =>
                      onFiltersChange({
                        ...filters,
                        populationRange: v as [number, number],
                      })
                    }
                    min={options.population_range.min}
                    max={options.population_range.max}
                    step={50000}
                    className="w-full"
                  />
                </div>

                {/* Quick presets */}
                <div className="pt-2 border-t border-border/50">
                  <div className="text-xs text-muted-foreground mb-2">Presets</div>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() =>
                        onFiltersChange({
                          ...filters,
                          growthRange: [2, 10],
                        })
                      }
                      className="px-2 py-1 text-xs rounded glass hover:bg-white/10"
                    >
                      Forte croissance
                    </button>
                    <button
                      onClick={() =>
                        onFiltersChange({
                          ...filters,
                          sizeRange: [100000, 500000],
                        })
                      }
                      className="px-2 py-1 text-xs rounded glass hover:bg-white/10"
                    >
                      Grands departements
                    </button>
                    <button
                      onClick={() =>
                        onFiltersChange({
                          ...filters,
                          unemploymentRange: [0, 7],
                        })
                      }
                      className="px-2 py-1 text-xs rounded glass hover:bg-white/10"
                    >
                      Faible chomage
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
