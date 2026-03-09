'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineChartBar,
  HiOutlineChevronUp,
  HiOutlineChevronDown,
  HiOutlineArrowsPointingOut,
  HiOutlineArrowsPointingIn,
} from 'react-icons/hi2';
import dynamic from 'next/dynamic';

// Dynamic imports for charts to reduce initial bundle
const GrowthLineChart = dynamic(
  () => import('./charts/GrowthLineChart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const SectorBarChart = dynamic(
  () => import('./charts/SectorBarChart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const RadarChart = dynamic(
  () => import('./charts/RadarChart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const RelationGraph = dynamic(
  () => import('./charts/RelationGraph'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const HeatmapChart = dynamic(
  () => import('./charts/HeatmapChart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const TreemapChart = dynamic(
  () => import('./charts/TreemapChart'),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

interface ChartsDrawerProps {
  departmentCode?: string | null;
  analysisData?: any;
  className?: string;
}

type TabKey = 'growth' | 'sectors' | 'radar' | 'relations' | 'heatmap' | 'treemap';

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'growth', label: 'Tendances', icon: '📈' },
  { key: 'sectors', label: 'Secteurs', icon: '📊' },
  { key: 'radar', label: 'Radar', icon: '🎯' },
  { key: 'relations', label: 'Relations', icon: '🔗' },
  { key: 'heatmap', label: 'Heatmap', icon: '🗺️' },
  { key: 'treemap', label: 'Treemap', icon: '🌳' },
];

export default function ChartsDrawer({
  departmentCode,
  analysisData,
  className = '',
}: ChartsDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('growth');

  // Drawer height based on state
  const getDrawerHeight = () => {
    if (!isOpen) return '48px'; // Collapsed - just header
    if (isExpanded) return '70vh'; // Expanded
    return '320px'; // Default open height
  };

  const renderChart = () => {
    const isLoading = !analysisData;

    switch (activeTab) {
      case 'growth':
        return <GrowthLineChart data={analysisData?.timeseries} isLoading={isLoading} />;
      case 'sectors':
        return <SectorBarChart data={analysisData?.sectors} isLoading={isLoading} />;
      case 'radar':
        return <RadarChart data={analysisData?.radarData} isLoading={isLoading} />;
      case 'relations':
        // RelationGraph expects nodes and links arrays
        return (
          <RelationGraph
            nodes={analysisData?.graph?.nodes}
            links={analysisData?.graph?.links}
            isLoading={isLoading}
          />
        );
      case 'heatmap':
        return (
          <HeatmapChart
            data={analysisData?.heatmapData?.data}
            xLabels={analysisData?.heatmapData?.xLabels}
            yLabels={analysisData?.heatmapData?.yLabels}
            isLoading={isLoading}
          />
        );
      case 'treemap':
        return <TreemapChart data={analysisData?.treemapData} isLoading={isLoading} />;
      default:
        return null;
    }
  };

  return (
    <motion.div
      initial={{ y: 100 }}
      animate={{ y: 0, height: getDrawerHeight() }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className={`fixed bottom-0 left-0 right-0 z-30 ${className}`}
    >
      <div className="glass rounded-t-xl shadow-2xl border border-white/10 border-b-0 h-full flex flex-col">
        {/* Header - Always visible */}
        <div
          className="flex items-center justify-between px-4 py-3 border-b border-border/50 cursor-pointer select-none"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className="flex items-center gap-3">
            <HiOutlineChartBar className="w-5 h-5 text-primary" />
            <span className="font-medium text-sm">Visualisations</span>
            {departmentCode && (
              <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-primary/20 text-primary">
                {departmentCode}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isOpen && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setIsExpanded(!isExpanded);
                }}
                className="p-1.5 rounded-md hover:bg-muted/50 transition-colors"
                title={isExpanded ? 'Reduire' : 'Agrandir'}
              >
                {isExpanded ? (
                  <HiOutlineArrowsPointingIn className="w-4 h-4" />
                ) : (
                  <HiOutlineArrowsPointingOut className="w-4 h-4" />
                )}
              </button>
            )}
            <button className="p-1.5 rounded-md hover:bg-muted/50 transition-colors">
              {isOpen ? (
                <HiOutlineChevronDown className="w-4 h-4" />
              ) : (
                <HiOutlineChevronUp className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Content - Only visible when open */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col overflow-hidden"
            >
              {/* Tabs */}
              <div className="flex items-center gap-1 px-4 py-2 border-b border-border/30 overflow-x-auto">
                {TABS.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                      activeTab === tab.key
                        ? 'bg-primary/20 text-primary'
                        : 'hover:bg-muted/50 text-muted-foreground'
                    }`}
                  >
                    <span>{tab.icon}</span>
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              {/* Chart Area */}
              <div className="flex-1 p-4 overflow-hidden">
                {renderChart()}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// Chart loading skeleton
function ChartSkeleton() {
  return (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-muted/30 animate-pulse" />
        <div className="h-3 w-24 bg-muted/30 rounded animate-pulse" />
      </div>
    </div>
  );
}
