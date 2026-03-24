'use client';

import { useCallback, useEffect, useState } from 'react';
import useSWR from 'swr';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { HiOutlineExclamationTriangle, HiOutlineArrowTrendingDown, HiOutlineArrowTrendingUp } from 'react-icons/hi2';
import Link from 'next/link';

interface Alert {
  code: string;
  name: string;
  severity: 'critical' | 'warning' | 'info';
  type: string;
  message: string;
  value: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const severityConfig = {
  critical: {
    color: 'bg-red-500/20 text-red-400 border-red-500/30',
    icon: '🔴',
    glow: 'red' as const,
  },
  warning: {
    color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    icon: '🟡',
    glow: 'cyan' as const,
  },
  info: {
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    icon: '🔵',
    glow: 'cyan' as const,
  },
};

export function AlertsWidget({ limit = 5 }: { limit?: number }) {
  const { data, error, isLoading } = useSWR<Alert[] | { detail?: string }>(
    `/api/v1/territorial/alerts?limit=${limit}`,
    fetcher,
    {
      refreshInterval: 60000, // Refresh every minute
      revalidateOnFocus: false,
    }
  );

  // Handle both array and error object responses
  const alerts = Array.isArray(data) ? data : [];
  const hasAlerts = alerts.length > 0;
  const criticalCount = alerts.filter((a) => a.severity === 'critical').length;

  // Determine card glow based on severity
  const cardGlow = criticalCount > 0 ? 'red' : hasAlerts ? 'cyan' : 'green';

  if (error) {
    return (
      <GlassCard glow="red">
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineExclamationTriangle className="h-5 w-5 text-red-400" />
            Alertes Territoriales
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground">Erreur de chargement</p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow={cardGlow} hoverGlow>
      <GlassCardHeader className="flex flex-row items-center justify-between pb-2">
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineExclamationTriangle className="h-5 w-5 text-primary" />
          Alertes Territoriales
        </GlassCardTitle>
        {hasAlerts && (
          <Badge variant="outline" className="text-xs">
            {alerts.length}
          </Badge>
        )}
      </GlassCardHeader>
      <GlassCardContent>
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-muted/20 rounded animate-pulse" />
            ))}
          </div>
        ) : !hasAlerts ? (
          <div className="text-center py-4 text-sm text-muted-foreground">
            <span className="text-green-400">✓</span> Aucune alerte active
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert, i) => {
              const config = severityConfig[alert.severity];
              const isNegative = alert.value < 0;
              return (
                <Link
                  key={i}
                  href={`/dashboard/tajine?dept=${alert.code}`}
                  className="block"
                >
                  <div
                    className={`p-2 rounded-md border ${config.color} hover:bg-white/5 transition-colors cursor-pointer`}
                  >
                    <div className="flex items-center gap-2">
                      <span>{config.icon}</span>
                      <span className="font-medium text-sm">
                        {alert.code} {alert.name}
                      </span>
                      {/* Show arrow based on alert type */}
                      {alert.type === 'health_score_low' ? (
                        <HiOutlineArrowTrendingDown className="h-4 w-4 ml-auto text-red-400" />
                      ) : alert.type === 'health_score_high' ? (
                        <HiOutlineArrowTrendingUp className="h-4 w-4 ml-auto text-green-400" />
                      ) : isNegative ? (
                        <HiOutlineArrowTrendingDown className="h-4 w-4 ml-auto text-red-400" />
                      ) : (
                        <HiOutlineArrowTrendingUp className="h-4 w-4 ml-auto text-green-400" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 pl-6">
                      {alert.message}
                    </p>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

export default AlertsWidget;
