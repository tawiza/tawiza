'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineBuildingOffice2,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineChartBar,
  HiOutlineXMark,
  HiOutlineUserGroup,
  HiOutlineBanknotes,
  HiOutlineMapPin,
  HiOutlineExclamationTriangle,
} from 'react-icons/hi2';
import { useDepartmentDetails } from '@/hooks';

interface DepartmentPanelProps {
  departmentCode: string | null;
  onClose: () => void;
  onAnalyze?: (code: string) => void;
  className?: string;
}

export default function DepartmentPanel({
  departmentCode,
  onClose,
  onAnalyze,
  className = '',
}: DepartmentPanelProps) {
  const { data: department, isLoading, error } = useDepartmentDetails(departmentCode);

  // Format large numbers
  const formatNumber = (num: number): string => {
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toLocaleString('fr-FR');
  };

  // Format currency
  const formatCurrency = (num: number): string => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(num);
  };

  // Get health score color
  const getHealthColor = (score: number): string => {
    if (score >= 70) return 'var(--success)'; // Green
    if (score >= 50) return 'var(--warning)'; // Yellow
    return 'var(--error)'; // Red
  };

  // Get growth color
  const getGrowthColor = (growth: number): string => {
    if (growth > 0) return 'var(--success)';
    if (growth < 0) return 'var(--error)';
    return 'hsl(var(--border))';
  };

  return (
    <AnimatePresence>
      {departmentCode && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 20 }}
          transition={{ duration: 0.2 }}
          className={`absolute top-4 right-4 w-[320px] sm:w-[360px] z-20 ${className}`}
        >
          <div className="glass rounded-xl shadow-2xl overflow-hidden border border-white/10">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-muted/20">
              <div className="flex items-center gap-2">
                <HiOutlineMapPin className="w-5 h-5 text-primary" />
                {isLoading ? (
                  <div className="h-5 w-32 bg-muted/30 rounded animate-pulse" />
                ) : (
                  <div>
                    <span className="font-medium text-sm">
                      {department?.name || `Departement ${departmentCode}`}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      ({departmentCode})
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-md hover:bg-muted/50 transition-colors"
                title="Fermer"
              >
                <HiOutlineXMark className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="p-4 space-y-4 max-h-[calc(100vh-200px)] overflow-y-auto">
              {isLoading ? (
                <LoadingSkeleton />
              ) : error ? (
                <ErrorState message="Impossible de charger les donnees" />
              ) : department ? (
                <>
                  {/* Health Score */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted/10">
                    <span className="text-sm text-muted-foreground">Score Sante</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: getHealthColor(department.health_score) }}
                      />
                      <span
                        className="text-lg font-bold"
                        style={{ color: getHealthColor(department.health_score || 0) }}
                      >
                        {department.health_score || 0}/100
                      </span>
                    </div>
                  </div>

                  {/* KPIs Grid */}
                  <div className="grid grid-cols-2 gap-3">
                    {/* Enterprises */}
                    <KPICard
                      icon={<HiOutlineBuildingOffice2 className="w-4 h-4" />}
                      label="Entreprises"
                      value={formatNumber(department.enterprises || 0)}
                      trend={department.growth || 0}
                      trendLabel={`${(department.growth || 0) > 0 ? '+' : ''}${(department.growth || 0).toFixed(1)}%`}
                    />

                    {/* Population */}
                    <KPICard
                      icon={<HiOutlineUserGroup className="w-4 h-4" />}
                      label="Population"
                      value={formatNumber(department.population || 0)}
                    />

                    {/* Price m2 */}
                    <KPICard
                      icon={<HiOutlineBanknotes className="w-4 h-4" />}
                      label="Prix m²"
                      value={formatCurrency(department.price_m2 || 0)}
                    />

                    {/* Unemployment */}
                    <KPICard
                      icon={<HiOutlineChartBar className="w-4 h-4" />}
                      label="Chomage"
                      value={`${(department.unemployment_rate || 0).toFixed(1)}%`}
                      warning={(department.unemployment_rate || 0) > 10}
                    />
                  </div>

                  {/* Sector Distribution */}
                  {department.sector_distribution && (
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Repartition Sectorielle
                      </span>
                      <div className="space-y-1.5">
                        {Object.entries(department.sector_distribution as Record<string, number>)
                          .sort(([, a], [, b]) => (b as number) - (a as number))
                          .slice(0, 5)
                          .map(([sector, percentage]) => (
                            <div key={sector} className="flex items-center gap-2">
                              <div className="flex-1 h-2 bg-muted/30 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary/70 rounded-full"
                                  style={{ width: `${percentage}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-muted-foreground w-24 truncate">
                                {sector}
                              </span>
                              <span className="text-[10px] font-medium w-8 text-right">
                                {(percentage as number).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Region & Area */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/30">
                    <span>Region: {department.region}</span>
                    <span>{department.area_km2?.toLocaleString('fr-FR')} km²</span>
                  </div>

                  {/* Analyze Button */}
                  {onAnalyze && (
                    <button
                      onClick={() => onAnalyze(departmentCode)}
                      className="w-full py-2.5 px-4 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                    >
                      <HiOutlineChartBar className="w-4 h-4" />
                      Analyser ce departement
                    </button>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// KPI Card Component
function KPICard({
  icon,
  label,
  value,
  trend,
  trendLabel,
  warning,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  trend?: number;
  trendLabel?: string;
  warning?: boolean;
}) {
  const getTrendIcon = () => {
    if (trend === undefined) return null;
    if (trend > 0) return <HiOutlineArrowTrendingUp className="w-3 h-3 text-[var(--success)]" />;
    if (trend < 0) return <HiOutlineArrowTrendingDown className="w-3 h-3 text-[var(--error)]" />;
    return null;
  };

  return (
    <div className="p-3 rounded-lg bg-muted/10 space-y-1">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-lg font-semibold ${warning ? 'text-[var(--error)]' : ''}`}>
          {value}
        </span>
        {trendLabel && (
          <div className="flex items-center gap-0.5">
            {getTrendIcon()}
            <span
              className="text-[10px]"
              style={{
                color:
                  trend && trend > 0
                    ? 'var(--success)'
                    : trend && trend < 0
                    ? 'var(--error)'
                    : undefined,
              }}
            >
              {trendLabel}
            </span>
          </div>
        )}
        {warning && <HiOutlineExclamationTriangle className="w-4 h-4 text-[var(--error)]" />}
      </div>
    </div>
  );
}

// Loading Skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-12 bg-muted/20 rounded-lg animate-pulse" />
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-muted/20 rounded-lg animate-pulse" />
        ))}
      </div>
      <div className="h-24 bg-muted/20 rounded-lg animate-pulse" />
    </div>
  );
}

// Error State
function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <HiOutlineExclamationTriangle className="w-10 h-10 text-[var(--error)]/50 mb-3" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
