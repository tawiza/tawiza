'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { HiOutlineChartBarSquare, HiOutlineSparkles } from 'react-icons/hi2';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { getMLAnomalies, getMLFactors, type MLFactors, type MLAnomaliesResponse } from '@/lib/api';

interface FeatureImportanceData {
  feature: string;
  importance: number;
  displayName: string;
}

// Feature display names mapping
const FEATURE_NAMES: Record<string, string> = {
  creation_entreprise: 'Créations entreprises',
  fermeture_entreprise: 'Fermetures entreprises',
  offres_emploi: 'Offres emploi',
  presse_positif: 'Presse positive',
  presse_negatif: 'Presse négative',
  population: 'Population',
  densite: 'Densité',
  chomage: 'Taux chômage',
  emploi: 'Emploi total',
  sante_score: 'Score santé',
  declin_score: 'Score déclin',
  tension_emploi: 'Tension emploi',
  attractivite: 'Attractivité',
};

/**
 * Feature Importance Chart Widget
 * Shows the most important variables for ML model decisions
 */
export function FeatureImportanceChart() {
  const [data, setData] = useState<FeatureImportanceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<'factors' | 'anomalies'>('factors');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Try to fetch from dedicated ML factors endpoint first
      let factors: MLFactors | null = null;
      let anomaliesData: MLAnomaliesResponse | null = null;

      try {
        factors = await getMLFactors();
      } catch (error) {
        console.warn('ML Factors endpoint failed or timed out, falling back to anomalies');
      }

      if (!factors || !factors.factors || factors.factors.length === 0) {
        // Fallback: get feature importance from anomalies summary
        anomaliesData = await getMLAnomalies();
        if (anomaliesData?.summary?.feature_importance) {
          factors = {
            factors: anomaliesData.summary.feature_importance.map(item => ({
              feature_name: item.feature,
              importance: item.importance,
              correlation: 0,
              description: FEATURE_NAMES[item.feature],
            })),
            method: anomaliesData.summary.method || 'isolation_forest',
            computed_at: new Date().toISOString(),
          };
          setSource('anomalies');
        }
      } else {
        setSource('factors');
      }

      if (factors && factors.factors) {
        // Transform and sort by importance
        const transformedData: FeatureImportanceData[] = factors.factors
          .map(factor => ({
            feature: factor.feature_name,
            importance: Math.abs(factor.importance), // Use absolute value for visualization
            displayName: FEATURE_NAMES[factor.feature_name] || factor.feature_name,
          }))
          .sort((a, b) => b.importance - a.importance)
          .slice(0, 10); // Top 10

        setData(transformedData);
      }
    } catch (error) {
      console.error('Failed to fetch feature importance:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 600000); // Refresh every 10 minutes (slower due to computation)
    return () => clearInterval(interval);
  }, [fetchData]);

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-background border border-border rounded-lg p-3 shadow-lg">
          <p className="text-sm font-medium">{payload[0].payload.displayName}</p>
          <p className="text-xs text-muted-foreground">
            Importance: {(payload[0].value * 100).toFixed(1)}%
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBarSquare className="h-5 w-5 text-primary" />
          Importance des Variables
        </GlassCardTitle>
        <GlassCardDescription>
          Facteurs les plus influents • Top 10
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-muted/50 rounded w-3/4" />
            <div className="h-4 bg-muted/50 rounded w-1/2" />
            <div className="h-4 bg-muted/50 rounded w-5/6" />
            <div className="h-4 bg-muted/50 rounded w-2/3" />
            <div className="h-4 bg-muted/50 rounded w-4/5" />
          </div>
        ) : data.length === 0 ? (
          <div className="text-center py-8">
            <HiOutlineSparkles className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              Analyse d&apos;importance en cours
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Calcul des facteurs les plus influents...
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Chart */}
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data}
                  layout="horizontal"
                  margin={{
                    top: 5,
                    right: 30,
                    left: 80,
                    bottom: 5,
                  }}
                >
                  <XAxis
                    type="number"
                    domain={[0, 1]}
                    tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                    fontSize={10}
                    className="text-muted-foreground"
                  />
                  <YAxis
                    type="category"
                    dataKey="displayName"
                    width={75}
                    fontSize={10}
                    className="text-muted-foreground"
                    tick={{ fontSize: 10 }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar
                    dataKey="importance"
                    fill="var(--chart-3)"
                    radius={[0, 2, 2, 0]}
                    fillOpacity={0.8}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Top 3 features summary */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Facteurs dominants
              </p>
              {data.slice(0, 3).map((item, index) => {
                const colors = ['var(--chart-3)', 'var(--info)', 'var(--chart-4)'];
                return (
                  <div key={item.feature} className="flex items-center gap-3">
                    <div className="flex items-center gap-2 flex-1">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: colors[index] }}
                      />
                      <span className="text-sm truncate">{item.displayName}</span>
                    </div>
                    <span className="text-sm font-mono text-muted-foreground">
                      {(item.importance * 100).toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Data source info */}
            <div className="pt-2 border-t border-muted/30">
              <p className="text-xs text-muted-foreground">
                Source: {source === 'factors' ? 'Analyse ML dédiée' : 'Détection d\'anomalies'}
                {source === 'anomalies' && ' (fallback)'}
              </p>
            </div>
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
