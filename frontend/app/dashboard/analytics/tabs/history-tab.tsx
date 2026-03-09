'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardDescription,
  GlassCardHeader,
  GlassCardTitle
} from '@/components/ui/glass-card';
import { Button } from '@/components/ui/button';
import { CognitiveBarChart } from '@/components/dashboard/CognitiveBarChart';
import Link from 'next/link';
import {
  HiOutlineChatBubbleLeftRight,
  HiOutlineChartBar,
  HiOutlineCheckCircle,
  HiOutlineClock,
  HiOutlineExclamationCircle,
  HiOutlineMapPin,
  HiOutlinePlus,
  HiOutlineSignal
} from 'react-icons/hi2';
import { cn } from '@/lib/utils';
import { getAnalytics, getRecentAnalyses, type AnalyticsData, type RecentAnalysis } from '@/lib/api';
import { useTAJINEWebSocket } from '@/hooks/use-tajine-websocket';

// Metric card for analytics
function AnalyticsMetricCard({
  title,
  value,
  description,
  icon: Icon,
  glow = 'cyan'
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  glow?: 'cyan' | 'green' | 'red';
}) {
  return (
    <GlassCard glow={glow} hoverGlow>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        </div>
        <Icon className="h-8 w-8 text-primary opacity-50" />
      </div>
    </GlassCard>
  );
}

// Department type for top departments
interface TopDepartment {
  code: string;
  name: string;
  count: number;
  change: string;
}

// Top departments card
function TopDepartmentsCard({ departments }: { departments: TopDepartment[] }) {
  return (
    <GlassCard glow="cyan" hoverGlow>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineMapPin className="h-5 w-5 text-primary" />
          Top 5 Departements
        </GlassCardTitle>
        <GlassCardDescription>
          Les plus analyses ce mois
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        <div className="space-y-3">
          {departments.map((dept, i) => (
            <div key={dept.code} className="flex items-center gap-3">
              <span className="text-lg font-bold text-muted-foreground w-6">
                {i + 1}
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-primary text-sm">{dept.code}</span>
                  <span className="font-medium">{dept.name}</span>
                </div>
              </div>
              <div className="text-right">
                <span className="font-bold">{dept.count}</span>
                <span className={cn(
                  "text-xs ml-2",
                  dept.change.startsWith('+') ? 'text-[var(--success)]' :
                  dept.change === '0' ? 'text-muted-foreground' : 'text-[var(--error)]'
                )}>
                  {dept.change}
                </span>
              </div>
            </div>
          ))}
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}

// Analysis item type
interface AnalysisItem {
  id: string | number;
  query: string;
  department: string;
  status: 'completed' | 'error' | 'pending';
  time: string;
  duration: string;
}

// Recent analyses card
function RecentAnalysesCard({ analyses }: { analyses: AnalysisItem[] }) {
  return (
    <GlassCard glow="cyan" hoverGlow className="lg:col-span-2">
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBar className="h-5 w-5 text-primary" />
          Analyses Recentes
        </GlassCardTitle>
        <GlassCardDescription>
          Historique des dernieres analyses TAJINE
        </GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {analyses.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>Aucune analyse recente</p>
            <Link href="/dashboard/ai-chat" className="text-primary hover:underline text-sm mt-2 inline-block">
              Demarrer une analyse
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {analyses.map((analysis) => (
                <div
                  key={analysis.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-normal cursor-pointer"
                >
                  {/* Status icon */}
                  <div className="mt-0.5">
                    {analysis.status === 'completed' ? (
                      <HiOutlineCheckCircle className="h-5 w-5 text-[var(--success)]" />
                    ) : analysis.status === 'pending' ? (
                      <HiOutlineClock className="h-5 w-5 text-[var(--warning)]" />
                    ) : (
                      <HiOutlineExclamationCircle className="h-5 w-5 text-[var(--error)]" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{analysis.query}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <span>{analysis.department}</span>
                      <span>{analysis.time}</span>
                      {analysis.duration !== '-' && (
                        <span className="flex items-center gap-1">
                          <HiOutlineClock className="h-3 w-3" />
                          {analysis.duration}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* View all link */}
            <div className="mt-4 text-center">
              <Link href="/dashboard/ai-chat" className="text-sm text-primary hover:underline">
                Voir toutes les analyses
              </Link>
            </div>
          </>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

// Default analytics data (fallback when backend unavailable)
const DEFAULT_ANALYTICS: AnalyticsData = {
  totalAnalyses: 0,
  analysesThisMonth: 0,
  successRate: 0,
  avgDuration: 0,
  cognitiveDistribution: [],
  topDepartments: [],
  recentAnalyses: [],
};

// Default departments (fallback)
const DEFAULT_TOP_DEPARTMENTS: TopDepartment[] = [
  { code: '75', name: 'Paris', count: 0, change: '0' },
  { code: '69', name: 'Rhone', count: 0, change: '0' },
  { code: '13', name: 'Bouches-du-Rhone', count: 0, change: '0' },
  { code: '33', name: 'Gironde', count: 0, change: '0' },
  { code: '31', name: 'Haute-Garonne', count: 0, change: '0' },
];

export default function HistoryTab() {
  const [analytics, setAnalytics] = useState<AnalyticsData>(DEFAULT_ANALYTICS);
  const [recentAnalyses, setRecentAnalyses] = useState<AnalysisItem[]>([]);
  const [topDepartments, setTopDepartments] = useState<TopDepartment[]>(DEFAULT_TOP_DEPARTMENTS);
  const [isConnected, setIsConnected] = useState(false);

  // WebSocket for real-time updates
  const { isConnected: wsConnected, currentTask } = useTAJINEWebSocket();
  const prevTaskRef = useRef<{ taskId: string; phase: string } | null>(null);

  const fetchData = useCallback(async () => {
    const [analyticsData, analysesData] = await Promise.all([
      getAnalytics(),
      getRecentAnalyses(5),
    ]);

    if (analyticsData) {
      setAnalytics(analyticsData);
      setIsConnected(true);

      // Update top departments from analytics data
      if (analyticsData.topDepartments && analyticsData.topDepartments.length > 0) {
        setTopDepartments(analyticsData.topDepartments);
      }

      // Update recent analyses from analytics data
      if (analyticsData.recentAnalyses && analyticsData.recentAnalyses.length > 0) {
        setRecentAnalyses(analyticsData.recentAnalyses.map(a => ({
          ...a,
          status: a.status as 'completed' | 'error' | 'pending',
        })));
      }
    }

    // Also check direct recent analyses endpoint
    if (analysesData && analysesData.length > 0) {
      setRecentAnalyses(analysesData.map(a => ({
        ...a,
        status: a.status as 'completed' | 'error' | 'pending',
      })));
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Auto-refresh when a TAJINE task completes via WebSocket
  useEffect(() => {
    if (!currentTask) {
      // Task ended - check if previous was running
      if (prevTaskRef.current) {
        // Task just completed, refresh data
        fetchData();
        prevTaskRef.current = null;
      }
      return;
    }

    // Track current task state
    prevTaskRef.current = {
      taskId: currentTask.taskId,
      phase: currentTask.phase || 'unknown',
    };
  }, [currentTask, fetchData]);

  return (
    <div className="h-full w-full space-y-6">
      {/* Connection status indicator */}
      {!isConnected && (
        <div className="glass p-3 rounded-lg border-l-4 border-[var(--warning)]">
          <p className="text-sm text-muted-foreground">
            Backend non connecte - affichage des donnees par defaut
          </p>
        </div>
      )}

      {/* WebSocket real-time indicator */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <HiOutlineSignal className={cn(
          "h-4 w-4 transition-colors",
          wsConnected ? "text-[var(--success)]" : "text-muted-foreground"
        )} />
        <span>
          {wsConnected ? "Synchronisation temps reel active" : "Mode polling (30s)"}
        </span>
        {currentTask && (
          <span className="text-primary animate-pulse">
            • Analyse en cours: {currentTask.phase}
          </span>
        )}
      </div>

      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analyses TAJINE</h1>
          <p className="text-sm text-muted-foreground">
            Statistiques et historique des analyses
          </p>
        </div>

        <Link href="/dashboard/ai-chat">
          <Button className="gap-2 transition-normal hover:glow-cyan">
            <HiOutlinePlus className="h-4 w-4" />
            Nouvelle analyse
          </Button>
        </Link>
      </div>

      {/* Metrics row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <AnalyticsMetricCard
          title="Total Analyses"
          value={analytics.totalAnalyses.toString()}
          description="Depuis le debut"
          icon={HiOutlineChartBar}
        />
        <AnalyticsMetricCard
          title="Ce mois"
          value={analytics.analysesThisMonth.toString()}
          description="Analyses ce mois"
          icon={HiOutlineChatBubbleLeftRight}
          glow="green"
        />
        <AnalyticsMetricCard
          title="Taux de succes"
          value={`${analytics.successRate.toFixed(0)}%`}
          description="Analyses reussies"
          icon={HiOutlineCheckCircle}
          glow="green"
        />
        <AnalyticsMetricCard
          title="Temps moyen"
          value={`${analytics.avgDuration.toFixed(1)}s`}
          description="Par analyse"
          icon={HiOutlineClock}
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <CognitiveBarChart
          data={analytics.cognitiveDistribution.length > 0
            ? analytics.cognitiveDistribution.map((d, i) => ({
                level: d.level,
                count: d.count,
                color: ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)'][i] || 'var(--info)'
              }))
            : undefined
          }
        />
        <TopDepartmentsCard departments={topDepartments} />
      </div>

      {/* Recent analyses */}
      <div className="grid gap-6 lg:grid-cols-3">
        <RecentAnalysesCard analyses={recentAnalyses} />
      </div>
    </div>
  );
}
