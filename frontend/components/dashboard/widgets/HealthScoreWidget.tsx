'use client';

import { useState } from 'react';
import useSWR from 'swr';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  HiOutlineHeart,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineMinus,
} from 'react-icons/hi2';
import Link from 'next/link';

interface HealthScoreComponents {
  emploi: number;
  dynamisme: number;
  finances: number;
  immobilier: number;
  demographie: number;
}

interface HealthScore {
  code: string;
  name: string;
  score: number;
  components: HealthScoreComponents;
  trend: 'up' | 'down' | 'stable';
}

const COMPONENT_LABELS: Record<keyof HealthScoreComponents, string> = {
  emploi: 'Emploi',
  dynamisme: 'Dynamisme',
  finances: 'Finances',
  immobilier: 'Immobilier',
  demographie: 'Démographie',
};

const COMPONENT_WEIGHTS: Record<keyof HealthScoreComponents, number> = {
  emploi: 30,
  dynamisme: 25,
  finances: 20,
  immobilier: 15,
  demographie: 10,
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function getScoreColor(score: number): string {
  if (score >= 75) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  if (score >= 25) return 'text-orange-400';
  return 'text-red-400';
}

function getScoreGlow(score: number): 'green' | 'cyan' | 'red' {
  if (score >= 60) return 'green';
  if (score >= 40) return 'cyan';
  return 'red';
}

function TrendIcon({ trend }: { trend: 'up' | 'down' | 'stable' }) {
  switch (trend) {
    case 'up':
      return <HiOutlineArrowTrendingUp className="h-4 w-4 text-green-400" />;
    case 'down':
      return <HiOutlineArrowTrendingDown className="h-4 w-4 text-red-400" />;
    default:
      return <HiOutlineMinus className="h-4 w-4 text-muted-foreground" />;
  }
}

function ScoreBreakdown({ components }: { components: HealthScoreComponents }) {
  return (
    <div className="grid grid-cols-5 gap-1 mt-2">
      {(Object.keys(components) as (keyof HealthScoreComponents)[]).map((key) => (
        <TooltipProvider key={key}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex flex-col items-center">
                <div className="text-[10px] text-muted-foreground truncate w-full text-center">
                  {COMPONENT_LABELS[key].slice(0, 3)}
                </div>
                <div
                  className={`text-xs font-medium ${getScoreColor(components[key])}`}
                >
                  {Math.round(components[key])}
                </div>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>
                {COMPONENT_LABELS[key]}: {components[key].toFixed(1)}/100 (
                {COMPONENT_WEIGHTS[key]}%)
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ))}
    </div>
  );
}

function HealthScoreRow({ score }: { score: HealthScore }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="py-2 border-b border-white/5 last:border-0 cursor-pointer hover:bg-white/5 rounded-md transition-colors px-2 -mx-2"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {score.code}
          </Badge>
          <span className="text-sm font-medium">{score.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-lg font-bold ${getScoreColor(score.score)}`}>
            {Math.round(score.score)}
          </span>
          <TrendIcon trend={score.trend} />
        </div>
      </div>

      {expanded && <ScoreBreakdown components={score.components} />}

      {!expanded && (
        <Progress
          value={score.score}
          className="h-1 mt-2"
          // Use custom color based on score
        />
      )}
    </div>
  );
}

export function HealthScoreWidget({ limit = 5 }: { limit?: number }) {
  const [showBottom, setShowBottom] = useState(false);

  const { data, error, isLoading } = useSWR<HealthScore[] | { detail?: string }>(
    `/api/v1/territorial/health-scores?limit=${limit}&bottom=${showBottom}`,
    fetcher,
    {
      refreshInterval: 300000, // Refresh every 5 minutes
      revalidateOnFocus: false,
    }
  );

  // Handle both array and error object responses
  const scores = Array.isArray(data) ? data : [];

  const avgScore = scores.length > 0
    ? scores.reduce((sum, d) => sum + d.score, 0) / scores.length
    : 0;

  if (error) {
    return (
      <GlassCard glow="red">
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineHeart className="h-5 w-5 text-red-400" />
            Santé Économique
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground">Erreur de chargement</p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow={scores.length > 0 ? getScoreGlow(avgScore) : 'cyan'} hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between pb-2">
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineHeart className="h-5 w-5 text-primary" />
          Santé Économique
        </GlassCardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant={showBottom ? 'outline' : 'default'}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setShowBottom(false)}
          >
            Top
          </Button>
          <Button
            variant={showBottom ? 'default' : 'outline'}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setShowBottom(true)}
          >
            Bottom
          </Button>
        </div>
      </GlassCardHeader>
      <GlassCardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(limit)].map((_, i) => (
              <div key={i} className="h-10 bg-muted/20 rounded animate-pulse" />
            ))}
          </div>
        ) : scores.length > 0 ? (
          <div className="space-y-1">
            {scores.map((score) => (
              <Link
                key={score.code}
                href={`/dashboard/tajine?dept=${score.code}`}
              >
                <HealthScoreRow score={score} />
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            Aucune donnée disponible
          </p>
        )}

        {scores.length > 0 && (
          <div className="mt-4 pt-3 border-t border-white/10 flex justify-between items-center">
            <span className="text-xs text-muted-foreground">
              Score moyen affiché
            </span>
            <span className={`text-sm font-bold ${getScoreColor(avgScore)}`}>
              {avgScore.toFixed(1)}
            </span>
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

export default HealthScoreWidget;
