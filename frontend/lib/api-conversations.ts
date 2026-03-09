/**
 * Conversations API client
 */

import { getAccessToken } from '@/contexts/AuthContext';

// Use relative URLs for Next.js proxy (same-origin cookies)
const API_BASE = '';

// Types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface ConversationSummary {
  id: string;
  title: string;
  level: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  preview?: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  level: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  // Optional TAJINE metadata for export
  territory?: string;
  sources?: string[];
  confidence?: number;
  mode?: string;
}

export interface ConversationList {
  conversations: ConversationSummary[];
  total: number;
  page: number;
  per_page: number;
}

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
  const token = getAccessToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// API Functions

export async function listConversations(
  page = 1,
  perPage = 20
): Promise<ConversationList> {
  const response = await fetch(
    `${API_BASE}/api/v1/conversations?page=${page}&per_page=${perPage}`,
    {
      headers: getAuthHeaders(),
      credentials: 'include',
    }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch conversations');
  }

  return response.json();
}

export async function createConversation(
  title?: string,
  level = 'analytical'
): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/api/v1/conversations`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify({ title, level }),
  });

  if (!response.ok) {
    throw new Error('Failed to create conversation');
  }

  return response.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/api/v1/conversations/${id}`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch conversation');
  }

  return response.json();
}

export async function updateConversation(
  id: string,
  data: { title?: string; level?: string }
): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/api/v1/conversations/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to update conversation');
  }

  return response.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/conversations/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to delete conversation');
  }
}

export async function addMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  metadata?: Record<string, unknown>
): Promise<Message> {
  const response = await fetch(
    `${API_BASE}/api/v1/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ role, content, metadata }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to add message');
  }

  return response.json();
}

export async function searchConversations(
  query: string,
  page = 1,
  perPage = 20
): Promise<ConversationList> {
  const response = await fetch(
    `${API_BASE}/api/v1/conversations/search?q=${encodeURIComponent(query)}&page=${page}&per_page=${perPage}`,
    {
      headers: getAuthHeaders(),
      credentials: 'include',
    }
  );

  if (!response.ok) {
    throw new Error('Failed to search conversations');
  }

  return response.json();
}

// Group conversations by date
export function groupConversationsByDate(
  conversations: ConversationSummary[]
): Record<string, ConversationSummary[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const groups: Record<string, ConversationSummary[]> = {
    "Aujourd'hui": [],
    'Hier': [],
    'Cette semaine': [],
    'Plus ancien': [],
  };

  for (const conv of conversations) {
    const date = new Date(conv.updated_at);

    if (date >= today) {
      groups["Aujourd'hui"].push(conv);
    } else if (date >= yesterday) {
      groups['Hier'].push(conv);
    } else if (date >= weekAgo) {
      groups['Cette semaine'].push(conv);
    } else {
      groups['Plus ancien'].push(conv);
    }
  }

  // Remove empty groups
  for (const key of Object.keys(groups)) {
    if (groups[key].length === 0) {
      delete groups[key];
    }
  }

  return groups;
}
