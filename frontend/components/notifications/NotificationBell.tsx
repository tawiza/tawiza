'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  HiBell,
  HiCheck,
  HiTrash,
  HiInformationCircle,
  HiCheckCircle,
  HiExclamationTriangle,
  HiXCircle,
  HiCpuChip,
} from 'react-icons/hi2';
import { cn } from '@/lib/utils';
import { useNotifications } from '@/contexts/NotificationContext';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';
import type { NotificationType } from '@/lib/websocket';

const NOTIFICATION_ICONS: Record<NotificationType, React.ReactNode> = {
  info: <HiInformationCircle className="h-4 w-4 text-blue-400" />,
  success: <HiCheckCircle className="h-4 w-4 text-green-400" />,
  warning: <HiExclamationTriangle className="h-4 w-4 text-amber-400" />,
  error: <HiXCircle className="h-4 w-4 text-red-400" />,
  agent_update: <HiCpuChip className="h-4 w-4 text-purple-400" />,
};

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const {
    notifications,
    unreadCount,
    isConnected,
    markAsRead,
    markAllAsRead,
    clearNotifications,
  } = useNotifications();

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative h-9 w-9">
          <HiBell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs bg-red-500 text-white border-0"
              variant="destructive"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
          {/* Connection indicator */}
          <span
            className={cn(
              'absolute bottom-0 right-0 h-2 w-2 rounded-full border border-background',
              isConnected ? 'bg-green-500' : 'bg-gray-500'
            )}
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h4 className="font-semibold">Notifications</h4>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={markAllAsRead}
              title="Marquer tout comme lu"
              disabled={unreadCount === 0}
            >
              <HiCheck className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={clearNotifications}
              title="Effacer tout"
              disabled={notifications.length === 0}
            >
              <HiTrash className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Notifications list */}
        <ScrollArea className="h-[300px]">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-8">
              <HiBell className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-sm">Aucune notification</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  className={cn(
                    'w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors',
                    !notification.read && 'bg-muted/30'
                  )}
                  onClick={() => markAsRead(notification.id)}
                >
                  <div className="flex gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {NOTIFICATION_ICONS[notification.type]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {notification.title}
                      </p>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                        {notification.message}
                      </p>
                      <p className="text-xs text-muted-foreground/70 mt-1">
                        {formatDistanceToNow(new Date(notification.timestamp), {
                          addSuffix: true,
                          locale: fr,
                        })}
                      </p>
                    </div>
                    {!notification.read && (
                      <div className="flex-shrink-0">
                        <span className="h-2 w-2 rounded-full bg-blue-500 block" />
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        <div className="border-t border-border px-4 py-2 text-center">
          <span className="text-xs text-muted-foreground">
            {isConnected ? (
              <span className="text-green-400">● Connecte</span>
            ) : (
              <span className="text-gray-400">○ Deconnecte</span>
            )}
          </span>
        </div>
      </PopoverContent>
    </Popover>
  );
}
