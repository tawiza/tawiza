'use client';

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

// Types
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'analyst' | 'viewer';
  preferences: {
    theme: 'dark' | 'light' | 'auto';
    default_level: string;
    notifications: boolean;
    language: string;
  };
  created_at: string;
  last_login: string | null;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  updatePreferences: (preferences: Partial<User['preferences']>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = '';

// Session duration: 24 hours
const SESSION_DURATION_MS = 24 * 60 * 60 * 1000;

// Token storage with localStorage persistence
function getStoredSession(): { token: string; user: User; expiresAt: number } | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('tawiza-session');
    if (!raw) return null;
    const session = JSON.parse(raw);
    // Check expiry
    if (session.expiresAt && Date.now() > session.expiresAt) {
      localStorage.removeItem('tawiza-session');
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

function storeSession(token: string, user: User) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('tawiza-session', JSON.stringify({
    token,
    user,
    expiresAt: Date.now() + SESSION_DURATION_MS,
  }));
  // Set cookie for middleware server-side auth check
  document.cookie = `tawiza-auth=1; path=/; max-age=${SESSION_DURATION_MS / 1000}; SameSite=Lax`;
}

function clearSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('tawiza-session');
  // Clear auth cookie
  document.cookie = 'tawiza-auth=; path=/; max-age=0';
}

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

// Auth Provider Component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Fetch current user profile
  const fetchUser = useCallback(async (): Promise<User | null> => {
    if (!accessToken) return null;
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error('Failed to fetch user');
      return await response.json();
    } catch {
      return null;
    }
  }, []);

  // Refresh token
  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) return false;
      const data = await response.json();
      accessToken = data.access_token;
      const userData = await fetchUser();
      if (userData) {
        setUser(userData);
        storeSession(data.access_token, userData);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [fetchUser]);

  // Login
  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Erreur de connexion');
    }

    const data = await response.json();
    accessToken = data.access_token;

    // Fetch user profile
    let userData = await fetchUser();
    if (!userData) {
      // Backend might not have /me endpoint - create from login response
      userData = {
        id: data.user_id || 'user',
        email: email,
        name: data.name || email.split('@')[0],
        role: data.role || 'admin',
        preferences: {
          theme: 'dark',
          default_level: 'analytical',
          notifications: true,
          language: 'fr',
        },
        created_at: new Date().toISOString(),
        last_login: new Date().toISOString(),
      };
    }

    setUser(userData);
    storeSession(data.access_token, userData);
    // Redirect to original page if available, otherwise dashboard
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect') || '/dashboard/main';
    router.push(redirect);
  }, [fetchUser, router]);

  // Logout
  const logout = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch { /* ignore */ }

    accessToken = null;
    setUser(null);
    clearSession();
    router.push('/login');
  }, [router]);

  // Update preferences
  const updatePreferences = useCallback(async (
    preferences: Partial<User['preferences']>
  ): Promise<void> => {
    if (!user) throw new Error('Not authenticated');
    // Update locally
    const updatedUser = { ...user, preferences: { ...user.preferences, ...preferences } };
    setUser(updatedUser);
    if (accessToken) {
      storeSession(accessToken, updatedUser);
    }
    // Try backend update (best effort)
    try {
      await fetch(`${API_BASE}/api/v1/auth/me/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify(preferences),
      });
    } catch { /* ignore */ }
  }, [user]);

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);

      // 1. Check localStorage for existing session
      const stored = getStoredSession();
      if (stored) {
        accessToken = stored.token;
        setUser(stored.user);
        setIsLoading(false);

        // Background: try to refresh token silently
        refreshToken().catch(() => {});
        return;
      }

      // 2. Try cookie-based refresh
      const success = await refreshToken();
      if (!success) {
        // Not authenticated - middleware handles redirect
      }

      setIsLoading(false);
    };

    initAuth();
  }, [refreshToken]);

  // Auto-refresh token before expiration (every 14 min)
  useEffect(() => {
    if (!accessToken) return;
    const interval = setInterval(() => {
      refreshToken().catch(() => {});
    }, 14 * 60 * 1000);
    return () => clearInterval(interval);
  }, [refreshToken]);

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshToken,
    updatePreferences,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
