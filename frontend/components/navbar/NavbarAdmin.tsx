'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { TajineLogo } from '@/components/ui/tajine-logo';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { NotificationBell } from '@/components/notifications';
import { GlobalSearch } from '@/components/ui/global-search';
import { useAuth } from '@/contexts/AuthContext';
import {
  HiOutlineHome,
  HiOutlineChatBubbleLeftRight,
  HiOutlineMapPin,
  HiOutlineChartBar,
  HiOutlineCog8Tooth,
  HiOutlineGlobeAlt,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineMoon,
  HiOutlineSun,
  HiOutlineUser,
  HiArrowRightOnRectangle,
  HiOutlineEllipsisHorizontal,
  HiOutlineShieldCheck,
  HiOutlineAcademicCap,
  HiOutlineBugAnt,
} from 'react-icons/hi2';

const NAV_ITEMS = [
  { name: 'Dashboard', path: '/dashboard/main', icon: HiOutlineHome },
  { name: 'TAJINE', path: '/dashboard/tajine', icon: HiOutlineGlobeEuropeAfrica },
  { name: 'Chat', path: '/dashboard/ai-chat', icon: HiOutlineChatBubbleLeftRight },
  { name: 'Analyses', path: '/dashboard/analytics', icon: HiOutlineChartBar },
  { name: 'Départements', path: '/dashboard/departments', icon: HiOutlineMapPin },
  { name: 'Sources', path: '/dashboard/data-sources', icon: HiOutlineGlobeAlt },
  { name: 'Investigation', path: '/dashboard/investigation', icon: HiOutlineShieldCheck },
];

const MORE_ITEMS = [
  { name: 'Fine-Tuning', path: '/dashboard/fine-tuning', icon: HiOutlineAcademicCap },
  { name: 'Crawler', path: '/dashboard/settings/crawler', icon: HiOutlineBugAnt },
  { name: 'Configuration', path: '/dashboard/settings', icon: HiOutlineCog8Tooth },
];

export default function AdminNavbar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { user, logout, isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const isActive = (path: string) => pathname?.includes(path);
  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  return (
    <TooltipProvider delayDuration={0}>
      <nav className="fixed left-0 right-0 top-0 z-[49] mx-3 mt-1 sm:mx-4 sm:mt-2 md:mx-6 md:mt-2">
        <div className={cn(
          "relative rounded-2xl border border-border bg-card shadow-lg shadow-black/5 dark:shadow-black/20 transition-all duration-300",
          scrolled ? "py-2 px-4 sm:py-2.5 sm:px-5" : "py-3 px-4 sm:py-3.5 sm:px-5"
        )}>
          <div className="flex items-center justify-between">
            {/* Left: Logo + Brand + Navigation */}
            <div className="flex items-center gap-3 sm:gap-5">
              {/* Logo + Brand */}
              <Link href="/dashboard/main" className="flex items-center gap-2.5 flex-shrink-0">
                <TajineLogo size={scrolled ? 32 : 40} className="transition-all duration-300" />
                <div className="flex items-center">
                  <span className={cn(
                    "font-bold text-foreground transition-all duration-300",
                    scrolled ? "text-base" : "text-lg"
                  )}>
                    Tawiza
                  </span>
                  <Badge
                    variant="outline"
                    className="ml-2 px-1.5 py-0 text-[10px] text-primary border-primary/30 bg-primary/10"
                  >
                    TAJINE
                  </Badge>
                </div>
              </Link>

              {/* Desktop Navigation */}
              <div className="hidden xl:flex items-center gap-0.5">
                {NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.path);
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      className={cn(
                        'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-all',
                        active
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.name}</span>
                    </Link>
                  );
                })}

                {/* More dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn(
                        'flex items-center gap-1.5 px-2.5 py-1.5 h-auto text-sm font-medium',
                        MORE_ITEMS.some((item) => isActive(item.path))
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <HiOutlineEllipsisHorizontal className="h-4 w-4" />
                      <span>Plus</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48">
                    {MORE_ITEMS.map((item) => {
                      const Icon = item.icon;
                      const active = isActive(item.path);
                      return (
                        <DropdownMenuItem key={item.path} asChild>
                          <Link href={item.path} className={cn('flex items-center gap-2 cursor-pointer', active && 'text-primary font-medium')}>
                            <Icon className="h-4 w-4" />
                            <span>{item.name}</span>
                          </Link>
                        </DropdownMenuItem>
                      );
                    })}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-1 sm:gap-2">
              <GlobalSearch />
              <NotificationBell />

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleTheme}
                    className="h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
                  >
                    {mounted ? (
                      theme === 'dark' ? <HiOutlineSun className="h-4 w-4" /> : <HiOutlineMoon className="h-4 w-4" />
                    ) : <div className="h-4 w-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p>{theme === 'dark' ? 'Mode clair' : 'Mode sombre'}</p>
                </TooltipContent>
              </Tooltip>

              {isAuthenticated && user && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
                    >
                      <HiOutlineUser className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-56" align="end">
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col space-y-1">
                        <p className="text-sm font-medium leading-none">{user.name}</p>
                        <p className="text-xs leading-none text-muted-foreground">{user.email}</p>
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <Link href="/dashboard/settings" className="flex items-center cursor-pointer">
                        <HiOutlineCog8Tooth className="mr-2 h-4 w-4" />
                        <span>Paramètres</span>
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => logout()}
                      className="text-destructive focus:text-destructive cursor-pointer"
                    >
                      <HiArrowRightOnRectangle className="mr-2 h-4 w-4" />
                      <span>Déconnexion</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </div>
      </nav>
    </TooltipProvider>
  );
}
