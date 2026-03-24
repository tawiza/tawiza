'use client';

import { useState, type ReactNode } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  content: ReactNode;
}

interface PageTabsProps {
  tabs: Tab[];
  defaultTab?: string;
}

export function PageTabs({ tabs, defaultTab }: PageTabsProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const tabParam = searchParams.get('tab');
  const activeTab = tabParam && tabs.some(t => t.id === tabParam)
    ? tabParam
    : defaultTab || tabs[0]?.id;

  const setTab = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', id);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const current = tabs.find(t => t.id === activeTab);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 border-b border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              tab.id === activeTab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
      {current?.content}
    </div>
  );
}
