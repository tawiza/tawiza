'use client';

import { Card } from '@/components/ui/card';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';

// Cognitive level colors (Nord Aurora)
const LEVEL_BORDER_COLORS: Record<string, string> = {
  reactive: 'border-l-info',     // nord9
  analytical: 'border-l-[var(--chart-2)]',   // nord8
  strategic: 'border-l-[var(--chart-4)]',    // nord7
  prospective: 'border-l-success',  // nord14
  theoretical: 'border-l-[var(--chart-3)]',  // nord15
};

const LEVEL_GLOW_COLORS: Record<string, string> = {
  reactive: 'shadow-[0_0_12px_rgba(129,161,193,0.3)]',
  analytical: 'shadow-[0_0_12px_rgba(136,192,208,0.3)]',
  strategic: 'shadow-[0_0_12px_rgba(143,188,187,0.3)]',
  prospective: 'shadow-[0_0_12px_rgba(163,190,140,0.3)]',
  theoretical: 'shadow-[0_0_12px_rgba(180,142,173,0.3)]',
};

interface MessageBoxProps {
  output: string;
  isStreaming?: boolean;
  level?: string;
}

export default function MessageBox({ output, isStreaming = false, level = 'analytical' }: MessageBoxProps) {
  const borderColor = LEVEL_BORDER_COLORS[level] || LEVEL_BORDER_COLORS.analytical;
  const glowColor = LEVEL_GLOW_COLORS[level] || '';

  return (
    <Card
      className={cn(
        'relative glass-card !max-h-max w-full transition-all duration-300',
        'border-l-4',
        borderColor,
        isStreaming && glowColor,
        output ? 'flex' : 'hidden'
      )}
    >
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown
          components={{
            // Style headings
            h1: ({ children }) => <h1 className="text-xl font-bold text-foreground mb-3">{children}</h1>,
            h2: ({ children }) => <h2 className="text-lg font-semibold text-foreground mb-2">{children}</h2>,
            h3: ({ children }) => <h3 className="text-base font-medium text-foreground mb-2">{children}</h3>,
            // Style paragraphs
            p: ({ children }) => <p className="text-sm leading-relaxed text-foreground/90 mb-3 last:mb-0">{children}</p>,
            // Style lists
            ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 text-sm">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 text-sm">{children}</ol>,
            li: ({ children }) => <li className="text-foreground/90">{children}</li>,
            // Style code blocks
            code: ({ className, children, ...props }) => {
              const isInline = !className;
              if (isInline) {
                return (
                  <code className="px-1.5 py-0.5 rounded bg-muted text-primary text-xs font-mono" {...props}>
                    {children}
                  </code>
                );
              }
              return (
                <code className={cn("block p-3 rounded-lg bg-muted/50 text-sm font-mono overflow-x-auto", className)} {...props}>
                  {children}
                </code>
              );
            },
            pre: ({ children }) => <pre className="mb-3 overflow-hidden rounded-lg">{children}</pre>,
            // Style blockquotes
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-primary/50 pl-4 italic text-muted-foreground mb-3">
                {children}
              </blockquote>
            ),
            // Style links
            a: ({ href, children }) => (
              <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
            // Style tables
            table: ({ children }) => (
              <div className="overflow-x-auto mb-3">
                <table className="min-w-full divide-y divide-border text-sm">{children}</table>
              </div>
            ),
            th: ({ children }) => <th className="px-3 py-2 text-left font-medium bg-muted/50">{children}</th>,
            td: ({ children }) => <td className="px-3 py-2 border-t border-border/50">{children}</td>,
            // Style strong/emphasis
            strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
            em: ({ children }) => <em className="italic">{children}</em>,
          }}
        >
          {output || ''}
        </ReactMarkdown>
      </div>

      {/* Typing cursor animation when streaming */}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse rounded-sm" />
      )}
    </Card>
  );
}
