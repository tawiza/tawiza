'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { HiOutlineMapPin, HiOutlineArrowPath } from 'react-icons/hi2';
import { getTerritorialRanking, type TerritorialRanking } from '@/lib/api';

function getScoreColor(score: number): string {
  if (score >= 60) return 'text-green-500';
  if (score >= 40) return 'text-yellow-500';
  return 'text-red-500';
}

function getScoreEmoji(score: number): string {
  if (score >= 60) return '🟢';
  if (score >= 40) return '🟡';
  return '🔴';
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const width = Math.round(confidence * 100);
  const color = confidence >= 0.7 ? 'bg-green-500' : confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="w-12 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
      <div
        className={`h-1.5 rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

export function TerritorialRankingWidget() {
  const [ranking, setRanking] = useState<TerritorialRanking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRanking = useCallback(async () => {
    try {
      setError(null);
      const data = await getTerritorialRanking();
      if (data) {
        setRanking(data.ranking.slice(0, 15)); // Top 15
      } else {
        setError('Impossible de charger le classement');
      }
    } catch (err) {
      setError('Erreur lors du chargement');
      console.error('Error fetching ranking:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  if (isLoading) {
    return (
      <GlassCard glow="cyan" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineMapPin className="h-5 w-5 text-primary" />
              Classement Territorial
            </GlassCardTitle>
            <GlassCardDescription>
              Ranking Phase 2 des départements
            </GlassCardDescription>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3 animate-pulse">
                <div className="w-6 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="w-8 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="flex-1 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
                <div className="w-12 h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
              </div>
            ))}
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  if (error) {
    return (
      <GlassCard glow="red" hoverGlow>
        <GlassCardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <GlassCardTitle className="flex items-center gap-2">
              <HiOutlineMapPin className="h-5 w-5 text-primary" />
              Classement Territorial
            </GlassCardTitle>
            <GlassCardDescription>
              Ranking Phase 2 des départements
            </GlassCardDescription>
          </div>
          <Button size="sm" variant="ghost" onClick={fetchRanking}>
            <HiOutlineArrowPath className="h-4 w-4" />
          </Button>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="text-center py-6 text-muted-foreground">
            <p>{error}</p>
            <Button size="sm" onClick={fetchRanking} className="mt-2">
              Réessayer
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between">
        <div className="space-y-1">
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineMapPin className="h-5 w-5 text-primary" />
            Classement Territorial
          </GlassCardTitle>
          <GlassCardDescription>
            Top {ranking.length} départements (Phase 2)
          </GlassCardDescription>
        </div>
        <Button size="sm" variant="ghost" onClick={fetchRanking}>
          <HiOutlineArrowPath className="h-4 w-4" />
        </Button>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="space-y-2">
          {/* Header */}
          <div className="flex items-center text-xs text-muted-foreground pb-1 border-b border-gray-200 dark:border-gray-700">
            <div className="w-6">Rk</div>
            <div className="w-8">Dep</div>
            <div className="flex-1">Département</div>
            <div className="w-12 text-center">Score</div>
            <div className="w-12 text-center">Conf</div>
          </div>

          {/* Rankings */}
          {ranking.map((dept, index) => (
            <div
              key={dept.code}
              className="flex items-center text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 py-1 transition-colors"
            >
              <div className="w-6 text-xs text-muted-foreground">
                {index + 1}
              </div>
              <div className="w-8 text-xs font-mono">
                {dept.code}
              </div>
              <div className="flex-1 text-sm">
                <div className="truncate">{dept.name}</div>
              </div>
              <div className="w-12 text-center">
                <div className="flex flex-col items-center">
                  <span className={`text-xs font-semibold ${getScoreColor(dept.score)}`}>
                    {getScoreEmoji(dept.score)}{dept.score}
                  </span>
                </div>
              </div>
              <div className="w-12 flex justify-center">
                <ConfidenceBar confidence={dept.confidence} />
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <span>🟢 ≥60</span>
            </div>
            <div className="flex items-center gap-1">
              <span>🟡 40-59</span>
            </div>
            <div className="flex items-center gap-1">
              <span>🔴 &lt;40</span>
            </div>
            <div className="ml-auto">
              Confiance: ■ sources/10
            </div>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}