'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import Draggable from 'react-draggable';
import { useTAJINE } from '@/contexts/TAJINEContext';
import {
  HiOutlineBuildingOffice2,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineChartBar,
  HiOutlineXMark,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineHome,
  HiOutlineBriefcase,
  HiOutlineUsers,
  HiOutlineCurrencyEuro,
  HiOutlineMapPin,
  HiOutlineMap,
  HiOutlineArrowsPointingOut,
} from 'react-icons/hi2';

// Map mode type - defined early for use in tile layer config
export type MapMode = 'standard' | 'satellite' | 'terrain';

// Tile layer configurations - defined early so TileLayerSwitcher can access it
const TILE_LAYERS: Record<MapMode, { url: string; attribution: string; name: string; subdomains?: string }> = {
  standard: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
    name: 'Standard',
  },
  satellite: {
    // ESRI World Imagery - official, free, and reliable satellite tiles
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
    name: 'Satellite',
  },
  terrain: {
    // OpenTopoMap for terrain visualization
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap contributors, &copy; OpenStreetMap',
    name: 'Terrain',
  },
};

// Dynamic import for Leaflet (SSR incompatible)
const MapContainer = dynamic(
  () => import('react-leaflet').then((mod) => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import('react-leaflet').then((mod) => mod.TileLayer),
  { ssr: false }
);
const GeoJSON = dynamic(
  () => import('react-leaflet').then((mod) => mod.GeoJSON),
  { ssr: false }
);

// Custom component to handle tile layer switching - imported dynamically for SSR safety
const TileLayerSwitcher = dynamic(
  () => import('./TileLayerSwitcher').then((mod) => mod.TileLayerSwitcher),
  { ssr: false }
);

// Types
interface DepartmentFeature {
  type: 'Feature';
  properties: {
    code: string;
    nom: string;
  };
  geometry: GeoJSON.Geometry;
}

interface DepartmentMetrics {
  code: string;
  name: string;
  enterprises: number;
  growth: number;
  analyses: number;
  unemployment?: number;
  population?: number;
  prix_m2?: number;
  health_score?: number;
  budget?: number;
  dette?: number;
  score?: number;
}

export type IndicatorType =
  | 'growth'
  | 'enterprises'
  | 'analyses'
  | 'dynamism'
  | 'prix_m2'
  | 'chomage'
  | 'population'
  | 'health_score'
  | 'budget'
  | 'dette'
  | 'signals'
  | 'attractivite';

interface FranceMapLeafletProps {
  data?: DepartmentMetrics[];
  onSelect?: (code: string | null) => void;
  selectedDepartment?: string | null;
  onDepartmentSelect?: (code: string) => void;
  className?: string;
  activeIndicator?: IndicatorType;
  onIndicatorChange?: (indicator: IndicatorType) => void;
}

export type { DepartmentMetrics };

// Nord color palette
const COLORS = {
  negative: 'var(--error)',
  neutral: 'hsl(var(--muted-foreground))',
  positive: 'var(--success)',
  selected: 'var(--chart-1)',
  hover: 'var(--chart-2)',
  stroke: 'hsl(var(--border))',
  background: 'hsl(var(--background))',
  purple: 'var(--chart-4)',
  orange: 'var(--chart-5)',
  yellow: 'var(--warning)',
};

// Choropleth color scale for attractivity (red=bad -> green=good)
const CHOROPLETH_SCALE = [
  '#dc2626', // 0-20:  red
  '#ea580c', // 20-40: orange
  '#f59e0b', // 40-60: amber
  '#65a30d', // 60-80: lime
  '#16a34a', // 80-100: green
] as const;

/** Returns a choropleth color for a 0-100 score */
function getChoroplethColor(score: number): string {
  if (score >= 80) return CHOROPLETH_SCALE[4];
  if (score >= 60) return CHOROPLETH_SCALE[3];
  if (score >= 40) return CHOROPLETH_SCALE[2];
  if (score >= 20) return CHOROPLETH_SCALE[1];
  return CHOROPLETH_SCALE[0];
}

// Indicator configurations
const INDICATOR_CONFIGS: Record<IndicatorType, {
  label: string;
  icon: React.ReactNode;
  colorScale: (value: number, min: number, max: number) => string;
  format: (value: number) => string;
  getValue: (d: DepartmentMetrics) => number;
  unit: string;
}> = {
  growth: {
    label: 'Croissance',
    icon: <HiOutlineArrowTrendingUp className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      if (value < 0) return COLORS.negative;
      if (value < 2) return COLORS.yellow;
      return COLORS.positive;
    },
    format: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`,
    getValue: (d) => d.growth,
    unit: '%',
  },
  enterprises: {
    label: 'Entreprises',
    icon: <HiOutlineBuildingOffice2 className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.yellow;
      if (normalized < 0.66) return COLORS.orange;
      return COLORS.positive;
    },
    format: (v) => v.toLocaleString('fr-FR'),
    getValue: (d) => d.enterprises,
    unit: '',
  },
  analyses: {
    label: 'Analyses',
    icon: <HiOutlineChartBar className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.neutral;
      if (normalized < 0.66) return COLORS.purple;
      return COLORS.selected;
    },
    format: (v) => v.toString(),
    getValue: (d) => d.analyses,
    unit: '',
  },
  dynamism: {
    label: 'Dynamisme',
    icon: <HiOutlineGlobeEuropeAfrica className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.negative;
      if (normalized < 0.66) return COLORS.yellow;
      return COLORS.positive;
    },
    format: (v) => v.toFixed(1),
    getValue: (d) => (d.enterprises * d.growth) / 1000,
    unit: '',
  },
  prix_m2: {
    label: 'Prix/m2',
    icon: <HiOutlineHome className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.positive;
      if (normalized < 0.66) return COLORS.yellow;
      return COLORS.negative;
    },
    format: (v) => `${v.toLocaleString('fr-FR')} EUR`,
    getValue: (d) => d.prix_m2 || 0,
    unit: 'EUR/m2',
  },
  chomage: {
    label: 'Chomage',
    icon: <HiOutlineBriefcase className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      if (value < 7) return COLORS.positive;
      if (value < 10) return COLORS.yellow;
      return COLORS.negative;
    },
    format: (v) => `${v.toFixed(1)}%`,
    getValue: (d) => d.unemployment || 0,
    unit: '%',
  },
  population: {
    label: 'Population',
    icon: <HiOutlineUsers className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.neutral;
      if (normalized < 0.66) return COLORS.yellow;
      return COLORS.orange;
    },
    format: (v) => `${(v / 1000).toFixed(0)}k`,
    getValue: (d) => d.population || 0,
    unit: 'hab',
  },
  health_score: {
    label: 'Sante eco.',
    icon: <HiOutlineChartBar className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      if (value < 40) return COLORS.negative;
      if (value < 70) return COLORS.yellow;
      return COLORS.positive;
    },
    format: (v) => `${v.toFixed(0)}/100`,
    getValue: (d) => d.health_score || 0,
    unit: '/100',
  },
  budget: {
    label: 'Budget',
    icon: <HiOutlineCurrencyEuro className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.neutral;
      if (normalized < 0.66) return COLORS.yellow;
      return COLORS.positive;
    },
    format: (v) => `${(v / 1e6).toFixed(0)}M EUR`,
    getValue: (d) => d.budget || 0,
    unit: 'EUR',
  },
  dette: {
    label: 'Dette',
    icon: <HiOutlineCurrencyEuro className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = (value - min) / (max - min);
      if (normalized < 0.33) return COLORS.positive;
      if (normalized < 0.66) return COLORS.yellow;
      return COLORS.negative;
    },
    format: (v) => `${(v / 1e6).toFixed(0)}M EUR`,
    getValue: (d) => d.dette || 0,
    unit: 'EUR',
  },
  signals: {
    label: 'Signaux collectés',
    icon: <HiOutlineArrowTrendingUp className="h-4 w-4" />,
    colorScale: (value, min, max) => {
      const normalized = max > min ? (value - min) / (max - min) : 0;
      const r = Math.round(26 + normalized * (232 - 26));
      const g = Math.round(26 + normalized * (90 - 26));
      const b = Math.round(46 + normalized * (60 - 46));
      return `rgb(${r}, ${g}, ${b})`;
    },
    format: (v) => `${v} signaux`,
    getValue: (d) => (d as any).signal_count || (d as any).total_signals || 0,
    unit: 'signaux',
  },
  attractivite: {
    label: 'Attractivite',
    icon: <HiOutlineArrowTrendingUp className="h-4 w-4" />,
    colorScale: (value, _min, _max) => getChoroplethColor(value),
    format: (v) => `${Math.round(v)}/100`,
    getValue: (d) => d.score ?? d.health_score ?? 0,
    unit: '/100',
  },
};

// France center coordinates - adjusted for better view
const FRANCE_CENTER: [number, number] = [46.8, 2.5];
// Extended bounds with padding for better visibility
const FRANCE_BOUNDS: [[number, number], [number, number]] = [
  [40.0, -6.0], // SW - extended for Corsica visibility
  [52.0, 11.0], // NE - extended for full map view
];

export function FranceMapLeaflet({
  data = [],
  onSelect,
  selectedDepartment,
  onDepartmentSelect,
  className = '',
  activeIndicator: externalIndicator,
  onIndicatorChange,
}: FranceMapLeafletProps) {
  const [geoData, setGeoData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [mapMode, setMapMode] = useState<MapMode>('standard');
  const [infoPanelPosition, setInfoPanelPosition] = useState({ x: 0, y: 0 });
  const infoPanelRef = useRef<HTMLDivElement>(null);
  const [internalIndicator, setInternalIndicator] = useState<IndicatorType>('growth');
  const [hoveredDept, setHoveredDept] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const geoJsonRef = useRef<any>(null);

  const activeIndicator = externalIndicator ?? internalIndicator;

  // Client-side only
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Load GeoJSON
  useEffect(() => {
    fetch('/data/france-departments.json')
      .then((res) => res.json())
      .then((data) => setGeoData(data))
      .catch((err) => console.error('Failed to load GeoJSON:', err));
  }, []);

  // Create data lookup map
  const dataMap = useMemo(() => {
    const map = new Map<string, DepartmentMetrics>();
    data.forEach((d) => map.set(d.code, d));
    return map;
  }, [data]);

  // Calculate min/max for color scaling
  const { minValue, maxValue } = useMemo(() => {
    const config = INDICATOR_CONFIGS[activeIndicator];
    const values = data.map((d) => config.getValue(d)).filter((v) => v !== undefined);
    return {
      minValue: Math.min(...values, 0),
      maxValue: Math.max(...values, 1),
    };
  }, [data, activeIndicator]);

  // Style function for GeoJSON features
  const getStyle = useCallback(
    (feature: any) => {
      const code = feature.properties.code;
      const deptData = dataMap.get(code);
      const config = INDICATOR_CONFIGS[activeIndicator];

      let fillColor = COLORS.neutral;
      let fillOpacity = 0.6;

      if (deptData) {
        const value = config.getValue(deptData);
        fillColor = config.colorScale(value, minValue, maxValue);
      }

      if (code === selectedDepartment) {
        fillColor = COLORS.selected;
        fillOpacity = 0.85;
      } else if (code === hoveredDept) {
        fillOpacity = 0.8;
      }

      return {
        fillColor,
        fillOpacity,
        color: code === selectedDepartment ? COLORS.selected : COLORS.stroke,
        weight: code === selectedDepartment ? 2 : 1,
      };
    },
    [dataMap, activeIndicator, minValue, maxValue, selectedDepartment, hoveredDept]
  );

  // Event handlers for each feature
  const onEachFeature = useCallback(
    (feature: any, layer: any) => {
      const code = feature.properties.code;
      const name = feature.properties.nom;
      const deptData = dataMap.get(code);
      const config = INDICATOR_CONFIGS[activeIndicator];

      // Tooltip
      const value = deptData ? config.getValue(deptData) : null;
      const tooltipContent = `
        <div class="p-2 bg-[var(--background)] border border-[var(--border)] rounded-lg shadow-lg">
          <div class="font-semibold">${name} (${code})</div>
          ${value !== null ? `<div class="text-sm text-muted-foreground">${config.label}: ${config.format(value)}</div>` : ''}
        </div>
      `;
      layer.bindTooltip(tooltipContent, { className: 'leaflet-tooltip-custom' });

      // Events
      layer.on({
        click: () => {
          if (onDepartmentSelect) onDepartmentSelect(code);
          if (onSelect) onSelect(code);
        },
        mouseover: () => setHoveredDept(code),
        mouseout: () => setHoveredDept(null),
      });
    },
    [dataMap, activeIndicator, onDepartmentSelect, onSelect]
  );

  // Handle indicator change
  const handleIndicatorChange = useCallback(
    (indicator: IndicatorType) => {
      if (onIndicatorChange) {
        onIndicatorChange(indicator);
      } else {
        setInternalIndicator(indicator);
      }
    },
    [onIndicatorChange]
  );

  // Refresh GeoJSON when data/indicator changes
  useEffect(() => {
    if (geoJsonRef.current) {
      geoJsonRef.current.clearLayers();
      if (geoData) {
        geoJsonRef.current.addData(geoData);
      }
    }
  }, [geoData, data, activeIndicator, selectedDepartment]);

  if (!isClient) {
    return (
      <div className={`relative min-h-[400px] h-full w-full bg-[var(--card)] rounded-xl ${className}`}>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="animate-pulse text-muted-foreground">Chargement de la carte...</div>
        </div>
      </div>
    );
  }

  const config = INDICATOR_CONFIGS[activeIndicator];

  return (
    <div className={`relative min-h-[400px] h-full w-full bg-[var(--card)] rounded-xl ${className}`}>
      {/* Map Mode Toggle - Top right */}
      <div className="absolute top-2 sm:top-4 right-2 sm:right-4 z-[1001] flex gap-0.5 sm:gap-1 glass rounded-lg p-0.5 sm:p-1">
        {(Object.keys(TILE_LAYERS) as MapMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setMapMode(mode)}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded transition-all ${
              mapMode === mode
                ? 'bg-[var(--primary)] text-white'
                : 'hover:bg-[var(--muted)] text-[var(--foreground)]'
            }`}
          >
            {mode === 'standard' && <HiOutlineMap className="inline h-3 sm:h-3.5 w-3 sm:w-3.5 mr-0.5 sm:mr-1" />}
            {mode === 'satellite' && <HiOutlineGlobeEuropeAfrica className="inline h-3 sm:h-3.5 w-3 sm:w-3.5 mr-0.5 sm:mr-1" />}
            {mode === 'terrain' && <HiOutlineMapPin className="inline h-3 sm:h-3.5 w-3 sm:w-3.5 mr-0.5 sm:mr-1" />}
            <span className="hidden sm:inline">{TILE_LAYERS[mode].name}</span>
          </button>
        ))}
      </div>

      {/* Indicator Selector - Vertical on right side, below map mode toggle */}
      <div className="absolute top-16 sm:top-20 right-2 sm:right-4 z-[1000] glass rounded-lg p-1.5 sm:p-2">
        <div className="text-[10px] sm:text-xs font-medium text-muted-foreground mb-1 sm:mb-2">Indicateur</div>
        <div className="flex flex-col gap-0.5 sm:gap-1">
          {(['attractivite', 'growth', 'enterprises', 'chomage', 'prix_m2'] as IndicatorType[]).map((ind) => {
            const indConfig = INDICATOR_CONFIGS[ind];
            return (
              <button
                key={ind}
                onClick={() => handleIndicatorChange(ind)}
                className={`flex items-center gap-1.5 px-2 sm:px-3 py-1 sm:py-1.5 text-[10px] sm:text-xs rounded transition-all whitespace-nowrap ${
                  activeIndicator === ind
                    ? 'bg-[var(--primary)] text-white'
                    : 'hover:bg-[var(--muted)]'
                }`}
              >
                {indConfig.icon}
                <span>{indConfig.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Legend - Above ChartsDrawer (60px from bottom) */}
      <div className="absolute bottom-[60px] sm:bottom-[64px] left-2 sm:left-4 z-[1000] glass rounded-lg p-2 sm:p-3">
        <div className="text-[10px] sm:text-xs font-medium mb-1 sm:mb-2">{config.label}</div>
        {activeIndicator === 'attractivite' ? (
          <div className="space-y-1">
            <div className="flex gap-0.5">
              {CHOROPLETH_SCALE.map((color, i) => (
                <div
                  key={i}
                  className="w-5 sm:w-6 h-2.5 sm:h-3 first:rounded-l-sm last:rounded-r-sm"
                  style={{ background: color }}
                />
              ))}
            </div>
            <div className="flex justify-between text-[9px] sm:text-[10px] text-muted-foreground">
              <span>0</span>
              <span>50</span>
              <span>100</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 sm:gap-2">
            <div className="flex gap-0.5">
              <div className="w-3 sm:w-4 h-2.5 sm:h-3 rounded-sm" style={{ background: COLORS.negative }} />
              <div className="w-3 sm:w-4 h-2.5 sm:h-3 rounded-sm" style={{ background: COLORS.yellow }} />
              <div className="w-3 sm:w-4 h-2.5 sm:h-3 rounded-sm" style={{ background: COLORS.positive }} />
            </div>
            <span className="text-[10px] sm:text-xs text-muted-foreground whitespace-nowrap">
              {config.format(minValue)} - {config.format(maxValue)}
            </span>
          </div>
        )}
      </div>

      {/* Selected Department Info - Draggable, responsive */}
      {selectedDepartment && dataMap.has(selectedDepartment) && (
        <Draggable
          handle=".drag-handle-leaflet"
          bounds="parent"
          position={infoPanelPosition}
          onStop={(e, d) => setInfoPanelPosition({ x: d.x, y: d.y })}
          nodeRef={infoPanelRef}
        >
          <div
            ref={infoPanelRef}
            className="absolute bottom-[60px] sm:bottom-[64px] right-2 sm:right-4 z-[1002] glass rounded-lg overflow-hidden min-w-[160px] sm:min-w-[200px] max-w-[200px] sm:max-w-[240px]"
          >
            {/* Drag handle header */}
            <div className="drag-handle-leaflet flex items-center justify-between p-1.5 sm:p-2 border-b border-border/30 cursor-move select-none bg-muted/20 hover:bg-muted/30 transition-colors">
              <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
                <HiOutlineArrowsPointingOut className="w-2.5 sm:w-3 h-2.5 sm:h-3 text-muted-foreground/60 flex-shrink-0" />
                <span className="font-semibold text-xs sm:text-sm truncate">
                  {dataMap.get(selectedDepartment)?.name || selectedDepartment}
                </span>
              </div>
              <button
                onClick={() => {
                  if (onDepartmentSelect) onDepartmentSelect('');
                  if (onSelect) onSelect(null);
                }}
                className="p-0.5 sm:p-1 hover:bg-[var(--muted)] rounded flex-shrink-0"
              >
                <HiOutlineXMark className="h-3.5 sm:h-4 w-3.5 sm:w-4" />
              </button>
            </div>
            {/* Content */}
            <div className="p-2 sm:p-3 space-y-0.5 sm:space-y-1 text-[10px] sm:text-xs">
              {(() => {
                const deptData = dataMap.get(selectedDepartment);
                if (!deptData) return null;
                const attractScore = deptData.score ?? deptData.health_score ?? 0;
                return (
                  <>
                    {/* Attractivity score bar */}
                    <div className="mb-1.5">
                      <div className="flex justify-between gap-2 mb-0.5">
                        <span className="text-muted-foreground">Attractivite</span>
                        <span className="font-bold" style={{ color: getChoroplethColor(attractScore) }}>
                          {Math.round(attractScore)}/100
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-muted/40 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(100, Math.max(0, attractScore))}%`,
                            background: getChoroplethColor(attractScore),
                          }}
                        />
                      </div>
                    </div>
                    {(['enterprises', 'growth', 'chomage'] as IndicatorType[]).map((ind) => {
                      const indConfig = INDICATOR_CONFIGS[ind];
                      const value = indConfig.getValue(deptData);
                      return (
                        <div key={ind} className="flex justify-between gap-2">
                          <span className="text-muted-foreground truncate">{indConfig.label}</span>
                          <span className="font-medium whitespace-nowrap">{indConfig.format(value)}</span>
                        </div>
                      );
                    })}
                  </>
                );
              })()}
            </div>
          </div>
        </Draggable>
      )}

      {/* Leaflet Map */}
      {typeof window !== 'undefined' && (
        <MapContainer
          center={FRANCE_CENTER}
          zoom={5.5}
          maxBounds={FRANCE_BOUNDS}
          maxBoundsViscosity={0.8}
          minZoom={4.5}
          maxZoom={12}
          style={{
            height: className.includes('h-full') ? '100%' : '400px',
            width: '100%',
            minHeight: '400px'
          }}
          className="rounded-xl"
          scrollWheelZoom={true}
        >
          <TileLayerSwitcher mode={mapMode} />
          {geoData && (
            <GeoJSON
              ref={geoJsonRef}
              key={`${activeIndicator}-${selectedDepartment}-${JSON.stringify(data.map(d => d.code))}`}
              data={geoData}
              style={getStyle}
              onEachFeature={onEachFeature}
            />
          )}
        </MapContainer>
      )}

      {/* Custom tooltip styles */}
      <style dangerouslySetInnerHTML={{ __html: `
        .leaflet-tooltip-custom {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          padding: 0 !important;
        }
        .leaflet-tooltip-custom::before {
          display: none;
        }
      `}} />
    </div>
  );
}

export default FranceMapLeaflet;
