'use client';

import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';
import {
  HiArrowUp,
  HiBolt,
  HiSparkles,
  HiStop,
} from 'react-icons/hi2';

interface ChatInputProps {
  onSubmit: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  fastMode?: boolean;
  onFastModeChange?: (fast: boolean) => void;
  placeholder?: string;
  suggestedQueries?: string[];
  onSuggestedQuery?: (query: string) => void;
}

export function ChatInput({
  onSubmit,
  onStop,
  disabled = false,
  isStreaming = false,
  fastMode = false,
  onFastModeChange,
  placeholder = "Posez votre question sur l'economie territoriale...",
  suggestedQueries = [],
  onSuggestedQuery,
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  };

  useEffect(() => { adjustHeight(); }, [message]);
  useEffect(() => { textareaRef.current?.focus(); }, []);

  useEffect(() => {
    const handleGlobalKeydown = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleGlobalKeydown);
    return () => window.removeEventListener('keydown', handleGlobalKeydown);
  }, []);

  const handleSubmit = () => {
    if (!message.trim() || disabled || isStreaming) return;
    onSubmit(message);
    setMessage('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = message.trim() && !isStreaming && !disabled;

  return (
    <div className="absolute bottom-0 left-0 right-0 z-40">
      {/* Gradient fade */}
      <div className="h-12 bg-gradient-to-t from-background via-background/80 to-transparent pointer-events-none" />

      <div className="bg-background pb-5 px-4">
        <div className="max-w-3xl mx-auto">
          {/* Suggested queries */}
          {!message && suggestedQueries.length > 0 && (
            <div className="grid grid-cols-2 gap-2 mb-3">
              {suggestedQueries.slice(0, 4).map((query, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setMessage(query);
                    onSuggestedQuery?.(query);
                  }}
                  className="group/q flex items-start gap-2.5 p-3 rounded-xl text-left text-sm
                    bg-card/80 backdrop-blur-sm border border-border/60
                    hover:border-primary/30 hover:bg-primary/5 hover:shadow-sm
                    text-muted-foreground hover:text-foreground
                    transition-all duration-200"
                >
                  <HiSparkles className="h-3.5 w-3.5 text-primary/60 group-hover/q:text-primary flex-shrink-0 mt-0.5 transition-colors" />
                  <span className="line-clamp-2 text-[13px] leading-snug">{query}</span>
                </button>
              ))}
            </div>
          )}

          {/* Input container */}
          <div
            className={cn(
              'relative rounded-2xl border transition-all duration-200',
              'bg-card/90 backdrop-blur-sm shadow-lg shadow-black/5',
              isStreaming
                ? 'border-primary/30 shadow-primary/5'
                : 'border-border/60 focus-within:border-primary/40 focus-within:shadow-primary/5'
            )}
          >
            {/* Streaming glow effect */}
            {isStreaming && (
              <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-r from-primary/20 via-primary/10 to-primary/20 animate-border-glow -z-10 blur-[2px]" />
            )}

            {/* Textarea area */}
            <div className="flex items-end gap-2 px-4 pt-3 pb-2">
              <textarea
                ref={textareaRef}
                placeholder={placeholder}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled || isStreaming}
                rows={1}
                className={cn(
                  'flex-1 resize-none bg-transparent border-0 focus:ring-0 focus:outline-none',
                  'text-sm leading-relaxed px-0 py-1',
                  'placeholder:text-muted-foreground/40',
                  'max-h-[200px] overflow-y-auto scrollbar-hide',
                  'disabled:opacity-40'
                )}
                style={{ minHeight: '28px' }}
              />

              {/* Action button */}
              <button
                onClick={isStreaming ? onStop : handleSubmit}
                disabled={!isStreaming && !canSend}
                className={cn(
                  'flex-shrink-0 h-8 w-8 rounded-lg flex items-center justify-center transition-all duration-200',
                  isStreaming
                    ? 'bg-foreground text-background hover:bg-foreground/80'
                    : canSend
                      ? 'bg-foreground text-background hover:bg-foreground/80 scale-100'
                      : 'bg-muted/60 text-muted-foreground/40 cursor-not-allowed scale-95'
                )}
              >
                {isStreaming ? (
                  <HiStop className="h-3.5 w-3.5" />
                ) : (
                  <HiArrowUp className="h-4 w-4" />
                )}
              </button>
            </div>

            {/* Bottom toolbar */}
            <div className="flex items-center justify-between px-4 py-2 border-t border-border/30">
              {/* Mode toggle */}
              <div className="flex items-center gap-0.5 bg-muted/40 rounded-lg p-0.5">
                <button
                  onClick={() => onFastModeChange?.(true)}
                  className={cn(
                    'flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-200',
                    fastMode
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  <HiBolt className="h-3 w-3" />
                  Rapide
                </button>
                <button
                  onClick={() => onFastModeChange?.(false)}
                  className={cn(
                    'flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-200',
                    !fastMode
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  <HiSparkles className="h-3 w-3" />
                  Complet
                </button>
              </div>

              {/* Hints */}
              <div className="flex items-center gap-2">
                <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-muted/50 text-[10px] text-muted-foreground/50 font-mono">
                  Enter
                </kbd>
                <span className="text-[10px] text-muted-foreground/40 hidden sm:inline">
                  pour envoyer
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
