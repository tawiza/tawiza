'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { HiOutlineCircleStack, HiOutlineMapPin } from 'react-icons/hi2';
import { getMLClusters, type MLClustersResponse } from '@/lib/api';

// Predefined colors for clusters
const CLUSTER_COLORS = [
  'var(--chart-1)', // Blue
  'var(--chart-4)', // Emerald
  'var(--chart-5)', // Amber
  'var(--error)', // Red
  'var(--chart-3)', // Purple
  'var(--info)', // Cyan
  'var(--success)', // Lime
  'var(--chart-5)', // Orange
];

/**
 * Cluster Map Widget - Displays economic clustering results
 * Shows departments grouped by economic profiles
 */
export function ClusterMapWidget() {
  const [data, setData] = useState<MLClustersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await getMLClusters();
      setData(response);
    } catch (error) {
      console.error('Failed to fetch ML clusters:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // Refresh every 5 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

  const clustersRaw = data?.clusters || {};
  const clusters = Array.isArray(clustersRaw)
    ? clustersRaw
    : Object.entries(clustersRaw).map(([key, val]: [string, any]) => ({
        cluster_id: key,
        size: val?.size ?? val?.department_codes?.length ?? 0,
        department_codes: val?.department_codes || [],
        ...val,
      }));
  const noiseDepartments = data?.noise_departments || [];

  return (
    <GlassCard glow="green" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineCircleStack className="h-5 w-5 text-primary" />
          Profils Économiques (Clustering)
        </GlassCardTitle>
        <GlassCardDescription>
          HDBSCAN • {data?.cluster_count || 0} profils économiques
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-16 bg-muted/50 rounded" />
            <div className="h-16 bg-muted/50 rounded" />
            <div className="h-16 bg-muted/50 rounded" />
          </div>
        ) : clusters.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-muted-foreground">
              Aucun profil économique identifié
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Clustering en cours d&apos;analyse
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="text-center p-2 rounded-lg bg-muted/20">
                <div className="text-lg font-bold">{data?.cluster_count}</div>
                <div className="text-xs text-muted-foreground">Profils</div>
              </div>
              <div className="text-center p-2 rounded-lg bg-muted/20">
                <div className="text-lg font-bold">{data?.total_departments}</div>
                <div className="text-xs text-muted-foreground">Départements</div>
              </div>
            </div>

            {/* Clusters */}
            <div className="space-y-3">
              {clusters.map((cluster, index) => {
                const color = CLUSTER_COLORS[index % CLUSTER_COLORS.length];
                return (
                  <div
                    key={cluster.cluster_id}
                    className="p-3 rounded-lg border border-muted/30 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: color }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">
                            {cluster.name || `Profil ${cluster.cluster_id}`}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            ({cluster.department_count} depts)
                          </span>
                        </div>
                        {cluster.description && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {cluster.description}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Department list */}
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(cluster.department_codes || cluster.departments || []).slice(0, 10).map((dept: string) => (
                        <span
                          key={dept}
                          className="text-[10px] px-1.5 py-0.5 rounded-full text-white font-mono"
                          style={{ backgroundColor: color }}
                        >
                          {dept}
                        </span>
                      ))}
                      {(cluster.department_codes || cluster.departments || []).length > 10 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/50 text-muted-foreground">
                          +{(cluster.department_codes || cluster.departments || []).length - 10}
                        </span>
                      )}
                    </div>

                    {/* Top characteristics */}
                    {cluster.characteristics && Object.keys(cluster.characteristics).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {Object.entries(cluster.characteristics)
                          .sort(([,a], [,b]) => Number(b) - Number(a))
                          .slice(0, 3)
                          .map(([char, value]) => (
                            <span
                              key={char}
                              className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/80 text-muted-foreground"
                            >
                              {char}: {typeof value === 'number' ? value.toFixed(2) : String(value)}
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Noise departments */}
            {noiseDepartments.length > 0 && (
              <div className="pt-3 border-t border-muted/30">
                <div className="flex items-center gap-2 mb-2">
                  <HiOutlineMapPin className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    Départements isolés ({noiseDepartments.length})
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {noiseDepartments.map((dept) => (
                    <span
                      key={dept}
                      className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/50 text-muted-foreground font-mono"
                    >
                      {dept}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Quality score */}
            {data?.silhouette_score !== undefined && (
              <div className="pt-2 border-t border-muted/30">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Qualité clustering</span>
                  <span className="font-mono">
                    {(data.silhouette_score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            {data?.computed_at && (
              <div className="pt-1">
                <p className="text-xs text-muted-foreground">
                  Calculé: {new Date(data.computed_at).toLocaleDateString('fr-FR', {
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