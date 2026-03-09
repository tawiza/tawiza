'use client';

import { cn } from '@/lib/utils';
import './energy-orb.css';

type OrbState = 'idle' | 'loading' | 'streaming' | 'complete';

interface EnergyOrbProps {
  state?: OrbState;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_CLASSES = {
  sm: 'w-6 h-6',
  md: 'w-8 h-8',
  lg: 'w-10 h-10',
};

const PARTICLE_COUNTS = {
  idle: 0,
  loading: 4,
  streaming: 8,
  complete: 4,
};

export default function EnergyOrb({
  state = 'idle',
  size = 'md',
  className = '',
}: EnergyOrbProps) {
  const particleCount = PARTICLE_COUNTS[state];

  return (
    <div
      className={cn(
        'energy-orb relative flex items-center justify-center',
        SIZE_CLASSES[size],
        state === 'streaming' && 'energy-orb--streaming',
        state === 'loading' && 'energy-orb--loading',
        state === 'complete' && 'energy-orb--complete',
        className
      )}
    >
      {/* Core orb */}
      <div
        className={cn(
          'energy-orb__core absolute rounded-full',
          'bg-gradient-to-br from-info to-primary',
          state === 'idle' && 'w-3 h-3',
          state === 'loading' && 'w-4 h-4',
          state === 'streaming' && 'w-5 h-5',
          state === 'complete' && 'w-5 h-5'
        )}
      />

      {/* Rotating ring */}
      {(state === 'loading' || state === 'streaming') && (
        <div
          className={cn(
            'energy-orb__ring absolute rounded-full border-2 border-transparent',
            'border-t-info border-r-primary/50',
            SIZE_CLASSES[size]
          )}
        />
      )}

      {/* Glow effect */}
      <div
        className={cn(
          'energy-orb__glow absolute rounded-full',
          SIZE_CLASSES[size],
          state !== 'idle' && 'opacity-100',
          state === 'idle' && 'opacity-0'
        )}
      />

      {/* Orbiting particles */}
      {particleCount > 0 && (
        <div className="energy-orb__particles absolute inset-0">
          {Array.from({ length: particleCount }).map((_, i) => (
            <div
              key={i}
              className="energy-orb__particle absolute w-1.5 h-1.5 rounded-full bg-info"
              style={{
                animationDelay: `${(i / particleCount) * -1}s`,
                '--particle-offset': `${(i / particleCount) * 360}deg`,
              } as React.CSSProperties}
            />
          ))}
        </div>
      )}
    </div>
  );
}
