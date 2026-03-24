'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Draggable from 'react-draggable';
import {
  HiOutlineChatBubbleLeftRight,
  HiOutlineXMark,
  HiOutlinePaperAirplane,
  HiOutlineChevronLeft,
  HiOutlineChevronRight,
  HiOutlineSparkles,
  HiOutlineCog6Tooth,
  HiOutlineArrowsPointingOut,
} from 'react-icons/hi2';
import { useTAJINE } from '@/contexts/TAJINEContext';
import ThinkingIndicator from '@/components/ui/thinking-indicator';

interface FloatingChatProps {
  className?: string;
  onAnalysisComplete?: () => void;
}

export default function FloatingChat({
  className = '',
  onAnalysisComplete,
}: FloatingChatProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [mode, setMode] = useState<'fast' | 'complete'>('fast');
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragRef = useRef<HTMLDivElement>(null);

  const {
    messages = [],
    isAnalyzing,
    currentPhase,
    sendMessage,
    analysisProgress,
    error,
  } = useTAJINE();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded) {
      inputRef.current?.focus();
    }
  }, [isExpanded]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isAnalyzing) return;

    const query = inputValue.trim();
    setInputValue('');

    await sendMessage(query, mode);
    onAnalysisComplete?.();
  };

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsExpanded(true);
        inputRef.current?.focus();
      }
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);

  return (
    <AnimatePresence>
      {isExpanded ? (
        <Draggable
          handle=".chat-drag-handle"
          bounds="parent"
          position={position}
          onStop={(e, d) => setPosition({ x: d.x, y: d.y })}
          nodeRef={dragRef}
        >
          <div
            ref={dragRef}
            className={`absolute top-20 left-4 w-[280px] sm:w-[340px] z-20 ${className}`}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
            >
              {/* Chat Panel */}
              <div className="glass rounded-xl shadow-2xl overflow-hidden border border-white/10">
                {/* Draggable Header */}
                <div className="chat-drag-handle flex items-center justify-between px-3 py-2 border-b border-border/50 bg-muted/20 cursor-move select-none">
                  <div className="flex items-center gap-2">
                    <HiOutlineArrowsPointingOut className="w-3 h-3 text-muted-foreground/60" />
                    <HiOutlineChatBubbleLeftRight className="w-4 h-4 text-primary" />
                    <span className="font-medium text-xs">TAJINE Chat</span>
                    {isAnalyzing && (
                      <span className="px-1.5 py-0.5 text-[9px] font-medium rounded-full bg-primary/20 text-primary animate-pulse">
                        {currentPhase || 'Analyse...'}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-0.5">
                    {/* Mode Toggle */}
                    <button
                      onClick={() => setMode(mode === 'fast' ? 'complete' : 'fast')}
                      className={`p-1 rounded-md transition-colors ${
                        mode === 'complete'
                          ? 'bg-primary/20 text-primary'
                          : 'hover:bg-muted/50 text-muted-foreground'
                      }`}
                      title={mode === 'fast' ? 'Mode Rapide' : 'Mode Complet'}
                    >
                      <HiOutlineCog6Tooth className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setIsExpanded(false)}
                      className="p-1 rounded-md hover:bg-muted/50 transition-colors"
                      title="Reduire (Echap)"
                    >
                      <HiOutlineChevronLeft className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Messages - Compact height */}
                <div className="h-[200px] sm:h-[280px] overflow-y-auto p-3 space-y-2">
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-4">
                      <HiOutlineSparkles className="w-8 h-8 text-primary/50 mb-2" />
                      <p className="text-xs text-muted-foreground">
                        Posez une question sur un territoire
                      </p>
                      <p className="text-[10px] text-muted-foreground/70 mt-1">
                        Ex: &quot;Analyse du departement 69&quot;
                      </p>
                    </div>
                  ) : (
                    messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] px-2 py-1.5 rounded-lg text-xs ${
                            msg.role === 'user'
                              ? 'bg-primary text-primary-foreground ml-2'
                              : 'glass mr-2'
                          }`}
                        >
                          {msg.content}
                          {msg.metadata?.confidence && (
                            <div className="mt-1 text-[9px] opacity-70">
                              Confiance: {Math.round(msg.metadata.confidence * 100)}%
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}

                  {/* Thinking indicator */}
                  {isAnalyzing && (
                    <div className="flex justify-start">
                      <div className="glass px-2 py-1.5 rounded-lg">
                        <ThinkingIndicator message={currentPhase || 'Analyse...'} />
                        {analysisProgress > 0 && (
                          <div className="mt-1 h-1 bg-muted/30 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary rounded-full transition-all duration-300"
                              style={{ width: `${analysisProgress}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Error message */}
                  {error && (
                    <div className="flex justify-center">
                      <div className="px-2 py-1.5 rounded-lg bg-[var(--error)]/20 text-[var(--error)] text-[10px]">
                        {error}
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <form onSubmit={handleSubmit} className="p-2 border-t border-border/50">
                  <div className="flex items-center gap-1.5">
                    <input
                      ref={inputRef}
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder="Question... (Ctrl+K)"
                      disabled={isAnalyzing}
                      className="flex-1 px-2 py-1.5 text-xs glass rounded-lg border-0 focus:ring-2 focus:ring-primary/30 disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={!inputValue.trim() || isAnalyzing}
                      className="p-1.5 rounded-lg bg-primary text-primary-foreground disabled:opacity-50 hover:opacity-90 transition-opacity"
                    >
                      <HiOutlinePaperAirplane className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {/* Mode indicator */}
                  <div className="mt-1.5 flex items-center justify-between text-[9px] text-muted-foreground">
                    <span>
                      {mode === 'fast' ? 'Rapide' : 'Complet'}
                    </span>
                    <span className="opacity-50">Ctrl+K</span>
                  </div>
                </form>
              </div>
            </motion.div>
          </div>
        </Draggable>
      ) : (
        <motion.button
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          onClick={() => setIsExpanded(true)}
          className={`absolute top-20 left-4 z-20 glass rounded-lg px-2 py-1.5 flex items-center gap-2 hover:bg-muted/50 transition-colors ${className}`}
          title="Ouvrir le chat (Ctrl+K)"
        >
          <HiOutlineChatBubbleLeftRight className="w-4 h-4 text-primary" />
          <HiOutlineChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
          {messages.length > 0 && (
            <span className="w-4 h-4 flex items-center justify-center rounded-full bg-primary text-primary-foreground text-[9px]">
              {messages.length}
            </span>
          )}
        </motion.button>
      )}
    </AnimatePresence>
  );
}
