'use client';

import { cn } from '@/lib/utils';
import {
  HiEye,
  HiMap,
  HiCpuChip,
  HiBeaker,
  HiAcademicCap,
  HiCheck,
  HiMagnifyingGlass,
  HiGlobeAlt,
  HiChartBar,
  HiCommandLine,
  HiSignal,
  HiBuildingOffice2,
} from 'react-icons/hi2';

export interface AgentTool {
  name: string;
  status: 'running' | 'complete' | 'error';
  params?: Record<string, unknown>;
}

export interface AgentPhase {
  name: string;
  label: string;
  status: 'pending' | 'running' | 'complete';
  message: string;
  progress: number;
  tools: AgentTool[];
}

const PHASE_CONFIG: Record<string, { icon: typeof HiEye; label: string; color: string }> = {
  perceive: { icon: HiEye, label: 'Perception', color: 'text-blue-400' },
  plan: { icon: HiMap, label: 'Planification', color: 'text-violet-400' },
  delegate: { icon: HiCpuChip, label: 'Delegation', color: 'text-amber-400' },
  synthesize: { icon: HiBeaker, label: 'Synthese', color: 'text-emerald-400' },
  learn: { icon: HiAcademicCap, label: 'Apprentissage', color: 'text-cyan-400' },
};

const TOOL_ICONS: Record<string, typeof HiMagnifyingGlass> = {
  data_hunter: HiMagnifyingGlass,
  sirene_search: HiBuildingOffice2,
  browser_automation: HiGlobeAlt,
  browser: HiGlobeAlt,
  crawler: HiGlobeAlt,
  territorial_analyzer: HiChartBar,
  competitor_analyzer: HiChartBar,
  sector_analyzer: HiChartBar,
  signal_detector: HiSignal,
  default: HiCommandLine,
};

const TOOL_LABELS: Record<string, string> = {
  data_hunter: 'DataHunter',
  sirene_search: 'API SIRENE',
  browser_automation: 'Navigateur',
  browser: 'Navigateur',
  crawler: 'Web Crawler',
  territorial_analyzer: 'Analyse Territoriale',
  competitor_analyzer: 'Analyse Concurrentielle',
  sector_analyzer: 'Analyse Sectorielle',
  signal_detector: 'Detection Signaux',
};

interface AgentTimelineProps {
  phases: AgentPhase[];
  model?: string;
  className?: string;
}

export function AgentTimeline({ phases, model, className }: AgentTimelineProps) {
  if (phases.length === 0) return null;

  return (
    <div className={cn('relative', className)}>
      {/* Model badge */}
      {model && (
        <div className="flex items-center gap-1.5 mb-3">
          <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wider">
            {model}
          </span>
        </div>
      )}

      {/* Timeline */}
      <div className="relative pl-6">
        {/* Vertical line */}
        <div className="absolute left-[9px] top-1 bottom-1 w-px bg-border/50" />

        {phases.map((phase, idx) => {
          const config = PHASE_CONFIG[phase.name] || PHASE_CONFIG.perceive;
          const Icon = config.icon;
          const isLast = idx === phases.length - 1;

          return (
            <div key={phase.name} className={cn('relative pb-4', isLast && 'pb-1')}>
              {/* Status dot */}
              <div className="absolute left-[-15px] top-[3px]">
                {phase.status === 'complete' ? (
                  <div className="h-[18px] w-[18px] rounded-full bg-primary/20 flex items-center justify-center">
                    <HiCheck className="h-2.5 w-2.5 text-primary" />
                  </div>
                ) : phase.status === 'running' ? (
                  <div className="h-[18px] w-[18px] rounded-full bg-primary/20 flex items-center justify-center">
                    <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                  </div>
                ) : (
                  <div className="h-[18px] w-[18px] rounded-full bg-muted/50 flex items-center justify-center">
                    <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/20" />
                  </div>
                )}
              </div>

              {/* Phase content */}
              <div className={cn(
                'transition-opacity duration-300',
                phase.status === 'pending' ? 'opacity-40' : 'opacity-100'
              )}>
                <div className="flex items-center gap-2">
                  <Icon className={cn('h-3.5 w-3.5', config.color)} />
                  <span className={cn(
                    'text-xs font-semibold',
                    phase.status === 'running' ? 'text-foreground' : 'text-muted-foreground'
                  )}>
                    {config.label}
                  </span>
                  {phase.status === 'running' && (
                    <span className="flex items-center gap-0.5 ml-1">
                      <span className="h-0.5 w-0.5 rounded-full bg-primary animate-thinking-dot" />
                      <span className="h-0.5 w-0.5 rounded-full bg-primary animate-thinking-dot" style={{ animationDelay: '200ms' }} />
                      <span className="h-0.5 w-0.5 rounded-full bg-primary animate-thinking-dot" style={{ animationDelay: '400ms' }} />
                    </span>
                  )}
                </div>

                {/* Phase message */}
                {phase.message && phase.status !== 'pending' && (
                  <p className="text-[11px] text-muted-foreground/70 mt-0.5 ml-5.5 leading-snug">
                    {phase.message}
                  </p>
                )}

                {/* Tool cards for delegate phase */}
                {phase.tools.length > 0 && (
                  <div className="mt-2 ml-5 space-y-1">
                    {phase.tools.map((tool, toolIdx) => {
                      const ToolIcon = TOOL_ICONS[tool.name] || TOOL_ICONS.default;
                      const toolLabel = TOOL_LABELS[tool.name] || tool.name;

                      return (
                        <div
                          key={`${tool.name}-${toolIdx}`}
                          className={cn(
                            'flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px]',
                            'border transition-all duration-300',
                            tool.status === 'running'
                              ? 'border-primary/20 bg-primary/5'
                              : tool.status === 'complete'
                                ? 'border-border/30 bg-muted/20'
                                : 'border-red-500/20 bg-red-500/5'
                          )}
                        >
                          <ToolIcon className={cn(
                            'h-3 w-3 flex-shrink-0',
                            tool.status === 'running' ? 'text-primary' : 'text-muted-foreground/60'
                          )} />
                          <span className={cn(
                            'font-medium',
                            tool.status === 'running' ? 'text-foreground' : 'text-muted-foreground/70'
                          )}>
                            {toolLabel}
                          </span>
                          <span className="ml-auto">
                            {tool.status === 'running' ? (
                              <div className="h-3 w-3 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin" />
                            ) : tool.status === 'complete' ? (
                              <HiCheck className="h-3 w-3 text-green-500" />
                            ) : (
                              <span className="text-red-400 text-[10px]">erreur</span>
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Global progress bar */}
      {phases.some(p => p.status === 'running') && (
        <div className="mt-2 ml-6">
          <div className="h-0.5 w-full rounded-full bg-muted/40 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary transition-all duration-700 ease-out"
              style={{
                width: `${Math.max(
                  ...phases.filter(p => p.status !== 'pending').map(p => p.progress),
                  5
                )}%`
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Compact summary shown after streaming is complete
 */
export function AgentSummaryBadge({
  phases,
  duration,
  className,
}: {
  phases: AgentPhase[];
  duration?: number;
  className?: string;
}) {
  const completedTools = phases
    .flatMap(p => p.tools)
    .filter(t => t.status === 'complete');

  if (completedTools.length === 0) return null;

  return (
    <div className={cn(
      'flex items-center gap-2 flex-wrap',
      className
    )}>
      <span className="text-[10px] text-muted-foreground/50">
        {completedTools.length} outil{completedTools.length > 1 ? 's' : ''} utilise{completedTools.length > 1 ? 's' : ''}
      </span>
      {completedTools.slice(0, 4).map((tool, idx) => {
        const ToolIcon = TOOL_ICONS[tool.name] || TOOL_ICONS.default;
        return (
          <div
            key={`${tool.name}-${idx}`}
            className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted/30 text-[10px] text-muted-foreground/60"
            title={TOOL_LABELS[tool.name] || tool.name}
          >
            <ToolIcon className="h-2.5 w-2.5" />
            <span className="hidden sm:inline">{TOOL_LABELS[tool.name] || tool.name}</span>
          </div>
        );
      })}
      {duration && (
        <span className="text-[10px] text-muted-foreground/40 font-mono">
          {duration < 60 ? `${Math.round(duration)}s` : `${Math.round(duration / 60)}m${Math.round(duration % 60)}s`}
        </span>
      )}
    </div>
  );
}
