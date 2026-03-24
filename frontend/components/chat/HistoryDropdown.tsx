'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  HiOutlineClock,
  HiOutlinePlus,
  HiOutlineTrash,
  HiMagnifyingGlass,
  HiChatBubbleLeftRight,
} from 'react-icons/hi2';
import { listConversations, deleteConversation, ConversationSummary } from '@/lib/api-conversations';

interface HistoryDropdownProps {
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onNewConversation: () => void;
}

export function HistoryDropdown({
  selectedId,
  onSelect,
  onNewConversation,
}: HistoryDropdownProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);

  // Load conversations when opened
  useEffect(() => {
    if (open) {
      loadConversations();
    }
  }, [open]);

  // Keyboard shortcut Cmd/Ctrl + H
  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'h') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, []);

  const loadConversations = async () => {
    setLoading(true);
    try {
      const data = await listConversations();
      setConversations(data.conversations);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (selectedId === id) {
        onSelect(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return "Aujourd'hui";
    if (days === 1) return 'Hier';
    if (days < 7) return `Il y a ${days} jours`;
    return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 hover:bg-white/5"
          title="Historique (Ctrl+H)"
        >
          <HiOutlineClock className="h-5 w-5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[400px] max-w-[90vw] p-0 bg-background border-border"
      >
        {/* Header */}
        <div className="p-3 border-b border-white/5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm">Historique</h3>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => {
                onNewConversation();
                setOpen(false);
              }}
            >
              <HiOutlinePlus className="h-3.5 w-3.5" />
              Nouveau
            </Button>
          </div>

          {/* Search */}
          <div className="relative">
            <HiMagnifyingGlass className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 pl-8 text-sm bg-muted border-border"
            />
          </div>
        </div>

        {/* Conversation list */}
        <ScrollArea className="h-[300px]">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <HiChatBubbleLeftRight className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-sm">
                {search ? 'Aucun resultat' : 'Aucune conversation'}
              </p>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {filteredConversations.map((conv) => (
                <motion.button
                  key={conv.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onClick={() => {
                    onSelect(conv.id);
                    setOpen(false);
                  }}
                  className={cn(
                    'w-full flex items-start gap-2 p-2 rounded-lg text-left transition-colors group',
                    selectedId === conv.id
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-white/5'
                  )}
                >
                  <HiChatBubbleLeftRight className="h-4 w-4 mt-0.5 flex-shrink-0 opacity-50" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium break-words">{conv.title}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {formatDate(conv.updated_at)} • {conv.message_count} messages
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(conv.id, e)}
                    className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-500 transition-all"
                    title="Supprimer"
                  >
                    <HiOutlineTrash className="h-3.5 w-3.5" />
                  </button>
                </motion.button>
              ))}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
