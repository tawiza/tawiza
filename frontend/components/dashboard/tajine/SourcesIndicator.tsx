'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineServerStack,
  HiOutlineSignal,
  HiOutlineExclamationCircle,
  HiOutlineCheckCircle,
  HiOutlineArrowPath,
} from 'react-icons/hi2';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  AdapterHealth,
  useSourcesHealth,
} from '@/hooks/use-sources-health';

interface SourcesIndicatorProps {
  className?: string;
}

// Helper functions
const calculateHealthPercentage = (health: any) => {
  if (!health?.adapters?.length) return 0;
  const up = health.adapters.filter((a: any) => a.status === 'up').length;
  return (up / health.adapters.length) * 100;
};

const getCategoryLabel = (category: string) => {
  const labels: Record<string, string> = {
    official: 'Officielles (INSEE, SIRENE)',
    legal: 'Legales (BODACC, BOAMP)',
    real_estate: 'Immobilier (DVF)',
    news: 'Actualites',
    territorial: 'Territoire',
  };
  return labels[category] || category;
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'up': return '✅';
    case 'down': return '❌';
    case 'degraded': return '⚠️';
    default: return '⚪';
  }
};

export default function SourcesIndicator({ className = '' }: SourcesIndicatorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { data: health, isLoading, error, mutate } = useSourcesHealth({ quick: true });

  // Calculate status
  const healthPercent = health ? calculateHealthPercentage(health) : 0;
  const statusColor =
    healthPercent >= 90
      ? 'var(--success)' // Green
      : healthPercent >= 70
      ? 'var(--warning)' // Yellow
      : 'var(--error)'; // Red

  const statusIcon =
    healthPercent >= 90 ? (
      <HiOutlineCheckCircle className="w-4 h-4" style={{ color: statusColor }} />
    ) : healthPercent >= 70 ? (
      <HiOutlineSignal className="w-4 h-4" style={{ color: statusColor }} />
    ) : (
      <HiOutlineExclamationCircle className="w-4 h-4" style={{ color: statusColor }} />
    );

  // Group adapters by category
  const adaptersByCategory = health?.adapters.reduce(
    (acc, adapter) => {
      const cat = adapter.category;
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(adapter);
      return acc;
    },
    {} as Record<string, AdapterHealth[]>
  );

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all glass hover:bg-white/10 ${className}`}
        >
          <HiOutlineServerStack className="w-4 h-4 text-muted-foreground" />
          <span className="hidden sm:inline">Sources</span>
          {isLoading ? (
            <HiOutlineArrowPath className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
          ) : error ? (
            <span className="flex items-center gap-1 text-[var(--error)]">
              <HiOutlineExclamationCircle className="w-3.5 h-3.5" />
              Erreur
            </span>
          ) : (
            <span className="flex items-center gap-1" style={{ color: statusColor }}>
              {statusIcon}
              {health?.online}/{health?.total}
            </span>
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent className="w-80 p-0" align="end">
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
              <div className="flex items-center gap-2">
                <HiOutlineServerStack className="w-5 h-5 text-primary" />
                <span className="font-medium text-sm">Sources de donnees</span>
              </div>
              <button
                onClick={() => mutate()}
                className="p-1.5 rounded-md hover:bg-muted/50 transition-colors"
                title="Rafraichir"
              >
                <HiOutlineArrowPath
                  className={`w-4 h-4 text-muted-foreground ${isLoading ? 'animate-spin' : ''}`}
                />
              </button>
            </div>

            {/* Health Summary */}
            {health && (
              <div className="px-4 py-3 border-b border-border/50 bg-muted/10">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Sante globale</span>
                  <span
                    className="text-sm font-semibold"
                    style={{ color: statusColor }}
                  >
                    {healthPercent}%
                  </span>
                </div>
                {/* Progress bar */}
                <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${healthPercent}%` }}
                    transition={{ duration: 0.5 }}
                    className="h-full rounded-full"
                    style={{ backgroundColor: statusColor }}
                  />
                </div>
                {/* Stats row */}
                <div className="flex items-center justify-between mt-2 text-[10px]">
                  <span className="flex items-center gap-1 text-[var(--success)]">
                    <span className="w-2 h-2 rounded-full bg-[var(--success)]" />
                    {health.online} en ligne
                  </span>
                  <span className="flex items-center gap-1 text-[var(--warning)]">
                    <span className="w-2 h-2 rounded-full bg-[var(--warning)]" />
                    {health.degraded} degradee
                  </span>
                  <span className="flex items-center gap-1 text-[var(--error)]">
                    <span className="w-2 h-2 rounded-full bg-[var(--error)]" />
                    {health.offline} hors ligne
                  </span>
                </div>
              </div>
            )}

            {/* Adapters by Category */}
            <div className="max-h-[300px] overflow-y-auto">
              {adaptersByCategory &&
                Object.entries(adaptersByCategory).map(([category, adapters]) => (
                  <div key={category} className="px-4 py-2 border-b border-border/30 last:border-0">
                    <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                      {getCategoryLabel(category as AdapterHealth['category'])}
                    </div>
                    <div className="space-y-1">
                      {(adapters as any[]).map((adapter) => (
                        <div
                          key={adapter.name}
                          className="flex items-center justify-between py-1"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-sm">
                              {getStatusIcon(adapter.status)}
                            </span>
                            <span className="text-xs">
                              {adapter.name.replace('Adapter', '')}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            {adapter.latency_ms && (
                              <span className="text-[10px] text-muted-foreground">
                                {Math.round(adapter.latency_ms)}ms
                              </span>
                            )}
                            {adapter.error && (
                              <span
                                className="text-[10px] text-[var(--error)] max-w-[80px] truncate"
                                title={adapter.error}
                              >
                                {adapter.error}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>

            {/* Footer */}
            <div className="px-4 py-2 border-t border-border/50 bg-muted/10">
              <span className="text-[10px] text-muted-foreground">
                Derniere verif: {health?.checked_at ? new Date(health.checked_at).toLocaleTimeString('fr-FR') : '-'}
              </span>
            </div>
          </motion.div>
        </AnimatePresence>
      </PopoverContent>
    </Popover>
  );
}
