'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import {
  HiOutlineCpuChip,
  HiOutlinePlay,
  HiOutlineCheckCircle,
  HiOutlineExclamationTriangle,
  HiOutlineCircleStack
} from 'react-icons/hi2';
import {
  getMLAnomalies,
  getMLClusters,
  runMLDetection,
  type MLAnomaliesResponse,
  type MLClustersResponse
} from '@/lib/api';

/**
 * ML Summary Card Widget
 * Shows a summary of ML analysis with option to trigger new detection
 */
export function MLSummaryCard() {
  const [anomaliesData, setAnomaliesData] = useState<MLAnomaliesResponse | null>(null);
  const [clustersData, setClustersData] = useState<MLClustersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [anomalies, clusters] = await Promise.all([
        getMLAnomalies(),
        getMLClusters(),
      ]);

      setAnomaliesData(anomalies);
      setClustersData(clusters);

      // Set last run from the most recent analysis
      if (anomalies?.last_analysis || clusters?.computed_at) {
        const anomaliesDate = anomalies?.last_analysis ? new Date(anomalies.last_analysis) : null;
        const clustersDate = clusters?.computed_at ? new Date(clusters.computed_at) : null;

        let mostRecent = null;
        if (anomaliesDate && clustersDate) {
          mostRecent = anomaliesDate > clustersDate ? anomaliesDate : clustersDate;
        } else if (anomaliesDate) {
          mostRecent = anomaliesDate;
        } else if (clustersDate) {
          mostRecent = clustersDate;
        }

        setLastRun(mostRecent ? mostRecent.toISOString() : null);
      }
    } catch (error) {
      console.error('Failed to fetch ML data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // Refresh every 5 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRunDetection = async () => {
    setRunning(true);
    try {
      const result = await runMLDetection();
      if (result?.success) {
        // Refresh data after successful run
        setTimeout(() => {
          fetchData();
        }, 2000); // Wait 2 seconds for backend to process
      }
    } catch (error) {
      console.error('Failed to run ML detection:', error);
    } finally {
      setRunning(false);
    }
  };

  const totalOutliers = anomaliesData?.outliers_count || 0;
  const totalClusters = clustersData?.cluster_count || 0;
  const totalDepartments = clustersData?.total_departments || 0;

  // Determine status based on data availability
  const hasData = anomaliesData || clustersData;
  const isRecent = lastRun && (Date.now() - new Date(lastRun).getTime()) < 24 * 60 * 60 * 1000; // 24h

  return (
    <GlassCard glow={hasData ? 'cyan' : 'yellow'} hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineCpuChip className="h-5 w-5 text-primary" />
          Intelligence Artificielle
        </GlassCardTitle>
        <GlassCardDescription>
          Analyse ML • Détection d&apos;anomalies et clustering
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-8 bg-muted/50 rounded" />
            <div className="h-6 bg-muted/50 rounded w-3/4" />
            <div className="h-10 bg-muted/50 rounded" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary statistics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center p-3 rounded-lg bg-muted/20">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <HiOutlineExclamationTriangle className="h-4 w-4 text-[var(--error)]" />
                  <span className="text-lg font-bold">{totalOutliers}</span>
                </div>
                <div className="text-xs text-muted-foreground">Outliers détectés</div>
              </div>

              <div className="text-center p-3 rounded-lg bg-muted/20">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <HiOutlineCircleStack className="h-4 w-4 text-[var(--success)]" />
                  <span className="text-lg font-bold">{totalClusters}</span>
                </div>
                <div className="text-xs text-muted-foreground">Profils économiques</div>
              </div>
            </div>

            {/* Methods used */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Méthodes utilisées
              </p>
              <div className="flex flex-wrap gap-2">
                {anomaliesData && (
                  <span className="text-xs px-2 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    Isolation Forest
                  </span>
                )}
                {clustersData && (
                  <span className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    HDBSCAN
                  </span>
                )}
                {clustersData?.method && (
                  <span className="text-xs px-2 py-1 rounded-full bg-green-500/20 text-green-300 border border-green-500/30">
                    {clustersData.method.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            {/* Performance indicators */}
            {clustersData?.silhouette_score !== undefined && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Qualité clustering: {(clustersData.silhouette_score * 100).toFixed(1)}%
                </p>
                <div className="w-full bg-muted/30 rounded-full h-1.5">
                  <div
                    className="h-1.5 rounded-full bg-gradient-to-r from-green-500 to-blue-500"
                    style={{ width: `${clustersData.silhouette_score * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Last analysis info */}
            {lastRun && (
              <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/20">
                <HiOutlineCheckCircle className={`h-4 w-4 ${isRecent ? 'text-green-500' : 'text-yellow-500'}`} />
                <div className="flex-1">
                  <p className="text-xs text-muted-foreground">
                    Dernière analyse
                  </p>
                  <p className="text-sm">
                    {new Date(lastRun).toLocaleDateString('fr-FR', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </p>
                </div>
                {!isRecent && (
                  <div className="text-xs px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-300">
                    Ancienne
                  </div>
                )}
              </div>
            )}

            {/* Run detection button */}
            <div className="pt-2 border-t border-muted/30">
              <Button
                onClick={handleRunDetection}
                disabled={running}
                className="w-full"
                variant="outline"
                size="sm"
              >
                <HiOutlinePlay className={`h-4 w-4 mr-2 ${running ? 'animate-spin' : ''}`} />
                {running ? 'Détection en cours...' : 'Relancer détection'}
              </Button>

              {!hasData && (
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  Aucune analyse disponible. Lancez une première détection.
                </p>
              )}
            </div>

            {/* Coverage info */}
            {totalDepartments > 0 && (
              <div className="pt-1">
                <p className="text-xs text-muted-foreground text-center">
                  Analyse sur {totalDepartments} départements
                </p>
              </div>
            )}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}