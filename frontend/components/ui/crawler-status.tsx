'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  HiOutlineServerStack,
  HiOutlineArrowPath,
  HiOutlinePlay,
  HiOutlineStop,
} from 'react-icons/hi2';
import { GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle, GlassCardDescription } from './glass-card';
import { Button } from './button';
import { getCrawlerStats, startCrawler, stopCrawler, triggerCrawl, type CrawlerStats } from '@/lib/api';

interface CrawlerStatusProps {
  className?: string;
}

export default function CrawlerStatus({ className = '' }: CrawlerStatusProps) {
  const [stats, setStats] = useState<CrawlerStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCrawling, setIsCrawling] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const data = await getCrawlerStats();
      if (data) {
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch crawler stats:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleStart = async () => {
    await startCrawler();
    fetchStats();
  };

  const handleStop = async () => {
    await stopCrawler();
    fetchStats();
  };

  const handleCrawl = async () => {
    setIsCrawling(true);
    await triggerCrawl();
    setIsCrawling(false);
    fetchStats();
  };

  if (isLoading) {
    return (
      <GlassCard className={className}>
        <GlassCardContent className="h-32 flex items-center justify-center">
          <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full" />
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="green" hoverGlow className={className}>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineServerStack className="h-5 w-5 text-primary" />
          Crawler
          {stats?.is_running && (
            <span className="ml-auto flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              <span className="text-xs text-green-400">Actif</span>
            </span>
          )}
        </GlassCardTitle>
        <GlassCardDescription>Collecte automatique des donnees</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center p-3 rounded-lg bg-white/5">
              <div className="text-2xl font-bold text-primary">
                {stats?.total_sources || 0}
              </div>
              <div className="text-xs text-muted-foreground">Sources</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white/5">
              <div className="text-2xl font-bold text-cyan-400">
                {stats?.results_cached || 0}
              </div>
              <div className="text-xs text-muted-foreground">En cache</div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            {stats?.is_running ? (
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={handleStop}
              >
                <HiOutlineStop className="h-4 w-4 mr-1" />
                Arreter
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={handleStart}
              >
                <HiOutlinePlay className="h-4 w-4 mr-1" />
                Demarrer
              </Button>
            )}
            <Button
              variant="default"
              size="sm"
              className="flex-1"
              onClick={handleCrawl}
              disabled={isCrawling || !stats?.is_running}
            >
              <HiOutlineArrowPath className={`h-4 w-4 mr-1 ${isCrawling ? 'animate-spin' : ''}`} />
              {isCrawling ? 'Crawl...' : 'Crawler'}
            </Button>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
