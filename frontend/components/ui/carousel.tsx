'use client';

import { useRef, useState, useEffect, useCallback, ReactNode } from 'react';
import { ChevronLeft, ChevronRight, X, Maximize2 } from 'lucide-react';

interface CarouselProps {
  children: ReactNode[];
  autoScrollMs?: number;
  className?: string;
  slideLabels?: string[];
}

export function Carousel({ children, autoScrollMs, className = '', slideLabels }: CarouselProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const totalSlides = children.length;

  const scrollToIndex = useCallback((index: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const target = Math.max(0, Math.min(index, totalSlides - 1));
    el.scrollTo({ left: target * el.offsetWidth, behavior: 'smooth' });
    setActiveIndex(target);
  }, [totalSlides]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el || el.offsetWidth === 0) return;
    const idx = Math.round(el.scrollLeft / el.offsetWidth);
    setActiveIndex(idx);
  }, []);

  // Auto-scroll (pauses when expanded or user interacted)
  useEffect(() => {
    if (!autoScrollMs || totalSlides <= 1 || paused || expandedIndex !== null) return;
    const timer = setInterval(() => {
      setActiveIndex(prev => {
        const next = (prev + 1) % totalSlides;
        scrollToIndex(next);
        return next;
      });
    }, autoScrollMs);
    return () => clearInterval(timer);
  }, [autoScrollMs, totalSlides, scrollToIndex, paused, expandedIndex]);

  // Pause auto-scroll on user interaction
  const handleUserInteraction = useCallback(() => {
    setPaused(true);
    // Resume after 30s of inactivity
    const timer = setTimeout(() => setPaused(false), 30000);
    return () => clearTimeout(timer);
  }, []);

  // ESC to close expanded view
  useEffect(() => {
    if (expandedIndex === null) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpandedIndex(null);
    };
    window.addEventListener('keydown', handler);
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
    };
  }, [expandedIndex]);

  if (totalSlides === 0) return null;

  return (
    <>
      {/* Normal carousel view */}
      <div className={`relative group ${className}`}>
        {/* Slides container */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="flex overflow-x-auto snap-x snap-mandatory scrollbar-hide"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {children.map((child, i) => (
            <div key={i} className="w-full flex-shrink-0 snap-center relative">
              {child}
              {/* Expand button overlay */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedIndex(i);
                  handleUserInteraction();
                }}
                className="absolute top-3 right-3 z-20 h-8 w-8 rounded-lg bg-card border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-card transition-all shadow-sm opacity-60 md:opacity-0 md:group-hover:opacity-100"
                title="Agrandir"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        {/* Navigation arrows */}
        {totalSlides > 1 && (
          <>
            <button
              onClick={() => { scrollToIndex(activeIndex - 1); handleUserInteraction(); }}
              disabled={activeIndex === 0}
              className="absolute left-1 md:left-2 top-1/2 -translate-y-1/2 z-10 h-8 w-8 rounded-full bg-card border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-card transition-all md:opacity-0 md:group-hover:opacity-100 disabled:opacity-0 shadow-sm"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => { scrollToIndex(activeIndex + 1); handleUserInteraction(); }}
              disabled={activeIndex === totalSlides - 1}
              className="absolute right-1 md:right-2 top-1/2 -translate-y-1/2 z-10 h-8 w-8 rounded-full bg-card border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-card transition-all md:opacity-0 md:group-hover:opacity-100 disabled:opacity-0 shadow-sm"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </>
        )}

        {/* Dots + labels */}
        {totalSlides > 1 && (
          <div className="flex items-center justify-center gap-2 mt-3">
            {children.map((_, i) => (
              <button
                key={i}
                onClick={() => { scrollToIndex(i); handleUserInteraction(); }}
                className={`flex items-center gap-1.5 transition-all ${
                  i === activeIndex
                    ? 'text-primary'
                    : 'text-muted-foreground/40 hover:text-muted-foreground/70'
                }`}
              >
                <span className={`block rounded-full transition-all ${
                  i === activeIndex ? 'w-6 h-2 bg-primary' : 'w-2 h-2 bg-current'
                }`} />
                {slideLabels?.[i] && (
                  <span className={`text-xs font-medium transition-all hidden sm:inline ${
                    i === activeIndex ? 'opacity-100' : 'opacity-0 w-0 overflow-hidden'
                  }`}>
                    {slideLabels[i]}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Expanded fullscreen overlay */}
      {expandedIndex !== null && (
        <div
          className="fixed inset-0 z-[100] bg-background flex flex-col animate-fade-in"
          onClick={() => setExpandedIndex(null)}
        >
          {/* Header */}
          <div className="shrink-0 flex items-center justify-between px-4 md:px-6 py-3 border-b border-border/50">
            <div className="flex items-center gap-3">
              {slideLabels?.[expandedIndex] && (
                <h2 className="text-lg font-semibold">{slideLabels[expandedIndex]}</h2>
              )}
              <span className="text-xs text-muted-foreground">
                {expandedIndex + 1}/{totalSlides}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Prev/Next in expanded mode */}
              {totalSlides > 1 && (
                <>
                  <button
                    onClick={(e) => { e.stopPropagation(); setExpandedIndex(Math.max(0, expandedIndex - 1)); }}
                    disabled={expandedIndex === 0}
                    className="h-8 w-8 rounded-lg border border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition disabled:opacity-30"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setExpandedIndex(Math.min(totalSlides - 1, expandedIndex + 1)); }}
                    disabled={expandedIndex === totalSlides - 1}
                    className="h-8 w-8 rounded-lg border border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition disabled:opacity-30"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); setExpandedIndex(null); }}
                className="h-8 w-8 rounded-lg border border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Content - full height */}
          <div
            className="flex-1 overflow-y-auto p-4 md:p-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="max-w-[1400px] mx-auto h-full [&_.h-\[250px\]]:h-[500px] [&_.h-\[300px\]]:h-[600px] [&_.h-\[320px\]]:h-[600px] [&_.md\:h-\[320px\]]:h-[600px] [&_.h-\[300px\].md\:h-\[500px\]]:h-[700px]">
              {children[expandedIndex]}
            </div>
          </div>

          {/* Slide tabs at bottom */}
          {totalSlides > 1 && (
            <div className="shrink-0 flex items-center justify-center gap-1 px-4 py-3 border-t border-border/50">
              {children.map((_, i) => (
                <button
                  key={i}
                  onClick={(e) => { e.stopPropagation(); setExpandedIndex(i); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    i === expandedIndex
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  {slideLabels?.[i] || `Slide ${i + 1}`}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
