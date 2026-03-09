'use client';

import { Badge } from '../ui/badge';
import {
  renderThumb,
  renderTrack,
  renderView
} from '@/components/scrollbar/Scrollbar';
import SidebarCard from '@/components/sidebar/components/SidebarCard';
import { IRoute } from '@/types/types';
import React, { PropsWithChildren, useCallback, useEffect, useState } from 'react';
import { Scrollbars } from 'react-custom-scrollbars-2';
import { HiX } from 'react-icons/hi';
import {
  HiOutlineBars3,
  HiOutlineXMark,
  HiOutlineMoon,
  HiOutlineSun
} from 'react-icons/hi2';
import { TajineLogo } from '@/components/ui/tajine-logo';
import NavLink from '@/components/link/NavLink';
import { usePathname } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { NotificationBell } from '@/components/notifications';

const SIDEBAR_STORAGE_KEY = 'sidebar-collapsed';

export interface CollapsibleSidebarProps extends PropsWithChildren {
  routes: IRoute[];
  open?: boolean;
  setOpen?: (open: boolean) => void;
  variant?: 'auth' | 'admin';
}

function CollapsibleSidebar(props: CollapsibleSidebarProps) {
  const { routes, open = true, setOpen, variant } = props;
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  // Hydration fix: wait for mount before rendering theme-dependent UI
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Collapsed state with localStorage persistence
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Load collapsed state from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (stored !== null) {
      setIsCollapsed(stored === 'true');
    }
  }, []);

  // Save collapsed state to localStorage and dispatch event for other components
  const toggleCollapsed = useCallback(() => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(newState));
    // Dispatch custom event to notify layout and navbar
    window.dispatchEvent(new CustomEvent('sidebar-toggle', { detail: { isCollapsed: newState } }));
  }, [isCollapsed]);

  // Keyboard shortcut: Ctrl+B
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'b') {
        e.preventDefault();
        toggleCollapsed();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleCollapsed]);

  // Check if route is active
  const activeRoute = useCallback(
    (routePath: string) => {
      return pathname?.includes(routePath);
    },
    [pathname]
  );

  // Toggle theme
  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  const sidebarWidth = isCollapsed ? 'w-[64px]' : 'w-[280px]';

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={`lg:!z-99 fixed !z-[99] min-h-full transition-all duration-300 ease-out-quart md:!z-[99] xl:!z-0 ${sidebarWidth} ${
          variant === 'auth' ? 'xl:hidden' : 'xl:block'
        } ${open ? '' : '-translate-x-[120%] xl:translate-x-[unset]'}`}
      >
        <div
          className={`glass m-3 ml-3 h-[96.5vh] w-full overflow-hidden sm:my-4 sm:mr-4 md:m-5 md:mr-[-50px]`}
        >
          <Scrollbars
            autoHide
            renderTrackVertical={renderTrack}
            renderThumbVertical={renderThumb}
            renderView={renderView}
            universal={true}
          >
            <div className="flex h-full flex-col justify-between">
              <div>
                {/* Mobile close button */}
                <span
                  className="absolute right-4 top-4 block cursor-pointer text-muted-foreground hover:text-foreground xl:hidden"
                  onClick={() => setOpen?.(false)}
                >
                  <HiX className="h-5 w-5" />
                </span>

                {/* Collapse toggle button */}
                <button
                  onClick={toggleCollapsed}
                  className="absolute right-3 top-3 hidden rounded-md p-1.5 text-muted-foreground transition-normal hover:bg-muted hover:text-foreground xl:block"
                  title="Toggle sidebar (Ctrl+B)"
                >
                  {isCollapsed ? (
                    <HiOutlineBars3 className="h-5 w-5" />
                  ) : (
                    <HiOutlineXMark className="h-5 w-5" />
                  )}
                </button>

                {/* Logo with animated scaling */}
                <div className={`mt-8 flex items-center transition-all duration-300 ease-out-quart ${isCollapsed ? 'justify-center' : 'justify-center'}`}>
                  <div className={`transition-transform duration-300 ease-out-quart ${isCollapsed ? 'scale-[0.7]' : 'scale-100'}`}>
                    <TajineLogo size={56} />
                  </div>
                  <div className={`overflow-hidden transition-all duration-300 ease-out-quart ${isCollapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
                    <div className="flex items-center whitespace-nowrap">
                      <h5 className="ms-2 text-2xl font-bold leading-5 text-foreground">
                        Tawiza
                      </h5>
                      <Badge
                        variant="outline"
                        className="ms-2 my-auto w-max px-2 py-0.5 text-xs text-primary border-primary/30 bg-primary/10"
                      >
                        TAJINE
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="mb-6 mt-6 h-px bg-border" />

                {/* Navigation items */}
                <nav className="px-3">
                  <ul className="space-y-1">
                    {routes.map((route, index) => {
                      const isActive = activeRoute(route.path.toLowerCase());
                      const isDisabled = route.disabled;
                      const href = route.layout ? route.layout + route.path : route.path;

                      const linkContent = (
                        <div
                          className={`group flex items-center transition-all duration-200 ease-out-quart ${
                            isCollapsed
                              ? 'justify-center w-10 h-10 mx-auto rounded-full'
                              : 'px-3 py-2.5 rounded-lg'
                          } ${
                            isActive
                              ? isCollapsed
                                ? 'bg-primary text-primary-foreground shadow-md'
                                : 'active-glow bg-primary/10 text-primary'
                              : isDisabled
                              ? 'cursor-not-allowed opacity-40'
                              : isCollapsed
                                ? 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                          }`}
                        >
                          <span className={`transition-transform duration-200 ${
                            isCollapsed
                              ? 'group-hover:scale-110'
                              : 'mr-3'
                          } ${isActive && isCollapsed ? 'scale-110' : ''}`}>
                            {route.icon}
                          </span>
                          <span className={`text-sm font-medium transition-all duration-200 ${
                            isCollapsed
                              ? 'w-0 opacity-0 overflow-hidden'
                              : 'w-auto opacity-100'
                          }`}>
                            {route.name}
                          </span>
                        </div>
                      );

                      if (isDisabled) {
                        return (
                          <li key={index}>
                            {isCollapsed ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  {linkContent}
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                  <p>{route.name} (bientot)</p>
                                </TooltipContent>
                              </Tooltip>
                            ) : (
                              linkContent
                            )}
                          </li>
                        );
                      }

                      return (
                        <li key={index}>
                          {isCollapsed ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <NavLink href={href}>
                                  {linkContent}
                                </NavLink>
                              </TooltipTrigger>
                              <TooltipContent side="right">
                                <p>{route.name}</p>
                              </TooltipContent>
                            </Tooltip>
                          ) : (
                            <NavLink href={href}>
                              {linkContent}
                            </NavLink>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </nav>
              </div>

              {/* Bottom section */}
              <div className="mb-6 mt-auto px-3">
                {/* Notifications & Theme controls */}
                <div className={`flex items-center gap-2 mb-3 ${isCollapsed ? 'justify-center' : ''}`}>
                  {/* Notification Bell */}
                  <NotificationBell />

                  {/* Theme toggle - only render after mount to avoid hydration mismatch */}
                  <button
                    onClick={toggleTheme}
                    className="flex items-center justify-center rounded-lg p-2 text-muted-foreground transition-normal hover:bg-muted hover:text-foreground"
                  >
                    {mounted ? (
                      theme === 'dark' ? (
                        <HiOutlineSun className="h-4 w-4" />
                      ) : (
                        <HiOutlineMoon className="h-4 w-4" />
                      )
                    ) : (
                      <div className="h-4 w-4" /> /* Placeholder during SSR */
                    )}
                  </button>
                </div>

                {/* Info Card - only when expanded */}
                {!isCollapsed && (
                  <div className="mt-4">
                    <SidebarCard />
                  </div>
                )}
              </div>
            </div>
          </Scrollbars>
        </div>
      </div>
    </TooltipProvider>
  );
}

export default CollapsibleSidebar;
