'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { HiOutlineMapPin } from 'react-icons/hi2';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { getCollectorSummary } from '@/lib/api';
import { DEPT_NAMES } from '@/lib/departments';

const BAR_COLORS = [
  'var(--info)', 'hsl(var(--primary))', 'var(--chart-1)', 'var(--success)', 'var(--chart-4)',
  'var(--chart-3)', 'var(--chart-5)', 'var(--warning)', 'var(--error)', 'hsl(var(--muted))',
];

interface DeptData {
  dept: string;
  name: string;
  count: number;
}

export function DepartmentBarChart({ days = 7 }: { days?: number }) {
  const [data, setData] = useState<DeptData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const summary = await getCollectorSummary(days);
    if (!summary?.by_department) {
      setLoading(false);
      return;
    }

    const sorted = Object.entries(summary.by_department)
      .map(([dept, count]) => ({
        dept,
        name: DEPT_NAMES[dept] || dept,
        count,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    setData(sorted);
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 120000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <GlassCard glow="green" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineMapPin className="h-5 w-5 text-primary" />
          Top Départements
        </GlassCardTitle>
        <GlassCardDescription>Signaux par département • {days}j</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse h-[250px] bg-muted/50 rounded" />
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">Aucune donnée</p>
        ) : (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="name"
                tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10 }}
                angle={-35}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(30,30,46,0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  color: 'hsl(var(--foreground))',
                  fontSize: 12,
                }}
                formatter={(value: number) => [`${value} signaux`, 'Total']}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
