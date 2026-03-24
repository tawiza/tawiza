'use client';

import { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HiOutlineSparkles } from 'react-icons/hi2';

interface ChartContainerProps {
  children: ReactNode;
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyMessage?: string;
  emptySubMessage?: string;
  isLive?: boolean;
  className?: string;
  /** Height class - responsive by default */
  heightClass?: string;
  /** Animation delay in seconds */
  delay?: number;
  /** Title for the chart (optional) */
  title?: string;
  /** Subtitle for the chart (optional) */
  subtitle?: string;
}

// Animation variants
const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (delay: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      delay,
      ease: [0.25, 0.46, 0.45, 0.94],
    },
  }),
};

const loadingVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.3 },
  },
  exit: {
    opacity: 0,
    scale: 0.8,
    transition: { duration: 0.2 },
  },
};

const liveIndicatorVariants = {
  hidden: { opacity: 0, x: 20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.3, delay: 0.5 },
  },
};

/**
 * Responsive chart container with loading, empty, and live states.
 * Provides consistent sizing across mobile and desktop with smooth animations.
 */
export default function ChartContainer({
  children,
  isLoading = false,
  isEmpty = false,
  emptyMessage = 'Aucune donnee disponible',
  emptySubMessage = 'Lancez une analyse pour visualiser',
  isLive = false,
  className = '',
  heightClass = 'h-[200px] sm:h-[280px] md:h-[350px]',
  delay = 0,
  title,
  subtitle,
}: ChartContainerProps) {
  return (
    <motion.div
      className={`relative w-full ${heightClass} ${className}`}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      custom={delay}
    >
      {/* Optional title */}
      {title && (
        <div className="mb-2">
          <h3 className="text-sm sm:text-base font-medium text-foreground">{title}</h3>
          {subtitle && (
            <p className="text-[10px] sm:text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      )}

      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            className={`flex items-center justify-center ${title ? 'h-[calc(100%-2rem)]' : 'h-full'}`}
            variants={loadingVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-muted-foreground">Chargement...</span>
            </div>
          </motion.div>
        ) : isEmpty ? (
          <motion.div
            key="empty"
            className={`flex flex-col items-center justify-center text-muted-foreground ${title ? 'h-[calc(100%-2rem)]' : 'h-full'}`}
            variants={loadingVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            <HiOutlineSparkles className="w-10 h-10 sm:w-12 sm:h-12 mb-3 opacity-30" />
            <p className="text-xs sm:text-sm text-center px-4">{emptyMessage}</p>
            <p className="text-[10px] sm:text-xs mt-1 text-center px-4">{emptySubMessage}</p>
          </motion.div>
        ) : (
          <motion.div
            key="content"
            className={title ? 'h-[calc(100%-2rem)]' : 'h-full'}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live data indicator with animation */}
      <AnimatePresence>
        {isLive && !isLoading && !isEmpty && (
          <motion.div
            className="absolute top-0 right-0 flex items-center gap-1 px-2 py-1 glass rounded-lg text-[10px] sm:text-xs z-10"
            variants={liveIndicatorVariants}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0, x: 20 }}
          >
            <HiOutlineSparkles className="w-3 h-3 text-[var(--success)] animate-pulse" />
            <span className="text-[var(--success)]">Live</span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
