'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/layout';
import { PageLoader } from '@/components/ui/page-loader';
import {
  GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle,
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import {
  Database, Search, ExternalLink, ChevronLeft, ChevronRight,
  Filter, X, Calendar, MapPin, FileText, Clock, ArrowUpDown,
  Newspaper, Briefcase, Home, Factory, Building2, TrendingUp,
  ChevronDown, ChevronUp, Eye, Download,
} from 'lucide-react';
import { DEPT_NAMES } from '@/lib/departments';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// ─── Source metadata ─────────────────────────────────────────
const SOURCE_META: Record<string, { label: string; color: string; Icon: any }> = {
  bodacc: { label: 'BODACC', color: 'var(--primary)', Icon: Factory },
  france_travail: { label: 'France Travail', color: 'var(--chart-2)', Icon: Briefcase },
  dvf: { label: 'DVF', color: 'var(--chart-3)', Icon: Home },
  sirene: { label: 'SIRENE', color: 'var(--chart-4)', Icon: Building2 },
  presse_locale: { label: 'Presse Locale', color: 'var(--warning)', Icon: Newspaper },
  insee: { label: 'INSEE', color: 'var(--chart-5)', Icon: TrendingUp },
  sitadel: { label: 'Sitadel', color: 'var(--success)', Icon: Building2 },
  caf: { label: 'CAF', color: 'var(--info)', Icon: FileText },
  education_nationale: { label: 'Education Nat.', color: 'var(--chart-1)', Icon: FileText },
  ofgl: { label: 'OFGL', color: 'var(--muted-foreground)', Icon: FileText },
  google_trends: { label: 'Google Trends', color: 'var(--chart-2)', Icon: TrendingUp },
  urssaf: { label: 'URSSAF', color: 'var(--chart-3)', Icon: FileText },
};

interface Signal {
  id: number;
  source: string;
  source_url: string | null;
  date: string | null;
  department: string | null;
  commune: string | null;
  metric: string;
  value: number | null;
  type: string | null;
  confidence: number | null;
  excerpt: string | null;
  entities: any;
}

interface SignalDetail {
  id: number;
  source: string;
  source_url: string | null;
  collected_at: string | null;
  date: string | null;
  department: string | null;
  commune: string | null;
  epci: string | null;
  metric: string;
  value: number | null;
  type: string | null;
  confidence: number | null;
  text: string | null;
  entities: any;
}

interface ListResponse {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  signals: Signal[];
}

export default function SignalsPage() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SignalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filters - initialize from URL params
  const [source, setSource] = useState(searchParams.get('source') || '');
  const [dept, setDept] = useState(searchParams.get('dept') || '');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sort, setSort] = useState('recent');
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  // Available sources from stats
  const [sources, setSources] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/signals/stats`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.by_source) setSources(d.by_source.map((s: any) => s.source));
      })
      .catch(() => {});
  }, []);

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (dept) params.set('dept', dept);
    if (search) params.set('q', search);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    params.set('sort', sort);
    params.set('page', String(page));
    params.set('per_page', '30');

    try {
      const r = await fetch(`${API_BASE}/api/v1/signals/list?${params}`);
      if (r.ok) {
        const d = await r.json();
        setData(d);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [source, dept, search, dateFrom, dateTo, sort, page]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  const loadDetail = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setDetailLoading(true);
    try {
      const r = await fetch(`${API_BASE}/api/v1/signals/detail/${id}`);
      if (r.ok) setDetail(await r.json());
    } catch (e) { console.error(e); }
    finally { setDetailLoading(false); }
  };

  const resetFilters = () => {
    setSource(''); setDept(''); setSearch(''); setSearchInput('');
    setDateFrom(''); setDateTo(''); setSort('recent'); setPage(1);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const hasFilters = source || dept || search || dateFrom || dateTo;

  const exportCSV = async () => {
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (dept) params.set('dept', dept);
    if (search) params.set('q', search);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    params.set('sort', sort);
    params.set('per_page', '5000');
    params.set('page', '1');
    try {
      const r = await fetch(`${API_BASE}/api/v1/signals/list?${params}`);
      if (!r.ok) return;
      const d = await r.json();
      const items = d.signals || [];
      if (!items.length) return;
      const header = 'id,source,metric_name,code_dept,metric_value,event_date,signal_type,confidence,extracted_text';
      const rows = items.map((s: any) =>
        [s.id, s.source, s.metric_name, s.code_dept, s.metric_value ?? '', s.event_date ?? '', s.signal_type ?? '', s.confidence ?? '',
         `"${(s.extracted_text || '').replace(/"/g, '""').substring(0, 500)}"`].join(',')
      );
      const csv = [header, ...rows].join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `signaux_tawiza_${new Date().toISOString().slice(0,10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
  };

  const getSourceMeta = (s: string) => SOURCE_META[s] || { label: s, color: 'var(--muted-foreground)', Icon: FileText };

  const formatMetric = (m: string) => m.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <DashboardLayout
      title="Explorateur de Signaux"
      description={`${data?.total?.toLocaleString('fr-FR') || '...'} signaux collectes`}
    >
      <div className="space-y-4">
        {/* Search bar + filter toggle */}
        <div className="flex gap-2 items-center">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder="Rechercher dans les signaux..."
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-muted/30 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <Button type="submit" size="sm">Rechercher</Button>
          </form>
          <Button
            variant={showFilters ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            className="gap-1"
          >
            <Filter className="h-3.5 w-3.5" />
            Filtres
            {hasFilters && <span className="ml-1 w-2 h-2 rounded-full bg-[var(--warning)]" />}
          </Button>
          <Button variant="outline" size="sm" onClick={exportCSV} className="gap-1" title="Exporter CSV">
            <Download className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <GlassCard>
            <GlassCardContent className="pt-4 pb-3">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Source</label>
                  <select
                    value={source}
                    onChange={e => { setSource(e.target.value); setPage(1); }}
                    className="w-full px-2 py-1.5 rounded bg-muted/40 border border-border text-sm"
                  >
                    <option value="">Toutes</option>
                    {sources.map(s => (
                      <option key={s} value={s}>{getSourceMeta(s).label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Departement</label>
                  <input
                    type="text"
                    value={dept}
                    onChange={e => { setDept(e.target.value); setPage(1); }}
                    placeholder="Ex: 75"
                    className="w-full px-2 py-1.5 rounded bg-muted/40 border border-border text-sm"
                    maxLength={3}
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Date debut</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={e => { setDateFrom(e.target.value); setPage(1); }}
                    className="w-full px-2 py-1.5 rounded bg-muted/40 border border-border text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Date fin</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={e => { setDateTo(e.target.value); setPage(1); }}
                    className="w-full px-2 py-1.5 rounded bg-muted/40 border border-border text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Tri</label>
                  <select
                    value={sort}
                    onChange={e => { setSort(e.target.value); setPage(1); }}
                    className="w-full px-2 py-1.5 rounded bg-muted/40 border border-border text-sm"
                  >
                    <option value="recent">Plus recent</option>
                    <option value="oldest">Plus ancien</option>
                    <option value="score">Score</option>
                  </select>
                </div>
              </div>
              {hasFilters && (
                <div className="mt-3 flex justify-end">
                  <Button variant="ghost" size="sm" onClick={resetFilters} className="gap-1 text-xs">
                    <X className="h-3 w-3" /> Reinitialiser
                  </Button>
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        )}

        {/* Results */}
        <div className="space-y-2">
          {loading ? (
            <PageLoader />
          ) : data?.signals.length === 0 ? (
            <GlassCard>
              <GlassCardContent className="py-12 text-center text-muted-foreground">
                Aucun signal trouve avec ces filtres.
              </GlassCardContent>
            </GlassCard>
          ) : (
            data?.signals.map((sig) => {
              const meta = getSourceMeta(sig.source);
              const Icon = meta.Icon;
              const isExpanded = expandedId === sig.id;

              return (
                <GlassCard key={sig.id} className="transition-all hover:border-primary/30">
                  {/* Compact row */}
                  <div
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => loadDetail(sig.id)}
                  >
                    <div className="flex items-start gap-3">
                      {/* Source badge */}
                      <div
                        className="shrink-0 flex items-center justify-center w-9 h-9 rounded-lg"
                        style={{ backgroundColor: `color-mix(in srgb, ${meta.color} 15%, transparent)` }}
                      >
                        <Icon className="h-4 w-4" style={{ color: meta.color }} />
                      </div>

                      {/* Main content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                            style={{
                              color: meta.color,
                              backgroundColor: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
                            }}
                          >
                            {meta.label}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {formatMetric(sig.metric)}
                          </span>
                          {sig.department && (
                            <span className="text-[10px] font-mono bg-muted/50 px-1.5 py-0.5 rounded">
                              {sig.department} {DEPT_NAMES[sig.department] || ''}
                            </span>
                          )}
                          {sig.value != null && (
                            <span className="text-xs font-mono font-semibold text-primary">
                              {sig.value.toLocaleString('fr-FR')}
                            </span>
                          )}
                        </div>
                        {sig.excerpt && (
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                            {sig.excerpt}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-1.5">
                          {sig.date && (
                            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {new Date(sig.date).toLocaleDateString('fr-FR')}
                            </span>
                          )}
                          {sig.source_url && (
                            <a
                              href={sig.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[10px] text-primary hover:underline flex items-center gap-1"
                              onClick={e => e.stopPropagation()}
                            >
                              <ExternalLink className="h-3 w-3" />
                              Source
                            </a>
                          )}
                          {sig.confidence != null && (
                            <span className="text-[10px] text-muted-foreground">
                              Confiance: {(sig.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Expand icon */}
                      <div className="shrink-0 mt-1">
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-border/50">
                      {detailLoading ? (
                        <div className="py-6 flex justify-center">
                          <div className="animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full" />
                        </div>
                      ) : detail ? (
                        <div className="pt-3 space-y-3">
                          {/* Meta grid */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                            {detail.department && (
                              <div className="bg-muted/20 rounded p-2">
                                <span className="text-muted-foreground block text-[10px]">Departement</span>
                                <span className="font-medium">{detail.department} — {DEPT_NAMES[detail.department] || ''}</span>
                              </div>
                            )}
                            {detail.commune && (
                              <div className="bg-muted/20 rounded p-2">
                                <span className="text-muted-foreground block text-[10px]">Commune</span>
                                <span className="font-medium">{detail.commune}</span>
                              </div>
                            )}
                            {detail.epci && (
                              <div className="bg-muted/20 rounded p-2">
                                <span className="text-muted-foreground block text-[10px]">EPCI</span>
                                <span className="font-medium">{detail.epci}</span>
                              </div>
                            )}
                            {detail.collected_at && (
                              <div className="bg-muted/20 rounded p-2">
                                <span className="text-muted-foreground block text-[10px]">Collecte</span>
                                <span className="font-medium">
                                  {new Date(detail.collected_at).toLocaleString('fr-FR')}
                                </span>
                              </div>
                            )}
                          </div>

                          {/* Full text */}
                          {detail.text && (
                            <div className="bg-muted/10 border border-border/30 rounded-lg p-3">
                              <p className="text-xs text-muted-foreground mb-1 font-medium">Contenu integral</p>
                              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                {detail.text}
                              </p>
                            </div>
                          )}

                          {/* Source link */}
                          {detail.source_url && (
                            <a
                              href={detail.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-2 text-sm text-primary hover:underline bg-primary/5 px-3 py-2 rounded-lg"
                            >
                              <ExternalLink className="h-4 w-4" />
                              Voir la source originale
                            </a>
                          )}

                          {/* Entities */}
                          {detail.entities && typeof detail.entities === 'object' && Object.keys(detail.entities).length > 0 && (
                            <div>
                              <p className="text-xs text-muted-foreground mb-1 font-medium">Entites extraites</p>
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(detail.entities).map(([k, v]) => (
                                  <span key={k} className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                                    {k}: {String(v)}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : null}
                    </div>
                  )}
                </GlassCard>
              );
            })
          )}
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Page {data.page} / {data.pages} ({data.total.toLocaleString('fr-FR')} resultats)
            </p>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              {/* Page numbers */}
              {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                const start = Math.max(1, Math.min(page - 2, data.pages - 4));
                const p = start + i;
                if (p > data.pages) return null;
                return (
                  <Button
                    key={p}
                    variant={p === page ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setPage(p)}
                    className="w-8"
                  >
                    {p}
                  </Button>
                );
              })}
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage(p => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
