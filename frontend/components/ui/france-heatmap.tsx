'use client';

import React, { useState, useCallback, useEffect, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip';

/**
 * FranceHeatmap - Interactive SVG map of France with department highlighting
 *
 * Shows territorial data as a heatmap with click interactions and tooltips.
 */

// Simplified France departments paths (mainland only for performance)
const DEPARTMENTS: Record<string, { path: string; name: string; center: [number, number] }> = {
  '01': { path: 'M380,320 L390,310 L405,315 L410,330 L395,340 L380,335 Z', name: 'Ain', center: [392, 325] },
  '03': { path: 'M305,310 L325,305 L335,320 L325,335 L305,330 Z', name: 'Allier', center: [320, 320] },
  '07': { path: 'M350,385 L365,375 L380,385 L375,405 L355,405 Z', name: 'Ardèche', center: [365, 390] },
  '13': { path: 'M370,460 L400,455 L415,475 L390,490 L365,480 Z', name: 'Bouches-du-Rhône', center: [390, 475] },
  '21': { path: 'M335,260 L360,255 L375,275 L365,295 L340,290 Z', name: "Côte-d'Or", center: [355, 275] },
  '26': { path: 'M375,395 L395,385 L415,400 L405,425 L380,420 Z', name: 'Drôme', center: [395, 405] },
  '33': { path: 'M175,385 L205,370 L225,395 L215,430 L180,425 Z', name: 'Gironde', center: [200, 400] },
  '34': { path: 'M330,465 L365,455 L375,480 L350,495 L325,485 Z', name: 'Hérault', center: [350, 475] },
  '38': { path: 'M385,350 L410,340 L425,365 L410,385 L385,375 Z', name: 'Isère', center: [405, 365] },
  '42': { path: 'M345,345 L370,340 L380,365 L365,380 L345,370 Z', name: 'Loire', center: [362, 360] },
  '44': { path: 'M160,295 L195,285 L210,305 L195,325 L160,320 Z', name: 'Loire-Atlantique', center: [185, 305] },
  '59': { path: 'M295,85 L335,75 L355,100 L340,125 L300,120 Z', name: 'Nord', center: [325, 100] },
  '63': { path: 'M300,345 L330,335 L350,360 L335,385 L305,375 Z', name: 'Puy-de-Dôme', center: [325, 360] },
  '67': { path: 'M425,195 L450,185 L465,210 L450,235 L425,225 Z', name: 'Bas-Rhin', center: [445, 210] },
  '69': { path: 'M365,325 L385,315 L400,335 L390,355 L365,350 Z', name: 'Rhône', center: [382, 335] },
  '75': { path: 'M285,175 L300,170 L310,185 L300,200 L285,195 Z', name: 'Paris', center: [297, 185] },
  '76': { path: 'M245,130 L280,120 L295,145 L280,170 L250,160 Z', name: 'Seine-Maritime', center: [270, 145] },
  '83': { path: 'M415,470 L450,460 L465,485 L445,505 L415,495 Z', name: 'Var', center: [440, 480] },
  '84': { path: 'M385,430 L410,420 L430,445 L415,465 L385,455 Z', name: 'Vaucluse', center: [408, 445] },
  '92': { path: 'M275,180 L290,175 L298,190 L288,205 L275,200 Z', name: 'Hauts-de-Seine', center: [286, 190] },
  '93': { path: 'M295,175 L315,170 L325,188 L312,205 L295,198 Z', name: 'Seine-Saint-Denis', center: [310, 187] },
  '94': { path: 'M295,198 L315,193 L325,215 L310,230 L292,220 Z', name: 'Val-de-Marne', center: [308, 212] },
};

// Generate more realistic department data
const generateDepartmentData = () => {
  const data: Record<string, { score: number; trend: 'up' | 'down' | 'stable'; enterprises: number }> = {};
  Object.keys(DEPARTMENTS).forEach((code) => {
    data[code] = {
      score: 30 + Math.random() * 60,
      trend: ['up', 'down', 'stable'][Math.floor(Math.random() * 3)] as 'up' | 'down' | 'stable',
      enterprises: Math.floor(1000 + Math.random() * 50000),
    };
  });
  // Lyon specifically
  data['69'] = { score: 78, trend: 'up', enterprises: 89234 };
  data['75'] = { score: 92, trend: 'stable', enterprises: 245000 };
  data['13'] = { score: 71, trend: 'up', enterprises: 112000 };
  return data;
};

// Color scale for heatmap
const getHeatColor = (score: number): string => {
  if (score >= 80) return 'var(--success)'; // green-500
  if (score >= 60) return 'var(--success)'; // lime-500
  if (score >= 40) return 'var(--warning)'; // yellow-500
  if (score >= 20) return 'var(--chart-5)'; // orange-500
  return 'var(--error)'; // red-500
};

const getTrendIcon = (trend: 'up' | 'down' | 'stable') => {
  switch (trend) {
    case 'up': return '↗';
    case 'down': return '↘';
    default: return '→';
  }
};

interface FranceHeatmapProps {
  onDepartmentClick?: (code: string, name: string) => void;
  selectedDepartment?: string;
  className?: string;
  data?: Record<string, { score: number; trend: 'up' | 'down' | 'stable'; enterprises: number }>;
}

const FranceHeatmap = memo(function FranceHeatmap({
  onDepartmentClick,
  selectedDepartment,
  className = '',
  data: externalData,
}: FranceHeatmapProps) {
  const [hoveredDept, setHoveredDept] = useState<string | null>(null);
  const [data, setData] = useState<Record<string, { score: number; trend: 'up' | 'down' | 'stable'; enterprises: number }>>(
    externalData || generateDepartmentData()
  );
  const [pulsingDepts, setPulsingDepts] = useState<string[]>([]);

  // Simulate real-time updates
  useEffect(() => {
    if (externalData) {
      setData(externalData);
      return;
    }

    const interval = setInterval(() => {
      const deptCodes = Object.keys(DEPARTMENTS);
      const randomDept = deptCodes[Math.floor(Math.random() * deptCodes.length)];

      setData((prev) => ({
        ...prev,
        [randomDept]: {
          ...prev[randomDept],
          score: Math.max(10, Math.min(100, prev[randomDept].score + (Math.random() - 0.5) * 5)),
          enterprises: prev[randomDept].enterprises + Math.floor((Math.random() - 0.3) * 10),
        },
      }));

      // Add pulse effect
      setPulsingDepts((prev) => [...prev, randomDept]);
      setTimeout(() => {
        setPulsingDepts((prev) => prev.filter((d) => d !== randomDept));
      }, 1000);
    }, 2000);

    return () => clearInterval(interval);
  }, [externalData]);

  const handleClick = useCallback(
    (code: string) => {
      if (onDepartmentClick) {
        onDepartmentClick(code, DEPARTMENTS[code]?.name || code);
      }
    },
    [onDepartmentClick]
  );

  return (
    <TooltipProvider>
      <div className={`relative ${className}`}>
        <svg
          viewBox="100 50 400 500"
          className="w-full h-full"
          style={{ maxHeight: '500px' }}
        >
          {/* Background gradient */}
          <defs>
            <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(255, 107, 74, 0.1)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <rect x="100" y="50" width="400" height="500" fill="url(#mapGlow)" />

          {/* Departments */}
          {Object.entries(DEPARTMENTS).map(([code, dept]) => {
            const deptData = data[code] || { score: 50, trend: 'stable', enterprises: 0 };
            const isSelected = selectedDepartment === code;
            const isHovered = hoveredDept === code;
            const isPulsing = pulsingDepts.includes(code);

            return (
              <Tooltip key={code}>
                <TooltipTrigger asChild>
                  <motion.path
                    d={dept.path}
                    fill={getHeatColor(deptData.score)}
                    stroke={isSelected ? 'hsl(var(--foreground))' : isHovered ? 'hsl(var(--foreground))' : 'hsl(var(--border))'}
                    strokeWidth={isSelected ? 3 : isHovered ? 2 : 1}
                    className="cursor-pointer"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{
                      opacity: 1,
                      scale: isPulsing ? 1.05 : 1,
                      filter: isSelected || isHovered ? 'url(#glow)' : 'none',
                    }}
                    transition={{
                      duration: 0.3,
                      scale: { duration: 0.2 },
                    }}
                    whileHover={{ scale: 1.08 }}
                    onClick={() => handleClick(code)}
                    onMouseEnter={() => setHoveredDept(code)}
                    onMouseLeave={() => setHoveredDept(null)}
                  />
                </TooltipTrigger>
                <TooltipContent side="top" className="bg-black/90 border-border">
                  <div className="text-sm">
                    <div className="font-bold flex items-center gap-2">
                      {dept.name} ({code})
                      <span className={deptData.trend === 'up' ? 'text-green-400' : deptData.trend === 'down' ? 'text-red-400' : 'text-gray-400'}>
                        {getTrendIcon(deptData.trend)}
                      </span>
                    </div>
                    <div className="text-foreground/70 mt-1">
                      Score: <span className="font-medium text-foreground">{Math.round(deptData.score)}/100</span>
                    </div>
                    <div className="text-foreground/70">
                      Entreprises: <span className="font-medium text-foreground">{deptData.enterprises.toLocaleString()}</span>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          })}

          {/* Department labels for major cities */}
          {['75', '69', '13', '33', '59'].map((code) => {
            const dept = DEPARTMENTS[code];
            if (!dept) return null;
            return (
              <motion.text
                key={`label-${code}`}
                x={dept.center[0]}
                y={dept.center[1]}
                textAnchor="middle"
                dominantBaseline="middle"
                className="text-[8px] fill-white font-bold pointer-events-none"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
              >
                {code}
              </motion.text>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 flex items-center gap-2 text-xs bg-zinc-900 rounded-lg px-3 py-2">
          <span className="text-foreground/60">Score:</span>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'var(--error)' }} />
            <span className="text-foreground/40">0</span>
          </div>
          <div className="w-12 h-2 rounded-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500" />
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'var(--success)' }} />
            <span className="text-foreground/40">100</span>
          </div>
        </div>

        {/* Active updates indicator */}
        <AnimatePresence>
          {pulsingDepts.length > 0 && (
            <motion.div
              className="absolute top-4 right-4 flex items-center gap-2 text-xs bg-green-500/20 text-green-400 rounded-full px-3 py-1"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
            >
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              Mise à jour temps réel
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </TooltipProvider>
  );
});

export default FranceHeatmap;
