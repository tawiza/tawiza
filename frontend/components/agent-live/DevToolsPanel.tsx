'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import {
  HiTv,
  HiOutlineCommandLine,
  HiChevronLeft,
  HiChevronRight,
  HiSignal,
} from 'react-icons/hi2';

// Dynamic imports for heavy components
const ScreenshotViewer = dynamic(
  () => import('@/components/agent-live/ScreenshotViewer'),
  { ssr: false }
);

const TerminalViewer = dynamic(
  () => import('@/components/agent-live/TerminalViewer'),
  { ssr: false }
);

interface DevToolsPanelProps {
  className?: string;
  defaultExpanded?: boolean;
  minWidth?: number;
  maxWidth?: number;
}

export function DevToolsPanel({
  className,
  defaultExpanded = false,
  minWidth = 400,
  maxWidth = 800,
}: DevToolsPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [width, setWidth] = useState(500);
  const [isResizing, setIsResizing] = useState(false);
  const [browserConnected, setBrowserConnected] = useState(false);
  const [hasActivity, setHasActivity] = useState(false);

  // Auto-expand when activity is detected
  useEffect(() => {
    if (hasActivity && !expanded) {
      setExpanded(true);
    }
  }, [hasActivity, expanded]);

  // Listen for terminal events
  useEffect(() => {
    const handleTerminalOutput = () => {
      setHasActivity(true);
    };

    window.addEventListener('code-terminal-output', handleTerminalOutput);
    return () => window.removeEventListener('code-terminal-output', handleTerminalOutput);
  }, []);

  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);

    const startX = e.clientX;
    const startWidth = width;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = startX - e.clientX;
      const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + delta));
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [width, minWidth, maxWidth]);

  // Keyboard shortcut Cmd/Ctrl + J
  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault();
        setExpanded((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, []);

  return (
    <div
      className={cn(
        'h-full flex',
        isResizing && 'select-none',
        className
      )}
    >
      {/* Collapsed sidebar - vertical tab */}
      <AnimatePresence>
        {!expanded && (
          <motion.button
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            onClick={() => setExpanded(true)}
            className={cn(
              'h-full w-10 flex flex-col items-center py-4 gap-3',
              'border-l border-border bg-background',
              'text-muted-foreground hover:text-foreground transition-all group'
            )}
            title="Agent Live (Ctrl+J)"
          >
            <HiChevronLeft className="h-4 w-4 group-hover:text-primary transition-colors" />

            {/* Status indicators */}
            <div className="flex flex-col items-center gap-2 mt-4">
              <div className={cn(
                'p-1.5 rounded-lg transition-all',
                browserConnected ? 'bg-green-500/20 text-green-500' : 'bg-white/5'
              )}>
                <HiTv className="h-4 w-4" />
              </div>
              <div className="p-1.5 rounded-lg bg-white/5">
                <HiOutlineCommandLine className="h-4 w-4" />
              </div>
            </div>

            {/* Connection indicator */}
            {browserConnected && (
              <div className="mt-auto flex flex-col items-center gap-1">
                <HiSignal className="h-3 w-3 text-green-500 animate-pulse" />
                <span className="text-[8px] text-green-500 font-medium writing-mode-vertical">LIVE</span>
              </div>
            )}
          </motion.button>
        )}
      </AnimatePresence>

      {/* Expanded sidebar */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="h-full overflow-hidden border-l border-border bg-background relative"
          >
            {/* Resize handle */}
            <div
              className="absolute left-0 top-0 w-1.5 h-full cursor-ew-resize hover:bg-primary/30 active:bg-primary/50 transition-colors z-20"
              onMouseDown={handleMouseDown}
            />

            <div className="h-full flex flex-col" style={{ width }}>
              {/* Header */}
              <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-muted/30">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      'w-2 h-2 rounded-full',
                      browserConnected ? 'bg-green-500 animate-pulse' : 'bg-muted-foreground/30'
                    )} />
                    <span className="text-sm font-semibold">Agent Live</span>
                  </div>
                  {browserConnected && (
                    <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-500 text-[10px] font-medium">
                      Connecte
                    </span>
                  )}
                </div>
                <button
                  onClick={() => setExpanded(false)}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/10 transition-all"
                  title="Fermer (Ctrl+J)"
                >
                  <HiChevronRight className="h-4 w-4" />
                </button>
              </div>

              {/* Content - Vertical stack layout */}
              <div className="flex-1 p-3 flex flex-col gap-3 min-h-0 overflow-hidden">
                {/* Browser panel */}
                <div className="flex-1 min-h-0 flex flex-col rounded-xl border border-border bg-card overflow-hidden shadow-lg">
                  <div className="px-3 py-2 border-b border-border flex items-center gap-2 bg-gradient-to-r from-primary/10 to-transparent shrink-0">
                    <HiTv className="h-4 w-4 text-primary" />
                    <span className="text-xs font-semibold text-primary">Browser</span>
                    {browserConnected && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    )}
                  </div>
                  <div className="flex-1 min-h-0 p-2">
                    <ScreenshotViewer
                      autoConnect={true}
                      onConnectionChange={(connected) => {
                        setBrowserConnected(connected);
                        if (connected) setHasActivity(true);
                      }}
                      className="h-full rounded-lg overflow-hidden"
                    />
                  </div>
                </div>

                {/* Terminal panel */}
                <div className="flex-1 min-h-0 flex flex-col rounded-xl border border-border bg-card overflow-hidden shadow-lg">
                  <div className="px-3 py-2 border-b border-border flex items-center gap-2 bg-gradient-to-r from-green-500/10 to-transparent shrink-0">
                    <HiOutlineCommandLine className="h-4 w-4 text-green-500" />
                    <span className="text-xs font-semibold text-green-500">Terminal</span>
                  </div>
                  <div className="flex-1 min-h-0 p-2">
                    <TerminalViewer className="h-full rounded-lg overflow-hidden" />
                  </div>
                </div>
              </div>

              {/* Footer status bar */}
              <div className="px-4 py-2 border-t border-border bg-muted/30 flex items-center justify-between text-[10px] text-muted-foreground">
                <span>Ctrl+J pour toggle</span>
                <span>Glisser le bord pour redimensionner</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
