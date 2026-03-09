'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineChartBar } from 'react-icons/hi2';

// Nord color palette
const COLORS = {
  primary: 'var(--chart-1)',   // nord8 - cyan
  secondary: 'var(--chart-2)', // nord9 - blue
  tertiary: 'var(--chart-3)',  // nord10 - dark blue
  positive: 'var(--success)',  // nord14 - green
  negative: 'var(--error)',  // nord11 - red
  grid: 'hsl(var(--border))',      // nord3
  text: 'hsl(var(--foreground))',      // nord6
};

interface DataPoint {
  date: string;
  value: number;
  department?: string;
}

interface GrowthLineChartProps {
  data?: DataPoint[];
  isLoading?: boolean;
}

// Custom tooltip
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="glass px-3 py-2 rounded-lg text-sm">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((entry: any, index: number) => (
        <p key={index} style={{ color: entry.color }}>
          Croissance: {entry.value > 0 ? '+' : ''}{entry.value.toFixed(1)}%
        </p>
      ))}
    </div>
  );
}

export default function GrowthLineChart({ data, isLoading }: GrowthLineChartProps) {
  const { selectedDepartment } = useTAJINE();

  const chartData = useMemo(() => {
    if (data && data.length > 0) return data;
    return [];
  }, [data]);

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
        <HiOutlineChartBar className="w-10 h-10 sm:w-12 sm:h-12 mb-3 opacity-30" />
        <p className="text-xs sm:text-sm">Aucune donnee disponible</p>
        <p className="text-[10px] sm:text-xs mt-1">Selectionnez un departement</p>
      </div>
    );
  }

  return (
    <div className="h-[220px] sm:h-[280px] md:h-[350px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} opacity={0.3} />
          <XAxis
            dataKey="date"
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickLine={{ stroke: COLORS.grid }}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickLine={{ stroke: COLORS.grid }}
            tickFormatter={(value) => `${value}%`}
            width={45}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: 10, fontSize: 11 }}
            formatter={(value) => (
              <span style={{ color: COLORS.text }}>{value}</span>
            )}
          />
          <Line
            type="monotone"
            dataKey="value"
            name={selectedDepartment ? `Dept. ${selectedDepartment}` : 'France'}
            stroke={COLORS.primary}
            strokeWidth={2}
            dot={{ fill: COLORS.primary, strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: COLORS.positive }}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>

      {selectedDepartment && (
        <p className="text-center text-[10px] sm:text-xs text-muted-foreground mt-2">
          Croissance entreprises - Departement {selectedDepartment}
        </p>
      )}
    </div>
  );
}
