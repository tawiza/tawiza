'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  HiOutlineChartBar,
  HiOutlineBuildingOffice2,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineCurrencyEuro,
  HiOutlineUsers,
  HiOutlineHome,
  HiOutlineBriefcase,
  HiOutlineXMark,
  HiOutlineAdjustmentsHorizontal,
  HiOutlineInformationCircle,
  HiOutlineSquares2X2,
  HiOutlineGlobeEuropeAfrica,
} from 'react-icons/hi2';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Extended indicator types for territorial analysis
export type ExtendedIndicatorType =
  | 'growth'
  | 'enterprises'
  | 'prix_m2'
  | 'chomage'
  | 'population'
  | 'health_score'
  | 'budget'
  | 'dette';

export interface IndicatorConfig {
  key: ExtendedIndicatorType;
  label: string;
  description: string;
  source: string;
  icon: React.ReactNode;
  unit: string;
  category: 'economic' | 'real_estate' | 'employment' | 'financial' | 'demographic';
  colorScheme: 'diverging' | 'sequential' | 'categorical';
  // Higher or lower is better?
  higherIsBetter?: boolean;
}

// All available indicators for the drawer
export const EXTENDED_INDICATORS: Record<ExtendedIndicatorType, IndicatorConfig> = {
  growth: {
    key: 'growth',
    label: 'Croissance Entreprises',
    description: 'Taux de croissance annuel du nombre d\'entreprises',
    source: 'SIRENE (INSEE)',
    icon: <HiOutlineArrowTrendingUp className="w-4 h-4" />,
    unit: '%',
    category: 'economic',
    colorScheme: 'diverging',
    higherIsBetter: true,
  },
  enterprises: {
    key: 'enterprises',
    label: 'Nombre d\'Entreprises',
    description: 'Total des entreprises actives dans le département',
    source: 'SIRENE (INSEE)',
    icon: <HiOutlineBuildingOffice2 className="w-4 h-4" />,
    unit: '',
    category: 'economic',
    colorScheme: 'sequential',
    higherIsBetter: true,
  },
  prix_m2: {
    key: 'prix_m2',
    label: 'Prix Immobilier',
    description: 'Prix médian au m² des transactions immobilières',
    source: 'DVF (DGFiP)',
    icon: <HiOutlineHome className="w-4 h-4" />,
    unit: '€/m²',
    category: 'real_estate',
    colorScheme: 'sequential',
  },
  chomage: {
    key: 'chomage',
    label: 'Taux de Chômage',
    description: 'Pourcentage de demandeurs d\'emploi cat. A',
    source: 'France Travail',
    icon: <HiOutlineBriefcase className="w-4 h-4" />,
    unit: '%',
    category: 'employment',
    colorScheme: 'diverging',
    higherIsBetter: false,
  },
  population: {
    key: 'population',
    label: 'Population',
    description: 'Population totale du département',
    source: 'INSEE',
    icon: <HiOutlineUsers className="w-4 h-4" />,
    unit: '',
    category: 'demographic',
    colorScheme: 'sequential',
  },
  health_score: {
    key: 'health_score',
    label: 'Score Santé',
    description: 'Indice composite de santé économique (0-100)',
    source: 'Tawiza (calculé)',
    icon: <HiOutlineGlobeEuropeAfrica className="w-4 h-4" />,
    unit: '/100',
    category: 'economic',
    colorScheme: 'diverging',
    higherIsBetter: true,
  },
  budget: {
    key: 'budget',
    label: 'Budget/Habitant',
    description: 'Budget de fonctionnement par habitant',
    source: 'OFGL (Bercy)',
    icon: <HiOutlineCurrencyEuro className="w-4 h-4" />,
    unit: '€',
    category: 'financial',
    colorScheme: 'sequential',
  },
  dette: {
    key: 'dette',
    label: 'Dette/Habitant',
    description: 'Encours de dette par habitant',
    source: 'OFGL (Bercy)',
    icon: <HiOutlineArrowTrendingDown className="w-4 h-4" />,
    unit: '€',
    category: 'financial',
    colorScheme: 'diverging',
    higherIsBetter: false,
  },
};

// Category labels and colors
const CATEGORIES = {
  economic: { label: 'Économie', color: 'bg-blue-500/20 text-blue-400' },
  real_estate: { label: 'Immobilier', color: 'bg-primary/20 text-primary' },
  employment: { label: 'Emploi', color: 'bg-orange-500/20 text-orange-400' },
  financial: { label: 'Finances', color: 'bg-purple-500/20 text-purple-400' },
  demographic: { label: 'Démographie', color: 'bg-green-500/20 text-green-400' },
};

interface IndicatorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  primaryIndicator: ExtendedIndicatorType;
  secondaryIndicator: ExtendedIndicatorType | null;
  onPrimaryChange: (indicator: ExtendedIndicatorType) => void;
  onSecondaryChange: (indicator: ExtendedIndicatorType | null) => void;
  biIndicatorMode: boolean;
  onBiIndicatorModeChange: (enabled: boolean) => void;
}

export default function IndicatorDrawer({
  isOpen,
  onClose,
  primaryIndicator,
  secondaryIndicator,
  onPrimaryChange,
  onSecondaryChange,
  biIndicatorMode,
  onBiIndicatorModeChange,
}: IndicatorDrawerProps) {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Group indicators by category
  const indicatorsByCategory = Object.entries(EXTENDED_INDICATORS).reduce(
    (acc, [key, config]) => {
      if (!acc[config.category]) {
        acc[config.category] = [];
      }
      acc[config.category].push(config);
      return acc;
    },
    {} as Record<string, IndicatorConfig[]>
  );

  const handleIndicatorClick = (indicator: ExtendedIndicatorType) => {
    if (biIndicatorMode && primaryIndicator !== indicator) {
      // In bi-indicator mode, clicking sets secondary
      onSecondaryChange(secondaryIndicator === indicator ? null : indicator);
    } else {
      // Normal mode - set primary
      onPrimaryChange(indicator);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 h-full w-80 glass border-r border-border/50 z-50 overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-border/50">
              <div className="flex items-center gap-2">
                <HiOutlineAdjustmentsHorizontal className="w-5 h-5 text-primary" />
                <h2 className="font-semibold">Indicateurs</h2>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 hover:bg-muted/50 rounded-md transition-colors"
              >
                <HiOutlineXMark className="w-5 h-5" />
              </button>
            </div>

            {/* Bi-indicator toggle */}
            <div className="p-4 border-b border-border/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HiOutlineSquares2X2 className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">Mode bi-indicateur</span>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HiOutlineInformationCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="max-w-xs text-xs">
                          Superpose deux indicateurs: couleur pour le principal, symboles pour le secondaire
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Switch
                  checked={biIndicatorMode}
                  onCheckedChange={onBiIndicatorModeChange}
                />
              </div>

              {/* Current selection summary */}
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-primary" />
                  <span className="text-xs text-muted-foreground">Principal:</span>
                  <span className="text-xs font-medium">
                    {EXTENDED_INDICATORS[primaryIndicator].label}
                  </span>
                </div>
                {biIndicatorMode && (
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full border-2 border-primary bg-transparent" />
                    <span className="text-xs text-muted-foreground">Secondaire:</span>
                    <span className="text-xs font-medium">
                      {secondaryIndicator
                        ? EXTENDED_INDICATORS[secondaryIndicator].label
                        : 'Aucun'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Indicator list by category */}
            <div className="flex-1 overflow-y-auto">
              {Object.entries(CATEGORIES).map(([catKey, catConfig]) => {
                const indicators = indicatorsByCategory[catKey] || [];
                if (indicators.length === 0) return null;

                return (
                  <div key={catKey} className="border-b border-border/30">
                    {/* Category header */}
                    <button
                      onClick={() =>
                        setActiveCategory(activeCategory === catKey ? null : catKey)
                      }
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Badge className={catConfig.color} variant="outline">
                          {catConfig.label}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {indicators.length} indicateurs
                        </span>
                      </div>
                      <motion.span
                        animate={{ rotate: activeCategory === catKey ? 180 : 0 }}
                        className="text-muted-foreground"
                      >
                        ▼
                      </motion.span>
                    </button>

                    {/* Category indicators */}
                    <AnimatePresence>
                      {(activeCategory === catKey || activeCategory === null) && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          {indicators.map((indicator) => {
                            const isPrimary = primaryIndicator === indicator.key;
                            const isSecondary = secondaryIndicator === indicator.key;

                            return (
                              <button
                                key={indicator.key}
                                onClick={() => handleIndicatorClick(indicator.key)}
                                className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors ${
                                  isPrimary
                                    ? 'bg-primary/10 border-l-2 border-primary'
                                    : isSecondary
                                    ? 'bg-cyan-500/10 border-l-2 border-cyan-500'
                                    : ''
                                }`}
                              >
                                <div
                                  className={`p-1.5 rounded-md ${
                                    isPrimary
                                      ? 'bg-primary/20 text-primary'
                                      : isSecondary
                                      ? 'bg-cyan-500/20 text-cyan-500'
                                      : 'bg-muted/50 text-muted-foreground'
                                  }`}
                                >
                                  {indicator.icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">
                                      {indicator.label}
                                    </span>
                                    {indicator.unit && (
                                      <span className="text-xs text-muted-foreground">
                                        ({indicator.unit})
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                                    {indicator.description}
                                  </p>
                                  <div className="flex items-center gap-2 mt-1">
                                    <span className="text-[10px] text-muted-foreground/70">
                                      Source: {indicator.source}
                                    </span>
                                  </div>
                                </div>
                                {/* Selection indicators */}
                                <div className="flex flex-col gap-1">
                                  {isPrimary && (
                                    <Badge className="text-[9px] px-1.5 py-0" variant="default">
                                      1°
                                    </Badge>
                                  )}
                                  {isSecondary && (
                                    <Badge
                                      className="text-[9px] px-1.5 py-0 bg-cyan-500/20 text-cyan-400"
                                      variant="outline"
                                    >
                                      2°
                                    </Badge>
                                  )}
                                </div>
                              </button>
                            );
                          })}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>

            {/* Footer with help */}
            <div className="p-4 border-t border-border/50 bg-muted/20">
              <p className="text-xs text-muted-foreground">
                {biIndicatorMode
                  ? 'Cliquez pour définir l\'indicateur secondaire (symboles)'
                  : 'Cliquez pour changer l\'indicateur de couleur'}
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
