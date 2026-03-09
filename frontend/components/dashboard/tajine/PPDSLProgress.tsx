'use client';

import { useTAJINE } from '@/contexts/TAJINEContext';
import { TAJINEPhase } from '@/hooks/use-tajine-websocket';

// Phase icons and labels
const PHASES: { key: TAJINEPhase; label: string; icon: string }[] = [
  { key: 'perceive', label: 'Percevoir', icon: '👁️' },
  { key: 'plan', label: 'Planifier', icon: '📋' },
  { key: 'delegate', label: 'Déléguer', icon: '🔧' },
  { key: 'synthesize', label: 'Synthétiser', icon: '🧠' },
  { key: 'learn', label: 'Apprendre', icon: '📚' },
];

// Nord colors for phases
const PHASE_COLORS: Record<TAJINEPhase, string> = {
  perceive: 'var(--chart-1)',   // nord8 - cyan
  plan: 'var(--chart-2)',       // nord9 - blue
  delegate: 'var(--chart-3)',   // nord10 - dark blue
  synthesize: 'var(--success)', // nord14 - green
  learn: 'var(--chart-4)',      // nord15 - purple
};

interface PPDSLProgressProps {
  className?: string;
  compact?: boolean;
}

export default function PPDSLProgress({ className = '', compact = false }: PPDSLProgressProps) {
  const { wsConnected, currentTask, currentPhase, thinking } = useTAJINE();

  // Don't render if no active task
  if (!currentTask && !thinking) {
    return null;
  }

  const currentPhaseIndex = currentPhase
    ? PHASES.findIndex(p => p.key === currentPhase)
    : -1;

  return (
    <div className={`glass rounded-lg p-4 ${className}`}>
      {/* Connection status */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}
        />
        <span className="text-xs text-muted-foreground">
          {wsConnected ? 'Connecté' : 'Déconnecté'}
        </span>
        {currentTask && (
          <span className="text-xs text-primary ml-auto">
            Tâche: {currentTask.taskId}
          </span>
        )}
      </div>

      {/* Phase progress bar */}
      <div className="flex items-center gap-1 mb-3">
        {PHASES.map((phase, index) => {
          const isActive = currentPhase === phase.key;
          const isComplete = currentPhaseIndex > index;
          const isPending = currentPhaseIndex < index;

          return (
            <div key={phase.key} className="flex-1 flex flex-col items-center">
              {/* Phase indicator */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm transition-all duration-300 ${
                  isActive
                    ? 'ring-2 ring-offset-2 ring-offset-background scale-110'
                    : ''
                }`}
                style={{
                  backgroundColor: isComplete || isActive
                    ? PHASE_COLORS[phase.key]
                    : 'rgba(76, 86, 106, 0.5)',
                  opacity: isPending ? 0.4 : 1,
                  // @ts-expect-error - CSS custom property for ring color
                  '--tw-ring-color': isActive ? PHASE_COLORS[phase.key] : undefined,
                }}
              >
                {isComplete ? '✓' : phase.icon}
              </div>

              {/* Phase label */}
              <span
                className={`text-[10px] mt-1 transition-opacity ${
                  isActive ? 'text-foreground font-medium' : 'text-muted-foreground'
                }`}
              >
                {phase.label}
              </span>

              {/* Progress bar connector */}
              {index < PHASES.length - 1 && (
                <div
                  className="absolute h-0.5 top-4 transition-all duration-300"
                  style={{
                    left: `${(index + 1) * 20}%`,
                    right: `${(4 - index) * 20}%`,
                    backgroundColor: isComplete
                      ? PHASE_COLORS[phase.key]
                      : 'rgba(76, 86, 106, 0.3)',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Current phase details */}
      {currentTask && (
        <div className="space-y-2">
          {/* Progress bar */}
          <div className="h-1.5 bg-background/50 rounded-full overflow-hidden">
            <div
              className="h-full transition-all duration-300 rounded-full"
              style={{
                width: `${currentTask.progress}%`,
                backgroundColor: currentPhase ? PHASE_COLORS[currentPhase] : 'var(--chart-1)',
              }}
            />
          </div>

          {/* Message */}
          <p className="text-xs text-muted-foreground truncate">
            {currentTask.message || 'Traitement en cours...'}
          </p>

          {/* Subtasks for plan phase */}
          {currentPhase === 'plan' && currentTask.subtasks && (
            <div className="text-xs space-y-1 mt-2">
              {currentTask.subtasks.slice(0, 3).map((subtask, i) => (
                <div key={subtask.id || i} className="flex items-center gap-2">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] ${
                    subtask.status === 'completed' ? 'bg-green-500' :
                    subtask.status === 'running' ? 'bg-blue-500 animate-pulse' :
                    'bg-gray-500'
                  }`}>
                    {subtask.status === 'completed' ? '✓' : i + 1}
                  </span>
                  <span className="truncate">{subtask.name}</span>
                </div>
              ))}
              {currentTask.subtasks.length > 3 && (
                <span className="text-muted-foreground">
                  +{currentTask.subtasks.length - 3} autres...
                </span>
              )}
            </div>
          )}

          {/* Tool info for delegate phase */}
          {currentPhase === 'delegate' && currentTask.tool && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Outil:</span>
              <code className="bg-background/50 px-2 py-0.5 rounded">
                {currentTask.tool}
              </code>
            </div>
          )}

          {/* Level info for synthesize phase */}
          {currentPhase === 'synthesize' && currentTask.level !== undefined && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Niveau cognitif:</span>
              <span className="font-medium">{currentTask.level + 1}/5</span>
            </div>
          )}

          {/* Trust delta for learn phase */}
          {currentPhase === 'learn' && currentTask.trustDelta !== undefined && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Delta confiance:</span>
              <span className={currentTask.trustDelta >= 0 ? 'text-green-500' : 'text-red-500'}>
                {currentTask.trustDelta >= 0 ? '+' : ''}{currentTask.trustDelta.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Thinking indicator */}
      {thinking && (
        <div className="mt-3 p-2 bg-background/30 rounded text-xs text-muted-foreground italic">
          <span className="inline-block animate-pulse mr-2">💭</span>
          {thinking.length > 100 ? thinking.slice(0, 100) + '...' : thinking}
        </div>
      )}
    </div>
  );
}
