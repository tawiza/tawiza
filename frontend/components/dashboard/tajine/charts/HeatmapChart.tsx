'use client';

import { useMemo, useState } from 'react';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineSparkles } from 'react-icons/hi2';

// Color scale from low (blue) to high (red) via Nord palette
const COLOR_SCALE = [
  'var(--chart-3)', // nord10 - dark blue (low)
  'var(--chart-2)', // nord9 - blue
  'var(--chart-1)', // nord8 - cyan
  'var(--chart-1)', // nord7 - teal
  'var(--success)', // nord14 - green
  'var(--warning)', // nord13 - yellow
  'var(--chart-5)', // nord12 - orange
  'var(--error)', // nord11 - red (high)
];

const COLORS = {
  text: 'hsl(var(--foreground))',
  textDark: 'hsl(var(--background))',
  border: 'hsl(var(--border))',
  background: 'rgba(46, 52, 64, 0.3)',
};

interface HeatmapCell {
  x: string;  // Column label (e.g., month or sector)
  y: string;  // Row label (e.g., department or metric)
  value: number;
  label?: string;
}

interface HeatmapChartProps {
  data?: HeatmapCell[];
  xLabels?: string[];
  yLabels?: string[];
  valueLabel?: string;
  isLoading?: boolean;
  /** Use live data from context analysis when available */
  useLiveData?: boolean;
}


// Get color from value (0-100 scale)
function getColor(value: number, min: number, max: number): string {
  const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const index = Math.floor(normalized * (COLOR_SCALE.length - 1));
  return COLOR_SCALE[index];
}

// Get contrasting text color
function getTextColor(value: number, min: number, max: number): string {
  const normalized = (value - min) / (max - min);
  return normalized > 0.5 ? COLORS.textDark : COLORS.text;
}

export default function HeatmapChart({
  data,
  xLabels,
  yLabels,
  valueLabel = 'Indice activite',
  isLoading,
  useLiveData = true,
}: HeatmapChartProps) {
  const { selectedDepartment, latestAnalysis } = useTAJINE();
  const [hoveredCell, setHoveredCell] = useState<HeatmapCell | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Check if we have live analysis data
  const liveAnalysis = useMemo(() => {
    if (!useLiveData || !latestAnalysis?.heatmapData?.data) return null;
    if (selectedDepartment && latestAnalysis.department !== selectedDepartment) return null;
    return latestAnalysis.heatmapData;
  }, [useLiveData, latestAnalysis, selectedDepartment]);

  const liveData = liveAnalysis?.data;
  const isUsingLiveData = !!liveData;

  const chartData = useMemo(() => {
    if (liveData && liveData.length > 0) return liveData;
    if (data && data.length > 0) return data;
    return [];
  }, [liveData, data]);

  const hasData = chartData.length > 0;

  // Extract labels from data if not provided (prioritize live analysis labels)
  const xAxisLabels = useMemo(() => {
    if (liveAnalysis?.xLabels && liveAnalysis.xLabels.length > 0) return liveAnalysis.xLabels;
    if (xLabels && xLabels.length > 0) return xLabels;
    if (chartData.length > 0) {
      return [...new Set(chartData.map(d => d.x))];
    }
    return [];
  }, [liveAnalysis, xLabels, chartData]);

  const yAxisLabels = useMemo(() => {
    if (liveAnalysis?.yLabels && liveAnalysis.yLabels.length > 0) return liveAnalysis.yLabels;
    if (yLabels && yLabels.length > 0) return yLabels;
    if (chartData.length > 0) {
      return [...new Set(chartData.map(d => d.y))];
    }
    return [];
  }, [liveAnalysis, yLabels, chartData]);

  const { minValue, maxValue } = useMemo(() => {
    const values = chartData.map(d => d.value);
    return {
      minValue: Math.min(...values),
      maxValue: Math.max(...values),
    };
  }, [chartData]);

  // Create a lookup map for quick access
  const dataMap = useMemo(() => {
    const map = new Map<string, HeatmapCell>();
    chartData.forEach(cell => {
      map.set(`${cell.x}-${cell.y}`, cell);
    });
    return map;
  }, [chartData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[220px] sm:h-[280px] md:h-[350px]">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="flex flex-col items-center justify-center h-[220px] sm:h-[280px] md:h-[350px] text-muted-foreground">
        <HiOutlineSparkles className="w-10 h-10 sm:w-12 sm:h-12 mb-3 opacity-30" />
        <p className="text-xs sm:text-sm text-center px-4">Aucune donnee disponible</p>
        <p className="text-[10px] sm:text-xs mt-1 text-center px-4">Lancez une analyse pour visualiser la heatmap</p>
      </div>
    );
  }

  const cellWidth = 100 / xAxisLabels.length;
  const cellHeight = 100 / yAxisLabels.length;

  return (
    <div className="h-[220px] sm:h-[280px] md:h-[350px] w-full relative overflow-hidden">
      {/* Live data indicator */}
      {isUsingLiveData && (
        <div className="absolute top-0 right-0 flex items-center gap-1 px-2 py-1 glass rounded-lg text-xs z-10">
          <HiOutlineSparkles className="w-3 h-3 text-[var(--success)] animate-pulse" />
          <span className="text-[var(--success)]">Live</span>
        </div>
      )}
      {/* Main grid container */}
      <div className="flex h-full overflow-hidden">
        {/* Y-axis labels */}
        <div className="flex flex-col justify-around w-16 sm:w-20 pr-1 sm:pr-2 text-right text-[10px] sm:text-xs shrink-0">
          {yAxisLabels.map(label => (
            <div key={label} className="text-muted-foreground truncate">
              {label}
            </div>
          ))}
        </div>

        {/* Heatmap grid */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Grid cells */}
          <div className="flex-1 relative min-h-0 overflow-hidden">
            <svg
              viewBox={`0 0 ${Math.max(xAxisLabels.length, 1) * 50} ${Math.max(yAxisLabels.length, 1) * 40}`}
              preserveAspectRatio="none"
              className="w-full h-full"
            >
              {yAxisLabels.map((yLabel, yIdx) =>
                xAxisLabels.map((xLabel, xIdx) => {
                  const cell = dataMap.get(`${xLabel}-${yLabel}`);
                  const value = cell?.value ?? 0;
                  const color = getColor(value, minValue, maxValue);
                  const textColor = getTextColor(value, minValue, maxValue);

                  return (
                    <g key={`${xLabel}-${yLabel}`}>
                      <rect
                        x={xIdx * 50 + 1}
                        y={yIdx * 40 + 1}
                        width={48}
                        height={38}
                        fill={color}
                        rx={4}
                        className="cursor-pointer transition-all duration-150 hover:opacity-80"
                        stroke={hoveredCell?.x === xLabel && hoveredCell?.y === yLabel ? COLORS.text : 'transparent'}
                        strokeWidth={2}
                        onMouseEnter={(e) => {
                          setHoveredCell(cell || null);
                          const rect = e.currentTarget.getBoundingClientRect();
                          setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
                        }}
                        onMouseLeave={() => setHoveredCell(null)}
                      />
                      <text
                        x={xIdx * 50 + 25}
                        y={yIdx * 40 + 24}
                        textAnchor="middle"
                        fill={textColor}
                        fontSize="11"
                        fontWeight="500"
                        pointerEvents="none"
                      >
                        {value.toFixed(0)}
                      </text>
                    </g>
                  );
                })
              )}
            </svg>
          </div>

          {/* X-axis labels */}
          <div className="flex justify-around h-6 text-xs text-muted-foreground">
            {xAxisLabels.map(label => (
              <div key={label} className="text-center">
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tooltip */}
      {hoveredCell && (
        <div
          className="fixed z-50 glass px-3 py-2 rounded-lg text-sm pointer-events-none"
          style={{
            left: tooltipPos.x,
            top: tooltipPos.y - 10,
            transform: 'translate(-50%, -100%)',
          }}
        >
          <p className="font-medium">{hoveredCell.y}</p>
          <p className="text-muted-foreground">{hoveredCell.x}</p>
          <p style={{ color: getColor(hoveredCell.value, minValue, maxValue) }}>
            {valueLabel}: {hoveredCell.value.toFixed(1)}
          </p>
        </div>
      )}

      {/* Color legend */}
      <div className="flex items-center justify-center gap-2 mt-1">
        <span className="text-[10px] sm:text-xs text-muted-foreground">Faible</span>
        <div className="flex h-2.5 rounded overflow-hidden">
          {COLOR_SCALE.map((color, idx) => (
            <div
              key={idx}
              className="w-4 h-full"
              style={{ backgroundColor: color }}
            />
          ))}
        </div>
        <span className="text-[10px] sm:text-xs text-muted-foreground">Eleve</span>
      </div>

      {selectedDepartment && (
        <p className="text-center text-[10px] sm:text-xs text-muted-foreground mt-1">
          Dept. {selectedDepartment}
        </p>
      )}
    </div>
  );
}
