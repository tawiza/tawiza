'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { HiOutlineChartBar } from 'react-icons/hi2';

// Nord Aurora palette for sectors
const SECTOR_COLORS = [
  'var(--chart-1)', // nord8 - cyan
  'var(--chart-2)', // nord9 - blue
  'var(--success)', // nord14 - green
  'var(--warning)', // nord13 - yellow
  'var(--chart-5)', // nord12 - orange
  'var(--chart-4)', // nord15 - purple
  'var(--chart-1)', // nord7 - teal
  'var(--chart-3)', // nord10 - dark blue
];

const COLORS = {
  grid: 'hsl(var(--border))',
  text: 'hsl(var(--foreground))',
};

interface SectorData {
  sector: string;
  count: number;
  growth: number;
}

interface SectorBarChartProps {
  data?: SectorData[];
  isLoading?: boolean;
}

// Custom tooltip
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  return (
    <div className="glass px-3 py-2 rounded-lg text-sm">
      <p className="font-medium mb-1">{label}</p>
      <p>Entreprises: {data.count.toLocaleString()}</p>
      <p style={{ color: data.growth >= 0 ? 'var(--success)' : 'var(--error)' }}>
        Croissance: {data.growth > 0 ? '+' : ''}{data.growth.toFixed(1)}%
      </p>
    </div>
  );
}

export default function SectorBarChart({ data, isLoading }: SectorBarChartProps) {
  const { selectedDepartment } = useTAJINE();

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    // Sort by count descending
    return [...data].sort((a, b) => b.count - a.count);
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
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 10, right: 20, left: 60, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} opacity={0.3} horizontal={false} />
          <XAxis
            type="number"
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 10 }}
            tickLine={{ stroke: COLORS.grid }}
            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
          />
          <YAxis
            type="category"
            dataKey="sector"
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.grid }}
            width={55}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(136, 192, 208, 0.1)' }} />
          <Bar
            dataKey="count"
            radius={[0, 4, 4, 0]}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={SECTOR_COLORS[index % SECTOR_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {selectedDepartment && (
        <p className="text-center text-[10px] sm:text-xs text-muted-foreground mt-2">
          Repartition sectorielle - Departement {selectedDepartment}
        </p>
      )}
    </div>
  );
}
