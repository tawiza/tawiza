'use client';

import MessageBoxChat from '@/components/MessageBoxChat';
import DashboardLayout from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useState, useEffect } from 'react';
import { HiUser, HiMiniPencilSquare, HiBolt } from 'react-icons/hi2';
import FlowFieldCanvas from '@/components/ui/flow-field/FlowFieldCanvas';
import EnergyOrb from '@/components/ui/energy-orb/EnergyOrb';

// Types for TAJINE cognitive levels
type TAJINELevel = 'reactive' | 'analytical' | 'strategic' | 'prospective' | 'theoretical';

const LEVELS: { id: TAJINELevel; name: string; description: string; color: string }[] = [
  { id: 'reactive', name: 'Réactif', description: 'Réponses rapides, données de base', color: 'var(--info)' },
  { id: 'analytical', name: 'Analytique', description: 'Analyse statistique approfondie', color: 'var(--chart-2)' },
  { id: 'strategic', name: 'Stratégique', description: 'Recommandations et stratégies', color: 'var(--chart-4)' },
  { id: 'prospective', name: 'Prospectif', description: 'Prédictions et scénarios', color: 'var(--success)' },
  { id: 'theoretical', name: 'Théorique', description: 'Cadres conceptuels économiques', color: 'var(--chart-3)' },
];

export default function Chat() {
  const [inputOnSubmit, setInputOnSubmit] = useState<string>('');
  const [inputMessage, setInputMessage] = useState<string>('');
  const [outputCode, setOutputCode] = useState<string>('');
  const [level, setLevel] = useState<TAJINELevel>('analytical');
  const [loading, setLoading] = useState<boolean>(false);
  const [fastMode, setFastMode] = useState<boolean>(true); // Fast mode enabled by default
  const [showComplete, setShowComplete] = useState<boolean>(false);

  // Brief "complete" flash after streaming ends
  useEffect(() => {
    if (!loading && outputCode) {
      setShowComplete(true);
      const timer = setTimeout(() => setShowComplete(false), 1500);
      return () => clearTimeout(timer);
    }
  }, [loading, outputCode]);

  // Compute orb state based on loading and output
  const orbState = loading ? 'streaming' : showComplete ? 'complete' : outputCode ? 'idle' : 'idle';

  const handleSubmit = async () => {
    if (!inputMessage.trim()) {
      return;
    }

    setInputOnSubmit(inputMessage);
    setOutputCode('');
    setLoading(true);

    try {
      const response = await fetch('/api/tajine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: inputMessage,
          cognitive_level: level,
          fast: fastMode,
        }),
      });

      if (!response.ok) {
        throw new Error('Erreur de communication avec TAJINE');
      }

      const data = response.body;
      if (!data) {
        throw new Error('Pas de donnees recues');
      }

      // Parse SSE streaming response
      const reader = data.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = JSON.parse(line.slice(6));

              if (jsonData.type === 'content' && jsonData.text) {
                setOutputCode((prev) => prev + jsonData.text);
              } else if (jsonData.type === 'error') {
                setOutputCode((prev) => prev + `\n\nErreur: ${jsonData.message}`);
              }
            } catch {
              // Not valid JSON, might be raw text
              const rawText = line.slice(6);
              if (rawText.trim()) {
                setOutputCode((prev) => prev + rawText);
              }
            }
          }
        }
      }

      // Process any remaining buffer
      if (buffer.startsWith('data: ')) {
        try {
          const jsonData = JSON.parse(buffer.slice(6));
          if (jsonData.type === 'content' && jsonData.text) {
            setOutputCode((prev) => prev + jsonData.text);
          }
        } catch {
          // Ignore parse errors for remaining buffer
        }
      }
    } catch (error) {
      setOutputCode(`Erreur: ${error instanceof Error ? error.message : 'Erreur inconnue'}`);
    } finally {
      setLoading(false);
      setInputMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <DashboardLayout
      title="TAJINE Chat"
      description="Assistant d'analyse territoriale"
    >
      {/* Flow Field - subtle particle animation */}
      <FlowFieldCanvas isStreaming={loading} />

      <div className="relative flex w-full flex-col pt-[20px] md:pt-0">
        <div className="mx-auto flex min-h-[75vh] w-full max-w-[1000px] flex-col xl:min-h-[85vh]">
          {/* Level Selector with Nord colors */}
          <div className={`flex w-full flex-col ${outputCode ? 'mb-5' : 'mb-auto'}`}>
            <div className="z-[2] mx-auto mb-5 flex w-max gap-1 rounded-xl glass p-1.5">
              {LEVELS.map((l) => {
                const isActive = level === l.id;
                return (
                  <div
                    key={l.id}
                    className={`flex cursor-pointer items-center justify-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ease-out-quart ${
                      isActive
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    }`}
                    onClick={() => setLevel(l.id)}
                    title={l.description}
                    style={{
                      borderBottom: isActive ? `2px solid ${l.color}` : '2px solid transparent',
                    }}
                  >
                    <span
                      className={`w-2 h-2 rounded-full mr-2 transition-transform duration-200 ${isActive ? 'scale-100' : 'scale-75 opacity-50'}`}
                      style={{ backgroundColor: l.color }}
                    />
                    {l.name}
                  </div>
                );
              })}
            </div>
            <p className="text-center text-xs text-muted-foreground animate-fade-in">
              {LEVELS.find((l) => l.id === level)?.description}
            </p>

            {/* Fast Mode Toggle */}
            <div className="flex items-center justify-center gap-3 mt-4">
              <button
                onClick={() => setFastMode(!fastMode)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  fastMode
                    ? 'bg-primary/20 text-primary border border-primary/30'
                    : 'glass text-muted-foreground hover:text-foreground'
                }`}
              >
                <HiBolt className={`h-4 w-4 ${fastMode ? 'text-primary' : ''}`} />
                {fastMode ? 'Mode Rapide (~5s)' : 'Mode Complet (~30s)'}
              </button>
              <span className="text-xs text-muted-foreground">
                {fastMode
                  ? 'Réponse directe LLM'
                  : 'Analyse multi-agents PPDSL'}
              </span>
            </div>
          </div>

          {/* Chat Messages */}
          <div className={`mx-auto flex w-full flex-col ${outputCode ? 'flex' : 'hidden'} mb-auto`}>
            {/* User Message */}
            <div className="mb-4 flex w-full items-start animate-fade-in">
              <div className="mr-4 flex h-10 min-h-[40px] min-w-[40px] items-center justify-center rounded-full bg-muted border border-border">
                <HiUser className="h-4 w-4 text-foreground" />
              </div>
              <div className="flex w-full gap-2">
                <div className="flex-1 glass-card !p-4">
                  <p className="text-sm font-medium leading-relaxed text-foreground">
                    {inputOnSubmit}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setInputMessage(inputOnSubmit);
                    setOutputCode('');
                  }}
                  className="flex w-10 h-10 cursor-pointer items-center justify-center rounded-lg glass hover:bg-muted/50 transition-colors"
                  title="Modifier la question"
                >
                  <HiMiniPencilSquare className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
            </div>

            {/* TAJINE Response */}
            <div className="flex w-full items-start animate-fade-in" style={{ animationDelay: '100ms' }}>
              <div className="mr-4 flex h-10 min-h-[40px] min-w-[40px] items-center justify-center rounded-full bg-card border border-border shadow-lg">
                <EnergyOrb state={orbState} size="md" />
              </div>
              <div className="flex-1">
                <MessageBoxChat output={outputCode} isStreaming={loading} level={level} />
              </div>
            </div>
          </div>

          {/* Input */}
          <div className="mt-5 flex gap-3">
            <Input
              className="h-14 flex-1 px-5 glass border-border focus:ring-2 focus:ring-primary/30 focus:border-primary placeholder:text-muted-foreground transition-all duration-200"
              placeholder="Posez votre question à TAJINE..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <Button
              className="h-14 px-8 text-base font-medium transition-all duration-200 hover:glow-cyan disabled:opacity-50"
              onClick={handleSubmit}
              disabled={loading || !inputMessage.trim()}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <EnergyOrb state="loading" size="sm" />
                  Analyse...
                </span>
              ) : (
                'Envoyer'
              )}
            </Button>
          </div>

          <div className="mt-4 flex flex-col items-center justify-center">
            <p className="text-center text-xs text-muted-foreground">
              TAJINE - Agent Intelligence Territoriale. Analyse des donnees economiques francaises.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
