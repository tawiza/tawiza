'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Loader2, Info, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface BreakdownComponent {
  source: string;
  name: string;
  impact: number;
  detail: string;
  weight: string;
}

interface VitalityBreakdownData {
  total: number;
  base: number;
  components: BreakdownComponent[];
  formula: string;
}

interface VitalityBreakdownProps {
  territoryCode: string;
  territoryName: string;
  currentVitality: number;
  trigger?: React.ReactNode;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function getSourceIcon(source: string): string {
  const icons: Record<string, string> = {
    'BODACC/SIRENE': '🏢',
    'BODACC': '📋',
    'SIRENE': '🏭',
    'France Travail': '💼',
    'INSEE': '📊',
    'DVF': '🏠',
  };
  return icons[source] || '📈';
}

function getImpactColor(impact: number): string {
  if (impact > 0) return 'text-emerald-600';
  if (impact < 0) return 'text-rose-600';
  return 'text-gray-500';
}

function getImpactBg(impact: number): string {
  if (impact > 0) return 'bg-emerald-100 dark:bg-emerald-900/30';
  if (impact < 0) return 'bg-rose-100 dark:bg-rose-900/30';
  return 'bg-gray-100 dark:bg-gray-800';
}

function ImpactBar({ impact, maxImpact = 15 }: { impact: number; maxImpact?: number }) {
  const absImpact = Math.abs(impact);
  const percentage = Math.min((absImpact / maxImpact) * 100, 100);

  return (
    <div className="flex items-center gap-2 w-32">
      {impact < 0 && (
        <>
          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex justify-end">
            <div
              className="h-full bg-rose-500 rounded-full"
              style={{ width: `${percentage}%` }}
            />
          </div>
          <TrendingDown className="h-4 w-4 text-rose-500" />
        </>
      )}
      {impact > 0 && (
        <>
          <TrendingUp className="h-4 w-4 text-emerald-500" />
          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full"
              style={{ width: `${percentage}%` }}
            />
          </div>
        </>
      )}
      {impact === 0 && (
        <>
          <Minus className="h-4 w-4 text-gray-400" />
          <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full" />
        </>
      )}
    </div>
  );
}

export default function VitalityBreakdown({
  territoryCode,
  territoryName,
  currentVitality,
  trigger
}: VitalityBreakdownProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [breakdown, setBreakdown] = useState<VitalityBreakdownData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchBreakdown = async () => {
    if (breakdown) return; // Already loaded

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/territorial/metrics/${territoryCode}?territory_name=${encodeURIComponent(territoryName)}`
      );
      if (!response.ok) throw new Error('Erreur de chargement');
      const data = await response.json();
      setBreakdown(data.computed.vitality_breakdown);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen) {
      fetchBreakdown();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="ghost" size="sm" className="gap-1">
            <Info className="h-4 w-4" />
            Détails
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            📊 Décomposition Vitalité  -  {territoryName}
          </DialogTitle>
          <DialogDescription>
            Comprendre d&apos;où vient le score de {currentVitality.toFixed(1)}/100
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="text-red-500 p-4 bg-red-50 rounded-lg">
            {error}
          </div>
        )}

        {breakdown && !loading && (
          <div className="space-y-6">
            {/* Score total avec barre */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-muted-foreground">Score total</span>
                <span className="text-2xl font-bold">{breakdown.total.toFixed(1)}</span>
              </div>
              <Progress value={breakdown.total} className="h-3" />
              <p className="text-xs text-muted-foreground">
                Base : {breakdown.base} points
              </p>
            </div>

            {/* Composantes */}
            <div className="space-y-3">
              <h4 className="font-semibold text-sm">Composantes du score</h4>

              {breakdown.components.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  Aucune donnée disponible pour ce territoire
                </p>
              ) : (
                <div className="space-y-2">
                  {breakdown.components.map((comp, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg ${getImpactBg(comp.impact)}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span>{getSourceIcon(comp.source)}</span>
                          <span className="font-medium">{comp.name}</span>
                          <Badge variant="outline" className="text-xs">
                            {comp.source}
                          </Badge>
                        </div>
                        <span className={`font-bold ${getImpactColor(comp.impact)}`}>
                          {comp.impact > 0 ? '+' : ''}{comp.impact.toFixed(1)} pts
                        </span>
                      </div>

                      <div className="flex items-center justify-between mt-2">
                        <span className="text-sm text-muted-foreground">
                          {comp.detail}
                        </span>
                        <ImpactBar impact={comp.impact} />
                      </div>

                      <div className="text-xs text-muted-foreground mt-1">
                        Poids : {comp.weight}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Formule */}
            <div className="pt-4 border-t">
              <h4 className="font-semibold text-sm mb-2">Formule de calcul</h4>
              <code className="text-xs bg-muted p-2 rounded block">
                {breakdown.formula}
              </code>
            </div>

            {/* Légende */}
            <div className="flex gap-4 text-xs text-muted-foreground pt-2 border-t">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-emerald-500" />
                <span>Impact positif</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-rose-500" />
                <span>Impact négatif</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-gray-400" />
                <span>Neutre</span>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
