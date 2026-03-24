'use client';

import { useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { HiOutlineCircleStack } from 'react-icons/hi2';
import { fetchDepartmentScores, type DepartmentScore } from '@/lib/api';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip
} from 'recharts';

interface RadarData {
  factor: string;
  value: number;
  fullMark: 100;
}

// Factor labels in French
const factorLabels: Record<string, string> = {
  sante: 'Santé',
  declin: 'Déclin',
  emploi: 'Emploi',
  immo: 'Immobilier',
  construction: 'Construction',
  presse: 'Presse'
};

// Custom tooltip component
function CustomTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    const data = payload[0].payload as RadarData;
    return (
      <div className="glass p-3 rounded-lg border">
        <p className="text-sm font-medium">{data.factor}</p>
        <p className="text-sm text-muted-foreground">
          Score: <span className="font-semibold text-primary">
            {data.value.toFixed(1)}
          </span>
        </p>
      </div>
    );
  }

  return null;
}

export default function FactorRadarChart() {
  const [scores, setScores] = useState<DepartmentScore[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadScores = async () => {
      try {
        const data = await fetchDepartmentScores();
        setScores(data);

        // Default to the top-scoring department
        if (data.length > 0) {
          const topDept = data.reduce((prev, current) =>
            (prev.composite_score > current.composite_score) ? prev : current
          );
          setSelectedDept(topDept.code_dept);
        }
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
      <GlassCard glow="green" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineCircleStack className="h-5 w-5 text-primary" />
            Facteurs Territoriaux
          </GlassCardTitle>
          <GlassCardDescription>Analyse radar des 6 dimensions</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="h-[350px] flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">
              Chargement des facteurs...
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (scores.length === 0) {
    return (
      <GlassCard glow="green" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineCircleStack className="h-5 w-5 text-primary" />
            Facteurs Territoriaux
          </GlassCardTitle>
          <GlassCardDescription>Analyse radar des 6 dimensions</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="h-[350px] flex items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Aucune donnée de facteurs disponible
            </p>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Find the selected department
  const selectedDepartment = scores.find(dept => dept.code_dept === selectedDept);

  // Prepare radar chart data
  const radarData: RadarData[] = selectedDepartment
    ? Object.entries(selectedDepartment.factors).map(([key, value]) => ({
        factor: factorLabels[key] || key,
        value: value,
        fullMark: 100
      }))
    : [];

  return (
    <GlassCard glow="green" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineCircleStack className="h-5 w-5 text-primary" />
          Facteurs Territoriaux
        </GlassCardTitle>
        <GlassCardDescription>
          Analyse radar des 6 dimensions pour le département sélectionné
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {/* Department selector */}
        <div className="mb-4">
          <Select value={selectedDept} onValueChange={setSelectedDept}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Choisir un département" />
            </SelectTrigger>
            <SelectContent>
              {scores
                .sort((a, b) => b.composite_score - a.composite_score)
                .map((dept) => (
                  <SelectItem key={dept.code_dept} value={dept.code_dept}>
                    {dept.code_dept} ({dept.composite_score.toFixed(0)})
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>

        {/* Radar chart */}
        <div className="h-[350px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid
                className="opacity-30"
                stroke="currentColor"
              />
              <PolarAngleAxis
                dataKey="factor"
                className="text-xs fill-muted-foreground"
                tick={{ fontSize: 12 }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                className="text-xs fill-muted-foreground"
                tick={{ fontSize: 10 }}
              />
              <Radar
                name="Scores"
                dataKey="value"
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.2}
                strokeWidth={2}
              />
              <Tooltip content={<CustomTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Department info */}
        {selectedDepartment && (
          <div className="mt-4 pt-4 border-t border-muted/30">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Score composite:</span>
                <span className="ml-2 font-semibold text-primary">
                  {selectedDepartment.composite_score.toFixed(1)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Catégorie:</span>
                <span className="ml-2 font-medium capitalize">
                  {selectedDepartment.category}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Population:</span>
                <span className="ml-2 font-medium">
                  {selectedDepartment.population.toLocaleString('fr-FR')}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Couverture:</span>
                <span className="ml-2 font-medium">
                  {(selectedDepartment.factor_coverage * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}