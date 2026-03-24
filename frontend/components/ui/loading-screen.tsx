'use client';

import { cn } from '@/lib/utils';
import Image from 'next/image';

interface LoadingScreenProps {
  fullScreen?: boolean;
  message?: string;
  className?: string;
}

export function LoadingScreen({ fullScreen = true, message, className }: LoadingScreenProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-4',
        fullScreen && 'fixed inset-0 z-[9999] bg-background',
        !fullScreen && 'w-full py-12',
        className
      )}
    >
      <Image
        src="/loading-tajine.webp"
        alt="Chargement..."
        width={400}
        height={225}
        className="drop-shadow-lg"
        unoptimized
        priority
      />
      {message && (
        <p className="text-sm text-muted-foreground animate-pulse font-medium">
          {message}
        </p>
      )}
    </div>
  );
}

/**
 * Inline loader for sections/cards (not full screen)
 */
export function LoadingInline({ message, className }: { message?: string; className?: string }) {
  return <LoadingScreen fullScreen={false} message={message} className={className} />;
}
