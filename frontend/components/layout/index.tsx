import AppSidebar from '@/components/layout/sidebar';
import MobileBottomNav from '@/components/navigation/MobileBottomNav';
import { GlobalSearch } from '@/components/ui/global-search';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { usePathname } from 'next/navigation';
import { OpenContext } from '@/contexts/layout';
import React, { useState } from 'react';

interface Props {
  children: React.ReactNode;
  title: string;
  description: string;
  headerActions?: React.ReactNode;
  fullHeight?: boolean;
}

const DashboardLayout: React.FC<Props> = (props: Props) => {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <OpenContext.Provider value={{ open, setOpen }}>
      <div className="flex h-screen w-full overflow-hidden">
        {/* Global search modal - triggered via Cmd+K from sidebar */}
        <GlobalSearch />

        {/* Sidebar */}
        <AppSidebar />

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Top header bar */}
          <header className="shrink-0 h-14 flex items-center justify-between pl-14 lg:pl-6 pr-4 border-b border-border/50 bg-background/80 backdrop-blur-sm">
            <div className="min-w-0 flex items-center gap-3">
              <h1 className="text-base font-semibold truncate">{props.title}</h1>
              {props.description && (
                <p className="text-xs text-muted-foreground hidden sm:block">{props.description}</p>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {props.headerActions}
              <ThemeToggle />
            </div>
          </header>

          {/* Scrollable content */}
          {props.fullHeight ? (
            <main className="flex-1 overflow-hidden">
              <div key={pathname} className="h-full">
                {props.children}
              </div>
            </main>
          ) : (
            <main className="flex-1 overflow-y-auto">
              <div className="p-4 md:p-6 pb-20 lg:pb-6 max-w-[1600px] mx-auto">
                <div key={pathname} className="animate-fade-in">
                  {props.children}
                </div>
              </div>
            </main>
          )}
        </div>

        {/* Mobile bottom navigation removed  -  sidebar handles mobile nav */}
      </div>
    </OpenContext.Provider>
  );
};

export default DashboardLayout;
