'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import {
  HiOutlineChartBar,
  HiOutlineChatBubbleLeftRight,
  HiOutlineGlobeEuropeAfrica,
  HiOutlineMapPin,
  HiOutlineSquares2X2,
} from 'react-icons/hi2';

const NAV_ITEMS = [
  {
    href: '/dashboard/main',
    icon: HiOutlineSquares2X2,
    label: 'Dashboard',
  },
  {
    href: '/dashboard/intelligence',
    icon: HiOutlineGlobeEuropeAfrica,
    label: 'Intelligence',
  },
  {
    href: '/dashboard/ai-chat',
    icon: HiOutlineChatBubbleLeftRight,
    label: 'Chat',
  },
  {
    href: '/dashboard/departments',
    icon: HiOutlineMapPin,
    label: 'Depts',
  },
  {
    href: '/dashboard/analytics',
    icon: HiOutlineChartBar,
    label: 'Analyses',
  },
];

export default function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 lg:hidden">
      {/* Backdrop blur effect */}
      <div className="absolute inset-0 glass border-t border-border" />

      {/* Navigation items */}
      <div className="relative flex items-center justify-around px-2 py-2 safe-area-inset-bottom">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname?.includes(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg transition-all',
                isActive
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Icon className={cn('h-5 w-5', isActive && 'scale-110')} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
