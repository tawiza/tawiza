'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';
import { cn } from '@/lib/utils';
import {
  HiUser,
  HiPaperAirplane,
  HiBolt,
  HiArrowDownTray,
  HiShare,
  HiDocumentText,
  HiCodeBracket,
  HiTableCells,
  HiDocument,
  HiMapPin,
  HiXMark,
  HiSparkles,
  HiClipboard,
  HiCheck,
  HiChevronDown,
  HiHandThumbUp,
  HiHandThumbDown,
} from 'react-icons/hi2';
import { ChatMessageSkeleton } from '@/components/skeletons';
import { OrbitSpinner } from '@/components/ui/orbit-spinner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';
import {
  getConversation,
  createConversation,
  addMessage,
  ConversationDetail,
  Message,
} from '@/lib/api-conversations';
import {
  exportAsJson,
  exportAsMarkdown,
  exportAsCsv,
  exportAsPdf,
  generateShareableLink,
  copyToClipboard,
} from '@/lib/export-utils';
import { getAccessToken, useAuth } from '@/contexts/AuthContext';
import { useTAJINE, AnalysisResult } from '@/contexts/TAJINEContext';
import { ReasoningStep } from '@/components/ui/reasoning-display';

// Cognitive levels - simplified for professional use
type TAJINELevel = 'reactive' | 'analytical' | 'strategic' | 'prospective' | 'theoretical';

const LEVELS: { id: TAJINELevel; name: string; description: string; color: string }[] = [
  { id: 'reactive', name: 'Reactif', description: 'Reponses rapides', color: 'var(--info)' },
  { id: 'analytical', name: 'Analytique', description: 'Analyse statistique', color: 'var(--chart-2)' },
  { id: 'strategic', name: 'Strategique', description: 'Recommandations', color: 'var(--chart-4)' },
  { id: 'prospective', name: 'Prospectif', description: 'Predictions', color: 'var(--success)' },
  { id: 'theoretical', name: 'Theorique', description: 'Cadres conceptuels', color: 'var(--chart-3)' },
];

// Copy message to clipboard helper with fallback for non-HTTPS contexts
const copyMessageContent = async (content: string): Promise<boolean> => {
  // Method 1: Modern Clipboard API (requires HTTPS or localhost)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(content);
      return true;
    } catch {
      // Fallback to method 2
    }
  }

  // Method 2: execCommand fallback for non-secure contexts
  const textarea = document.createElement('textarea');
  textarea.value = content;
  textarea.style.cssText = 'position:fixed;opacity:0;left:-9999px;top:-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    const success = document.execCommand('copy');
    document.body.removeChild(textarea);
    return success;
  } catch {
    document.body.removeChild(textarea);
    return false;
  }
};

const LEVEL_BORDER_COLORS: Record<string, string> = {
  reactive: 'border-l-info',
  analytical: 'border-l-[var(--chart-2)]',
  strategic: 'border-l-[var(--chart-4)]',
  prospective: 'border-l-success',
  theoretical: 'border-l-[var(--chart-3)]',
};

// PPDSL phases for Complete mode display
const PPDSL_PHASES = [
  { id: 'perceive', name: 'Perception', icon: 'P', color: 'var(--info)' },
  { id: 'plan', name: 'Planification', icon: 'P', color: 'var(--chart-2)' },
  { id: 'delegate', name: 'Delegation', icon: 'D', color: 'var(--chart-4)' },
  { id: 'synthesize', name: 'Synthese', icon: 'S', color: 'var(--success)' },
  { id: 'learn', name: 'Apprentissage', icon: 'L', color: 'var(--chart-3)' },
];

interface ChatViewProps {
  conversationId: string | null;
  onConversationCreated: (id: string) => void;
}

// Cognitive signature from unified mode
interface CognitiveSignature {
  discovery?: boolean;
  causal?: boolean;
  scenario?: boolean;
  strategy?: boolean;
  theoretical?: boolean;
}

interface MessageMetadata {
  confidence?: number;
  cognitive_signature?: CognitiveSignature;
  unified?: boolean;
  fast?: boolean;
}

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

// Custom markdown components for better rendering
const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="overflow-x-auto my-4 rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-muted/50">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-border bg-background">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-muted/30 transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-xs font-semibold text-foreground uppercase tracking-wider whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-sm text-muted-foreground whitespace-nowrap">{children}</td>
  ),
  // Better code blocks
  pre: ({ children }) => (
    <pre className="my-3 p-4 bg-muted/50 rounded-lg overflow-x-auto text-xs">{children}</pre>
  ),
  code: ({ className, children, ...props }) => {
    const isInline = !className;
    return isInline ? (
      <code className="px-1.5 py-0.5 bg-muted rounded text-xs font-mono text-primary" {...props}>
        {children}
      </code>
    ) : (
      <code className={cn('font-mono text-xs', className)} {...props}>{children}</code>
    );
  },
  // Better lists
  ul: ({ children }) => (
    <ul className="my-2 pl-4 space-y-1 list-disc marker:text-primary">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 pl-4 space-y-1 list-decimal marker:text-primary">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-sm text-muted-foreground">{children}</li>
  ),
  // Better headings
  h1: ({ children }) => (
    <h1 className="text-xl font-bold text-foreground mt-4 mb-2 border-b border-border pb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-foreground mt-3 mb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-medium text-foreground mt-2 mb-1">{children}</h3>
  ),
  // Better blockquotes
  blockquote: ({ children }) => (
    <blockquote className="my-3 pl-4 border-l-4 border-primary/50 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  // Better horizontal rules
  hr: () => (
    <hr className="my-4 border-border" />
  ),
  // Better paragraphs
  p: ({ children }) => (
    <p className="my-2 text-sm leading-relaxed">{children}</p>
  ),
  // Better strong/emphasis
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-muted-foreground">{children}</em>
  ),
};

export default function ChatView({ conversationId, onConversationCreated }: ChatViewProps) {
  const { user } = useAuth();
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [level, setLevel] = useState<TAJINELevel>('analytical');
  const [fastMode, setFastMode] = useState(true); // Default to fast mode (PPDSL mode available via toggle)
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false); // True when AI is processing but no content yet
  const [messageMetadata, setMessageMetadata] = useState<Record<string, MessageMetadata>>({});
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'useful' | 'not_useful'>>({});
  // PPDSL phase tracking for Complete mode
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [phaseMessage, setPhaseMessage] = useState<string>('');
  // Ref to track accumulated response - avoids closure issues with React batching
  const fullResponseRef = useRef<string>('');

  // ReasoningDisplay steps - converted from PPDSL phases
  const reasoningSteps: ReasoningStep[] = PPDSL_PHASES.map((phase, idx) => {
    const currentIdx = PPDSL_PHASES.findIndex(p => p.id === currentPhase);
    return {
      id: phase.id,
      label: phase.name,
      status: idx < currentIdx ? 'done' : phase.id === currentPhase ? 'active' : 'pending',
    };
  });
  const reasoningProgress = currentPhase
    ? Math.round(((PPDSL_PHASES.findIndex(p => p.id === currentPhase) + 1) / PPDSL_PHASES.length) * 100)
    : 0;
  const scrollRef = useRef<HTMLDivElement>(null);

  // TAJINE context for sharing analysis results with visualizations
  const { addAnalysisResult, selectedDepartment, setSelectedDepartment, latestAnalysis } = useTAJINE();

  // Include department context in query when selected
  const buildQueryWithContext = (query: string): string => {
    if (selectedDepartment && !query.toLowerCase().includes(selectedDepartment)) {
      return `[Departement ${selectedDepartment}] ${query}`;
    }
    return query;
  };

  // Suggested queries based on selected department
  const suggestedQueries = selectedDepartment
    ? [
        `Analyse economique du departement ${selectedDepartment}`,
        `Secteurs porteurs dans le ${selectedDepartment}`,
        `Tendances de creation d'entreprises`,
        `Comparaison regionale`,
      ]
    : [
        'Analyse des secteurs porteurs en France',
        'Tendances economiques nationales',
        'Top 10 departements par creation',
        'Predictions 2025',
      ];

  const handleSuggestedQuery = (query: string) => {
    setInputMessage(query);
  };

  // Export handlers
  const handleExport = (format: 'pdf' | 'json' | 'csv' | 'md') => {
    if (!conversation) {
      toast.error('Aucune conversation', {
        description: 'Commencez une conversation avant de pouvoir exporter.',
      });
      return;
    }

    try {
      switch (format) {
        case 'pdf':
          exportAsPdf(conversation);
          break;
        case 'json':
          exportAsJson(conversation);
          break;
        case 'csv':
          exportAsCsv(conversation);
          break;
        case 'md':
          exportAsMarkdown(conversation);
          break;
      }
      toast.success('Export reussi', {
        description: `La conversation a ete exportee en ${format.toUpperCase()}.`,
      });
    } catch {
      toast.error('Erreur d\'export', {
        description: 'Une erreur est survenue lors de l\'export.',
      });
    }
  };

  const handleShare = async () => {
    if (!conversation) {
      toast.error('Aucune conversation', {
        description: 'Commencez une conversation avant de pouvoir partager.',
      });
      return;
    }

    const shareableLink = generateShareableLink(conversation.id);
    const success = await copyToClipboard(shareableLink);

    if (success) {
      toast.success('Lien copie !', {
        description: 'Le lien de partage a ete copie dans le presse-papiers.',
      });
    } else {
      toast.error('Erreur de copie', {
        description: 'Impossible de copier le lien. Essayez manuellement.',
      });
    }
  };

  // Copy message handler
  const handleCopyMessage = async (messageId: string, content: string) => {
    const success = await copyMessageContent(content);
    if (success) {
      setCopiedMessageId(messageId);
      toast.success('Message copie');
      // Reset after 2 seconds
      setTimeout(() => setCopiedMessageId(null), 2000);
    } else {
      toast.error('Erreur de copie');
    }
  };

  // Feedback handler for DPO data collection
  const handleFeedback = async (messageId: string, useful: boolean) => {
    const feedback = useful ? 'useful' : 'not_useful';
    setFeedbackGiven((prev) => ({ ...prev, [messageId]: feedback }));

    // Find the message and send feedback to backend
    const message = messages.find((m) => m.id === messageId);
    if (!message) return;

    try {
      await fetch('/api/v1/tajine/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: messageId,
          conversation_id: conversationId,
          content: message.content,
          useful,
          // Include metadata for DPO training
          metadata: messageMetadata[messageId],
        }),
      });
      toast.success(useful ? 'Merci pour votre retour positif' : 'Retour enregistre');
    } catch {
      // Still show success to user, feedback saved locally
      toast.success('Retour enregistre');
    }
  };

  // Load conversation
  useEffect(() => {
    if (conversationId) {
      loadConversation(conversationId);
    } else {
      setConversation(null);
      setMessages([]);
    }
  }, [conversationId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const loadConversation = async (id: string) => {
    setIsLoading(true);
    try {
      const data = await getConversation(id);
      setConversation(data);
      setMessages(data.messages);
      setLevel(data.level as TAJINELevel);
    } catch (error) {
      console.error('Error loading conversation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!inputMessage.trim() || isStreaming) return;

    const userMessage = inputMessage;
    setInputMessage('');
    setIsStreaming(true);
    setIsThinking(true); // Start thinking phase

    // Add user message to UI immediately (before any async operations)
    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      // Try to create/use conversation (optional - chat works without it)
      let currentConvId = conversationId;
      try {
        if (!currentConvId) {
          const newConv = await createConversation(undefined, level);
          currentConvId = newConv.id;
          setConversation(newConv);
          onConversationCreated(newConv.id);
        }
        // Save user message to backend (if conversation exists)
        if (currentConvId) {
          await addMessage(currentConvId, 'user', userMessage);
        }
      } catch (convError) {
        // Conversation API failed (likely not authenticated)
        // Continue anyway - chat will work without persistence
        console.warn('Conversation API unavailable, continuing without persistence:', convError);
      }

      // Create placeholder for assistant response
      const tempAssistantMsg: Message = {
        id: `temp-assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempAssistantMsg]);

      // Call TAJINE API with streaming (include department context if selected)
      const queryWithContext = buildQueryWithContext(userMessage);
      const response = await fetch('/api/tajine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryWithContext,
          cognitive_level: level,
          fast: fastMode,
          department: selectedDepartment || undefined,
          session_id: user?.id || 'anonymous',
        }),
      });

      if (!response.ok) {
        throw new Error('Erreur de communication avec TAJINE');
      }

      // Parse SSE streaming response
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      // Reset the ref at the start of each request
      fullResponseRef.current = '';
      let currentMsgId = tempAssistantMsg.id;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = JSON.parse(line.slice(6));

              // Handle PPDSL phase events (Complete mode only)
              if (jsonData.type === 'phase') {
                setCurrentPhase(jsonData.phase);
                setPhaseMessage(jsonData.message || '');
              }

              // Handle progress events (heartbeat messages during long operations)
              if (jsonData.type === 'progress') {
                setPhaseMessage(jsonData.message || 'Analyse en cours...');
              }

              if (jsonData.type === 'content' && jsonData.text) {
                // First content received - exit thinking phase
                if (isThinking) {
                  setIsThinking(false);
                }
                // Use ref to avoid closure issues with React batching
                fullResponseRef.current += jsonData.text;
                const currentContent = fullResponseRef.current;
                // Update the assistant message in real-time
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (updated[lastIdx]?.role === 'assistant') {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      content: currentContent,
                    };
                  }
                  return updated;
                });
              }

              // Capture metadata from completion event
              if (jsonData.type === 'complete') {
                // Clear phase tracking
                setCurrentPhase(null);
                setPhaseMessage('');

                const metadata: MessageMetadata = {
                  confidence: jsonData.confidence,
                  cognitive_signature: jsonData.cognitive_signature,
                  unified: jsonData.unified,
                  fast: jsonData.fast,
                };
                setMessageMetadata((prev) => ({
                  ...prev,
                  [currentMsgId]: metadata,
                }));

                // Share analysis result with visualizations via context
                // Extract chart data if present in the response
                const analysisResult: AnalysisResult = {
                  id: currentMsgId,
                  timestamp: new Date(),
                  department: selectedDepartment,
                  cognitiveLevel: level,
                  confidence: jsonData.confidence,
                  insights: jsonData.cognitive_signature?.insights || [],
                  // Chart data from backend analysis
                  radarData: jsonData.charts?.radar,
                  treemapData: jsonData.charts?.treemap,
                  heatmapData: jsonData.charts?.heatmap,
                  sankeyData: jsonData.charts?.sankey,
                };
                addAnalysisResult(analysisResult);
              }

              // Handle real-time chart data updates
              if (jsonData.type === 'chart_data') {
                const chartUpdate: Partial<AnalysisResult> = {
                  id: currentMsgId,
                  timestamp: new Date(),
                  department: selectedDepartment,
                  cognitiveLevel: level,
                };
                if (jsonData.chart === 'radar' && jsonData.data) {
                  chartUpdate.radarData = jsonData.data;
                }
                if (jsonData.chart === 'treemap' && jsonData.data) {
                  chartUpdate.treemapData = jsonData.data;
                }
                if (jsonData.chart === 'heatmap' && jsonData.data) {
                  chartUpdate.heatmapData = jsonData.data;
                }
                if (jsonData.chart === 'sankey' && jsonData.data) {
                  chartUpdate.sankeyData = jsonData.data;
                }
                addAnalysisResult(chartUpdate as AnalysisResult);
              }
            } catch (parseError) {
              // Raw text fallback
              const rawText = line.slice(6);
              if (rawText.trim()) {
                fullResponseRef.current += rawText;
                const currentContent = fullResponseRef.current;
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (updated[lastIdx]?.role === 'assistant') {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      content: currentContent,
                    };
                  }
                  return updated;
                });
              }
            }
          }
        }
      }

      // Save assistant message to backend (if conversation exists)
      if (fullResponseRef.current && currentConvId) {
        try {
          await addMessage(currentConvId, 'assistant', fullResponseRef.current);
        } catch {
          console.warn('Failed to save assistant message');
        }
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue';

      // Always show toast for immediate user feedback
      toast.error('Erreur de communication', {
        description: errorMessage,
      });

      // Update assistant message if it exists
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (updated[lastIdx]?.role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: `Erreur: ${errorMessage}`,
          };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col h-full">
        {/* Header skeleton */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 w-20 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        </div>
        {/* Messages skeleton */}
        <div className="flex-1 p-4 space-y-4 max-w-3xl mx-auto w-full">
          <ChatMessageSkeleton isUser={false} />
          <ChatMessageSkeleton isUser={true} />
          <ChatMessageSkeleton isUser={false} />
        </div>
        {/* Input skeleton */}
        <div className="p-4 border-t border-border">
          <div className="flex gap-2 max-w-3xl mx-auto">
            <div className="flex-1 h-12 bg-muted rounded-lg animate-pulse" />
            <div className="h-12 w-16 bg-muted rounded-lg animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Department indicator (when selected from map) */}
      {selectedDepartment && (
        <div className="px-3 py-2 sm:px-4 bg-primary/5 border-b border-primary/20 flex items-center gap-2">
          <HiMapPin className="h-4 w-4 text-primary flex-shrink-0" />
          <span className="text-xs sm:text-sm font-medium text-primary truncate">
            Dept. {selectedDepartment}
          </span>
          <span className="hidden sm:inline text-xs text-muted-foreground">
            Les requetes seront contextualisees
          </span>
          <button
            onClick={() => setSelectedDepartment(null)}
            className="ml-auto p-1.5 rounded-lg hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
            title="Retirer le contexte departement"
          >
            <HiXMark className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Toolbar - Clean professional design */}
      <div className="px-3 py-2 sm:px-4 sm:py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-3 max-w-3xl mx-auto">
          {/* Mode Toggle - Clear and prominent */}
          <div className="flex items-center bg-background rounded-lg p-1 border border-border">
            <button
              onClick={() => setFastMode(true)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all',
                fastMode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Rapide
            </button>
            <button
              onClick={() => setFastMode(false)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all',
                !fastMode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Complet
            </button>
          </div>

          {/* Level Selector - Dropdown for cleaner UI */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-background border border-border text-xs sm:text-sm hover:bg-accent transition-colors">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: LEVELS.find(l => l.id === level)?.color }}
                />
                <span className="hidden sm:inline">{LEVELS.find(l => l.id === level)?.name}</span>
                <span className="sm:hidden">{LEVELS.find(l => l.id === level)?.name.slice(0, 4)}</span>
                <HiChevronDown className="h-3 w-3 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-48">
              {LEVELS.map((l) => (
                <DropdownMenuItem
                  key={l.id}
                  onClick={() => setLevel(l.id)}
                  className={cn(level === l.id && 'bg-accent')}
                >
                  <span
                    className="w-2 h-2 rounded-full mr-2"
                    style={{ backgroundColor: l.color }}
                  />
                  <div className="flex flex-col">
                    <span className="font-medium">{l.name}</span>
                    <span className="text-[10px] text-muted-foreground">{l.description}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Actions */}
          <div className="flex items-center gap-1">
            <TooltipProvider>
              {/* Export Dropdown */}
              <DropdownMenu>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        disabled={!conversation}
                      >
                        <HiArrowDownTray className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                  <TooltipContent>Exporter</TooltipContent>
                </Tooltip>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem onClick={() => handleExport('pdf')}>
                    <HiDocument className="h-4 w-4 mr-2" />
                    PDF
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport('md')}>
                    <HiDocumentText className="h-4 w-4 mr-2" />
                    Markdown
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => handleExport('json')}>
                    <HiCodeBracket className="h-4 w-4 mr-2" />
                    JSON
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleExport('csv')}>
                    <HiTableCells className="h-4 w-4 mr-2" />
                    CSV
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Share Button */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleShare}
                    disabled={!conversation}
                  >
                    <HiShare className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Partager</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea ref={scrollRef} className="flex-1 px-3 py-4 sm:p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground px-4">
            <img src="/loading-tajine.webp" alt="TAJINE" className="w-32 h-auto drop-shadow-lg" />
            <p className="mt-4 text-base sm:text-lg font-medium">TAJINE</p>
            <p className="text-xs sm:text-sm text-center">
              {selectedDepartment
                ? `Analyse du departement ${selectedDepartment}`
                : "Posez votre question sur l'economie territoriale"}
            </p>

            {/* Suggested queries */}
            <div className="mt-4 sm:mt-6 flex flex-wrap justify-center gap-1.5 sm:gap-2 max-w-md sm:max-w-lg">
              {suggestedQueries.map((query, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedQuery(query)}
                  className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 sm:py-1.5 rounded-full text-[10px] sm:text-xs bg-accent/50 hover:bg-accent text-foreground transition-all hover:scale-105"
                >
                  <HiSparkles className="h-2.5 sm:h-3 w-2.5 sm:w-3 text-primary" />
                  <span className="line-clamp-1">{query}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-3 sm:space-y-4 max-w-3xl mx-auto">
            {messages.map((msg, idx) => (
              <div
                key={msg.id}
                className={cn(
                  'flex gap-2 sm:gap-3',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
{/* Removed EnergyOrb and external OrbitSpinner - using only internal OrbitSpinner */}
                <div className="group relative max-w-[90%] sm:max-w-[80%]">
                  <Card
                    className={cn(
                      'p-3 sm:p-4',
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : cn('border-l-4', LEVEL_BORDER_COLORS[level])
                    )}
                  >
                    {msg.role === 'assistant' ? (
                      <>
                        {/* Show loading spinner when AI is processing */}
                        {isStreaming && idx === messages.length - 1 && !msg.content ? (
                          <div className="py-3 flex items-center gap-3">
                            <OrbitSpinner size="md" color="var(--chart-5)" particleCount={3} />
                            <span className="text-sm text-muted-foreground">
                              {phaseMessage || 'Analyse en cours...'}
                            </span>
                          </div>
                        ) : msg.content ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkMath]}
                              rehypePlugins={[rehypeKatex, rehypeHighlight]}
                              components={markdownComponents}
                            >
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <div className="text-sm text-muted-foreground italic">
                            Reponse en cours de chargement...
                          </div>
                        )}
                        {/* Cognitive metadata display for unified mode */}
                        {messageMetadata[msg.id] && !isStreaming && (
                          <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-4 text-xs text-muted-foreground">
                            {/* Confidence score */}
                            {messageMetadata[msg.id].confidence !== undefined && (
                              <div className="flex items-center gap-1.5">
                                <span>Confiance:</span>
                                <div className="flex items-center gap-1">
                                  <div
                                    className="h-1.5 rounded-full bg-gradient-to-r from-amber-500 to-green-500"
                                    style={{ width: `${messageMetadata[msg.id].confidence! * 60}px` }}
                                  />
                                  <span className="font-medium">
                                    {Math.round(messageMetadata[msg.id].confidence! * 100)}%
                                  </span>
                                </div>
                              </div>
                            )}
                            {/* Mode indicator */}
                            {messageMetadata[msg.id].unified && (
                              <span className="px-2 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-medium">
                                COMPLET
                              </span>
                            )}
                            {messageMetadata[msg.id].fast && (
                              <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-500 text-[10px] font-medium">
                                RAPIDE
                              </span>
                            )}
                            {/* Cognitive signature */}
                            {messageMetadata[msg.id].cognitive_signature && (
                              <div className="flex items-center gap-1">
                                {Object.entries(messageMetadata[msg.id].cognitive_signature || {}).map(([key, active]) => (
                                  <span
                                    key={key}
                                    className={cn(
                                      'w-2 h-2 rounded-full',
                                      active ? 'bg-green-500' : 'bg-muted'
                                    )}
                                    title={key}
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm">{msg.content}</p>
                    )}
                  </Card>
                  {/* Action buttons - Copy and Feedback */}
                  {msg.content && !isStreaming && (
                    <div className="flex justify-end items-center gap-2 mt-1">
                      {/* Feedback buttons for assistant messages */}
                      {msg.role === 'assistant' && !feedbackGiven[msg.id] && (
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <span className="mr-1">Utile ?</span>
                          <button
                            onClick={() => handleFeedback(msg.id, true)}
                            className="p-1.5 rounded-md hover:bg-green-500/10 hover:text-green-500 transition-colors"
                            title="Utile"
                          >
                            <HiHandThumbUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleFeedback(msg.id, false)}
                            className="p-1.5 rounded-md hover:bg-red-500/10 hover:text-red-500 transition-colors"
                            title="Pas utile"
                          >
                            <HiHandThumbDown className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                      {/* Feedback confirmation */}
                      {msg.role === 'assistant' && feedbackGiven[msg.id] && (
                        <span className={cn(
                          'text-xs px-2 py-0.5 rounded',
                          feedbackGiven[msg.id] === 'useful'
                            ? 'text-green-500 bg-green-500/10'
                            : 'text-muted-foreground bg-muted'
                        )}>
                          {feedbackGiven[msg.id] === 'useful' ? 'Merci !' : 'Note'}
                        </span>
                      )}
                      {/* Copy button */}
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleCopyMessage(msg.id, msg.content);
                        }}
                        className={cn(
                          'flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-all',
                          'text-muted-foreground hover:text-foreground hover:bg-accent',
                          copiedMessageId === msg.id && 'text-green-500'
                        )}
                      >
                        {copiedMessageId === msg.id ? (
                          <>
                            <HiCheck className="h-3.5 w-3.5" />
                            <span>Copie</span>
                          </>
                        ) : (
                          <>
                            <HiClipboard className="h-3.5 w-3.5" />
                            <span>Copier</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="flex-shrink-0 mt-1">
                    <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                      <HiUser className="h-4 w-4" />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Input - Professional textarea with actions */}
      <div className="p-3 sm:p-4 border-t border-border bg-muted/30 safe-area-inset-bottom">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end gap-2 bg-background rounded-xl border border-border p-2">
            {/* Textarea */}
            <textarea
              placeholder="Posez votre question sur l'economie territoriale..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              rows={1}
              className={cn(
                'flex-1 resize-none bg-transparent border-0 focus:ring-0 focus:outline-none',
                'text-sm sm:text-base px-2 py-2',
                'placeholder:text-muted-foreground',
                'max-h-32 overflow-y-auto',
                'disabled:opacity-50'
              )}
              style={{
                height: 'auto',
                minHeight: '40px',
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 128) + 'px';
              }}
            />

            {/* Action buttons */}
            <div className="flex items-center gap-1 pb-1">
              {/* Clear button - only show if there's text */}
              {inputMessage.trim() && (
                <button
                  onClick={() => setInputMessage('')}
                  className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                  title="Effacer"
                >
                  <HiXMark className="h-4 w-4" />
                </button>
              )}

              {/* Send button */}
              <Button
                onClick={handleSubmit}
                disabled={isStreaming || !inputMessage.trim()}
                size="sm"
                className="h-9 px-4 rounded-lg"
              >
                {isStreaming ? (
                  <span className="flex items-center gap-0.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" style={{ animationDelay: '0ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" style={{ animationDelay: '150ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" style={{ animationDelay: '300ms' }} />
                  </span>
                ) : (
                  <HiPaperAirplane className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          {/* Hint */}
          <p className="text-[10px] text-muted-foreground mt-1.5 px-2">
            Entree pour envoyer, Shift+Entree pour nouvelle ligne
          </p>
        </div>
      </div>
    </div>
  );
}
