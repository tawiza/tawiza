'use client';

import { useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { HiOutlineChartBarSquare } from 'react-icons/hi2';
import { fetchDepartmentScores, type DepartmentScore } from '@/lib/api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

interface ChartData {
  code_dept: string;
  score: number;
  category: string;
  fill: string;
}

// Color mapping based on score ranges
const getScoreColor = (score: number): string => {
  if (score >= 60) return 'var(--success)'; // green-500
  if (score >= 40) return 'var(--warning)'; // yellow-500
  if (score >= 20) return 'var(--chart-1)'; // blue-500
  return 'var(--error)'; // red-500
};

// Custom tooltip component
function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    const data = payload[0].payload as ChartData;
    return (
      <div className="glass p-3 rounded-lg border">
        <p className="font-medium text-sm">{`Département ${data.code_dept}`}</p>
        <p className="text-sm text-muted-foreground">
          Score: <span className="font-semibold" style={{ color: data.fill }}>
            {data.score.toFixed(1)}
          </span>
        </p>
        <p className="text-xs text-muted-foreground capitalize">
          Catégorie: {data.category}
        </p>
      </div>
    );
  }

  return null;
}

export default function DepartmentRankingChart() {
  const [scores, setScores] = useState<DepartmentScore[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadScores = async () => {
      try {
        const data = await fetchDepartmentScores();
        setScores(data);
      } catch (error) {
        console.error('Failed to load department scores:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadScores();
  }, []);

  if (isLoading) {
    return (
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineChartBarSquare className="h-5 w-5 text-primary" />
            Classement Départemental
          </GlassCardTitle>
          <GlassCardDescription>Scores de santé territoriale</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="h-[400px] flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">
              Chargement des données...
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (scores.length === 0) {
    return (
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineChartBarSquare className="h-5 w-5 text-primary" />
            Classement Départemental
          </GlassCardTitle>
          <GlassCardDescription>Scores de santé territoriale</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="h-[400px] flex items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Aucune donnée de classement disponible
            </p>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Prepare data for chart
  const chartData: ChartData[] = scores
    .sort((a, b) => b.composite_score - a.composite_score) // Sort by score descending
    .map((dept) => ({
      code_dept: dept.code_dept,
      score: dept.composite_score,
      category: dept.category,
      fill: getScoreColor(dept.composite_score)
    }));

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBarSquare className="h-5 w-5 text-primary" />
          Classement Départemental
        </GlassCardTitle>
        <GlassCardDescription>
          {scores.length} départements classés par score de santé territoriale
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="horizontal"
              margin={{
                top: 20,
                right: 30,
                left: 20,
                bottom: 5,
              }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                className="opacity-30"
                stroke="currentColor"
              />
              <XAxis
                type="number"
                domain={[0, 100]}
                className="text-xs fill-muted-foreground"
              />
              <YAxis
                type="category"
                dataKey="code_dept"
                className="text-xs fill-muted-foreground"
                width={40}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: 'rgba(255, 255, 255, 0.1)' }}
              />
              <Bar
                dataKey="score"
                radius={[0, 4, 4, 0]}
                fillOpacity={0.8}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap justify-center gap-4 mt-4 pt-4 border-t border-muted/30">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-xs text-muted-foreground">Excellent (&gt;60)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="text-xs text-muted-foreground">Moyen (40-60)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-xs text-muted-foreground">Faible (20-40)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-xs text-muted-foreground">Critique (&lt;20)</span>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}