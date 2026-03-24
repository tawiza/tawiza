'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  HiPlus,
  HiMagnifyingGlass,
  HiChatBubbleLeftRight,
  HiTrash,
  HiEllipsisVertical,
} from 'react-icons/hi2';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  listConversations,
  deleteConversation,
  searchConversations,
  groupConversationsByDate,
  ConversationSummary,
} from '@/lib/api-conversations';
import { cn } from '@/lib/utils';
import { ChatListSkeleton } from '@/components/skeletons';

interface ConversationSidebarProps {
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewConversation: () => void;
}

// Cognitive level colors
const LEVEL_COLORS: Record<string, string> = {
  reactive: 'bg-info',
  analytical: 'bg-[var(--chart-2)]',
  strategic: 'bg-[var(--chart-4)]',
  prospective: 'bg-success',
  theoretical: 'bg-[var(--chart-3)]',
};

export default function ConversationSidebar({
  selectedId,
  onSelect,
  onNewConversation,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Load conversations
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    setIsLoading(true);
    try {
      const data = await listConversations(1, 100);
      setConversations(data.conversations);
    } catch (error) {
      console.error('Error loading conversations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Search conversations
  useEffect(() => {
    if (!searchQuery.trim()) {
      loadConversations();
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await searchConversations(searchQuery, 1, 100);
        setConversations(data.conversations);
      } catch (error) {
        console.error('Error searching:', error);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (selectedId === id) {
        onNewConversation();
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

  const groupedConversations = groupConversationsByDate(conversations);

  return (
    <div className="flex h-full flex-col border-r border-border bg-muted/30">
      {/* Header */}
      <div className="p-3 border-b border-border">
        <Button
          onClick={onNewConversation}
          className="w-full justify-start gap-2"
          variant="outline"
        >
          <HiPlus className="h-4 w-4" />
          Nouvelle conversation
        </Button>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-border">
        <div className="relative">
          <HiMagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 bg-background"
          />
        </div>
      </div>

      {/* Conversations List */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            <ChatListSkeleton count={5} />
          ) : Object.keys(groupedConversations).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <HiChatBubbleLeftRight className="h-8 w-8 mb-2 opacity-50" />
              <p className="text-sm">Aucune conversation</p>
            </div>
          ) : (
            Object.entries(groupedConversations).map(([group, convs]) => (
              <div key={group} className="mb-4">
                <h3 className="text-xs font-medium text-muted-foreground px-2 mb-1">
                  {group}
                </h3>
                {convs.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => onSelect(conv.id)}
                    className={cn(
                      'group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors',
                      selectedId === conv.id
                        ? 'bg-accent text-accent-foreground'
                        : 'hover:bg-accent/50'
                    )}
                  >
                    <div
                      className={cn(
                        'h-2 w-2 rounded-full flex-shrink-0',
                        LEVEL_COLORS[conv.level] || LEVEL_COLORS.analytical
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{conv.title}</p>
                      {conv.preview && (
                        <p className="text-xs text-muted-foreground truncate">
                          {conv.preview}
                        </p>
                      )}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <HiEllipsisVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => handleDelete(conv.id, e)}
                          className="text-destructive focus:text-destructive"
                        >
                          <HiTrash className="mr-2 h-4 w-4" />
                          Supprimer
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
