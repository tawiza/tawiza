'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineChartBar } from 'react-icons/hi2';

// Nord colors
const COLORS = {
  area: 'var(--chart-1)',      // nord8
  areaFill: 'rgba(136, 192, 208, 0.3)',
  median: 'var(--success)',    // nord14
  p5: 'var(--error)',        // nord11
  p95: 'var(--success)',       // nord14
  grid: 'hsl(var(--border))',
  text: 'hsl(var(--foreground))',
};

interface HistogramBin {
  bin: number;
  count: number;
  cumulative?: number;
}

interface MonteCarloChartProps {
  data?: HistogramBin[];
  percentile5?: number;
  percentile50?: number;
  percentile95?: number;
  isLoading?: boolean;
}

// Custom tooltip
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  return (
    <div className="glass px-3 py-2 rounded-lg text-sm">
      <p className="font-medium">Croissance: {data.bin.toFixed(1)}%</p>
      <p className="text-muted-foreground">Frequence: {Math.round(data.count)}</p>
    </div>
  );
}

export default function MonteCarloChart({
  data,
  percentile5,
  percentile50,
  percentile95,
  isLoading,
}: MonteCarloChartProps) {
  const { selectedDepartment } = useTAJINE();

  const chartData = useMemo(() => {
    if (data && data.length > 0) return data;
    return [];
  }, [data]);

  const hasData = chartData.length > 0;
  const p5 = percentile5 ?? 0;
  const p50 = percentile50 ?? 0;
  const p95 = percentile95 ?? 0;

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
        <HiOutlineChartBar className="w-10 h-10 sm:w-12 sm:h-12 mb-3 opacity-30" />
        <p className="text-xs sm:text-sm">Aucune donnee disponible</p>
        <p className="text-[10px] sm:text-xs mt-1">Lancez une simulation Monte Carlo</p>
      </div>
    );
  }

  return (
    <div className="h-[220px] sm:h-[280px] md:h-[350px] w-full">
      <ResponsiveContainer width="100%" height="85%">
        <AreaChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} opacity={0.3} />
          <XAxis
            dataKey="bin"
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickFormatter={(value) => `${value}%`}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickFormatter={(value) => value.toFixed(0)}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Percentile reference lines - use nearest bin for alignment */}
          <ReferenceLine
            x={Math.round(p5)}
            stroke={COLORS.p5}
            strokeDasharray="5 5"
            strokeWidth={1.5}
            label={{ value: `P5: ${p5.toFixed(1)}%`, fill: COLORS.p5, fontSize: 9, position: 'top' }}
          />
          <ReferenceLine
            x={Math.round(p50)}
            stroke={COLORS.median}
            strokeWidth={2.5}
            label={{ value: `Méd: ${p50.toFixed(1)}%`, fill: COLORS.median, fontSize: 9, position: 'top' }}
          />
          <ReferenceLine
            x={Math.round(p95)}
            stroke={COLORS.p95}
            strokeDasharray="5 5"
            strokeWidth={1.5}
            label={{ value: `P95: ${p95.toFixed(1)}%`, fill: COLORS.p95, fontSize: 9, position: 'top' }}
          />

          <Area
            type="monotone"
            dataKey="count"
            stroke={COLORS.area}
            fill={COLORS.areaFill}
            strokeWidth={2}
            animationDuration={1000}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend - responsive */}
      <div className="flex flex-wrap justify-center gap-3 sm:gap-6 mt-1 text-[10px] sm:text-xs">
        <span className="flex items-center gap-1">
          <div className="w-2 sm:w-3 h-0.5" style={{ backgroundColor: COLORS.p5 }} />
          P5: {p5.toFixed(1)}%
        </span>
        <span className="flex items-center gap-1">
          <div className="w-2 sm:w-3 h-0.5" style={{ backgroundColor: COLORS.median }} />
          Med: {p50.toFixed(1)}%
        </span>
        <span className="flex items-center gap-1">
          <div className="w-2 sm:w-3 h-0.5" style={{ backgroundColor: COLORS.p95 }} />
          P95: {p95.toFixed(1)}%
        </span>
      </div>

      {selectedDepartment && (
        <p className="text-center text-[10px] sm:text-xs text-muted-foreground mt-1">
          Simulation 1000 iterations - Dept. {selectedDepartment}
        </p>
      )}
    </div>
  );
}
