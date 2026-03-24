'use client';

import { useMemo } from 'react';
import {
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineSparkles } from 'react-icons/hi2';

// Nord color palette
const COLORS = {
  primary: 'var(--chart-1)',     // nord8 - cyan
  secondary: 'var(--chart-2)',   // nord9 - blue
  tertiary: 'var(--success)',    // nord14 - green
  quaternary: 'var(--warning)',  // nord13 - yellow
  grid: 'hsl(var(--border))',        // nord3
  text: 'hsl(var(--foreground))',        // nord6
  background: 'rgba(46, 52, 64, 0.5)',
  live: 'var(--success)',        // nord14 - green for live indicator
};

interface MetricData {
  metric: string;
  value: number;
  fullMark: number;
  benchmark?: number;
}

interface RadarChartProps {
  data?: MetricData[];
  showBenchmark?: boolean;
  isLoading?: boolean;
  /** Use live data from context analysis when available */
  useLiveData?: boolean;
}


// Custom tooltip
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  return (
    <div className="glass px-3 py-2 rounded-lg text-sm">
      <p className="font-medium mb-1">{data.metric}</p>
      <p style={{ color: COLORS.primary }}>
        Departement: {data.value}%
      </p>
      {data.benchmark !== undefined && (
        <p style={{ color: COLORS.tertiary }}>
          Moyenne France: {data.benchmark}%
        </p>
      )}
    </div>
  );
}

export default function RadarChart({ data, showBenchmark = true, isLoading, useLiveData = true }: RadarChartProps) {
  const { selectedDepartment, latestAnalysis } = useTAJINE();

  // Check if we have live analysis data that matches the current department
  const liveData = useMemo(() => {
    if (!useLiveData || !latestAnalysis?.radarData) return null;
    if (selectedDepartment && latestAnalysis.department !== selectedDepartment) return null;
    // Transform context data to match MetricData interface
    return latestAnalysis.radarData.map(item => ({
      metric: item.metric,
      value: item.value,
      fullMark: 100,
      benchmark: item.benchmark,
    }));
  }, [useLiveData, latestAnalysis, selectedDepartment]);

  const isUsingLiveData = !!liveData;

  const chartData = useMemo(() => {
    // Priority: live analysis data > API data
    if (liveData && liveData.length > 0) return liveData;
    if (data && data.length > 0) return data;
    return [];
  }, [liveData, data]);

  const hasData = chartData.length > 0;

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
        <p className="text-[10px] sm:text-xs mt-1 text-center px-4">Lancez une analyse pour visualiser les metriques</p>
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
        <RechartsRadarChart data={chartData} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
          <PolarGrid stroke={COLORS.grid} strokeOpacity={0.5} />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: COLORS.text, fontSize: 11 }}
            tickLine={{ stroke: COLORS.grid }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickCount={5}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Benchmark radar (national average) */}
          {showBenchmark && (
            <Radar
              name="Moyenne France"
              dataKey="benchmark"
              stroke={COLORS.tertiary}
              fill={COLORS.tertiary}
              fillOpacity={0.2}
              strokeWidth={1}
              strokeDasharray="5 5"
              animationDuration={1200}
              animationEasing="ease-out"
            />
          )}

          {/* Department radar */}
          <Radar
            name={selectedDepartment ? `Dept. ${selectedDepartment}` : 'Departement'}
            dataKey="value"
            stroke={COLORS.primary}
            fill={COLORS.primary}
            fillOpacity={0.4}
            strokeWidth={2}
            dot={{ fill: COLORS.primary, r: 3 }}
            activeDot={{ r: 5, fill: COLORS.secondary }}
            animationDuration={800}
            animationEasing="ease-out"
          />

          <Legend
            wrapperStyle={{ paddingTop: 10, fontSize: 11 }}
            formatter={(value) => (
              <span style={{ color: COLORS.text }}>{value}</span>
            )}
          />
        </RechartsRadarChart>
      </ResponsiveContainer>

      {selectedDepartment && (
        <p className="text-center text-xs text-muted-foreground mt-2">
          Indicateurs territoriaux - Departement {selectedDepartment} vs Moyenne nationale
        </p>
      )}
    </div>
  );
}
