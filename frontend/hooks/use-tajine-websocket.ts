/**
 * WebSocket hook for real-time TAJINE updates.
 */

import { useEffect, useCallback, useRef, useState } from 'react';
import { mutate } from 'swr';
import { useAuth } from '@/contexts/AuthContext';

export type TAJINEPhase = 'perceive' | 'plan' | 'delegate' | 'synthesize' | 'learn';

export interface TAJINEProgressState {
  taskId: string;
  phase: TAJINEPhase;
  status: 'start' | 'complete' | 'error';
  progress: number;
  message: string;
  data?: Record<string, unknown>;
  subtasks?: Array<{ id: string; name: string; status: string }>;
  tool?: string;
  level?: number;
  trustDelta?: number;
}

export interface AnalysisCompleteData {
  taskId: string;
  department: string | null;
  cognitiveLevel: string;
  fastMode: boolean;
  confidence: number;
  radarData: any[];
  treemapData: any[];
  heatmapData: any;
  sankeyData: any;
  insights: string[];
}

export interface TAJINEWebSocketState {
  isConnected: boolean;
  currentTask: TAJINEProgressState | null;
  recentTasks: TAJINEProgressState[];
  thinking: string | null;
  latestAnalysis: AnalysisCompleteData | null;
}

// Dynamic WebSocket URL based on current host (supports remote access)
const getWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws';

  // Use environment variable if set
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;

  // Dynamic: use same hostname as frontend, but port 8000
  const hostname = window.location.hostname;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${hostname}:8000/ws`;
};

export function useTAJINEWebSocket() {
  const { user } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 3000;

  const [state, setState] = useState<TAJINEWebSocketState>({
    isConnected: false,
    currentTask: null,
    recentTasks: [],
    thinking: null,
    latestAnalysis: null,
  });

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data);
      if (!msg.type) return;

      if (msg.type === 'tajine.thinking') {
        setState(prev => ({ ...prev, thinking: msg.content || null }));
        return;
      }

      if (msg.type === 'code.terminal') {
        // Emit a custom event for the TerminalViewer component
        window.dispatchEvent(new CustomEvent('code-terminal-output', {
          detail: { task_id: msg.task_id, content: msg.content, stream: msg.stream }
        }));
        return;
      }

      // Dispatch browser screenshot events for ScreenshotViewer
      if (msg.type === 'browser.screenshot') {
        window.dispatchEvent(new CustomEvent('browser-screenshot', { detail: msg }));
        return;
      }

      if (msg.type === 'browser.action' || msg.type === 'browser.status') {
        window.dispatchEvent(new CustomEvent('browser-event', { detail: msg }));
        return;
      }

      if (msg.type === 'tajine.analysis_complete') {
        const analysisData: AnalysisCompleteData = {
          taskId: msg.task_id || '',
          department: msg.department || null,
          cognitiveLevel: msg.cognitive_level || 'analytical',
          fastMode: msg.fast_mode || false,
          confidence: msg.confidence || 0,
          radarData: msg.radar_data || [],
          treemapData: msg.treemap_data || [],
          heatmapData: msg.heatmap_data || { data: [], xLabels: [], yLabels: [] },
          sankeyData: msg.sankey_data || { nodes: [], links: [] },
          insights: msg.insights || [],
        };
        setState(prev => ({ ...prev, latestAnalysis: analysisData, thinking: null }));
        mutate('/api/v1/tajine/departments/stats');
        return;
      }

      if (msg.type.startsWith('tajine.')) {
        const phaseMap: Record<string, TAJINEPhase> = {
          'tajine.perceive': 'perceive',
          'tajine.plan': 'plan',
          'tajine.delegate': 'delegate',
          'tajine.synthesize': 'synthesize',
          'tajine.learn': 'learn',
        };
        const phase = phaseMap[msg.type];
        if (phase && msg.task_id) {
          const progressState: TAJINEProgressState = {
            taskId: msg.task_id,
            phase,
            status: (msg.status as any) || 'start',
            progress: msg.progress || 0,
            message: msg.message || '',
            data: msg.data,
            subtasks: msg.subtasks,
            tool: msg.tool,
            level: msg.level,
            trustDelta: msg.trust_delta,
          };
          setState(prev => ({
            ...prev,
            currentTask: progressState,
            recentTasks: [progressState, ...prev.recentTasks.filter(t => t.taskId !== msg.task_id).slice(0, 9)],
            thinking: null,
          }));
        }
      }
    } catch (err) {
      console.error('[WS] Parse error:', err);
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const sessionId = user?.id || 'anonymous';
      const wsUrl = getWsUrl();
      const url = new URL(wsUrl);
      url.searchParams.set('session_id', sessionId);

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      // Heartbeat interval to keep connection alive
      let heartbeatInterval: NodeJS.Timeout | null = null;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        setState(prev => ({ ...prev, isConnected: true }));

        // Start heartbeat every 30 seconds
        heartbeatInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }));
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++;
          reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
        }
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
        if (heartbeatInterval) clearInterval(heartbeatInterval);
      };
    } catch (err) {
      console.error('[WS] Connection error:', err);
    }
  }, [handleMessage, user?.id]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS;
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
    subscribeToTask: (taskId: string) => sendMessage({ type: 'task.subscribe', task_id: taskId }),
  };
}
