'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { TajineLogo } from '@/components/ui/tajine-logo';
import {
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  MapPin,
  Map,
  Settings,
  ChevronLeft,
  ChevronRight,
  Globe,
  Search,
  LogOut,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

interface NavSection {
  label: string;
  items: { name: string; path: string; icon: any }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Principal',
    items: [
      { name: "Vue d'ensemble", path: '/dashboard/main', icon: LayoutDashboard },
      { name: 'Chat TAJINE', path: '/dashboard/ai-chat', icon: MessageSquare },
    ],
  },
  {
    label: 'Analyse',
    items: [
      { name: 'Territoires', path: '/dashboard/tajine', icon: Map },
      { name: 'Analytics', path: '/dashboard/analytics', icon: BarChart3 },
      { name: 'Departements', path: '/dashboard/departments', icon: MapPin },
      { name: 'Sources', path: '/dashboard/data-sources', icon: Globe },
    ],
  },
  {
    label: 'Admin',
    items: [
      { name: 'Configuration', path: '/dashboard/settings', icon: Settings },
    ],
  },
];

// Flat list for NavItem rendering
const NAV_ITEMS = NAV_SECTIONS.flatMap(s => s.items);

export default function AppSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Keyboard shortcut: Ctrl+B to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        setCollapsed(c => !c);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const isActive = (path: string) => {
    if (path === '/dashboard/main') return pathname === '/dashboard/main' || pathname === '/dashboard';
    return pathname?.startsWith(path);
  };

  const NavItem = ({ item }: { item: { name: string; path: string; icon: any } }) => {
    const active = isActive(item.path);
    const Icon = item.icon;
    return (
      <Link
        href={item.path}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
          'hover:bg-primary/10 hover:text-primary',
          active
            ? 'bg-primary/15 text-primary shadow-sm'
            : 'text-muted-foreground',
          collapsed && 'justify-center px-2'
        )}
        title={collapsed ? item.name : undefined}
      >
        <Icon className={cn('shrink-0', collapsed ? 'h-5 w-5' : 'h-4.5 w-4.5')} />
        {!collapsed && <span className="truncate">{item.name}</span>}
      </Link>
    );
  };

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile toggle button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg bg-card border border-border shadow-md"
      >
        <LayoutDashboard className="h-5 w-5" />
      </button>

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-screen flex flex-col',
          'bg-background border-r border-border',
          'transition-all duration-300 ease-out',
          // Desktop
          'lg:relative lg:z-auto',
          collapsed ? 'w-[68px]' : 'w-[220px]',
          // Mobile
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Header */}
        <div className={cn(
          'flex items-center border-b border-border shrink-0',
          collapsed ? 'justify-center h-16 px-4' : 'gap-3 h-20 px-4'
        )}>
          <TajineLogo className={cn('shrink-0 transition-all duration-300', collapsed ? 'h-9 w-9' : 'h-11 w-11')} />
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-base font-bold truncate">Tawiza</span>
              <span className="text-[10px] text-muted-foreground truncate">Intelligence Territoriale</span>
            </div>
          )}
        </div>

        {/* Search trigger */}
        <div className="px-3 pt-3">
          <button
            onClick={() => (window as any).__openGlobalSearch?.()}
            className={cn(
              'flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors border border-border',
              collapsed && 'justify-center px-2'
            )}
            title="Rechercher (Cmd+K)"
          >
            <Search className="h-4 w-4 shrink-0" />
            {!collapsed && (
              <>
                <span className="flex-1 text-left truncate">Rechercher...</span>
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground/70">
                  {"\u2318"}K
                </kbd>
              </>
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
          {NAV_SECTIONS.map(section => (
            <div key={section.label}>
              {!collapsed && (
                <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  {section.label}
                </p>
              )}
              {collapsed && <div className="border-t border-border/40 mx-2 mb-2" />}
              <div className="space-y-0.5">
                {section.items.map(item => (
                  <NavItem key={item.path} item={item} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer: user + collapse + logout */}
        <div className="shrink-0 border-t border-border p-3 space-y-2">
          {/* User info */}
          {!collapsed && user && (
            <div className="px-3 py-1.5 text-xs text-muted-foreground truncate">
              {user.email}
            </div>
          )}

          {/* Logout */}
          {showLogoutConfirm ? (
            <div className="flex items-center gap-1.5 px-2">
              <button
                onClick={() => { logout(); setShowLogoutConfirm(false); }}
                className="flex-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-red-500/15 text-red-400 hover:bg-red-500/25 transition-colors"
              >
                Confirmer
              </button>
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="flex-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-muted/50 text-muted-foreground hover:bg-muted transition-colors"
              >
                Annuler
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowLogoutConfirm(true)}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors w-full',
                collapsed && 'justify-center px-2'
              )}
              title="Deconnexion"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Deconnexion</span>}
            </button>
          )}

          {/* Collapse toggle */}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="hidden lg:flex w-full items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted/50 transition-colors"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Reduire</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
