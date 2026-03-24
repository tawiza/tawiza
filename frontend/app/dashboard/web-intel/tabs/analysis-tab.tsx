'use client';

import { useState, useCallback } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Globe,
  Search,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  Building2,
  Loader2,
  CheckCircle,
  XCircle,
  BarChart3,
  FileText,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Types ───────────────────────────────────────────────────
interface CrawlSignal {
  source: string;
  source_url: string;
  signal_type: string;
  metric_name: string;
  confidence: number;
  event_date: string;
  extracted_text: string;
  raw_data: {
    siret: string;
    nom: string;
    pattern: string;
    details: string;
    snapshots_count: number;
    timeline_start: string;
    timeline_end: string;
  };
}

interface AnalysisResult {
  success: boolean;
  signals_count: number;
  enterprises_analyzed: number;
  signals: CrawlSignal[];
}

interface HealthStatus {
  status: string;
  cdx_api: string;
}

// ─── Helpers ─────────────────────────────────────────────────
const SIGNAL_CONFIG: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  positif: { label: 'Positif', color: 'text-green-500', icon: TrendingUp },
  negatif: { label: 'Negatif', color: 'text-red-500', icon: TrendingDown },
  neutre: { label: 'Neutre', color: 'text-yellow-500', icon: Minus },
};

const METRIC_LABELS: Record<string, string> = {
  site_disparu: 'Site disparu',
  pic_recrutement: 'Pic de recrutement',
  declin_activite: 'Declin activite',
  pivot_entreprise: 'Pivot detecte',
  croissance_entreprise: 'Croissance',
  site_inactif: 'Site inactif',
};

function formatDate(d: string): string {
  if (!d) return '-';
  try {
    return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return d;
  }
}

// ─── Component ───────────────────────────────────────────────
export default function AnalysisTab() {
  // Form state
  const [siret, setSiret] = useState('');
  const [nom, setNom] = useState('');
  const [siteWeb, setSiteWeb] = useState('');
  const [naf, setNaf] = useState('');
  const [codeDept, setCodeDept] = useState('');

  // Results state
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Health state
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(false);

  const checkHealth = useCallback(async () => {
    setCheckingHealth(true);
    try {
      const res = await fetch('/api/v1/crawler/commoncrawl/health');
      if (res.ok) {
        setHealth(await res.json());
      } else {
        setHealth({ status: 'error', cdx_api: 'unreachable' });
      }
    } catch {
      setHealth({ status: 'error', cdx_api: 'unreachable' });
    } finally {
      setCheckingHealth(false);
    }
  }, []);

  const analyzeSingle = useCallback(async () => {
    if (!siteWeb || !nom) {
      setError('Le nom et le site web sont requis');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch('/api/v1/crawler/commoncrawl/analyze/single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          siret: siret || '00000000000000',
          nom,
          site_web: siteWeb,
          naf,
          code_dept: codeDept || null,
          months_back: 12,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Erreur ${res.status}`);
      }

      const data: AnalysisResult = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  }, [siret, nom, siteWeb, naf, codeDept]);

  return (
    <div className="space-y-6">
      {/* Header KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Globe className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Common Crawl</p>
              <p className="text-lg font-bold">CDX Index</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Activity className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Statut API</p>
              {health ? (
                <p className={cn("text-lg font-bold", health.status === 'healthy' ? 'text-green-500' : 'text-red-500')}>
                  {health.status === 'healthy' ? 'En ligne' : 'Hors ligne'}
                </p>
              ) : (
                <Button variant="ghost" size="sm" onClick={checkHealth} disabled={checkingHealth} className="px-0 h-7">
                  {checkingHealth ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verifier'}
                </Button>
              )}
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Signaux detectes</p>
              <p className="text-2xl font-bold">{result?.signals_count ?? '-'}</p>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Clock className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Modele LLM</p>
              <p className="text-lg font-bold">qwen3.5:27b</p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Analysis Form */}
      <GlassCard>
        <GlassCardHeader className="pb-3">
          <GlassCardTitle className="flex items-center gap-2 text-base">
            <Search className="h-4 w-4 text-primary" />
            Analyser une entreprise
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Nom entreprise *</label>
              <Input
                placeholder="Ex: Michelin"
                value={nom}
                onChange={e => setNom(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Site web *</label>
              <Input
                placeholder="Ex: michelin.fr"
                value={siteWeb}
                onChange={e => setSiteWeb(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">SIRET</label>
              <Input
                placeholder="Ex: 85520018900013"
                value={siret}
                onChange={e => setSiret(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Code NAF</label>
              <Input
                placeholder="Ex: 2211Z"
                value={naf}
                onChange={e => setNaf(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Departement</label>
              <Input
                placeholder="Ex: 63"
                value={codeDept}
                onChange={e => setCodeDept(e.target.value)}
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={analyzeSingle}
                disabled={loading || !nom || !siteWeb}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyse en cours...
                  </>
                ) : (
                  <>
                    <Globe className="h-4 w-4 mr-2" />
                    Lancer l&apos;analyse
                  </>
                )}
              </Button>
            </div>
          </div>

          {loading && (
            <div className="mt-4 p-4 rounded-lg bg-muted/30 border border-border/50">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <div>
                  <p className="text-sm font-medium">Analyse en cours</p>
                  <p className="text-xs text-muted-foreground">
                    Recherche dans les archives Common Crawl, extraction WARC, analyse LLM...
                    Cela peut prendre plusieurs minutes.
                  </p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-500" />
                <p className="text-sm text-red-500">{error}</p>
              </div>
            </div>
          )}
        </GlassCardContent>
      </GlassCard>

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <GlassCard>
            <GlassCardHeader className="pb-3">
              <GlassCardTitle className="flex items-center gap-2 text-base">
                <FileText className="h-4 w-4 text-primary" />
                Resultats de l&apos;analyse
                <Badge variant="secondary" className="text-[10px]">
                  {result.signals_count} signal{result.signals_count !== 1 ? 'x' : ''}
                </Badge>
              </GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              {result.signals_count === 0 ? (
                <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/30">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <div>
                    <p className="text-sm font-medium">Aucun pattern anormal detecte</p>
                    <p className="text-xs text-muted-foreground">
                      Le site web est stable et actif sur la periode analysee.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {result.signals.map((sig, i) => {
                    const config = SIGNAL_CONFIG[sig.signal_type] || SIGNAL_CONFIG.neutre;
                    const Icon = config.icon;
                    return (
                      <div
                        key={i}
                        className="p-4 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 transition-colors"
                      >
                        <div className="flex items-start gap-3">
                          <div className={cn("mt-0.5", config.color)}>
                            <Icon className="h-5 w-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold">
                                {METRIC_LABELS[sig.metric_name] || sig.metric_name}
                              </span>
                              <Badge
                                variant="outline"
                                className={cn(
                                  'text-[10px] px-1.5 py-0',
                                  sig.signal_type === 'positif' && 'bg-green-500/10 text-green-500 border-green-500/30',
                                  sig.signal_type === 'negatif' && 'bg-red-500/10 text-red-500 border-red-500/30',
                                  sig.signal_type === 'neutre' && 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30',
                                )}
                              >
                                {config.label}
                              </Badge>
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                Confiance: {(sig.confidence * 100).toFixed(0)}%
                              </Badge>
                            </div>

                            {sig.raw_data?.pattern && (
                              <p className="text-xs text-muted-foreground mt-1">{sig.raw_data.pattern}</p>
                            )}
                            {sig.raw_data?.details && (
                              <p className="text-xs mt-1">{sig.raw_data.details}</p>
                            )}

                            <div className="flex items-center gap-4 mt-2 text-[10px] text-muted-foreground">
                              {sig.raw_data?.nom && (
                                <span className="flex items-center gap-1">
                                  <Building2 className="h-3 w-3" />
                                  {sig.raw_data.nom}
                                </span>
                              )}
                              {sig.raw_data?.snapshots_count && (
                                <span className="flex items-center gap-1">
                                  <Globe className="h-3 w-3" />
                                  {sig.raw_data.snapshots_count} snapshots
                                </span>
                              )}
                              {sig.raw_data?.timeline_start && sig.raw_data?.timeline_end && (
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDate(sig.raw_data.timeline_start)} - {formatDate(sig.raw_data.timeline_end)}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        </>
      )}
    </div>
  );
}
