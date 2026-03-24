'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';
import { motion, AnimatePresence } from 'framer-motion';
import Draggable from 'react-draggable';
import { useTAJINE } from '@/contexts/TAJINEContext';
import {
  HiOutlineBuildingOffice2,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineChartBar,
  HiOutlineXMark,
  HiOutlineMagnifyingGlassPlus,
  HiOutlineMagnifyingGlassMinus,
  HiOutlineArrowPath,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineHome,
  HiOutlineBriefcase,
  HiOutlineUsers,
  HiOutlineCurrencyEuro,
  HiOutlineArrowsPointingOut,
  HiOutlineSparkles,
} from 'react-icons/hi2';

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
  // Extended metrics for territorial analysis
  unemployment?: number;
  population?: number;
  prix_m2?: number;
  health_score?: number;
  budget?: number;
  dette?: number;
  // Collector data fields
  signal_count?: number;
  total_signals?: number;
  anomalies?: number;
  latest_signal?: string;
  sources?: Record<string, number>;
  // Composite attractivity score
  score?: number;
}

// All indicator types (base + extended)
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

interface FranceMapProps {
  data?: DepartmentMetrics[];
  onSelect?: (code: string | null) => void;
  selectedDepartment?: string | null;
  onDepartmentSelect?: (code: string) => void;
  className?: string;
  // External indicator control
  activeIndicator?: IndicatorType;
  onIndicatorChange?: (indicator: IndicatorType) => void;
}

// Export types for external use
export type { DepartmentMetrics };

interface IndicatorConfig {
  key: IndicatorType;
  label: string;
  icon: React.ReactNode;
  colorScale: (value: number, min: number, max: number) => string;
  format: (value: number) => string;
  getValue: (d: DepartmentMetrics) => number;
  legendSteps: number[];
  unit: string;
}

// Nord color palette
const COLORS = {
  negative: 'var(--error)',  // nord11 - red
  neutral: 'hsl(var(--muted-foreground))',   // nord4 - light gray
  positive: 'var(--success)',  // nord14 - green
  selected: 'var(--chart-1)',  // nord8 - cyan
  hover: 'var(--chart-2)',     // nord9 - blue
  stroke: 'hsl(var(--border))',    // nord3 - dark gray
  background: 'hsl(var(--background))', // nord0
  purple: 'var(--chart-4)',    // nord15
  orange: 'var(--chart-5)',    // nord12
  yellow: 'var(--warning)',    // nord13
};

// DOM-TOM codes for special positioning
const DOM_CODES = ['971', '972', '973', '974', '976'];

// Indicator configurations
const INDICATORS: Record<IndicatorType, IndicatorConfig> = {
  growth: {
    key: 'growth',
    label: 'Croissance',
    icon: <HiOutlineArrowTrendingUp className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleLinear<string>()
        .domain([min, 0, max])
        .range([COLORS.negative, COLORS.neutral, COLORS.positive])
        .clamp(true);
      return scale(value);
    },
    format: (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`,
    getValue: (d) => d.growth,
    legendSteps: [-5, -2, 0, 2, 5],
    unit: '%'
  },
  enterprises: {
    key: 'enterprises',
    label: 'Entreprises',
    icon: <HiOutlineBuildingOffice2 className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolateBlues)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => v.toLocaleString(),
    getValue: (d) => d.enterprises,
    legendSteps: [10000, 50000, 100000, 200000],
    unit: ''
  },
  analyses: {
    key: 'analyses',
    label: 'Analyses',
    icon: <HiOutlineChartBar className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolatePurples)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => v.toString(),
    getValue: (d) => d.analyses,
    legendSteps: [0, 5, 10, 20],
    unit: ''
  },
  signals: {
    key: 'signals',
    label: 'Signaux collectés',
    icon: <HiOutlineSparkles className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolateOranges)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => `${v.toLocaleString()} signaux`,
    getValue: (d) => d.signal_count || d.total_signals || 0,
    legendSteps: [0, 100, 500, 1000, 5000],
    unit: ''
  },
  dynamism: {
    key: 'dynamism',
    label: 'Dynamisme',
    icon: <HiOutlineGlobeEuropeAfrica className="w-4 h-4" />,
    colorScale: (value) => {
      if (value >= 2) return COLORS.positive;
      if (value >= 0) return COLORS.yellow;
      return COLORS.negative;
    },
    format: (v) => v >= 2 ? 'Dynamique' : v >= 0 ? 'Stable' : 'Déclin',
    getValue: (d) => d.growth, // Based on growth
    legendSteps: [-5, 0, 2, 5],
    unit: ''
  },
  // Extended indicators
  prix_m2: {
    key: 'prix_m2',
    label: 'Prix/m²',
    icon: <HiOutlineHome className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolateYlOrRd)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => `${v.toLocaleString()} €/m²`,
    getValue: (d) => d.prix_m2 ?? 0,
    legendSteps: [1000, 2000, 4000, 8000],
    unit: '€/m²'
  },
  chomage: {
    key: 'chomage',
    label: 'Chômage',
    icon: <HiOutlineBriefcase className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      // Inverted: higher unemployment = more red
      const scale = d3.scaleLinear<string>()
        .domain([min, (min + max) / 2, max])
        .range([COLORS.positive, COLORS.yellow, COLORS.negative])
        .clamp(true);
      return scale(value);
    },
    format: (v) => `${v.toFixed(1)}%`,
    getValue: (d) => d.unemployment ?? 0,
    legendSteps: [5, 7, 9, 12],
    unit: '%'
  },
  population: {
    key: 'population',
    label: 'Population',
    icon: <HiOutlineUsers className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolateGreens)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => {
      if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
      if (v >= 1000) return `${(v / 1000).toFixed(0)}k`;
      return v.toString();
    },
    getValue: (d) => d.population ?? 0,
    legendSteps: [100000, 500000, 1000000, 2000000],
    unit: ''
  },
  health_score: {
    key: 'health_score',
    label: 'Score Santé',
    icon: <HiOutlineGlobeEuropeAfrica className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleLinear<string>()
        .domain([0, 50, 100])
        .range([COLORS.negative, COLORS.yellow, COLORS.positive])
        .clamp(true);
      return scale(value);
    },
    format: (v) => `${v.toFixed(0)}/100`,
    getValue: (d) => d.health_score ?? 50,
    legendSteps: [0, 25, 50, 75, 100],
    unit: '/100'
  },
  budget: {
    key: 'budget',
    label: 'Budget/hab',
    icon: <HiOutlineCurrencyEuro className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      const scale = d3.scaleSequential(d3.interpolateBlues)
        .domain([min, max]);
      return scale(value);
    },
    format: (v) => `${v.toLocaleString()} €`,
    getValue: (d) => d.budget ?? 0,
    legendSteps: [500, 1000, 1500, 2000],
    unit: '€/hab'
  },
  dette: {
    key: 'dette',
    label: 'Dette/hab',
    icon: <HiOutlineArrowTrendingDown className="w-4 h-4" />,
    colorScale: (value, min, max) => {
      // Higher debt = more red
      const scale = d3.scaleLinear<string>()
        .domain([min, (min + max) / 2, max])
        .range([COLORS.positive, COLORS.yellow, COLORS.negative])
        .clamp(true);
      return scale(value);
    },
    format: (v) => `${v.toLocaleString()} €`,
    getValue: (d) => d.dette ?? 0,
    legendSteps: [200, 500, 1000, 2000],
    unit: '€/hab'
  },
  attractivite: {
    key: 'attractivite',
    label: 'Attractivite',
    icon: <HiOutlineArrowTrendingUp className="w-4 h-4" />,
    colorScale: (value) => {
      if (value >= 80) return '#16a34a';
      if (value >= 60) return '#65a30d';
      if (value >= 40) return '#f59e0b';
      if (value >= 20) return '#ea580c';
      return '#dc2626';
    },
    format: (v) => `${Math.round(v)}/100`,
    getValue: (d) => d.score ?? d.health_score ?? 0,
    legendSteps: [0, 20, 40, 60, 80, 100],
    unit: '/100'
  },
};

// Export INDICATORS for external use
export { INDICATORS };

export default function FranceMap({
  data = [],
  onSelect,
  selectedDepartment: propSelectedDept,
  onDepartmentSelect,
  className = '',
  activeIndicator: externalIndicator,
  onIndicatorChange
}: FranceMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [geoData, setGeoData] = useState<DepartmentFeature[] | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);
  const { selectedDepartment: contextSelectedDept, setSelectedDepartment } = useTAJINE();

  // Explorer mode state - use external indicator if provided
  const [internalIndicator, setInternalIndicator] = useState<IndicatorType>('growth');
  const activeIndicator = externalIndicator ?? internalIndicator;
  const setActiveIndicator = (ind: IndicatorType) => {
    if (onIndicatorChange) {
      onIndicatorChange(ind);
    } else {
      setInternalIndicator(ind);
    }
  };

  const [legendFilter, setLegendFilter] = useState<number | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panelMinimized, setPanelMinimized] = useState(false);
  const [panelPosition, setPanelPosition] = useState({ x: 0, y: 0 });
  const panelRef = useRef<HTMLDivElement>(null);

  // Use prop if provided, otherwise fall back to context
  const selectedDepartment = propSelectedDept !== undefined ? propSelectedDept : contextSelectedDept;

  // Reset panel minimized state when department changes
  useEffect(() => {
    setPanelMinimized(false);
  }, [selectedDepartment]);

  // Current indicator config
  const indicator = INDICATORS[activeIndicator];

  // Handle department selection - call both handlers
  const handleSelect = useCallback((code: string) => {
    setSelectedDepartment(code); // Update context
    onDepartmentSelect?.(code);  // Call prop handler
    onSelect?.(code);            // Legacy handler
  }, [setSelectedDepartment, onDepartmentSelect, onSelect]);

  // Compute national averages for comparison
  const nationalStats = useMemo(() => {
    if (data.length === 0) return null;
    const totalEnterprises = data.reduce((sum, d) => sum + d.enterprises, 0);
    const avgGrowth = data.reduce((sum, d) => sum + d.growth, 0) / data.length;
    const totalAnalyses = data.reduce((sum, d) => sum + d.analyses, 0);
    return {
      avgEnterprises: Math.round(totalEnterprises / data.length),
      totalEnterprises,
      avgGrowth: avgGrowth,
      totalAnalyses
    };
  }, [data]);

  // Min/Max for current indicator
  const { minValue, maxValue } = useMemo(() => {
    if (data.length === 0) return { minValue: 0, maxValue: 0 };
    const values = data.map(d => indicator.getValue(d));
    return {
      minValue: Math.min(...values),
      maxValue: Math.max(...values)
    };
  }, [data, indicator]);

  // Create color scale based on active indicator
  const colorScale = useCallback((value: number) => {
    if (data.length === 0) return COLORS.neutral;
    return indicator.colorScale(value, minValue, maxValue);
  }, [data, indicator, minValue, maxValue]);

  // Zoom control functions
  const handleZoomIn = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(300).call(
      zoomRef.current.scaleBy, 1.5
    );
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(300).call(
      zoomRef.current.scaleBy, 0.67
    );
  }, []);

  const handleZoomReset = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(300).call(
      zoomRef.current.transform, d3.zoomIdentity
    );
    setZoomLevel(1);
  }, []);

  // Get metrics for a department
  const getMetrics = useCallback((code: string): DepartmentMetrics | undefined => {
    return data.find(d => d.code === code);
  }, [data]);

  // Load GeoJSON
  useEffect(() => {
    fetch('/data/france-departments.json')
      .then(res => res.json())
      .then((geo: GeoJSON.FeatureCollection) => {
        setGeoData(geo.features as DepartmentFeature[]);
      })
      .catch(err => console.error('Failed to load France GeoJSON:', err));
  }, []);

  // Render map with D3
  useEffect(() => {
    if (!geoData || !svgRef.current || !containerRef.current) return;

    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 500;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Clear previous render
    svg.selectAll('*').remove();

    // Create main group for zoom/pan
    const g = svg.append('g');

    // Filter metropole vs DOM
    const metropole = geoData.filter(f => !DOM_CODES.includes(f.properties.code));
    const dom = geoData.filter(f => DOM_CODES.includes(f.properties.code));

    // Projection for metropolitan France
    const projection = d3.geoConicConformal()
      .center([2.454071, 46.279229])
      .scale(width * 4)
      .translate([width * 0.45, height * 0.52]);

    const path = d3.geoPath().projection(projection);

    // Get fill color for a department
    const getDeptColor = (code: string) => {
      if (code === selectedDepartment) return COLORS.selected;
      const metrics = getMetrics(code);
      if (!metrics) return COLORS.neutral;
      const value = indicator.getValue(metrics);
      // Apply legend filter if active
      if (legendFilter !== null) {
        const steps = indicator.legendSteps;
        const stepIndex = steps.findIndex(s => s === legendFilter);
        if (stepIndex >= 0) {
          const nextStep = steps[stepIndex + 1];
          if (value < legendFilter || (nextStep !== undefined && value >= nextStep)) {
            return 'rgba(46, 52, 64, 0.3)'; // Dimmed
          }
        }
      }
      return colorScale(value);
    };

    // Draw metropolitan departments
    g.selectAll('.department')
      .data(metropole)
      .enter()
      .append('path')
      .attr('class', 'department')
      .attr('d', path as any)
      .attr('fill', d => getDeptColor(d.properties.code))
      .attr('stroke', d => d.properties.code === selectedDepartment ? COLORS.selected : COLORS.stroke)
      .attr('stroke-width', d => d.properties.code === selectedDepartment ? 2 : 0.5)
      .style('cursor', 'pointer')
      .style('transition', 'fill 0.2s ease, stroke-width 0.2s ease')
      .on('mouseenter', function(event, d) {
        if (d.properties.code !== selectedDepartment) {
          d3.select(this)
            .attr('fill', COLORS.hover)
            .attr('stroke-width', 1.5);
        }

        const metrics = getMetrics(d.properties.code);
        const rect = container.getBoundingClientRect();
        const indicatorValue = metrics ? indicator.getValue(metrics) : null;
        setTooltip({
          x: event.clientX - rect.left,
          y: event.clientY - rect.top - 10,
          content: `${d.properties.code} - ${d.properties.nom}${
            metrics ? `\n${indicator.label}: ${indicator.format(indicatorValue!)}\nEntreprises: ${metrics.enterprises.toLocaleString()}` : ''
          }`
        });
      })
      .on('mouseleave', function(event, d) {
        if (d.properties.code !== selectedDepartment) {
          d3.select(this)
            .attr('fill', getDeptColor(d.properties.code))
            .attr('stroke-width', 0.5);
        }
        setTooltip(null);
      })
      .on('click', function(event, d) {
        const newSelection = d.properties.code === selectedDepartment ? null : d.properties.code;
        setSelectedDepartment(newSelection);
        onSelect?.(newSelection);
      });

    // Draw DOM-TOM in bottom right corner
    const domWidth = width * 0.15;
    const domHeight = height * 0.12;
    const domStartX = width * 0.75;
    const domStartY = height * 0.65;

    dom.forEach((dept, i) => {
      const row = Math.floor(i / 3);
      const col = i % 3;
      const x = domStartX + col * (domWidth + 5);
      const y = domStartY + row * (domHeight + 5);

      // Mini projection for each DOM
      const domProjection = d3.geoMercator()
        .fitSize([domWidth, domHeight], dept);
      const domPath = d3.geoPath().projection(domProjection);

      const domGroup = g.append('g')
        .attr('transform', `translate(${x}, ${y})`);

      // Background
      domGroup.append('rect')
        .attr('width', domWidth)
        .attr('height', domHeight)
        .attr('fill', 'rgba(46, 52, 64, 0.5)')
        .attr('rx', 4);

      // Department shape
      domGroup.append('path')
        .datum(dept)
        .attr('d', domPath as any)
        .attr('fill', () => getDeptColor(dept.properties.code))
        .attr('stroke', COLORS.stroke)
        .attr('stroke-width', 0.5)
        .style('cursor', 'pointer')
        .on('mouseenter', function(event) {
          d3.select(this).attr('fill', COLORS.hover);
          const metrics = getMetrics(dept.properties.code);
          const indicatorValue = metrics ? indicator.getValue(metrics) : null;
          const rect = container.getBoundingClientRect();
          setTooltip({
            x: event.clientX - rect.left,
            y: event.clientY - rect.top - 10,
            content: `${dept.properties.code} - ${dept.properties.nom}${
              metrics ? `\n${indicator.label}: ${indicator.format(indicatorValue!)}` : ''
            }`
          });
        })
        .on('mouseleave', function() {
          d3.select(this).attr('fill', getDeptColor(dept.properties.code));
          setTooltip(null);
        })
        .on('click', function() {
          const newSelection = dept.properties.code === selectedDepartment ? null : dept.properties.code;
          setSelectedDepartment(newSelection);
          onSelect?.(newSelection);
        });

      // Label
      domGroup.append('text')
        .attr('x', domWidth / 2)
        .attr('y', domHeight - 4)
        .attr('text-anchor', 'middle')
        .attr('fill', 'hsl(var(--foreground))')
        .attr('font-size', '8px')
        .text(dept.properties.code);
    });

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setZoomLevel(event.transform.k);
      });

    zoomRef.current = zoom;
    svg.call(zoom);

  }, [geoData, data, selectedDepartment, colorScale, getMetrics, setSelectedDepartment, onSelect, indicator, legendFilter]);

  // Get selected department metrics
  const selectedMetrics = useMemo(() => {
    if (!selectedDepartment) return null;
    return data.find(d => d.code === selectedDepartment);
  }, [selectedDepartment, data]);

  // Get department name from geoData
  const selectedDeptName = useMemo(() => {
    if (!selectedDepartment || !geoData) return '';
    const dept = geoData.find(d => d.properties.code === selectedDepartment);
    return dept?.properties.nom || '';
  }, [selectedDepartment, geoData]);

  return (
    <div ref={containerRef} className={`relative w-full h-full min-h-[300px] sm:min-h-[400px] ${className}`}>
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ background: 'transparent' }}
      />

      {/* Tooltip */}
      <AnimatePresence>
        {tooltip && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="absolute pointer-events-none z-50 px-2 sm:px-3 py-1.5 sm:py-2 text-[10px] sm:text-xs glass rounded-lg shadow-lg whitespace-pre-line"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: 'translate(-50%, -100%)',
            }}
          >
            {tooltip.content}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Indicator Selector moved to external header - controlled via props */}

      {/* Zoom Controls - Bottom Right */}
      <div className="absolute bottom-2 sm:bottom-4 right-2 sm:right-4 z-10">
        <div className="glass rounded-lg p-1 flex flex-col gap-1">
          <button
            onClick={handleZoomIn}
            className="p-1.5 hover:bg-muted/50 rounded-md transition-colors"
            title="Zoom avant"
          >
            <HiOutlineMagnifyingGlassPlus className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 hover:bg-muted/50 rounded-md transition-colors"
            title="Zoom arrière"
          >
            <HiOutlineMagnifyingGlassMinus className="w-4 h-4" />
          </button>
          <div className="w-full h-px bg-border/50" />
          <button
            onClick={handleZoomReset}
            className="p-1.5 hover:bg-muted/50 rounded-md transition-colors"
            title="Réinitialiser"
          >
            <HiOutlineArrowPath className="w-4 h-4" />
          </button>
          <span className="text-[9px] text-center text-muted-foreground">
            {Math.round(zoomLevel * 100)}%
          </span>
        </div>
      </div>

      {/* Interactive Legend - Bottom Left */}
      <div className="absolute bottom-2 sm:bottom-4 left-2 sm:left-4 mt-14 z-10">
        <div className="glass rounded-lg px-2 sm:px-3 py-1.5 sm:py-2">
          <div className="flex items-center gap-1 mb-1.5">
            {indicator.icon}
            <span className="text-[10px] sm:text-xs text-muted-foreground">{indicator.label}</span>
            {legendFilter !== null && (
              <button
                onClick={() => setLegendFilter(null)}
                className="ml-1 text-[9px] text-[var(--chart-1)] hover:underline"
              >
                ×
              </button>
            )}
          </div>
          <div className="flex items-center gap-0.5">
            {indicator.legendSteps.map((step, idx) => {
              const isFiltered = legendFilter === step;
              const nextStep = indicator.legendSteps[idx + 1];
              const color = indicator.colorScale(step, minValue, maxValue);
              return (
                <button
                  key={step}
                  onClick={() => setLegendFilter(isFiltered ? null : step)}
                  className={`flex flex-col items-center transition-all ${
                    isFiltered ? 'scale-110' : 'hover:scale-105'
                  }`}
                  title={nextStep !== undefined ? `${step} à ${nextStep}${indicator.unit}` : `>${step}${indicator.unit}`}
                >
                  <div
                    className={`w-4 sm:w-5 h-3 sm:h-4 rounded-sm ${isFiltered ? 'ring-2 ring-[var(--chart-1)]' : ''}`}
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-[8px] sm:text-[9px] text-muted-foreground mt-0.5">
                    {activeIndicator === 'enterprises' ? `${Math.round(step / 1000)}k` : step}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* KPI Panel for selected department - Draggable & Minimizable */}
      <AnimatePresence>
        {selectedDepartment && !panelMinimized && (
          <Draggable
            handle=".drag-handle"
            bounds="parent"
            position={panelPosition}
            onStop={(e, data) => setPanelPosition({ x: data.x, y: data.y })}
            nodeRef={panelRef}
          >
            <motion.div
              ref={panelRef}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              className="absolute top-2 sm:top-4 right-2 sm:right-4 glass rounded-lg shadow-lg overflow-hidden w-[160px] sm:w-[200px] z-20"
            >
              {/* Drag Handle Header */}
              <div className="drag-handle flex items-center justify-between px-2 sm:px-3 py-1.5 sm:py-2 border-b border-border/50 cursor-move select-none bg-muted/20 hover:bg-muted/30 transition-colors">
                <div className="flex items-center gap-1.5">
                  <HiOutlineArrowsPointingOut className="w-3 h-3 text-muted-foreground/60" />
                  <div>
                    <span className="text-xs sm:text-sm font-medium" style={{ color: COLORS.selected }}>
                      {selectedDepartment}
                    </span>
                    <p className="text-[9px] sm:text-[10px] text-muted-foreground truncate max-w-[90px] sm:max-w-[120px]">
                      {selectedDeptName}
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPanelMinimized(true);
                  }}
                  className="p-1 hover:bg-muted/50 rounded-md transition-colors cursor-pointer"
                  title="Minimiser"
                >
                  <HiOutlineXMark className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-muted-foreground" />
                </button>
              </div>

            {/* KPIs */}
            {selectedMetrics ? (
              <div className="p-2 sm:p-3 space-y-2 sm:space-y-2.5">
                {/* Enterprises with national comparison */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="p-1 sm:p-1.5 rounded-md bg-[var(--chart-1)]/20">
                      <HiOutlineBuildingOffice2 className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-[var(--chart-1)]" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[9px] sm:text-[10px] text-muted-foreground">Entreprises</p>
                      <p className="text-xs sm:text-sm font-medium">{selectedMetrics.enterprises.toLocaleString()}</p>
                    </div>
                  </div>
                  {nationalStats && (
                    <div className="ml-7 sm:ml-8">
                      <div className="h-1 bg-muted/30 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[var(--chart-1)]/60 rounded-full"
                          style={{ width: `${Math.min(100, (selectedMetrics.enterprises / nationalStats.avgEnterprises) * 50)}%` }}
                        />
                      </div>
                      <p className="text-[8px] sm:text-[9px] text-muted-foreground mt-0.5">
                        {selectedMetrics.enterprises > nationalStats.avgEnterprises ? '+' : ''}
                        {Math.round(((selectedMetrics.enterprises / nationalStats.avgEnterprises) - 1) * 100)}% vs moy.
                      </p>
                    </div>
                  )}
                </div>

                {/* Growth with national comparison */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className={`p-1 sm:p-1.5 rounded-md ${selectedMetrics.growth >= 0 ? 'bg-[var(--success)]/20' : 'bg-[var(--error)]/20'}`}>
                      <HiOutlineArrowTrendingUp className={`w-3 sm:w-3.5 h-3 sm:h-3.5 ${selectedMetrics.growth >= 0 ? 'text-[var(--success)]' : 'text-[var(--error)]'}`} />
                    </div>
                    <div className="flex-1">
                      <p className="text-[9px] sm:text-[10px] text-muted-foreground">Croissance</p>
                      <p className={`text-xs sm:text-sm font-medium ${selectedMetrics.growth >= 0 ? 'text-[var(--success)]' : 'text-[var(--error)]'}`}>
                        {selectedMetrics.growth > 0 ? '+' : ''}{selectedMetrics.growth.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  {nationalStats && (
                    <div className="ml-7 sm:ml-8">
                      <p className="text-[8px] sm:text-[9px] text-muted-foreground">
                        Moy. nationale: {nationalStats.avgGrowth > 0 ? '+' : ''}{nationalStats.avgGrowth.toFixed(1)}%
                      </p>
                    </div>
                  )}
                </div>

                {/* Analyses */}
                <div className="flex items-center gap-2">
                  <div className="p-1 sm:p-1.5 rounded-md bg-[var(--chart-4)]/20">
                    <HiOutlineChartBar className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-[var(--chart-4)]" />
                  </div>
                  <div>
                    <p className="text-[9px] sm:text-[10px] text-muted-foreground">Analyses TAJINE</p>
                    <p className="text-xs sm:text-sm font-medium">{selectedMetrics.analyses}</p>
                  </div>
                </div>

                {/* Dynamism badge */}
                <div className="pt-1 sm:pt-2 border-t border-border/30">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] sm:text-[10px] text-muted-foreground">Dynamisme</span>
                    <span
                      className={`text-[9px] sm:text-[10px] px-2 py-0.5 rounded-full font-medium ${
                        selectedMetrics.growth >= 2
                          ? 'bg-[var(--success)]/20 text-[var(--success)]'
                          : selectedMetrics.growth >= 0
                          ? 'bg-[var(--warning)]/20 text-[var(--warning)]'
                          : 'bg-[var(--error)]/20 text-[var(--error)]'
                      }`}
                    >
                      {selectedMetrics.growth >= 2 ? 'Dynamique' : selectedMetrics.growth >= 0 ? 'Stable' : 'Déclin'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-2 sm:p-3 text-center text-[10px] sm:text-xs text-muted-foreground">
                Pas de données disponibles
              </div>
            )}
            </motion.div>
          </Draggable>
        )}
      </AnimatePresence>

      {/* Minimized panel button - shows when panel is minimized but department selected */}
      <AnimatePresence>
        {selectedDepartment && panelMinimized && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={() => setPanelMinimized(false)}
            className="absolute top-2 sm:top-4 right-2 sm:right-4 glass rounded-lg px-2 sm:px-3 py-1.5 sm:py-2 flex items-center gap-2 hover:bg-muted/50 transition-colors z-10"
            title="Ouvrir le panneau détails"
          >
            <span className="text-xs sm:text-sm font-medium" style={{ color: COLORS.selected }}>
              {selectedDepartment}
            </span>
            <HiOutlineChartBar className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-muted-foreground" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
