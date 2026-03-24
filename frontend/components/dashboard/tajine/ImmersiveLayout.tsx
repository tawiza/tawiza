'use client';

import { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineCog6Tooth,
  HiOutlineArrowsPointingOut,
  HiOutlineArrowsPointingIn,
  HiOutlineServerStack,
  HiOutlineSquares2X2,
} from 'react-icons/hi2';
import FloatingChat from './FloatingChat';
import DepartmentPanel from './DepartmentPanel';
import ChartsDrawer from './ChartsDrawer';
import SourcesIndicator from './SourcesIndicator';
import PPDSLProgress from './PPDSLProgress';
import { useTAJINE } from '@/contexts/TAJINEContext';

// Import IndicatorType for type safety
import type { IndicatorType } from './FranceMapLeaflet';

// Dynamic import for map (heavy component)
const FranceMapLeaflet = dynamic(
  () => import('./FranceMapLeaflet'),
  { ssr: false, loading: () => <MapSkeleton /> }
);

interface ImmersiveLayoutProps {
  departments: any[];
  isLoading?: boolean;
  className?: string;
}

export default function ImmersiveLayout({
  departments,
  isLoading,
  className = '',
}: ImmersiveLayoutProps) {
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null);
  const [mapIndicator, setMapIndicator] = useState<IndicatorType>('growth');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const { sendMessage, latestAnalysis, isAnalyzing } = useTAJINE();

  // Handle department selection
  const handleDepartmentSelect = useCallback((code: string) => {
    setSelectedDepartment(code);
  }, []);

  // Handle department close
  const handleDepartmentClose = useCallback(() => {
    setSelectedDepartment(null);
  }, []);

  // Handle analyze action from department panel
  const handleAnalyzeDepartment = useCallback(async (code: string) => {
    const dept = departments.find(d => d.code === code);
    const deptName = dept?.name || code;
    await sendMessage(`Analyse économique complète du département ${deptName} (${code})`, 'complete');
  }, [departments, sendMessage]);

  // Handle analysis complete callback
  const handleAnalysisComplete = useCallback(() => {
    // Could trigger chart refresh or other actions
  }, []);

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  return (
    <div className={`relative w-full h-screen overflow-hidden bg-background ${className}`}>
      {/* Full-screen Map Background */}
      <div className="absolute inset-0 z-0">
        {isLoading ? (
          <MapSkeleton />
        ) : (
          <FranceMapLeaflet
            data={departments}
            selectedDepartment={selectedDepartment}
            onDepartmentSelect={handleDepartmentSelect}
            activeIndicator={mapIndicator}
            onIndicatorChange={setMapIndicator}
            className="w-full h-full"
          />
        )}
      </div>

      {/* Top Bar - Logo, Sources, Settings */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3">
        <div className="glass rounded-lg px-4 py-2 flex items-center gap-3">
          <span className="font-semibold text-sm">TAJINE</span>
          <span className="text-xs text-muted-foreground">Intelligence Territoriale</span>
        </div>

        <SourcesIndicator />

        <div className="glass rounded-lg p-1 flex gap-1">
          {/* Exit immersive mode - return to classic with sidebar */}
          <button
            onClick={() => {
              if (typeof window !== 'undefined') {
                localStorage.setItem('tajine-layout-mode', 'classic');
                window.location.reload();
              }
            }}
            className="p-2 rounded-md hover:bg-muted/50 transition-colors"
            title="Mode classique (avec menu)"
          >
            <HiOutlineSquares2X2 className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-md hover:bg-muted/50 transition-colors"
            title={isFullscreen ? 'Quitter plein écran' : 'Plein écran'}
          >
            {isFullscreen ? (
              <HiOutlineArrowsPointingIn className="w-4 h-4" />
            ) : (
              <HiOutlineArrowsPointingOut className="w-4 h-4" />
            )}
          </button>
          {/* Settings button with relative container for dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-2 rounded-md transition-colors ${
                showSettings ? 'bg-primary/20 text-primary' : 'hover:bg-muted/50'
              }`}
              title="Paramètres"
            >
              <HiOutlineCog6Tooth className="w-4 h-4" />
            </button>

            {/* Settings Panel - positioned relative to button */}
            <AnimatePresence>
              {showSettings && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute top-full right-0 mt-2 z-50 glass rounded-lg p-3 min-w-[200px]"
                >
                  <div className="text-xs font-medium mb-3">Parametres</div>

                  {/* Map Mode */}
                  <div className="mb-3">
                    <div className="text-[10px] text-muted-foreground mb-1">Mode carte</div>
                    <div className="flex gap-1">
                      {(['growth', 'enterprises', 'chomage'] as const).map((ind) => (
                        <button
                          key={ind}
                          onClick={() => {
                            setMapIndicator(ind);
                            setShowSettings(false);
                          }}
                          className={`px-2 py-1 rounded text-[10px] transition-colors ${
                            mapIndicator === ind
                              ? 'bg-primary/20 text-primary'
                              : 'hover:bg-muted/50 text-muted-foreground'
                          }`}
                        >
                          {ind === 'growth' && 'Croissance'}
                          {ind === 'enterprises' && 'Entreprises'}
                          {ind === 'chomage' && 'Chomage'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Quick Actions */}
                  <div className="pt-2 border-t border-border/30">
                    <button
                      onClick={() => {
                        setSelectedDepartment(null);
                        setShowSettings(false);
                      }}
                      className="w-full text-left px-2 py-1.5 text-[10px] rounded hover:bg-muted/50 transition-colors"
                    >
                      Reinitialiser la selection
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Floating Chat Panel (Left) */}
      <FloatingChat
        onAnalysisComplete={handleAnalysisComplete}
      />

      {/* Department Panel (Right - appears on click) */}
      <DepartmentPanel
        departmentCode={selectedDepartment}
        onClose={handleDepartmentClose}
        onAnalyze={handleAnalyzeDepartment}
      />

      {/* PPDSL Progress (Bottom left, above charts) */}
      {isAnalyzing && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className="absolute bottom-[360px] left-4 z-20 w-[320px]"
        >
          <PPDSLProgress compact />
        </motion.div>
      )}

      {/* Charts Drawer (Bottom) */}
      <ChartsDrawer
        departmentCode={selectedDepartment}
        analysisData={latestAnalysis}
      />

      {/* Legend gradient - positioned above ChartsDrawer (48px header + margin) */}
      <div className="absolute bottom-[60px] right-4 z-20">
        <div className="glass rounded-lg px-3 py-2">
          <div className="text-[10px] text-muted-foreground mb-1">Légende</div>
          <div className="flex items-center gap-2">
            <div className="w-20 h-2 rounded-full bg-gradient-to-r from-[var(--error)] via-[var(--warning)] to-[var(--success)]" />
            <span className="text-[10px] text-muted-foreground">
              {mapIndicator === 'chomage' ? 'Haut → Bas' : 'Bas → Haut'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Map loading skeleton
function MapSkeleton() {
  return (
    <div className="w-full h-full bg-muted/10 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-muted/30 animate-pulse" />
        <div className="h-4 w-32 bg-muted/30 rounded animate-pulse" />
        <div className="h-3 w-48 bg-muted/20 rounded animate-pulse" />
      </div>
    </div>
  );
}
