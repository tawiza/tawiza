'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  HiOutlineBell,
  HiOutlineExclamationTriangle,
  HiOutlineInformationCircle,
  HiOutlineXCircle,
  HiOutlineCheckCircle,
} from 'react-icons/hi2';
import { GlassCard, GlassCardContent, GlassCardHeader, GlassCardTitle, GlassCardDescription } from './glass-card';
import { Button } from './button';
import { getAlerts, markAlertRead, type Alert } from '@/lib/api';

interface AlertsWidgetProps {
  limit?: number;
  className?: string;
  territory?: string;
}

const severityConfig = {
  info: {
    icon: HiOutlineInformationCircle,
    color: 'text-blue-400',
    bg: 'bg-blue-400/10',
  },
  warning: {
    icon: HiOutlineExclamationTriangle,
    color: 'text-yellow-400',
    bg: 'bg-yellow-400/10',
  },
  critical: {
    icon: HiOutlineXCircle,
    color: 'text-red-400',
    bg: 'bg-red-400/10',
  },
};

const typeLabels: Record<string, string> = {
  enterprise_creation: 'Création entreprise',
  enterprise_closure: 'Fermeture',
  market_opportunity: 'Marché public',
  legal_announcement: 'Annonce légale',
  economic_indicator: 'Indicateur éco.',
  subsidy_available: 'Subvention',
  job_market_change: 'Emploi',
  real_estate_change: 'Immobilier',
};

export default function AlertsWidget({ limit = 5, className = '', territory }: AlertsWidgetProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await getAlerts({
        status: 'new',
        territory,
        limit
      });
      if (response?.alerts) {
        setAlerts(response.alerts);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setIsLoading(false);
    }
  }, [limit, territory]);

  useEffect(() => {
    fetchAlerts();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const handleMarkRead = async (alertId: string) => {
    await markAlertRead(alertId);
    setAlerts(prev => prev.filter(a => a.id !== alertId));
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 60) return `${diffMins}min`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h`;
    return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  };

  if (isLoading) {
    return (
      <GlassCard className={className}>
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineBell className="h-5 w-5 text-primary" />
            Alertes
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 animate-pulse bg-white/5 rounded-lg" />
            ))}
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="cyan" hoverGlow className={className}>
      <GlassCardHeader>
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineBell className="h-5 w-5 text-primary" />
          Alertes
          {alerts.length > 0 && (
            <span className="ml-auto text-xs bg-primary/20 px-2 py-0.5 rounded-full">
              {alerts.length} nouvelles
            </span>
          )}
        </GlassCardTitle>
        <GlassCardDescription>Changements significatifs detectes</GlassCardDescription>
      </GlassCardHeader>
      <GlassCardContent>
        {alerts.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <HiOutlineCheckCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Aucune nouvelle alerte</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert, index) => {
              const config = severityConfig[alert.severity] || severityConfig.info;
              const Icon = config.icon;

              return (
                <div
                  key={alert.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-white/5 opacity-0 animate-fade-in group"
                  style={{ animationDelay: `${index * 80}ms`, animationFillMode: 'forwards' }}
                >
                  <div className={`p-1.5 rounded ${config.bg}`}>
                    <Icon className={`h-4 w-4 ${config.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium truncate">{alert.title}</p>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {formatTime(alert.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        {typeLabels[alert.type] || alert.type}
                      </span>
                      {alert.territory && (
                        <>
                          <span className="text-xs text-muted-foreground">•</span>
                          <span className="text-xs text-primary">{alert.territory}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => handleMarkRead(alert.id)}
                  >
                    <HiOutlineCheckCircle className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
