"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";

interface EPCIScore {
  code_epci: string;
  nom: string;
  population: number;
  departments: string[];
  composite_score: number;
  factor_scores: Record<string, number>;
  signal_count: number;
  source_count: number;
}

export default function EPCIScoresWidget() {
  const [epcis, setEpcis] = useState<EPCIScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [deptFilter, setDeptFilter] = useState<string>("");

  useEffect(() => {
    const url = deptFilter
      ? `/api/collector/epci/scores?days=180&code_dept=${deptFilter}`
      : "/api/collector/epci/scores?days=180";
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        setEpcis(data.epcis || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [deptFilter]);

  const getScoreColor = (score: number) => {
    if (score >= 65) return "text-emerald-400";
    if (score >= 55) return "text-blue-400";
    if (score >= 45) return "text-amber-400";
    return "text-red-400";
  };

  const getBarColor = (score: number) => {
    if (score >= 65) return "bg-emerald-500/80";
    if (score >= 55) return "bg-blue-500/80";
    if (score >= 45) return "bg-amber-500/80";
    return "bg-red-500/80";
  };

  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            🏘️ Scores EPCI (Intercommunalités)
          </h3>
          <p className="text-sm text-white/50 mt-1">
            {epcis.length} EPCI scorés — granularité intercommunale
          </p>
        </div>
        <div>
          <input
            type="text"
            placeholder="Dept (ex: 35)"
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-white/30 w-28 focus:outline-none focus:border-blue-500/50"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center text-white/40 py-8">Chargement...</div>
      ) : epcis.length === 0 ? (
        <div className="text-center text-white/40 py-8">Aucun EPCI trouvé</div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2 scrollbar-thin">
          {epcis.slice(0, 20).map((epci, i) => (
            <motion.div
              key={epci.code_epci}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
            >
              <span className="text-white/30 text-sm w-6 text-right">
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-white text-sm font-medium truncate">
                    {epci.nom || epci.code_epci}
                  </span>
                  <span className="text-white/30 text-xs flex-shrink-0">
                    {epci.departments.join(", ")}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${getBarColor(epci.composite_score)} transition-all`}
                      style={{ width: `${epci.composite_score}%` }}
                    />
                  </div>
                  <span className="text-white/40 text-xs flex-shrink-0">
                    {epci.signal_count} sig · {epci.source_count} src
                  </span>
                </div>
              </div>
              <span
                className={`text-lg font-bold tabular-nums ${getScoreColor(epci.composite_score)}`}
              >
                {epci.composite_score.toFixed(0)}
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
