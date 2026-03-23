'use client';

import { useState, useEffect, useRef } from 'react';
import DashboardLayout from '@/components/layout';
import { ScrollArea } from '@/components/ui/scroll-area';
import { HistoryDropdown } from '@/components/chat/HistoryDropdown';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageCard } from '@/components/chat/MessageCard';
import { type AgentPhase, type AgentTool } from '@/components/chat/AgentTimeline';
import {
  HiOutlineShare,
  HiOutlineArrowDownTray,
  HiMapPin,
  HiXMark,
  HiPlus,
} from 'react-icons/hi2';
import { toast } from 'sonner';
import {
  getConversation,
  createConversation,
  addMessage,
  Message,
} from '@/lib/api-conversations';
import { useAuth } from '@/contexts/AuthContext';
import { useTAJINE, AnalysisResult } from '@/contexts/TAJINEContext';

type TAJINELevel = 'reactive' | 'analytical' | 'strategic' | 'prospective' | 'theoretical';

interface MessageMetadata {
  confidence?: number;
  unified?: boolean;
  fast?: boolean;
}

const PPDSL_PHASES = ['perceive', 'plan', 'delegate', 'synthesize', 'learn'];

function createInitialPhases(): AgentPhase[] {
  return PPDSL_PHASES.map(name => ({
    name,
    label: name,
    status: 'pending' as const,
    message: '',
    progress: 0,
    tools: [],
  }));
}

export default function AiChatPage() {
  const { user } = useAuth();
  const { addAnalysisResult, selectedDepartment, setSelectedDepartment } = useTAJINE();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [phaseMessage, setPhaseMessage] = useState('');
  const [fastMode, setFastMode] = useState(true);
  const [level] = useState<TAJINELevel>('analytical');
  const [messageMetadata, setMessageMetadata] = useState<Record<string, MessageMetadata>>({});
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, 'useful' | 'not_useful'>>({});

  // Agent live state
  const [agentPhases, setAgentPhases] = useState<AgentPhase[]>([]);
  const [agentModel, setAgentModel] = useState<string>('');
  const [agentStartTime, setAgentStartTime] = useState<number>(0);
  const [agentDuration, setAgentDuration] = useState<number>(0);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fullResponseRef = useRef<string>('');

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

  useEffect(() => {
    if (conversationId) loadConversation(conversationId);
  }, [conversationId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, agentPhases]);

  const loadConversation = async (id: string) => {
    setIsLoading(true);
    try {
      const data = await getConversation(id);
      setMessages(data.messages);
    } catch (error) {
      console.error('Error loading conversation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setMessageMetadata({});
    setFeedbackGiven({});
    setAgentPhases([]);
  };

  const buildQueryWithContext = (query: string): string => {
    if (selectedDepartment && !query.toLowerCase().includes(selectedDepartment)) {
      return `[Departement ${selectedDepartment}] ${query}`;
    }
    return query;
  };

  // Update a specific phase in the agent timeline
  const updatePhase = (phaseName: string, updates: Partial<AgentPhase>) => {
    setAgentPhases(prev => prev.map(p =>
      p.name === phaseName ? { ...p, ...updates } : p
    ));
  };

  // Add or update a tool in a phase
  const upsertTool = (phaseName: string, toolName: string, status: AgentTool['status']) => {
    setAgentPhases(prev => prev.map(p => {
      if (p.name !== phaseName) return p;
      const existingIdx = p.tools.findIndex(t => t.name === toolName);
      if (existingIdx >= 0) {
        const newTools = [...p.tools];
        newTools[existingIdx] = { ...newTools[existingIdx], status };
        return { ...p, tools: newTools };
      }
      return { ...p, tools: [...p.tools, { name: toolName, status }] };
    }));
  };

  const handleSubmit = async (userMessage: string) => {
    if (!userMessage.trim() || isStreaming) return;

    setIsStreaming(true);
    setIsThinking(true);
    setAgentPhases(createInitialPhases());
    setAgentModel('');
    setAgentStartTime(Date.now());
    setAgentDuration(0);

    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      let currentConvId = conversationId;
      try {
        if (!currentConvId) {
          const newConv = await createConversation(undefined, level);
          currentConvId = newConv.id;
          setConversationId(newConv.id);
        }
        if (currentConvId) {
          await addMessage(currentConvId, 'user', userMessage);
        }
      } catch {
        console.warn('Conversation API unavailable');
      }

      const tempAssistantMsg: Message = {
        id: `temp-assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, tempAssistantMsg]);

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

      if (!response.ok) throw new Error('Erreur de communication avec TAJINE');

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      fullResponseRef.current = '';
      const currentMsgId = tempAssistantMsg.id;

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

              // START event - model info
              if (jsonData.type === 'start') {
                setAgentModel(jsonData.model || jsonData.tier || '');
              }

              // PHASE events - update timeline
              if (jsonData.type === 'phase') {
                const phaseName = jsonData.phase;
                const progress = jsonData.progress || 0;
                const message = jsonData.message || '';

                if (phaseName && PPDSL_PHASES.includes(phaseName)) {
                  // Mark current phase as running, previous as complete
                  setAgentPhases(prev => prev.map(p => {
                    if (p.name === phaseName) {
                      return { ...p, status: 'running', message, progress };
                    }
                    const phaseIdx = PPDSL_PHASES.indexOf(phaseName);
                    const currentIdx = PPDSL_PHASES.indexOf(p.name);
                    if (currentIdx < phaseIdx && p.status === 'running') {
                      return { ...p, status: 'complete' };
                    }
                    return p;
                  }));

                  // Check for tool execution in delegate phase
                  if (phaseName === 'delegate' && jsonData.data?.tool) {
                    upsertTool('delegate', jsonData.data.tool, 'running');
                  }

                  // Check for completed tools list
                  if (phaseName === 'delegate' && jsonData.data?.tools_executed) {
                    for (const toolName of jsonData.data.tools_executed) {
                      upsertTool('delegate', toolName, 'complete');
                    }
                  }

                  // Mark phase complete if progress suggests it
                  if (progress >= 90 || message.toLowerCase().includes('complete')) {
                    updatePhase(phaseName, { status: 'complete', progress, message });
                  }
                }

                setPhaseMessage(message);
              }

              // THINKING events
              if (jsonData.type === 'thinking') {
                setPhaseMessage(jsonData.message || 'Reflexion...');
              }

              // PROGRESS events (heartbeat)
              if (jsonData.type === 'progress') {
                setPhaseMessage(jsonData.message || 'Analyse en cours...');
              }

              // CONTENT events - streaming text
              if (jsonData.type === 'content' && jsonData.text) {
                if (isThinking) setIsThinking(false);

                // Mark all phases as complete when content starts
                setAgentPhases(prev => prev.map(p =>
                  p.status !== 'pending' ? { ...p, status: 'complete' } : p
                ));

                fullResponseRef.current += jsonData.text;
                const currentContent = fullResponseRef.current;
                setMessages(prev => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (updated[lastIdx]?.role === 'assistant') {
                    updated[lastIdx] = { ...updated[lastIdx], content: currentContent };
                  }
                  return updated;
                });
              }

              // COMPLETE event
              if (jsonData.type === 'complete') {
                setPhaseMessage('');
                setAgentDuration((Date.now() - agentStartTime) / 1000);

                // Mark all phases as complete
                setAgentPhases(prev => prev.map(p => ({ ...p, status: 'complete' })));

                setMessageMetadata(prev => ({
                  ...prev,
                  [currentMsgId]: {
                    confidence: jsonData.confidence,
                    unified: jsonData.unified,
                    fast: jsonData.fast,
                  },
                }));

                const analysisResult: AnalysisResult = {
                  id: currentMsgId,
                  timestamp: new Date(),
                  department: selectedDepartment,
                  cognitiveLevel: level,
                  confidence: jsonData.confidence,
                  insights: [],
                  radarData: jsonData.charts?.radar,
                  heatmapData: jsonData.charts?.heatmap,
                };
                addAnalysisResult(analysisResult);
              }

              // ERROR event
              if (jsonData.type === 'error') {
                toast.error('Erreur TAJINE', { description: jsonData.message });
              }
            } catch {
              const rawText = line.slice(6);
              if (rawText.trim()) {
                fullResponseRef.current += rawText;
                setMessages(prev => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (updated[lastIdx]?.role === 'assistant') {
                    updated[lastIdx] = { ...updated[lastIdx], content: fullResponseRef.current };
                  }
                  return updated;
                });
              }
            }
          }
        }
      }

      if (fullResponseRef.current && currentConvId) {
        try {
          await addMessage(currentConvId, 'assistant', fullResponseRef.current);
        } catch {
          console.warn('Failed to save assistant message');
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue';
      toast.error('Erreur de communication', { description: errorMessage });
      setMessages(prev => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (updated[lastIdx]?.role === 'assistant') {
          updated[lastIdx] = { ...updated[lastIdx], content: `Erreur: ${errorMessage}` };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
      setAgentDuration((Date.now() - agentStartTime) / 1000);
    }
  };

  const handleCopyMessage = async (content: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(content);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = content;
        textarea.style.cssText = 'position:fixed;opacity:0;left:-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      toast.success('Message copie');
    } catch {
      toast.error('Erreur de copie');
    }
  };

  const handleFeedback = async (messageId: string, useful: boolean) => {
    setFeedbackGiven(prev => ({ ...prev, [messageId]: useful ? 'useful' : 'not_useful' }));

    const message = messages.find(m => m.id === messageId);
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
          metadata: messageMetadata[messageId],
        }),
      });
    } catch {
      // Feedback saved locally
    }
  };

  const handleShare = async () => {
    if (messages.length === 0) return;
    const shareText = messages
      .map(m => `${m.role === 'user' ? 'Vous' : 'TAJINE'}: ${m.content}`)
      .join('\n\n');
    try {
      if (navigator.share) {
        await navigator.share({ title: 'Conversation TAJINE', text: shareText });
      } else {
        await navigator.clipboard.writeText(shareText);
        toast.success('Conversation copiee');
      }
    } catch {
      toast.error('Erreur lors du partage');
    }
  };

  const handleExport = () => {
    if (messages.length === 0) return;
    const exportData = {
      id: conversationId,
      department: selectedDepartment,
      exported_at: new Date().toISOString(),
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
        created_at: m.created_at,
        metadata: messageMetadata[m.id],
      })),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tajine-conversation-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Conversation exportee');
  };

  // Header actions injected into DashboardLayout top bar
  const headerActions = (
    <>
      <button
        onClick={handleNewConversation}
        className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        title="Nouvelle conversation"
      >
        <HiPlus className="h-4 w-4" />
      </button>
      <HistoryDropdown
        selectedId={conversationId}
        onSelect={setConversationId}
        onNewConversation={handleNewConversation}
      />
      <div className="w-px h-5 bg-border/50 mx-0.5" />
      <button
        onClick={handleShare}
        className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        title="Partager"
      >
        <HiOutlineShare className="h-4 w-4" />
      </button>
      <button
        onClick={handleExport}
        className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        title="Exporter JSON"
      >
        <HiOutlineArrowDownTray className="h-4 w-4" />
      </button>
    </>
  );

  return (
    <DashboardLayout title="TAJINE" description="" headerActions={headerActions} fullHeight>
      <div className="h-full flex flex-col">
        {/* Department context banner */}
        {selectedDepartment && (
          <div className="px-4 py-1.5 bg-primary/5 border-b border-primary/20 flex items-center gap-2">
            <HiMapPin className="h-3.5 w-3.5 text-primary" />
            <span className="text-xs font-medium text-primary">Dept. {selectedDepartment}</span>
            <span className="text-[10px] text-muted-foreground hidden sm:inline">
               -  Contexte actif
            </span>
            <button
              onClick={() => setSelectedDepartment(null)}
              className="ml-auto p-0.5 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
            >
              <HiXMark className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Messages area */}
        <div className="flex-1 min-h-0 relative">
          <ScrollArea ref={scrollRef} className="h-full px-4 py-6 pb-52">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full max-w-md mx-auto text-center">
                <div className="relative mb-8">
                  <div className="absolute -inset-8 rounded-full">
                    <div className="absolute inset-0 rounded-full bg-primary/5 animate-pulse-ring" />
                    <div className="absolute inset-2 rounded-full bg-primary/8 animate-pulse-ring" style={{ animationDelay: '600ms' }} />
                    <div className="absolute inset-4 rounded-full bg-primary/10 animate-pulse-ring" style={{ animationDelay: '1200ms' }} />
                  </div>
                  <img src="/loading-tajine.webp" alt="TAJINE" className="relative w-20 h-auto drop-shadow-xl" />
                </div>
                <h2 className="text-xl font-semibold text-foreground mb-1">TAJINE</h2>
                <p className="text-sm text-muted-foreground/70">
                  {selectedDepartment
                    ? `Intelligence territoriale  -  ${selectedDepartment}`
                    : "Agent d'intelligence territoriale"}
                </p>
              </div>
            ) : (
              <div className="space-y-6 max-w-3xl mx-auto">
                {messages.map((msg, idx) => {
                  const isLastAssistant = msg.role === 'assistant' && idx === messages.length - 1;
                  return (
                    <MessageCard
                      key={msg.id}
                      id={msg.id}
                      role={msg.role}
                      content={msg.content}
                      isStreaming={isStreaming && isLastAssistant}
                      isThinking={isThinking && isLastAssistant && !msg.content}
                      thinkingMessage={phaseMessage || 'Analyse en cours...'}
                      confidence={messageMetadata[msg.id]?.confidence}
                      modeLabel={
                        messageMetadata[msg.id]?.unified
                          ? 'COMPLET'
                          : messageMetadata[msg.id]?.fast
                            ? 'RAPIDE'
                            : undefined
                      }
                      agentPhases={isLastAssistant ? agentPhases : []}
                      agentModel={isLastAssistant ? agentModel : undefined}
                      agentDuration={isLastAssistant ? agentDuration : undefined}
                      onCopy={handleCopyMessage}
                      onFeedback={useful => handleFeedback(msg.id, useful)}
                      feedbackGiven={feedbackGiven[msg.id]}
                    />
                  );
                })}
              </div>
            )}
          </ScrollArea>

          <ChatInput
            onSubmit={handleSubmit}
            isStreaming={isStreaming}
            fastMode={fastMode}
            onFastModeChange={setFastMode}
            suggestedQueries={messages.length === 0 ? suggestedQueries : []}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
