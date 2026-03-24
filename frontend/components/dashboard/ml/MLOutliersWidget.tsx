'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { HiOutlineExclamationTriangle, HiOutlineArrowTrendingDown } from 'react-icons/hi2';
import { getMLAnomalies, type MLAnomaliesResponse, type MLAnomaly } from '@/lib/api';

/**
 * ML Outliers Widget - Displays Isolation Forest outliers
 * Shows anomalous departments with their anomaly scores
 */
export function MLOutliersWidget() {
  const [data, setData] = useState<MLAnomaliesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await getMLAnomalies();
      setData(response);
    } catch (error) {
      console.error('Failed to fetch ML outliers:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // Refresh every 5 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

  const isolationForestOutliers = data?.isolation_forest_outliers || [];

  return (
    <GlassCard glow={isolationForestOutliers.length > 0 ? 'red' : 'cyan'} hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineExclamationTriangle className="h-5 w-5 text-primary" />
          Départements Atypiques (ML)
        </GlassCardTitle>
        <GlassCardDescription>
          Isolation Forest • Détection d&apos;anomalies
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-12 bg-muted/50 rounded" />
            <div className="h-12 bg-muted/50 rounded" />
            <div className="h-12 bg-muted/50 rounded" />
          </div>
        ) : isolationForestOutliers.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-muted-foreground">
              Aucun département atypique détecté
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Tous les profils économiques sont dans la normale
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl font-bold">{isolationForestOutliers.length}</span>
              <span className="text-xs text-muted-foreground">outliers détectés</span>
            </div>

            {isolationForestOutliers.map((outlier, index) => (
              <div
                key={outlier.code_dept}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <HiOutlineArrowTrendingDown className="h-5 w-5 flex-shrink-0 text-[var(--error)]" />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {outlier.department_name || `Dept ${outlier.code_dept}`}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      {outlier.code_dept}
                    </span>
                  </div>

                  {/* Anomaly score bar */}
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-muted-foreground">Score d&apos;anomalie</span>
                      <span className="font-mono">
                        {outlier.anomaly_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="w-full bg-muted/30 rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-[var(--error)] to-red-600"
                        style={{
                          width: `${Math.min(Math.abs(outlier.anomaly_score) * 100, 100)}%`,
                        }}
                      />
                    </div>
                  </div>

                  {outlier.confidence && (
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/80 text-muted-foreground">
                        Confiance: {(outlier.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {data?.last_analysis && (
              <div className="mt-3 pt-2 border-t border-muted/30">
                <p className="text-xs text-muted-foreground">
                  Dernière analyse: {new Date(data.last_analysis).toLocaleDateString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </p>
              </div>
            )}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}