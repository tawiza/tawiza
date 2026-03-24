'use client';

import { useState } from 'react';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import { cn } from '@/lib/utils';
import { ThinkingAnimation } from '@/components/ui/spoiler';
import { AgentTimeline, AgentSummaryBadge, type AgentPhase } from './AgentTimeline';
import {
  HiClipboard,
  HiCheck,
  HiHandThumbUp,
  HiHandThumbDown,
  HiChevronDown,
} from 'react-icons/hi2';

interface MessageCardProps {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  isThinking?: boolean;
  thinkingMessage?: string;
  confidence?: number;
  modeLabel?: string;
  agentPhases?: AgentPhase[];
  agentModel?: string;
  agentDuration?: number;
  onCopy?: (content: string) => void;
  onFeedback?: (useful: boolean) => void;
  feedbackGiven?: 'useful' | 'not_useful' | null;
}

const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="overflow-x-auto my-4 rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/30">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-border">{children}</tbody>,
  tr: ({ children }) => <tr className="hover:bg-muted/20 transition-colors">{children}</tr>,
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-sm text-muted-foreground">{children}</td>
  ),
  pre: ({ children }) => (
    <pre className="my-3 p-4 bg-zinc-950 border border-border rounded-xl overflow-x-auto text-[13px] leading-relaxed">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isInline = !className;
    return isInline ? (
      <code className="px-1.5 py-0.5 bg-primary/10 rounded text-[13px] font-mono text-primary" {...props}>
        {children}
      </code>
    ) : (
      <code className={cn('font-mono text-[13px]', className)} {...props}>{children}</code>
    );
  },
  ul: ({ children }) => <ul className="my-2 pl-5 space-y-1.5 list-disc marker:text-primary/50">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 pl-5 space-y-1.5 list-decimal marker:text-primary/50">{children}</ol>,
  li: ({ children }) => <li className="text-[14px] leading-relaxed">{children}</li>,
  h1: ({ children }) => (
    <h1 className="text-xl font-bold mt-6 mb-3 pb-2 border-b border-border">{children}</h1>
  ),
  h2: ({ children }) => <h2 className="text-lg font-semibold mt-5 mb-2">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-medium mt-4 mb-1.5">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 pl-4 border-l-3 border-primary/30 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-5 border-border" />,
  p: ({ children }) => <p className="my-2 text-[14px] leading-[1.7]">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic text-muted-foreground">{children}</em>,
};

export function MessageCard({
  id,
  role,
  content,
  isStreaming = false,
  isThinking = false,
  thinkingMessage = 'Analyse en cours...',
  confidence,
  modeLabel,
  agentPhases = [],
  agentModel,
  agentDuration,
  onCopy,
  onFeedback,
  feedbackGiven,
}: MessageCardProps) {
  const [copied, setCopied] = useState(false);
  const [timelineExpanded, setTimelineExpanded] = useState(false);
  const isUser = role === 'user';
  const hasAgentPhases = agentPhases.length > 0;
  const isAgentWorking = hasAgentPhases && agentPhases.some(p => p.status === 'running');

  const handleCopy = () => {
    onCopy?.(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // User message
  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[80%] lg:max-w-[70%]">
          <div className="bg-foreground/[0.08] rounded-2xl rounded-br-sm px-4 py-3">
            <p className="text-[14px] leading-relaxed whitespace-pre-wrap">{content}</p>
          </div>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="group animate-fade-in">
      <div className="flex gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 mt-1">
          <div className={cn(
            'h-7 w-7 rounded-lg flex items-center justify-center transition-all duration-300',
            'bg-gradient-to-br from-primary/20 to-primary/5 border border-border',
            (isStreaming || isAgentWorking) && 'border-primary/40 shadow-sm shadow-primary/10'
          )}>
            <span className={cn(
              'text-[11px] font-bold text-primary transition-opacity',
              (isThinking || isAgentWorking) && 'animate-pulse'
            )}>T</span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Agent Timeline - shown during thinking/streaming when phases exist */}
          {hasAgentPhases && (isThinking || isStreaming || isAgentWorking) && (
            <div className="mb-4 py-3 px-3 rounded-xl bg-muted/10 border border-border/30">
              <AgentTimeline
                phases={agentPhases}
                model={agentModel}
              />
            </div>
          )}

          {/* Collapsed timeline summary - after completion */}
          {hasAgentPhases && !isStreaming && !isThinking && !isAgentWorking && content && (
            <div className="mb-3">
              <button
                onClick={() => setTimelineExpanded(!timelineExpanded)}
                className="flex items-center gap-1.5 text-[11px] text-muted-foreground/50 hover:text-muted-foreground transition-colors group/tl"
              >
                <HiChevronDown className={cn(
                  'h-3 w-3 transition-transform duration-200',
                  timelineExpanded && 'rotate-180'
                )} />
                <span>Agent TAJINE</span>
                <span className="text-muted-foreground/30"> - </span>
                <AgentSummaryBadge
                  phases={agentPhases}
                  duration={agentDuration}
                />
              </button>
              {timelineExpanded && (
                <div className="mt-2 py-2 px-3 rounded-lg bg-muted/10 border border-border/20 animate-fade-in">
                  <AgentTimeline phases={agentPhases} model={agentModel} />
                </div>
              )}
            </div>
          )}

          {/* Thinking fallback (when no phases available) */}
          {isThinking && !content && !hasAgentPhases && (
            <div className="py-2">
              <ThinkingAnimation text={thinkingMessage} />
            </div>
          )}

          {/* Message content */}
          {content ? (
            <>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex, rehypeHighlight]}
                  components={markdownComponents}
                >
                  {content}
                </ReactMarkdown>
                {/* Streaming cursor */}
                {isStreaming && (
                  <span className="inline-block w-[3px] h-[18px] ml-0.5 -mb-[3px] bg-primary/70 rounded-full animate-cursor-blink" />
                )}
              </div>

              {/* Metadata + Actions footer */}
              {!isStreaming && (
                <div className="flex items-center gap-3 mt-3 pt-2">
                  {/* Confidence bar */}
                  {confidence !== undefined && (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div className="h-1 w-12 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-green-500 transition-all duration-500"
                          style={{ width: `${confidence * 100}%` }}
                        />
                      </div>
                      <span className="font-mono text-[11px]">{Math.round(confidence * 100)}%</span>
                    </div>
                  )}

                  {/* Mode badge */}
                  {modeLabel && (
                    <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-medium">
                      {modeLabel}
                    </span>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-0.5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    {!feedbackGiven && onFeedback && (
                      <>
                        <button
                          onClick={() => onFeedback(true)}
                          className="p-1.5 rounded-lg hover:bg-green-500/10 hover:text-green-500 text-muted-foreground transition-colors"
                          title="Utile"
                        >
                          <HiHandThumbUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onFeedback(false)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 hover:text-red-500 text-muted-foreground transition-colors"
                          title="Pas utile"
                        >
                          <HiHandThumbDown className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}

                    {feedbackGiven && (
                      <span className={cn(
                        'text-[11px] px-1.5 py-0.5 rounded',
                        feedbackGiven === 'useful' ? 'text-green-500' : 'text-muted-foreground'
                      )}>
                        {feedbackGiven === 'useful' ? 'Merci !' : 'Note'}
                      </span>
                    )}

                    <button
                      onClick={handleCopy}
                      className={cn(
                        'p-1.5 rounded-lg text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors',
                        copied && 'text-green-500'
                      )}
                      title="Copier"
                    >
                      {copied ? <HiCheck className="h-3.5 w-3.5" /> : <HiClipboard className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : !isThinking && !hasAgentPhases ? (
            <div className="py-2">
              <ThinkingAnimation text="Preparation de la reponse..." />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
