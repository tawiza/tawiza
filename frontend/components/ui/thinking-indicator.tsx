'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface ThinkingIndicatorProps {
  className?: string;
  message?: string;
}

export function ThinkingIndicator({ className, message = 'TAJINE reflechit...' }: ThinkingIndicatorProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        'flex items-start gap-3 p-4 max-w-[85%] sm:max-w-[70%]',
        className
      )}
    >
      {/* Brain/Thinking animation */}
      <div className="relative flex-shrink-0">
        {/* Outer glow ring */}
        <motion.div
          className="absolute inset-0 rounded-full bg-primary/20"
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.5, 0.2, 0.5],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{ width: 40, height: 40 }}
        />

        {/* Inner orb */}
        <motion.div
          className="relative w-10 h-10 rounded-full bg-gradient-to-br from-primary/80 to-primary flex items-center justify-center"
          animate={{
            scale: [1, 0.95, 1],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          {/* Brain icon with pulse */}
          <motion.svg
            viewBox="0 0 24 24"
            className="w-5 h-5 text-primary-foreground"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            animate={{
              opacity: [1, 0.6, 1],
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
            />
          </motion.svg>
        </motion.div>

        {/* Orbiting dots */}
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="absolute w-1.5 h-1.5 rounded-full bg-primary"
            animate={{
              rotate: 360,
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'linear',
              delay: i * 1,
            }}
            style={{
              top: '50%',
              left: '50%',
              transformOrigin: '0 0',
              marginTop: -3,
              marginLeft: 22,
            }}
          />
        ))}
      </div>

      {/* Thinking text with animated dots */}
      <div className="flex flex-col gap-2 pt-1">
        <div className="glass rounded-lg px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-foreground font-medium">{message}</span>
            <span className="flex gap-0.5">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="w-1 h-1 rounded-full bg-primary"
                  animate={{
                    y: [0, -4, 0],
                    opacity: [0.4, 1, 0.4],
                  }}
                  transition={{
                    duration: 0.8,
                    repeat: Infinity,
                    delay: i * 0.15,
                    ease: 'easeInOut',
                  }}
                />
              ))}
            </span>
          </div>

          {/* Neural activity visualization */}
          <div className="mt-3 flex gap-1">
            {Array.from({ length: 8 }).map((_, i) => (
              <motion.div
                key={i}
                className="w-1 rounded-full bg-primary/60"
                animate={{
                  height: [4, 12, 6, 16, 4],
                }}
                transition={{
                  duration: 1.2,
                  repeat: Infinity,
                  delay: i * 0.1,
                  ease: 'easeInOut',
                }}
              />
            ))}
          </div>
        </div>

        {/* Subtle hint about what's happening */}
        <motion.span
          className="text-[10px] text-muted-foreground px-1"
          animate={{
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          Analyse cognitive en cours
        </motion.span>
      </div>
    </motion.div>
  );
}

export default ThinkingIndicator;
