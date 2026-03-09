'use client';

import { useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { HiOutlineHeart, HiOutlineArrowTrendingUp, HiOutlineArrowTrendingDown } from 'react-icons/hi2';
import { fetchDepartmentScores, type DepartmentScore } from '@/lib/api';

function ScoreBar({ score, className }: { score: number; className?: string }) {
  // Color gradient: red (0-30), yellow (30-60), green (60-100)
  const getColor = (score: number) => {
    if (score >= 60) return 'bg-green-500';
    if (score >= 30) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className={`w-full bg-muted/30 rounded-full h-2 ${className}`}>
      <div
        className={`h-2 rounded-full transition-all duration-300 ${getColor(score)}`}
        style={{ width: `${Math.min(score, 100)}%` }}
      />
    </div>
  );
}

function DepartmentRow({ dept, rank }: { dept: DepartmentScore; rank: number }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-xs font-mono text-muted-foreground w-6 text-right">
        {rank}
      </span>
      <span className="text-sm font-medium w-8">
        {dept.code_dept}
      </span>
      <div className="flex-1 min-w-0">
        <ScoreBar score={dept.composite_score} />
      </div>
      <span className="text-sm font-semibold w-12 text-right">
        {dept.composite_score.toFixed(0)}
      </span>
    </div>
  );
}

export default function TerritorialHealthWidget() {
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
      <GlassCard glow="green" hoverGlow>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineHeart className="h-5 w-5 text-primary" />
            Santé Territoriale
          </GlassCardTitle>
          <GlassCardDescription>Départements les plus/moins prospères</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 py-2 animate-pulse">
                <div className="w-6 h-4 bg-muted/50 rounded" />
                <div className="w-8 h-4 bg-muted/50 rounded" />
                <div className="flex-1 h-2 bg-muted/50 rounded-full" />
                <div className="w-12 h-4 bg-muted/50 rounded" />
              </div>
            ))}
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
            <HiOutlineHeart className="h-5 w-5 text-primary" />
            Santé Territoriale
          </GlassCardTitle>
          <GlassCardDescription>Départements les plus/moins prospères</GlassCardDescription>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            Aucune donnée de score territorial disponible
          </p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Sort by score (descending) and get top 5 and bottom 5
  const sortedScores = [...scores].sort((a, b) => b.composite_score - a.composite_score);
  const topDepartments = sortedScores.slice(0, 5);
  const bottomDepartments = sortedScores.slice(-5).reverse(); // Reverse to show worst first

  return (
    <GlassCard glow="green" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineHeart className="h-5 w-5 text-primary" />
          Santé Territoriale
        </GlassCardTitle>
        <GlassCardDescription>
          {scores.length} départements analysés - Scores composites
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="space-y-4">
          {/* Top 5 Healthiest */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <HiOutlineArrowTrendingUp className="h-4 w-4 text-green-500" />
              <h4 className="text-sm font-medium text-green-500">Les plus prospères</h4>
            </div>
            <div className="space-y-1">
              {topDepartments.map((dept, index) => (
                <DepartmentRow
                  key={dept.code_dept}
                  dept={dept}
                  rank={index + 1}
                />
              ))}
            </div>
          </div>

          <hr className="border-muted/30" />

          {/* Bottom 5 Most Distressed */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <HiOutlineArrowTrendingDown className="h-4 w-4 text-red-500" />
              <h4 className="text-sm font-medium text-red-500">Les plus en difficulté</h4>
            </div>
            <div className="space-y-1">
              {bottomDepartments.map((dept, index) => (
                <DepartmentRow
                  key={dept.code_dept}
                  dept={dept}
                  rank={sortedScores.length - bottomDepartments.length + index + 1}
                />
              ))}
            </div>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}