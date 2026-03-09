'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-[72px] h-8" />;

  const isDark = theme === 'dark';

  return (
    <button
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className={cn(
        'relative flex items-center w-[72px] h-8 rounded-full p-1 transition-colors duration-300',
        isDark
          ? 'bg-muted border border-border/50'
          : 'bg-primary/10 border border-primary/20'
      )}
      title={isDark ? 'Passer en mode clair' : 'Passer en mode sombre'}
    >
      {/* Sliding pill */}
      <span
        className={cn(
          'absolute top-1 h-6 w-6 rounded-full transition-all duration-300 ease-out-quart shadow-sm',
          isDark
            ? 'left-[calc(100%-28px)] bg-primary/80'
            : 'left-1 bg-primary'
        )}
      />
      {/* Icons */}
      <span className={cn(
        'relative z-10 flex items-center justify-center w-6 h-6 transition-colors',
        !isDark ? 'text-primary-foreground' : 'text-muted-foreground'
      )}>
        <Sun className="h-3.5 w-3.5" />
      </span>
      <span className={cn(
        'relative z-10 flex items-center justify-center w-6 h-6 ml-auto transition-colors',
        isDark ? 'text-primary-foreground' : 'text-muted-foreground'
      )}>
        <Moon className="h-3.5 w-3.5" />
      </span>
    </button>
  );
}
