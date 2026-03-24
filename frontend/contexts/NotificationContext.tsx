'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { toast } from 'sonner';
import {
  wsService,
  Notification,
  WebSocketMessage,
  AgentStatus,
  AnalysisProgress,
} from '@/lib/websocket';

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  agentStatus: AgentStatus | null;
  analysisProgress: AnalysisProgress | null;
  isConnected: boolean;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearNotifications: () => void;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'notification': {
        const notification = message.data as Notification;
        setNotifications((prev) => [notification, ...prev].slice(0, 50)); // Keep last 50

        // Show toast based on notification type
        switch (notification.type) {
          case 'success':
            toast.success(notification.title, { description: notification.message });
            break;
          case 'error':
            toast.error(notification.title, { description: notification.message });
            break;
          case 'warning':
            toast.warning(notification.title, { description: notification.message });
            break;
          case 'agent_update':
            toast.info(notification.title, {
              description: notification.message,
              icon: '🤖',
            });
            break;
          default:
            toast.info(notification.title, { description: notification.message });
        }
        break;
      }

      case 'agent_status':
        setAgentStatus(message.data as AgentStatus);
        break;

      case 'analysis_progress':
        setAnalysisProgress(message.data as AnalysisProgress);
        break;

      case 'error':
        const errorNotif = message.data as Notification;
        toast.error(errorNotif.title, { description: errorNotif.message });
        break;
    }
  }, []);

  // Connect to WebSocket on mount
  useEffect(() => {
    wsService.connect();
    const unsubscribe = wsService.subscribe(handleMessage);

    // Check connection status periodically
    const interval = setInterval(() => {
      setIsConnected(wsService.isConnected());
    }, 1000);

    return () => {
      unsubscribe();
      clearInterval(interval);
      wsService.disconnect();
    };
  }, [handleMessage]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const addNotification = useCallback(
    (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => {
      const newNotification: Notification = {
        ...notification,
        id: `local-${Date.now()}`,
        timestamp: new Date().toISOString(),
        read: false,
      };
      setNotifications((prev) => [newNotification, ...prev].slice(0, 50));

      // Show toast
      switch (notification.type) {
        case 'success':
          toast.success(notification.title, { description: notification.message });
          break;
        case 'error':
          toast.error(notification.title, { description: notification.message });
          break;
        case 'warning':
          toast.warning(notification.title, { description: notification.message });
          break;
        default:
          toast.info(notification.title, { description: notification.message });
      }
    },
    []
  );

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        agentStatus,
        analysisProgress,
        isConnected,
        markAsRead,
        markAllAsRead,
        clearNotifications,
        addNotification,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}
