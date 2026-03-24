'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, X, MapPin, Calendar, Database, ArrowRight, Command, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface SearchResult {
  signal_id: number;
  similarity: number;
  source: string;
  department: string;
  date: string;
  metric: string;
  value: number;
  type: string;
  text: string;
}

interface SearchResponse {
  query: string;
  total_embeddings: number;
  results: SearchResult[];
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalEmbeddings, setTotalEmbeddings] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const router = useRouter();

  // Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults([]);
      setError(null);
    }
  }, [open]);

  // Debounced search
  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/signals/search?q=${encodeURIComponent(q)}&limit=20`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: SearchResponse = await res.json();
      setResults(data.results || []);
      setTotalEmbeddings(data.total_embeddings);
    } catch (err) {
      setError('Erreur lors de la recherche');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 300);
  };

  const handleResultClick = (result: SearchResult) => {
    setOpen(false);
    const dept = result.department?.replace(/\s+/g, '-');
    if (dept) {
      router.push(`/dashboard/departments/${dept}`);
    }
  };

  const sourceColors: Record<string, string> = {
    BODACC: 'bg-[var(--error)]/20 text-[var(--error)] border-[var(--error)]/30',
    BOAMP: 'bg-[var(--warning)]/20 text-[var(--warning)] border-[var(--warning)]/30',
    INSEE: 'bg-primary/20 text-primary border-primary/30',
    DVF: 'bg-[var(--success)]/20 text-[var(--success)] border-[var(--success)]/30',
    ATIH: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    DARES: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  };

  const getSourceClass = (source: string) => {
    const key = Object.keys(sourceColors).find((k) => source?.toUpperCase().includes(k));
    return key ? sourceColors[key] : 'bg-muted/50 text-muted-foreground border-border';
  };

  // Expose open function globally for sidebar trigger
  useEffect(() => {
    (window as any).__openGlobalSearch = () => setOpen(true);
    return () => { delete (window as any).__openGlobalSearch; };
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100]" onClick={() => setOpen(false)}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" />

      {/* Dialog */}
      <div
        className="relative mx-auto mt-[15vh] w-full max-w-2xl px-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="rounded-2xl border border-border bg-card shadow-2xl overflow-hidden">
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <Search className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Recherche semantique dans les signaux..."
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-sm"
            />
            {loading && <Loader2 className="h-4 w-4 text-muted-foreground animate-spin flex-shrink-0" />}
            <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Results */}
          <div className="max-h-[60vh] overflow-y-auto">
            {error && (
              <div className="px-4 py-8 text-center text-sm text-[var(--error)]">{error}</div>
            )}

            {!error && query.length >= 2 && !loading && results.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                {totalEmbeddings === 0
                  ? 'Les embeddings ne sont pas encore prets. Veuillez patienter.'
                  : 'Aucun resultat pour cette recherche.'}
              </div>
            )}

            {!error && query.length < 2 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Tapez au moins 2 caracteres pour lancer la recherche
              </div>
            )}

            {results.map((result) => (
              <button
                key={result.signal_id}
                onClick={() => handleResultClick(result)}
                className="w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors border-b border-border/50 last:border-b-0 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className={cn('text-[10px] px-1.5 py-0', getSourceClass(result.source))}>
                        {result.source}
                      </Badge>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <MapPin className="h-3 w-3" />
                        {result.department}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        {result.date}
                      </span>
                    </div>
                    <p className="text-sm text-foreground mt-1 line-clamp-2">{result.text}</p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground/70">
                      <Database className="h-3 w-3" />
                      <span>{result.metric}</span>
                      {result.value != null && <span className="font-medium">{result.value}</span>}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-xs font-mono text-primary">
                      {(result.similarity * 100).toFixed(0)}%
                    </span>
                    <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-border flex items-center justify-between text-[10px] text-muted-foreground/60">
            <span>Recherche semantique via embeddings</span>
            <div className="flex items-center gap-2">
              <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono">ESC</kbd>
              <span>pour fermer</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
