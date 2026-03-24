'use client';

import { cn } from '@/lib/utils';

interface TajineLogoProps {
  size?: number;
  isStreaming?: boolean;
  className?: string;
}

export default function TajineLogoAnimated({
  size = 48,
  isStreaming = false,
  className = '',
}: TajineLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn(
        'transition-all duration-300',
        isStreaming && 'drop-shadow-[0_0_12px_rgba(136,192,208,0.5)]',
        className
      )}
    >
      {/* Cone/lid - geometric triangle */}
      <path
        d="M24 8L36 30H12L24 8Z"
        fill="url(#cone-gradient)"
        stroke="#88C0D0"
        strokeWidth="1.5"
        strokeLinejoin="round"
        className={cn(
          'transition-all duration-300',
          isStreaming && 'animate-pulse'
        )}
      />

      {/* Circuit lines on cone */}
      <line x1="24" y1="14" x2="24" y2="22" stroke="#8FBCBB" strokeWidth="1" opacity="0.4"/>
      <line x1="20" y1="22" x2="28" y2="22" stroke="#8FBCBB" strokeWidth="1" opacity="0.4"/>

      {/* Data points */}
      <circle cx="24" cy="16" r="1.5" fill="#88C0D0"/>
      <circle cx="24" cy="20" r="1" fill="#81A1C1" opacity="0.8"/>
      <circle cx="24" cy="24" r="1" fill="#81A1C1" opacity="0.6"/>

      {/* Base/plate */}
      <ellipse
        cx="24"
        cy="34"
        rx="14"
        ry="5"
        fill="#3B4252"
        stroke="#88C0D0"
        strokeWidth="1.5"
      />

      {/* Steam wisps - animated */}
      <g>
        <path
          d="M20 6C20 6 19 3 20 1"
          stroke="#8FBCBB"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="animate-steam opacity-50"
          style={{ animationDelay: '0s' }}
        />
        <path
          d="M24 5C24 5 24 2 25 0"
          stroke="#88C0D0"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="animate-steam opacity-70"
          style={{ animationDelay: '0.3s' }}
        />
        <path
          d="M28 6C28 6 29 3 28 1"
          stroke="#8FBCBB"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="animate-steam opacity-50"
          style={{ animationDelay: '0.6s' }}
        />
      </g>

      {/* Gradient definition */}
      <defs>
        <linearGradient id="cone-gradient" x1="24" y1="8" x2="24" y2="30" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#4C566A"/>
          <stop offset="100%" stopColor="#2E3440"/>
        </linearGradient>
      </defs>
    </svg>
  );
}
