'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineCommandLine,
  HiOutlineTrash,
  HiOutlineClipboard,
  HiOutlineCheck,
  HiOutlineSignal,
  HiOutlineExclamationCircle,
} from 'react-icons/hi2';
import { cn } from '@/lib/utils';
import { useTAJINE } from '@/contexts/TAJINEContext';

interface TerminalLine {
  id: string;
  content: string;
  stream: 'stdout' | 'stderr' | 'system';
  timestamp: Date;
}

interface TerminalViewerProps {
  taskId?: string;
  lines?: TerminalLine[];
  className?: string;
  maxLines?: number;
}

// Nord Color Palette
const COLORS = {
  bg: 'rgba(46, 52, 64, 0.8)', // nord0 with opacity
  text: 'hsl(var(--foreground))',            // nord4
  prompt: 'var(--info)',          // nord8 (cyan)
  error: 'var(--error)',           // nord11 (red)
  success: 'var(--success)',         // nord14 (green)
  border: 'rgba(255, 255, 255, 0.1)',
};

export default function TerminalViewer({
  taskId,
  className = '',
  maxLines = 100
}: TerminalViewerProps) {
  const { wsConnected } = useTAJINE();
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([]);
  const [isCopied, setIsCopied] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new lines
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [terminalLines]);

  // Listen for WebSocket messages (conceptually, this will be wired in the parent page)
  // But we expose a global window event for simplicity in this bridge
  useEffect(() => {
    const handleTerminalOutput = (event: any) => {
      const { task_id, content, stream } = event.detail;
      if (taskId && task_id !== taskId) return;

      const newLine: TerminalLine = {
        id: Math.random().toString(36).substr(2, 9),
        content,
        stream: stream || 'stdout',
        timestamp: new Date(),
      };

      setTerminalLines(prev => [...prev.slice(-(maxLines - 1)), newLine]);
    };

    window.addEventListener('code-terminal-output', handleTerminalOutput);
    return () => window.removeEventListener('code-terminal-output', handleTerminalOutput);
  }, [taskId, maxLines]);

  const copyToClipboard = () => {
    const text = terminalLines.map(l => l.content).join('\n');
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const clearTerminal = () => {
    setTerminalLines([]);
  };

  return (
    <div className={cn(
      "flex flex-col h-full rounded-lg overflow-hidden border border-border bg-card shadow-2xl",
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <HiOutlineCommandLine className="w-4 h-4 text-info" />
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Python Interpreter {taskId ? `[${taskId}]` : ''}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={copyToClipboard}
            className="p-1 rounded hover:bg-white/10 transition-colors text-muted-foreground"
            title="Copier tout"
          >
            {isCopied ? <HiOutlineCheck className="w-3.5 h-3.5 text-success" /> : <HiOutlineClipboard className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={clearTerminal}
            className="p-1 rounded hover:bg-white/10 transition-colors text-muted-foreground"
            title="Effacer"
          >
            <HiOutlineTrash className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div
        ref={scrollRef}
        className="flex-1 p-3 font-mono text-xs overflow-y-auto scrollbar-thin scrollbar-thumb-white/10"
      >
        {terminalLines.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center select-none">
            {wsConnected ? (
              <>
                <div className="relative">
                  <HiOutlineCommandLine className="w-12 h-12 text-info/50 animate-pulse" />
                  <span className="absolute -top-1 -right-1 w-3 h-3 bg-success rounded-full animate-ping" />
                  <span className="absolute -top-1 -right-1 w-3 h-3 bg-success rounded-full" />
                </div>
                <p className="mt-4 text-sm font-medium text-success">Terminal pret</p>
                <p className="mt-2 text-xs opacity-50 text-center max-w-[200px]">
                  En attente d&apos;execution de code...
                </p>
                <p className="mt-1 text-[10px] opacity-30">
                  Les sorties Python s&apos;afficheront ici
                </p>
              </>
            ) : (
              <>
                <div className="relative">
                  <HiOutlineExclamationCircle className="w-12 h-12 text-error/50" />
                </div>
                <p className="mt-4 text-sm font-medium text-error">WebSocket deconnecte</p>
                <p className="mt-2 text-xs opacity-50 text-center max-w-[200px]">
                  Connexion au serveur en cours...
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-1">
            {terminalLines.map((line) => (
              <motion.div
                key={line.id}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex gap-2"
              >
                <span className="text-white/20 select-none">
                  {line.timestamp.toLocaleTimeString([], { hour12: false })}
                </span>
                <span className={cn(
                  "break-all",
                  line.stream === 'stderr' ? "text-error" :
                  line.stream === 'system' ? "text-warning italic" :
                  "text-foreground"
                )}>
                  {line.stream === 'stdout' && <span className="text-info mr-1">❯</span>}
                  {line.content}
                </span>
              </motion.div>
            ))}
            {/* Cursor animation */}
            <motion.div
              animate={{ opacity: [1, 0] }}
              transition={{ repeat: Infinity, duration: 0.8 }}
              className="inline-block w-2 h-4 bg-info/50 ml-1 translate-y-0.5"
            />
          </div>
        )}
      </div>

      {/* Footer / Status */}
      <div className="px-3 py-1.5 border-t border-white/5 bg-black/20 flex items-center justify-between text-[9px] font-mono text-muted-foreground uppercase">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            {wsConnected ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-success">Connecte</span>
              </>
            ) : (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-error" />
                <span className="text-error">Deconnecte</span>
              </>
            )}
          </span>
          <span>UTF-8</span>
        </div>
        <span>Lines: {terminalLines.length}</span>
      </div>
    </div>
  );
}
