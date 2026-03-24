'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface OrbitSpinnerProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  particleCount?: number;
}

export function OrbitSpinner({
  className,
  size = 'md',
  color = 'var(--chart-5)', // Nord Orange
  particleCount = 3,
}: OrbitSpinnerProps) {
  const sizes = {
    sm: { container: 24, orbit: 10, particle: 3 },
    md: { container: 32, orbit: 14, particle: 4 },
    lg: { container: 48, orbit: 20, particle: 5 },
  };

  const s = sizes[size];

  return (
    <div
      className={cn('relative flex items-center justify-center', className)}
      style={{ width: s.container, height: s.container }}
    >
      {/* Central dot - pulsing */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: s.particle * 1.5,
          height: s.particle * 1.5,
          backgroundColor: color,
        }}
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.8, 1, 0.8],
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Orbiting particles */}
      {Array.from({ length: particleCount }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: s.particle,
            height: s.particle,
            backgroundColor: color,
            boxShadow: `0 0 ${s.particle * 2}px ${color}`,
          }}
          animate={{
            rotate: 360,
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'linear',
            delay: (i * 2) / particleCount,
          }}
          // Position on orbit
          initial={false}
        >
          <motion.div
            className="absolute rounded-full"
            style={{
              width: s.particle,
              height: s.particle,
              backgroundColor: color,
              left: s.orbit,
              top: 0,
              boxShadow: `0 0 ${s.particle * 2}px ${color}`,
            }}
          />
        </motion.div>
      ))}

      {/* Orbit ring - subtle glow */}
      <motion.div
        className="absolute rounded-full border"
        style={{
          width: s.orbit * 2 + s.particle,
          height: s.orbit * 2 + s.particle,
          borderColor: `${color}30`,
        }}
        animate={{
          opacity: [0.3, 0.6, 0.3],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Trail effect */}
      {Array.from({ length: particleCount }).map((_, i) => (
        <motion.div
          key={`trail-${i}`}
          className="absolute"
          style={{
            width: s.orbit * 2,
            height: s.orbit * 2,
          }}
          animate={{
            rotate: 360,
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'linear',
            delay: (i * 2) / particleCount,
          }}
        >
          <motion.div
            className="absolute rounded-full"
            style={{
              width: s.particle,
              height: s.particle,
              backgroundColor: color,
              right: 0,
              top: '50%',
              transform: 'translateY(-50%)',
              boxShadow: `0 0 ${s.particle * 3}px ${color}`,
            }}
            animate={{
              opacity: [1, 0.7, 1],
              scale: [1, 0.8, 1],
            }}
            transition={{
              duration: 0.5,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        </motion.div>
      ))}
    </div>
  );
}

export default OrbitSpinner;
