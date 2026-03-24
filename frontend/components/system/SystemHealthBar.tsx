'use client';

import { useSystemHealth, getStatusColor, getStatusIcon, formatLatency } from '@/hooks/use-system-health';
import { OllamaModelSelector } from './OllamaModelSelector';
import { RefreshCw } from 'lucide-react';

interface ServiceIndicatorProps {
  name: string;
  displayName: string;
  status: 'connected' | 'degraded' | 'disconnected' | 'checking';
  latency?: number | null;
  message?: string | null;
}

function ServiceIndicator({ name, displayName, status, latency, message }: ServiceIndicatorProps) {
  const color = getStatusColor(status);
  const icon = getStatusIcon(status);

  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 transition-colors cursor-default"
      title={message || `${displayName}: ${status}${latency ? ` (${formatLatency(latency)})` : ''}`}
    >
      <span style={{ color }} className="text-sm font-bold">
        {icon}
      </span>
      <span className="text-xs text-gray-300">{displayName}</span>
      {latency !== null && latency !== undefined && (
        <span className="text-[10px] text-gray-500">{formatLatency(latency)}</span>
      )}
    </div>
  );
}

interface SystemHealthBarProps {
  showOllamaSelector?: boolean;
  compact?: boolean;
}

export function SystemHealthBar({ showOllamaSelector = true, compact = false }: SystemHealthBarProps) {
  const { services, overall, isLoading, refresh, getService } = useSystemHealth(15000);

  // Service display mapping
  const serviceDisplayNames: Record<string, string> = {
    backend: 'API',
    ollama: 'Ollama',
    neo4j: 'Neo4j',
    postgresql: 'PostgreSQL',
    websocket: 'WebSocket',
    scheduler: 'Scheduler',
    telemetry: 'Telemetrie',
  };

  // Key services to show in compact mode
  const keyServices = compact
    ? ['backend', 'ollama', 'websocket']
    : ['backend', 'ollama', 'neo4j', 'postgresql', 'websocket', 'scheduler'];

  const overallColor = overall === 'healthy' ? 'var(--success)' : overall === 'degraded' ? 'var(--warning)' : 'var(--error)';

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 bg-card rounded-lg border border-border">
      {/* Overall status indicator */}
      <div className="flex items-center gap-2" title={`Status global: ${overall}`}>
        <div
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: overallColor }}
        />
        <span className="text-xs font-medium text-gray-300">
          {overall === 'healthy' ? 'Système OK' : overall === 'degraded' ? 'Dégradé' : 'Problème'}
        </span>
      </div>

      {/* Separator */}
      <div className="w-px h-4 bg-white/20" />

      {/* Service indicators */}
      <div className="flex items-center gap-1">
        {isLoading && services.length === 0 ? (
          <span className="text-xs text-gray-500">Verification...</span>
        ) : (
          keyServices.map((serviceName) => {
            const service = getService(serviceName);
            if (!service) return null;
            return (
              <ServiceIndicator
                key={serviceName}
                name={serviceName}
                displayName={serviceDisplayNames[serviceName] || serviceName}
                status={service.status}
                latency={service.latency_ms}
                message={service.message}
              />
            );
          })
        )}
      </div>

      {/* Ollama model selector */}
      {showOllamaSelector && (
        <>
          <div className="w-px h-4 bg-white/20" />
          <OllamaModelSelector compact />
        </>
      )}

      {/* Refresh button */}
      <button
        onClick={refresh}
        className="p-1 rounded hover:bg-white/10 transition-colors"
        title="Rafraichir le statut"
        disabled={isLoading}
      >
        <RefreshCw
          className={`w-3.5 h-3.5 text-gray-400 ${isLoading ? 'animate-spin' : ''}`}
        />
      </button>
    </div>
  );
}

export default SystemHealthBar;
