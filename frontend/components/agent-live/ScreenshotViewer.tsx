'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  HiOutlineArrowsPointingOut,
  HiOutlineArrowsPointingIn,
  HiOutlineSignal,
  HiOutlineExclamationCircle,
  HiOutlineCamera,
  HiOutlineClock,
  HiOutlineGlobeAlt,
  HiOutlineShieldCheck,
  HiOutlineComputerDesktop,
} from 'react-icons/hi2';
import { SiGooglechrome, SiFirefox } from 'react-icons/si';
import { cn } from '@/lib/utils';
import { useTAJINE } from '@/contexts/TAJINEContext';

interface ScreenshotViewerProps {
  taskId?: string;
  className?: string;
  onConnectionChange?: (connected: boolean) => void;
  autoConnect?: boolean;
}

type BrowserTypeValue = 'nodriver' | 'camoufox' | 'playwright' | 'browser_use';

interface BrowserScreenshot {
  action: string;
  screenshot_b64: string;
  url?: string;
  timestamp: string;
  browser_type?: BrowserTypeValue;
  browser_info?: Record<string, unknown>;
}

/**
 * ScreenshotViewer - Uses TAJINEContext WebSocket instead of creating its own connection.
 * Listens to window events dispatched by use-tajine-websocket hook.
 */
export default function ScreenshotViewer({
  taskId,
  className,
  onConnectionChange,
}: ScreenshotViewerProps) {
  // Use context for WebSocket connection status
  const { wsConnected } = useTAJINE();

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentScreenshot, setCurrentScreenshot] = useState<BrowserScreenshot | null>(null);
  const [screenshotHistory, setScreenshotHistory] = useState<BrowserScreenshot[]>([]);
  const [lastAction, setLastAction] = useState<string>('');
  const [currentUrl, setCurrentUrl] = useState<string>('');
  const [browserType, setBrowserType] = useState<BrowserTypeValue>('playwright');
  const [stealthMode, setStealthMode] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Notify parent of connection changes
  useEffect(() => {
    onConnectionChange?.(wsConnected);
  }, [wsConnected, onConnectionChange]);

  // Listen for browser screenshot events from the context WebSocket
  useEffect(() => {
    const handleScreenshot = (event: CustomEvent) => {
      const data = event.detail;

      // Filter by taskId if provided
      if (taskId && data.task_id !== taskId) return;

      const screenshot: BrowserScreenshot = {
        action: data.action,
        screenshot_b64: data.screenshot_b64,
        url: data.url,
        timestamp: data.timestamp,
        browser_type: data.browser_type,
        browser_info: data.browser_info,
      };

      setCurrentScreenshot(screenshot);
      setLastAction(data.action);
      if (data.url) setCurrentUrl(data.url);
      if (data.browser_type) {
        setBrowserType(data.browser_type);
        setStealthMode(['nodriver', 'camoufox'].includes(data.browser_type));
      }

      // Keep last 10 screenshots in history
      setScreenshotHistory((prev) => [...prev.slice(-9), screenshot]);
    };

    const handleBrowserEvent = (event: CustomEvent) => {
      const data = event.detail;

      // Filter by taskId if provided
      if (taskId && data.task_id !== taskId) return;

      if (data.type === 'browser.action') {
        setLastAction(data.action);
      }

      if (data.type === 'browser.status') {
        if (data.current_url) setCurrentUrl(data.current_url);
        if (data.browser_type) {
          setBrowserType(data.browser_type);
          setStealthMode(data.stealth_mode ?? false);
        }
      }
    };

    window.addEventListener('browser-screenshot', handleScreenshot as EventListener);
    window.addEventListener('browser-event', handleBrowserEvent as EventListener);

    return () => {
      window.removeEventListener('browser-screenshot', handleScreenshot as EventListener);
      window.removeEventListener('browser-event', handleBrowserEvent as EventListener);
    };
  }, [taskId]);

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // Handle fullscreen change from ESC key
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Format action for display
  const formatAction = (action: string): string => {
    const actionLabels: Record<string, string> = {
      navigate: 'Navigation',
      click: 'Clic',
      type: 'Saisie',
      scroll: 'Defilement',
      extract: 'Extraction',
      solve_captcha: 'CAPTCHA',
      screenshot: 'Capture',
      start: 'Demarrage',
      stop: 'Arret',
    };
    return actionLabels[action] || action;
  };

  // Browser type badge with icon and color
  const BrowserTypeBadge = () => {
    const config: Record<BrowserTypeValue, {
      label: string;
      icon: React.ReactNode;
      className: string;
      tooltip: string;
    }> = {
      nodriver: {
        label: 'Chrome Stealth',
        icon: <SiGooglechrome className="h-3 w-3" />,
        className: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        tooltip: 'nodriver - Chrome CDP direct (anti-detection)',
      },
      camoufox: {
        label: 'Firefox Stealth',
        icon: <SiFirefox className="h-3 w-3" />,
        className: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
        tooltip: 'Camoufox - Firefox C++ fingerprint spoofing',
      },
      playwright: {
        label: 'Playwright',
        icon: <HiOutlineComputerDesktop className="h-3 w-3" />,
        className: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
        tooltip: 'Standard Playwright browser',
      },
      browser_use: {
        label: 'Browser Use',
        icon: <HiOutlineComputerDesktop className="h-3 w-3" />,
        className: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
        tooltip: 'browser-use LLM-powered automation',
      },
    };

    const { label, icon, className: badgeClassName, tooltip } = config[browserType] || config.playwright;

    return (
      <Badge
        className={cn('gap-1', badgeClassName)}
        title={tooltip}
      >
        {icon}
        {label}
        {stealthMode && (
          <HiOutlineShieldCheck className="h-3 w-3 ml-0.5" title="Mode Stealth actif" />
        )}
      </Badge>
    );
  };

  // Status badge component
  const StatusBadge = () => {
    if (wsConnected) {
      return (
        <Badge className="gap-1 bg-green-500/20 text-green-400 border-green-500/30">
          <HiOutlineSignal className="h-3 w-3" />
          Connecte
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="gap-1">
        <HiOutlineExclamationCircle className="h-3 w-3 opacity-50" />
        Deconnecte
      </Badge>
    );
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        'flex h-full flex-col bg-background rounded-lg overflow-hidden border border-border',
        isFullscreen && 'fixed inset-0 z-50',
        className
      )}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border px-3 py-2 bg-muted/30">
        <div className="flex items-center gap-2">
          <StatusBadge />
          {wsConnected && <BrowserTypeBadge />}
          {lastAction && wsConnected && (
            <Badge variant="outline" className="gap-1 text-primary">
              <HiOutlineClock className="h-3 w-3" />
              {formatAction(lastAction)}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Screenshot count */}
          {screenshotHistory.length > 0 && (
            <Badge variant="secondary" className="gap-1">
              <HiOutlineCamera className="h-3 w-3" />
              {screenshotHistory.length}
            </Badge>
          )}

          {/* Fullscreen toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Quitter plein ecran' : 'Plein ecran'}
          >
            {isFullscreen ? (
              <HiOutlineArrowsPointingIn className="h-4 w-4" />
            ) : (
              <HiOutlineArrowsPointingOut className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* URL bar */}
      {currentUrl && wsConnected && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/20 border-b border-border text-xs">
          <HiOutlineGlobeAlt className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="truncate text-muted-foreground">{currentUrl}</span>
        </div>
      )}

      {/* Screenshot display */}
      <div className="flex-1 relative bg-background overflow-hidden">
        {/* Disconnected state */}
        {!wsConnected && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
            <HiOutlineExclamationCircle className="h-12 w-12 mb-4 opacity-30 text-red-400" />
            <p className="text-sm font-medium text-red-400">WebSocket deconnecte</p>
            <p className="text-xs mt-1 opacity-50">
              Connexion au serveur en cours...
            </p>
          </div>
        )}

        {/* Connected but no screenshot yet */}
        {wsConnected && !currentScreenshot && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
            <div className="relative">
              <HiOutlineSignal className="h-12 w-12 animate-pulse text-green-500/50" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-ping" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full" />
            </div>
            <p className="text-sm mt-4 font-medium text-green-500">Connecte au WebSocket</p>
            <p className="text-xs mt-2 opacity-70 text-center max-w-[200px]">
              En attente d&apos;activite navigateur...
            </p>
            <p className="text-[10px] mt-1 opacity-40">
              Lancez une requete TAJINE pour voir l&apos;agent naviguer
            </p>
          </div>
        )}

        {/* Screenshot image - using img for base64 data URLs (not supported by next/image) */}
        {currentScreenshot && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`data:image/png;base64,${currentScreenshot.screenshot_b64}`}
            alt={`Browser screenshot - ${currentScreenshot.action}`}
            className="w-full h-full object-contain"
          />
        )}
      </div>

      {/* Screenshot history thumbnails */}
      {screenshotHistory.length > 1 && (
        <div className="border-t border-border px-2 py-1.5 bg-muted/20">
          <div className="flex gap-1 overflow-x-auto">
            {screenshotHistory.slice(-5).map((shot, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentScreenshot(shot)}
                className={cn(
                  'flex-shrink-0 w-16 h-10 rounded border overflow-hidden transition-all',
                  shot === currentScreenshot
                    ? 'border-primary ring-1 ring-primary'
                    : 'border-border hover:border-muted-foreground'
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/png;base64,${shot.screenshot_b64}`}
                  alt={`Historique ${idx + 1}`}
                  className="w-full h-full object-cover"
                />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
