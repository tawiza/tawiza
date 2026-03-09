'use client';

import React, { useState, useEffect, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

interface ActivityItem {
  id: string;
  type: 'analysis' | 'alert' | 'data' | 'ai' | 'user';
  title: string;
  description: string;
  timestamp: Date;
  metadata?: {
    territory?: string;
    sector?: string;
    confidence?: number;
    source?: string;
  };
}

const ACTIVITY_ICONS: Record<string, string> = {
  analysis: '📊',
  alert: '⚠️',
  data: '📥',
  ai: '🧠',
  user: '👤',
};

const ACTIVITY_COLORS: Record<string, string> = {
  analysis: 'from-blue-500/20 to-cyan-500/20 border-cyan-500/30',
  alert: 'from-yellow-500/20 to-orange-500/20 border-orange-500/30',
  data: 'from-green-500/20 to-emerald-500/20 border-emerald-500/30',
  ai: 'from-purple-500/20 to-pink-500/20 border-pink-500/30',
  user: 'from-gray-500/20 to-slate-500/20 border-slate-500/30',
};

// Sample activities generator
const generateActivity = (): ActivityItem => {
  const types: ActivityItem['type'][] = ['analysis', 'alert', 'data', 'ai'];
  const type = types[Math.floor(Math.random() * types.length)];

  const activities: Record<string, { title: string; description: string }[]> = {
    analysis: [
      { title: 'Analyse territoriale terminée', description: 'Rhône (69) - Score: 78/100' },
      { title: 'Rapport SWOT généré', description: 'Bouches-du-Rhône - 4 forces identifiées' },
      { title: 'Tendance détectée', description: 'Hausse création entreprises tech +15%' },
      { title: 'Comparaison multi-territoires', description: '5 départements analysés' },
    ],
    alert: [
      { title: 'Signal faible détecté', description: 'Concentration secteur agroalimentaire' },
      { title: 'Alerte économique', description: 'Baisse activité BTP Nord-Est' },
      { title: 'Opportunité identifiée', description: 'Zone franche urbaine disponible' },
    ],
    data: [
      { title: 'SIRENE synchronisé', description: '12,847 nouveaux établissements' },
      { title: 'BODACC mis à jour', description: '234 annonces traitées' },
      { title: 'INSEE rafraîchi', description: 'Données démographiques 2024' },
      { title: 'DVF importé', description: '1,523 transactions immobilières' },
    ],
    ai: [
      { title: 'TAJINE: Analyse causale', description: 'Facteurs croissance identifiés' },
      { title: 'Scénario prospectif généré', description: 'Monte Carlo - 1000 simulations' },
      { title: 'Recommandation stratégique', description: 'Investissement suggéré: infrastructure' },
      { title: 'Apprentissage complété', description: 'Précision améliorée +2.3%' },
    ],
  };

  const items = activities[type];
  const item = items[Math.floor(Math.random() * items.length)];

  return {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    type,
    title: item.title,
    description: item.description,
    timestamp: new Date(),
    metadata: {
      territory: ['69', '75', '13', '33', '59'][Math.floor(Math.random() * 5)],
      confidence: 70 + Math.floor(Math.random() * 25),
    },
  };
};

interface ActivityFeedProps {
  maxItems?: number;
  className?: string;
  showHeader?: boolean;
}

const ActivityFeed = memo(function ActivityFeed({
  maxItems = 8,
  className = '',
  showHeader = true,
}: ActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isPaused, setIsPaused] = useState(false);

  // Initialize with some activities
  useEffect(() => {
    const initial = Array.from({ length: 3 }, () => {
      const activity = generateActivity();
      activity.timestamp = new Date(Date.now() - Math.random() * 60000);
      return activity;
    });
    setActivities(initial.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()));
  }, []);

  // Add new activities periodically
  useEffect(() => {
    if (isPaused) return;

    const interval = setInterval(() => {
      setActivities((prev) => {
        const newActivity = generateActivity();
        const updated = [newActivity, ...prev].slice(0, maxItems);
        return updated;
      });
    }, 3000 + Math.random() * 4000);

    return () => clearInterval(interval);
  }, [isPaused, maxItems]);

  return (
    <div
      className={`relative ${className}`}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {showHeader && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
            </span>
            Activité Temps Réel
          </h3>
          <span className="text-xs text-muted-foreground">
            {isPaused ? '⏸️ En pause' : '▶️ Live'}
          </span>
        </div>
      )}

      <div className="space-y-2 overflow-hidden">
        <AnimatePresence mode="popLayout" initial={false}>
          {activities.map((activity) => (
            <motion.div
              key={activity.id}
              layout
              initial={{ opacity: 0, x: -20, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20, scale: 0.95 }}
              transition={{
                duration: 0.3,
                layout: { duration: 0.2 },
              }}
              className={`
                relative p-3 rounded-lg border
                bg-gradient-to-r ${ACTIVITY_COLORS[activity.type]}
                hover:scale-[1.02] transition-transform cursor-default
              `}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl">{ACTIVITY_ICONS[activity.type]}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">{activity.title}</span>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                      {formatDistanceToNow(activity.timestamp, { addSuffix: true, locale: fr })}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{activity.description}</p>
                  {activity.metadata?.confidence && (
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                          className="h-full bg-primary/60 rounded-full"
                          initial={{ width: 0 }}
                          animate={{ width: `${activity.metadata.confidence}%` }}
                          transition={{ duration: 0.5, delay: 0.2 }}
                        />
                      </div>
                      <span className="text-[10px] text-muted-foreground">
                        {activity.metadata.confidence}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Gradient fade at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-background to-transparent pointer-events-none" />
    </div>
  );
});

export default ActivityFeed;
