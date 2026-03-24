'use client';

import { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTAJINE } from '@/contexts/TAJINEContext';
import { useConversations, useConversation, deleteConversation, Conversation } from '@/lib/api-tajine';
import {
  HiOutlineTrash,
  HiOutlineEye,
  HiOutlineClock,
  HiOutlineCheckCircle,
  HiOutlineExclamationCircle,
  HiOutlineChevronUp,
  HiOutlineChevronDown,
} from 'react-icons/hi2';
import { format, formatDistanceToNow, isToday, isThisWeek, isThisMonth } from 'date-fns';
import { fr } from 'date-fns/locale';
import AdvancedFilters, { FilterState, defaultFilters } from './AdvancedFilters';

// Nord status colors
const STATUS_CONFIG = {
  completed: { color: 'text-[var(--success)]', bg: 'bg-[var(--success)]/20', icon: HiOutlineCheckCircle, label: 'Terminé' },
  pending: { color: 'text-[var(--warning)]', bg: 'bg-[var(--warning)]/20', icon: HiOutlineClock, label: 'En cours' },
  error: { color: 'text-[var(--error)]', bg: 'bg-[var(--error)]/20', icon: HiOutlineExclamationCircle, label: 'Erreur' },
};

const COGNITIVE_LEVELS: Record<string, string> = {
  tactical: 'Tactique',
  strategic: 'Stratégique',
  theoretical: 'Théorique',
};

interface ConversationHistoryProps {
  searchQuery?: string;
  onConversationSelect?: (id: string) => void;
}


function StatusBadge({ status }: { status: Conversation['status'] }) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${config.bg} ${config.color}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

function ConversationRow({
  conversation,
  isSelected,
  onView,
  onDelete
}: {
  conversation: Conversation;
  isSelected: boolean;
  onView: () => void;
  onDelete: () => void;
}) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDeleting) return;

    setIsDeleting(true);
    try {
      await deleteConversation(conversation.id);
      onDelete();
    } catch (error) {
      console.error('Delete failed:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const timeAgo = formatDistanceToNow(new Date(conversation.created_at), {
    addSuffix: true,
    locale: fr
  });

  return (
    <div
      className={`glass rounded-lg cursor-pointer transition-all hover:bg-white/5 ${
        isSelected ? 'ring-2 ring-primary/50 bg-primary/5' : ''
      }`}
      onClick={onView}
    >
      {/* Mobile layout */}
      <div className="sm:hidden p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm line-clamp-2 flex-1">{conversation.query_preview}</p>
          <StatusBadge status={conversation.status} />
        </div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span>{timeAgo}</span>
            {conversation.department_code && (
              <span className="px-1.5 py-0.5 font-mono glass rounded text-[9px]">
                {conversation.department_code}
              </span>
            )}
            <span>{COGNITIVE_LEVELS[conversation.cognitive_level]}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              className="p-1 rounded hover:bg-primary/20 text-primary transition-colors"
              onClick={(e) => { e.stopPropagation(); onView(); }}
            >
              <HiOutlineEye className="w-3.5 h-3.5" />
            </button>
            <button
              className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors disabled:opacity-50"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              <HiOutlineTrash className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Desktop layout */}
      <div className="hidden sm:flex items-center gap-4 p-3">
        {/* Time */}
        <div className="w-24 text-xs text-muted-foreground shrink-0">
          {timeAgo}
        </div>

        {/* Department */}
        <div className="w-16 text-center shrink-0">
          {conversation.department_code ? (
            <span className="inline-block px-2 py-0.5 text-xs font-mono glass rounded">
              {conversation.department_code}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">National</span>
          )}
        </div>

        {/* Cognitive Level */}
        <div className="w-20 text-xs text-muted-foreground shrink-0">
          {COGNITIVE_LEVELS[conversation.cognitive_level] || conversation.cognitive_level}
        </div>

        {/* Query Preview */}
        <div className="flex-1 min-w-0">
          <p className="text-sm truncate">{conversation.query_preview}</p>
        </div>

        {/* Status */}
        <div className="w-24 shrink-0">
          <StatusBadge status={conversation.status} />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            className="p-1.5 rounded-lg hover:bg-primary/20 text-primary transition-colors"
            onClick={(e) => { e.stopPropagation(); onView(); }}
            title="Voir les details"
          >
            <HiOutlineEye className="w-4 h-4" />
          </button>
          <button
            className="p-1.5 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors disabled:opacity-50"
            onClick={handleDelete}
            disabled={isDeleting}
            title="Supprimer"
          >
            <HiOutlineTrash className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ConversationDetail({ conversationId }: { conversationId: string }) {
  const { conversation, isLoading, isError } = useConversation(conversationId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError || !conversation) {
    return (
      <div className="text-center text-muted-foreground py-8">
        Impossible de charger la conversation
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 glass rounded-lg max-h-64 overflow-y-auto">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {format(new Date(conversation.created_at), 'PPpp', { locale: fr })}
        </span>
        <StatusBadge status={conversation.status} />
      </div>

      <div className="space-y-3">
        {conversation.messages.map((message) => (
          <div
            key={message.id}
            className={`p-3 rounded-lg ${
              message.role === 'user'
                ? 'bg-primary/10 ml-8'
                : 'bg-white/5 mr-8'
            }`}
          >
            <p className="text-xs font-medium text-muted-foreground mb-1">
              {message.role === 'user' ? 'Vous' : 'TAJINE'}
            </p>
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            {message.metadata?.confidence && (
              <p className="text-xs text-muted-foreground mt-2">
                Confiance: {(message.metadata.confidence * 100).toFixed(0)}%
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Sortable column header
function SortableHeader({
  label,
  sortKey,
  currentSort,
  currentOrder,
  onSort,
  className = '',
}: {
  label: string;
  sortKey: FilterState['sortBy'];
  currentSort: FilterState['sortBy'];
  currentOrder: FilterState['sortOrder'];
  onSort: (key: FilterState['sortBy']) => void;
  className?: string;
}) {
  const isActive = currentSort === sortKey;

  return (
    <button
      onClick={() => onSort(sortKey)}
      className={`flex items-center gap-1 text-xs font-medium transition-colors ${
        isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
      } ${className}`}
    >
      {label}
      {isActive && (
        currentOrder === 'asc' ? (
          <HiOutlineChevronUp className="w-3 h-3" />
        ) : (
          <HiOutlineChevronDown className="w-3 h-3" />
        )
      )}
    </button>
  );
}

export default function ConversationHistory({ searchQuery = '', onConversationSelect }: ConversationHistoryProps) {
  const { selectedDepartment, setActiveConversation, activeConversation } = useTAJINE();
  const { conversations: apiConversations, isLoading, mutate } = useConversations(selectedDepartment);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(defaultFilters);

  // Use API data only - no mock fallback in production
  const conversations = apiConversations;

  // Handle sort toggle
  const handleSort = useCallback((sortBy: FilterState['sortBy']) => {
    setFilters(prev => ({
      ...prev,
      sortBy,
      sortOrder: prev.sortBy === sortBy && prev.sortOrder === 'desc' ? 'asc' : 'desc',
    }));
  }, []);

  // Filter and sort conversations
  const filteredConversations = useMemo(() => {
    let result = [...conversations];

    // Text search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(c =>
        c.query_preview.toLowerCase().includes(query) ||
        c.department_code?.includes(query) ||
        c.cognitive_level.toLowerCase().includes(query)
      );
    }

    // Date range filter
    if (filters.dateRange !== 'all') {
      result = result.filter(c => {
        const date = new Date(c.created_at);
        switch (filters.dateRange) {
          case 'today': return isToday(date);
          case 'week': return isThisWeek(date);
          case 'month': return isThisMonth(date);
          default: return true;
        }
      });
    }

    // Status filter
    if (filters.status.length > 0) {
      result = result.filter(c => filters.status.includes(c.status));
    }

    // Cognitive level filter
    if (filters.cognitiveLevel.length > 0) {
      result = result.filter(c => filters.cognitiveLevel.includes(c.cognitive_level as any));
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      switch (filters.sortBy) {
        case 'date':
          comparison = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
          break;
        case 'department':
          comparison = (a.department_code || 'ZZ').localeCompare(b.department_code || 'ZZ');
          break;
        case 'status':
          comparison = a.status.localeCompare(b.status);
          break;
        case 'level':
          comparison = a.cognitive_level.localeCompare(b.cognitive_level);
          break;
      }
      return filters.sortOrder === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [conversations, searchQuery, filters]);

  const handleView = (id: string) => {
    setSelectedId(selectedId === id ? null : id);
    setActiveConversation(id);
    onConversationSelect?.(id);
  };

  const handleDelete = () => {
    mutate();
    if (selectedId === activeConversation) {
      setActiveConversation(null);
      setSelectedId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-4 p-3 glass rounded-lg animate-pulse">
            <div className="w-24 h-4 bg-muted rounded" />
            <div className="w-16 h-4 bg-muted rounded" />
            <div className="flex-1 h-4 bg-muted rounded" />
            <div className="w-20 h-4 bg-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (filteredConversations.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="mb-2">Aucune conversation trouvée</p>
        <p className="text-xs">
          {searchQuery ? 'Essayez une autre recherche' : 'Démarrez une nouvelle analyse TAJINE'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Advanced filters */}
      <AdvancedFilters filters={filters} onFiltersChange={setFilters} />

      {/* Table header - desktop */}
      <div className="hidden sm:flex items-center gap-4 px-3">
        <SortableHeader
          label="Date"
          sortKey="date"
          currentSort={filters.sortBy}
          currentOrder={filters.sortOrder}
          onSort={handleSort}
          className="w-24"
        />
        <SortableHeader
          label="Dept."
          sortKey="department"
          currentSort={filters.sortBy}
          currentOrder={filters.sortOrder}
          onSort={handleSort}
          className="w-16 justify-center"
        />
        <SortableHeader
          label="Niveau"
          sortKey="level"
          currentSort={filters.sortBy}
          currentOrder={filters.sortOrder}
          onSort={handleSort}
          className="w-20"
        />
        <div className="flex-1 text-xs font-medium text-muted-foreground">Requete</div>
        <SortableHeader
          label="Statut"
          sortKey="status"
          currentSort={filters.sortBy}
          currentOrder={filters.sortOrder}
          onSort={handleSort}
          className="w-24"
        />
        <div className="w-16 text-xs font-medium text-muted-foreground">Actions</div>
      </div>

      {/* Mobile header */}
      <div className="sm:hidden flex items-center justify-between px-3 text-xs text-muted-foreground">
        <span>{filteredConversations.length} conversation{filteredConversations.length > 1 ? 's' : ''}</span>
        <button
          onClick={() => handleSort('date')}
          className="flex items-center gap-1"
        >
          Tri: Date
          {filters.sortOrder === 'asc' ? (
            <HiOutlineChevronUp className="w-3 h-3" />
          ) : (
            <HiOutlineChevronDown className="w-3 h-3" />
          )}
        </button>
      </div>

      {/* Conversation list with animations */}
      <AnimatePresence mode="popLayout">
        {filteredConversations.map((conversation, index) => (
          <motion.div
            key={conversation.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.2, delay: index * 0.03 }}
          >
            <ConversationRow
              conversation={conversation}
              isSelected={selectedId === conversation.id}
              onView={() => handleView(conversation.id)}
              onDelete={handleDelete}
            />

            {/* Expanded detail view */}
            <AnimatePresence>
              {selectedId === conversation.id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="mt-2 ml-0 sm:ml-4 overflow-hidden"
                >
                  <ConversationDetail conversationId={conversation.id} />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Results summary */}
      {filteredConversations.length > 0 && (
        <div className="flex items-center justify-between px-3 pt-2 text-xs text-muted-foreground">
          <span>
            {filteredConversations.length} resultat{filteredConversations.length > 1 ? 's' : ''}
            {(filters.status.length > 0 || filters.cognitiveLevel.length > 0 || filters.dateRange !== 'all') && ' (filtre)'}
          </span>
          {filteredConversations.length >= 20 && (
            <span>Limite atteinte</span>
          )}
        </div>
      )}
    </div>
  );
}
