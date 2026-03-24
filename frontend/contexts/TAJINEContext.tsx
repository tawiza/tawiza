'use client';

import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { useTAJINEWebSocket, TAJINEProgressState, TAJINEPhase } from '../hooks/use-tajine-websocket';

// Types
export interface TAJINEFilters {
  cognitiveLevel?: string;
  status?: 'completed' | 'error' | 'pending';
  searchQuery?: string;
}

// Chat message type
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: {
    confidence?: number;
    cognitiveLevel?: string;
    department?: string;
  };
}

// Analysis result from TAJINE agent
export interface AnalysisResult {
  id: string;
  timestamp: Date;
  department: string | null;
  cognitiveLevel: string;
  // Data for visualizations
  radarData?: { metric: string; value: number; fullMark?: number; benchmark: number }[];
  treemapData?: any[];
  // Heatmap comes as structured object from backend
  heatmapData?: {
    data: { x: string; y: string; value: number }[];
    xLabels: string[];
    yLabels: string[];
  };
  sankeyData?: { nodes: any[]; links: any[] };
  // Insights extracted from analysis
  insights?: string[];
  confidence?: number;
  // Unified Synthesis (Complete Mode)
  unifiedSynthesis?: {
    executive_summary: string;
    sections: any[];
    recommendations: any[];
    overall_confidence: number;
    territory?: string;
    sector?: string;
    cognitive_signature?: any;
  };
  // Standard Analysis (Fast Mode)
  analysis?: any;
}

export interface TAJINEState {
  selectedDepartment: string | null;
  dateRange: [Date, Date];
  activeConversation: string | null;
  filters: TAJINEFilters;
  // WebSocket state
  wsConnected: boolean;
  currentTask: TAJINEProgressState | null;
  currentPhase: TAJINEPhase | null;
  thinking: string | null;
  // Chat state
  messages: ChatMessage[];
  isAnalyzing: boolean;
  analysisProgress: number;
  error: string | null;
  // Analysis results for visualizations
  latestAnalysis: AnalysisResult | null;
  analysisHistory: AnalysisResult[];
}

export interface TAJINEContextValue extends TAJINEState {
  setSelectedDepartment: (dept: string | null) => void;
  setDateRange: (range: [Date, Date]) => void;
  setActiveConversation: (id: string | null) => void;
  setFilters: (filters: TAJINEFilters) => void;
  clearFilters: () => void;
  // WebSocket actions
  subscribeToTask: (taskId: string) => void;
  // Chat actions
  sendMessage: (query: string, mode?: 'fast' | 'complete') => Promise<void>;
  clearMessages: () => void;
  // Analysis actions
  addAnalysisResult: (result: AnalysisResult) => void;
  clearAnalysisHistory: () => void;
}

// Default values
const defaultDateRange: [Date, Date] = [
  new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), // 1 year ago
  new Date(),
];

const defaultState: Omit<TAJINEState, 'wsConnected' | 'currentTask' | 'currentPhase' | 'thinking'> = {
  selectedDepartment: null,
  dateRange: defaultDateRange,
  activeConversation: null,
  filters: {},
  // Chat state
  messages: [],
  isAnalyzing: false,
  analysisProgress: 0,
  error: null,
  // Analysis results
  latestAnalysis: null,
  analysisHistory: [],
};

// Context
const TAJINEContext = createContext<TAJINEContextValue | null>(null);

// Provider
export function TAJINEProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<TAJINEState, 'wsConnected' | 'currentTask' | 'currentPhase' | 'thinking'>>(defaultState);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisResult[]>([]);
  const [latestAnalysis, setLatestAnalysis] = useState<AnalysisResult | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // WebSocket connection for real-time updates
  const {
    isConnected: wsConnected,
    currentTask,
    thinking,
    subscribeToTask,
    latestAnalysis: wsLatestAnalysis,
  } = useTAJINEWebSocket();

  const setSelectedDepartment = useCallback((dept: string | null) => {
    setState((prev) => ({ ...prev, selectedDepartment: dept }));
  }, []);

  const setDateRange = useCallback((range: [Date, Date]) => {
    setState((prev) => ({ ...prev, dateRange: range }));
  }, []);

  const setActiveConversation = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, activeConversation: id }));
  }, []);

  const setFilters = useCallback((filters: TAJINEFilters) => {
    setState((prev) => ({ ...prev, filters: { ...prev.filters, ...filters } }));
  }, []);

  const clearFilters = useCallback(() => {
    setState((prev) => ({ ...prev, filters: {}, selectedDepartment: null }));
  }, []);

  // Chat functions
  const sendMessage = useCallback(async (query: string, mode: 'fast' | 'complete' = 'fast') => {
    // Add user message
    const userMessage: ChatMessage = { role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);
    setIsAnalyzing(true);
    setError(null);
    setAnalysisProgress(0);

    try {
      // Call TAJINE analyze API with SSE
      const response = await fetch('/api/v1/tajine/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode }),
      });

      if (!response.ok) {
        throw new Error(`Erreur API: ${response.status}`);
      }

      // Parse SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.progress) {
                  setAnalysisProgress(data.progress);
                }
                if (data.response) {
                  fullResponse = data.response;
                }
                if (data.final_response) {
                  fullResponse = data.final_response;
                }
              } catch {
                // Ignore JSON parse errors for partial data
              }
            }
          }
        }
      }

      // Add assistant response
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: fullResponse || 'Analyse terminée.',
        metadata: { confidence: 0.8 },
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
      const errorMessage: ChatMessage = {
        role: 'system',
        content: `Erreur: ${err instanceof Error ? err.message : 'Erreur inconnue'}`,
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsAnalyzing(false);
      setAnalysisProgress(100);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    setAnalysisProgress(0);
  }, []);

  // Sync progress with WebSocket task
  useEffect(() => {
    if (currentTask) {
      // 'start' means in progress, 'complete' or 'error' means done
      setIsAnalyzing(currentTask.status === 'start');
      setAnalysisProgress(currentTask.progress || 0);

      // Capture synthesis data when complete
      if (currentTask.phase === 'synthesize' && currentTask.status === 'complete' && currentTask.data) {
        const synthesisData = currentTask.data;

        // Update latestAnalysis with synthesis data
        setLatestAnalysis(prev => {
          if (!prev) return {
            id: currentTask.taskId,
            timestamp: new Date(),
            department: state.selectedDepartment,
            cognitiveLevel: 'synthesis',
            confidence: typeof synthesisData.confidence === 'number' ? synthesisData.confidence : 0,
            unifiedSynthesis: synthesisData.unified_synthesis as any,
            analysis: synthesisData.analysis
          };

          return {
            ...prev,
            confidence: typeof synthesisData.confidence === 'number' ? synthesisData.confidence : prev.confidence,
            unifiedSynthesis: synthesisData.unified_synthesis as any,
            analysis: synthesisData.analysis
          };
        });
      }
    }
  }, [currentTask, state.selectedDepartment]);

  // Analysis result management
  const addAnalysisResult = useCallback((result: AnalysisResult) => {
    setLatestAnalysis(result);
    setAnalysisHistory((prev) => [result, ...prev].slice(0, 50)); // Keep last 50
  }, []);

  const clearAnalysisHistory = useCallback(() => {
    setAnalysisHistory([]);
    setLatestAnalysis(null);
  }, []);

  // Sync WebSocket analysis to context state (multi-tab sync)
  useEffect(() => {
    if (wsLatestAnalysis) {
      // Convert WebSocket data to AnalysisResult format
      const result: AnalysisResult = {
        id: wsLatestAnalysis.taskId,
        timestamp: new Date(),
        department: wsLatestAnalysis.department,
        cognitiveLevel: wsLatestAnalysis.cognitiveLevel,
        radarData: wsLatestAnalysis.radarData,
        treemapData: wsLatestAnalysis.treemapData,
        heatmapData: wsLatestAnalysis.heatmapData,
        sankeyData: wsLatestAnalysis.sankeyData,
        insights: wsLatestAnalysis.insights,
        confidence: wsLatestAnalysis.confidence,
      };
      setLatestAnalysis(result);
      setAnalysisHistory((prev) => [result, ...prev].slice(0, 50));
    }
  }, [wsLatestAnalysis]);

  // Derive current phase from current task
  const currentPhase = currentTask?.phase || null;

  return (
    <TAJINEContext.Provider
      value={{
        ...state,
        wsConnected,
        currentTask,
        currentPhase,
        thinking,
        // Chat state
        messages,
        isAnalyzing,
        analysisProgress,
        error,
        // Analysis results
        latestAnalysis,
        analysisHistory,
        // Actions
        setSelectedDepartment,
        setDateRange,
        setActiveConversation,
        setFilters,
        clearFilters,
        subscribeToTask,
        sendMessage,
        clearMessages,
        addAnalysisResult,
        clearAnalysisHistory,
      }}
    >
      {children}
    </TAJINEContext.Provider>
  );
}

// Hook
export function useTAJINE() {
  const context = useContext(TAJINEContext);
  if (!context) {
    throw new Error('useTAJINE must be used within a TAJINEProvider');
  }
  return context;
}
