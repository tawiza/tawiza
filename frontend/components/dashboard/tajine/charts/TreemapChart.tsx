'use client';

import { useMemo, useState, useCallback } from 'react';
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineSparkles } from 'react-icons/hi2';

// Nord Aurora palette for sectors
const SECTOR_COLORS = [
  'var(--chart-1)', // nord8 - cyan
  'var(--chart-2)', // nord9 - blue
  'var(--success)', // nord14 - green
  'var(--warning)', // nord13 - yellow
  'var(--chart-5)', // nord12 - orange
  'var(--chart-4)', // nord15 - purple
  '#8fbcbb',        // nord7 - teal (distinct from chart-1)
  'var(--chart-3)', // nord10 - dark blue
  'var(--error)',    // nord11 - red
];

const COLORS = {
  text: 'hsl(var(--foreground))',
  textDark: 'hsl(var(--background))',
  border: 'hsl(var(--border))',
};

interface TreemapNode {
  name: string;
  size?: number;
  children?: TreemapNode[];
  color?: string;
  growth?: number;
}

interface TreemapChartProps {
  data?: TreemapNode[];
  isLoading?: boolean;
  /** Use live data from context analysis when available */
  useLiveData?: boolean;
}


// Custom content renderer for treemap cells
function CustomizedContent(props: any) {
  const { x, y, width, height, name, size, growth, depth, _colorIdx } = props;

  // Skip root node
  if (depth === 0) return null;

  // Use injected color index from parent sector
  const bgColor = SECTOR_COLORS[(_colorIdx ?? 0) % SECTOR_COLORS.length];
  const opacity = depth === 1 ? 1 : 0.8;

  // Determine text color based on background
  const textColor = COLORS.textDark;

  // Only show text if cell is big enough
  const showName = width > 40 && height > 25;
  const showSize = width > 60 && height > 40;
  const showGrowth = width > 80 && height > 55 && growth !== undefined;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={bgColor}
        fillOpacity={opacity}
        stroke={COLORS.border}
        strokeWidth={depth === 1 ? 2 : 1}
        rx={4}
        style={{ cursor: 'pointer' }}
      />
      {showName && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showSize ? 8 : 0)}
          textAnchor="middle"
          fill={textColor}
          fontSize={depth === 1 ? 12 : 10}
          fontWeight={depth === 1 ? 600 : 400}
        >
          {name}
        </text>
      )}
      {showSize && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 8}
          textAnchor="middle"
          fill={textColor}
          fontSize={9}
          opacity={0.8}
        >
          {(size / 1000).toFixed(1)}k
        </text>
      )}
      {showGrowth && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 20}
          textAnchor="middle"
          fill={growth >= 0 ? 'var(--success)' : 'var(--error)'}
          fontSize={9}
          fontWeight={500}
        >
          {growth > 0 ? '+' : ''}{growth.toFixed(1)}%
        </text>
      )}
    </g>
  );
}

// Custom tooltip
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  if (!data.name || data.name === 'Secteurs') return null;

  return (
    <div className="glass px-3 py-2 rounded-lg text-sm z-50">
      <p className="font-medium mb-1">{data.name}</p>
      {data.size && (
        <p className="text-muted-foreground">
          Entreprises: {data.size.toLocaleString()}
        </p>
      )}
      {data.growth !== undefined && (
        <p style={{ color: data.growth >= 0 ? 'var(--success)' : 'var(--error)' }}>
          Croissance: {data.growth > 0 ? '+' : ''}{data.growth.toFixed(1)}%
        </p>
      )}
    </div>
  );
}

export default function TreemapChart({ data, isLoading, useLiveData = true }: TreemapChartProps) {
  const { selectedDepartment, latestAnalysis } = useTAJINE();
  const [activeNode, setActiveNode] = useState<string | null>(null);

  // Check if we have live analysis data
  const liveData = useMemo(() => {
    if (!useLiveData || !latestAnalysis?.treemapData) return null;
    if (selectedDepartment && latestAnalysis.department !== selectedDepartment) return null;
    return latestAnalysis.treemapData;
  }, [useLiveData, latestAnalysis, selectedDepartment]);

  const isUsingLiveData = !!liveData;

  const rawData = useMemo(() => {
    if (liveData && liveData.length > 0) return liveData;
    if (data && data.length > 0) return data;
    return [];
  }, [liveData, data]);

  // Inject _colorIdx into each node so children inherit parent sector color
  const chartData = useMemo(() => {
    return rawData.map((root: TreemapNode) => ({
      ...root,
      children: root.children?.map((sector, sectorIdx) => ({
        ...sector,
        _colorIdx: sectorIdx,
        children: sector.children?.map(leaf => ({
          ...leaf,
          _colorIdx: sectorIdx,
        })),
      })),
    }));
  }, [rawData]);

  const hasData = chartData.length > 0;

  const handleClick = useCallback((node: any) => {
    if (node && node.name) {
      setActiveNode(activeNode === node.name ? null : node.name);
    }
  }, [activeNode]);

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
        <p className="text-[10px] sm:text-xs mt-1 text-center px-4">Lancez une analyse pour visualiser la repartition</p>
      </div>
    );
  }

  return (
    <div className="h-[220px] sm:h-[280px] md:h-[350px] w-full relative">
      {/* Live data indicator */}
      {isUsingLiveData && (
        <div className="absolute top-0 right-0 flex items-center gap-1 px-2 py-1 glass rounded-lg text-xs z-10">
          <HiOutlineSparkles className="w-3 h-3 text-[var(--success)] animate-pulse" />
          <span className="text-[var(--success)]">Live</span>
        </div>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={chartData}
          dataKey="size"
          aspectRatio={4 / 3}
          stroke={COLORS.border}
          fill="var(--chart-3)"
          content={<CustomizedContent />}
          onClick={handleClick}
          animationDuration={300}
          isAnimationActive={true}
        >
          <Tooltip content={<CustomTooltip />} />
        </Treemap>
      </ResponsiveContainer>

      {/* Dynamic Legend based on data */}
      {chartData[0]?.children && (
        <div className="flex flex-wrap justify-center gap-3 mt-3 text-xs">
          {chartData[0].children.slice(0, 6).map((sector: TreemapNode, idx: number) => (
            <span key={sector.name} className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: SECTOR_COLORS[idx % SECTOR_COLORS.length] }}
              />
              {sector.name}
            </span>
          ))}
        </div>
      )}

      {selectedDepartment && (
        <p className="text-center text-xs text-muted-foreground mt-2">
          Repartition sectorielle hierarchique - Departement {selectedDepartment}
        </p>
      )}
    </div>
  );
}
