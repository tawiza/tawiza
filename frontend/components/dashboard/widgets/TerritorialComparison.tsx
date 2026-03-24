'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Loader2,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  RefreshCw,
  Building2,
  Briefcase,
  Home,
  Users,
  Activity,
  Info
} from 'lucide-react';
import VitalityBreakdown from './VitalityBreakdown';

interface TerritoryData {
  code: string;
  name: string;
  creations: number;
  closures: number;
  procedures: number;
  net_creation: number;
  vitality_index: number;
  job_offers?: number;
  unemployment_rate?: number;
  real_estate_tx?: number;
  avg_price_sqm?: number;
  error?: string;
}

interface ComparisonData {
  territories: TerritoryData[];
  generated_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function getVitalityColor(index: number): string {
  if (index >= 55) return 'text-emerald-500';
  if (index >= 45) return 'text-amber-500';
  return 'text-rose-500';
}

function getVitalityBgColor(index: number): string {
  if (index >= 55) return 'bg-emerald-500';
  if (index >= 45) return 'bg-amber-500';
  return 'bg-rose-500';
}

function getVitalityBadge(index: number): { variant: 'default' | 'secondary' | 'destructive'; label: string; emoji: string } {
  if (index >= 55) return { variant: 'default', label: 'Dynamique', emoji: '🟢' };
  if (index >= 45) return { variant: 'secondary', label: 'Stable', emoji: '🟡' };
  return { variant: 'destructive', label: 'Vigilance', emoji: '🔴' };
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
}

function TerritoryCard({ territory }: { territory: TerritoryData }) {
  const badge = getVitalityBadge(territory.vitality_index);

  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
      {/* Header avec vitalité */}
      <div className={`p-4 ${territory.vitality_index >= 55 ? 'bg-emerald-50 dark:bg-emerald-950/30' : territory.vitality_index >= 45 ? 'bg-amber-50 dark:bg-amber-950/30' : 'bg-rose-50 dark:bg-rose-950/30'}`}>
        <div className="flex justify-between items-start">
          <div>
            <h3 className="font-bold text-lg">{territory.name}</h3>
            <p className="text-sm text-muted-foreground">Dept. {territory.code}</p>
          </div>
          <div className="text-right">
            <VitalityBreakdown
              territoryCode={territory.code}
              territoryName={territory.name}
              currentVitality={territory.vitality_index}
              trigger={
                <button className="group cursor-pointer">
                  <div className={`text-3xl font-bold ${getVitalityColor(territory.vitality_index)} group-hover:underline`}>
                    {territory.vitality_index.toFixed(1)}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                    <Info className="h-3 w-3" />
                    Voir détails
                  </div>
                </button>
              }
            />
            <Badge variant={badge.variant} className="mt-1">
              {badge.emoji} {badge.label}
            </Badge>
          </div>
        </div>

        {/* Barre de vitalité */}
        <div className="mt-3">
          <Progress
            value={territory.vitality_index}
            className="h-2"
          />
        </div>
      </div>

      {/* Métriques */}
      <CardContent className="p-4 grid grid-cols-2 gap-4">
        {/* Entreprises */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Building2 className="h-4 w-4" />
            Entreprises
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-emerald-600">+{territory.creations} créations</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-rose-600">-{territory.closures} fermetures</span>
          </div>
          <div className={`font-bold ${territory.net_creation >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
            Solde: {territory.net_creation >= 0 ? '+' : ''}{territory.net_creation}
          </div>
        </div>

        {/* Emploi */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Briefcase className="h-4 w-4" />
            Emploi
          </div>
          {territory.job_offers !== undefined && (
            <div className="text-sm">
              <span className="font-medium">{territory.job_offers}</span> offres actives
            </div>
          )}
          {territory.unemployment_rate !== undefined && territory.unemployment_rate > 0 && (
            <div className={`text-sm font-bold ${territory.unemployment_rate > 8 ? 'text-rose-600' : territory.unemployment_rate < 6 ? 'text-emerald-600' : 'text-amber-600'}`}>
              Chômage: {territory.unemployment_rate.toFixed(1)}%
            </div>
          )}
          {territory.procedures > 0 && (
            <div className="text-sm text-orange-600">
              ⚠️ {territory.procedures} procédures
            </div>
          )}
        </div>

        {/* Immobilier (si disponible) */}
        {(territory.real_estate_tx !== undefined && territory.real_estate_tx > 0) && (
          <div className="col-span-2 pt-2 border-t space-y-1">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Home className="h-4 w-4" />
              Immobilier
            </div>
            <div className="flex justify-between text-sm">
              <span>{territory.real_estate_tx} transactions</span>
              {territory.avg_price_sqm !== undefined && territory.avg_price_sqm > 0 && (
                <span className="font-medium">{formatNumber(territory.avg_price_sqm)} €/m²</span>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function TerritorialComparison() {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [departments, setDepartments] = useState('75,69,13,33,59');
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/territorial/compare?departments=${encodeURIComponent(departments)}`
      );
      if (!response.ok) throw new Error('Erreur de chargement');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-xl font-bold flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Comparatif Territorial
            </CardTitle>
            <CardDescription>
              Indicateurs économiques multi-sources en temps réel
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant={viewMode === 'cards' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('cards')}
            >
              Cartes
            </Button>
            <Button
              variant={viewMode === 'table' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('table')}
            >
              Tableau
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <Input
            placeholder="Départements (ex: 75,69,13)"
            value={departments}
            onChange={(e) => setDepartments(e.target.value)}
            className="max-w-xs"
          />
          <Button onClick={fetchData} disabled={loading}>
            Comparer
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {error && (
          <div className="text-red-500 p-4 bg-red-50 rounded-lg mb-4">
            {error}
          </div>
        )}

        {loading && !data && (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {data && viewMode === 'cards' && (
          <div className="space-y-6">
            {/* Cartes territoriales */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.territories.map((t) => (
                <TerritoryCard key={t.code} territory={t} />
              ))}
            </div>

            {/* Sources de données */}
            <div className="flex flex-wrap gap-2 pt-4 border-t">
              <Badge variant="outline" className="text-xs">
                <Building2 className="h-3 w-3 mr-1" /> SIRENE
              </Badge>
              <Badge variant="outline" className="text-xs">
                📋 BODACC
              </Badge>
              <Badge variant="outline" className="text-xs">
                <Briefcase className="h-3 w-3 mr-1" /> France Travail
              </Badge>
              <Badge variant="outline" className="text-xs">
                <Users className="h-3 w-3 mr-1" /> INSEE
              </Badge>
              <Badge variant="outline" className="text-xs">
                <Home className="h-3 w-3 mr-1" /> DVF
              </Badge>
            </div>

            <p className="text-xs text-muted-foreground">
              Généré: {new Date(data.generated_at).toLocaleString('fr-FR')}
            </p>
          </div>
        )}

        {data && viewMode === 'table' && (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-3 font-medium">Département</th>
                    <th className="text-right p-3 font-medium">Vitalité</th>
                    <th className="text-right p-3 font-medium">Solde</th>
                    <th className="text-right p-3 font-medium">Offres</th>
                    <th className="text-right p-3 font-medium">Chômage</th>
                    <th className="text-right p-3 font-medium">Immo.</th>
                    <th className="text-center p-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.territories.map((t) => (
                    <tr key={t.code} className="border-b hover:bg-muted/50">
                      <td className="p-3">
                        <div className="font-medium">{t.name}</div>
                        <div className="text-xs text-muted-foreground">Dept. {t.code}</div>
                      </td>
                      <td className={`text-right p-3 font-bold text-lg ${getVitalityColor(t.vitality_index)}`}>
                        <VitalityBreakdown
                          territoryCode={t.code}
                          territoryName={t.name}
                          currentVitality={t.vitality_index}
                          trigger={
                            <button className="hover:underline cursor-pointer">
                              {t.vitality_index.toFixed(1)}
                            </button>
                          }
                        />
                      </td>
                      <td className="text-right p-3">
                        <span className={`font-medium ${t.net_creation >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                          {t.net_creation >= 0 ? '+' : ''}{t.net_creation}
                        </span>
                      </td>
                      <td className="text-right p-3">
                        {t.job_offers || '-'}
                      </td>
                      <td className="text-right p-3">
                        {t.unemployment_rate ? (
                          <span className={t.unemployment_rate > 8 ? 'text-rose-600 font-medium' : ''}>
                            {t.unemployment_rate.toFixed(1)}%
                          </span>
                        ) : '-'}
                      </td>
                      <td className="text-right p-3">
                        {t.real_estate_tx || '-'}
                      </td>
                      <td className="text-center p-3">
                        <Badge variant={getVitalityBadge(t.vitality_index).variant}>
                          {getVitalityBadge(t.vitality_index).emoji} {getVitalityBadge(t.vitality_index).label}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Légende */}
            <div className="flex gap-4 text-sm text-muted-foreground pt-4 border-t">
              <div className="flex items-center gap-1">
                <TrendingUp className="h-4 w-4 text-emerald-500" />
                <span>Dynamique &gt; 55</span>
              </div>
              <div className="flex items-center gap-1">
                <TrendingDown className="h-4 w-4 text-amber-500" />
                <span>Stable 45-55</span>
              </div>
              <div className="flex items-center gap-1">
                <AlertTriangle className="h-4 w-4 text-rose-500" />
                <span>Vigilance &lt; 45</span>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              Sources: SIRENE • BODACC • France Travail • INSEE • DVF | Généré: {new Date(data.generated_at).toLocaleString('fr-FR')}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
