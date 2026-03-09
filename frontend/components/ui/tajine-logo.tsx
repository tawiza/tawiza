'use client';

import { cn } from '@/lib/utils';
import Image from 'next/image';

interface TajineLogoProps {
  size?: number;
  className?: string;
}

export function TajineLogo({ size = 64, className }: TajineLogoProps) {
  return (
    <>
      {/* Light mode: cream bg, dark tajine */}
      <Image
        src="/logo-tajine-v2-light.svg"
        alt="TAJINE"
        width={size}
        height={size}
        className={cn('drop-shadow-sm object-contain dark:hidden', className)}
        priority
      />
      {/* Dark mode: transparent bg, golden tajine */}
      <Image
        src="/logo-tajine-v2-dark.svg"
        alt="TAJINE"
        width={size}
        height={size}
        className={cn('drop-shadow-sm object-contain hidden dark:block', className)}
        priority
      />
    </>
  );
}
