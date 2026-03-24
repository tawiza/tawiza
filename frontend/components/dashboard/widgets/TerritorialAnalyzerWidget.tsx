'use client';

import { useState } from 'react';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  HiOutlineChartBar,
  HiOutlineUserGroup,
  HiOutlinePlay,
  HiOutlineArrowTrendingUp,
  HiOutlineArrowTrendingDown,
  HiOutlineExclamationTriangle,
} from 'react-icons/hi2';
import {
  useAttractiveness,
  useScenarios,
  runSimulation,
  type AttractivenessScore,
  type WhatIfScenario,
  type TerritorialSimulationResult,
} from '@/lib/api-tajine';

// French departments for selection
const DEPARTMENTS = [
  { code: '75', name: 'Paris' },
  { code: '69', name: 'Rhône' },
  { code: '13', name: 'Bouches-du-Rhône' },
  { code: '33', name: 'Gironde' },
  { code: '31', name: 'Haute-Garonne' },
  { code: '44', name: 'Loire-Atlantique' },
  { code: '59', name: 'Nord' },
  { code: '06', name: 'Alpes-Maritimes' },
  { code: '34', name: 'Hérault' },
  { code: '67', name: 'Bas-Rhin' },
];

const AXIS_LABELS: Record<string, string> = {
  infrastructure: 'Infrastructure',
  capital_humain: 'Capital Humain',
  environnement_eco: 'Environnement Éco.',
  qualite_vie: 'Qualité de Vie',
  accessibilite: 'Accessibilité',
  innovation: 'Innovation',
};

// Attractiveness Radar Chart (simplified SVG)
function AttractivenessRadar({ data }: { data: AttractivenessScore }) {
  const axes = Object.entries(data.axes);
  const n = axes.length;
  const cx = 100, cy = 100, r = 80;

  // Calculate points for radar polygon
  const points = axes.map(([, axis], i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const value = axis.score / 100;
    return {
      x: cx + r * value * Math.cos(angle),
      y: cy + r * value * Math.sin(angle),
    };
  });

  const polygonPoints = points.map((p) => `${p.x},${p.y}`).join(' ');

  // Grid circles
  const gridCircles = [0.25, 0.5, 0.75, 1].map((scale) => (
    <circle
      key={scale}
      cx={cx}
      cy={cy}
      r={r * scale}
      fill="none"
      stroke="rgba(255,255,255,0.1)"
      strokeWidth="1"
    />
  ));

  // Axis lines and labels
  const axisLines = axes.map(([name], i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    const labelX = cx + (r + 15) * Math.cos(angle);
    const labelY = cy + (r + 15) * Math.sin(angle);

    return (
      <g key={name}>
        <line
          x1={cx}
          y1={cy}
          x2={x}
          y2={y}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
        />
        <text
          x={labelX}
          y={labelY}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-[8px] fill-muted-foreground"
        >
          {AXIS_LABELS[name]?.split(' ')[0] || name}
        </text>
      </g>
    );
  });

  return (
    <svg viewBox="0 0 200 200" className="w-full h-48">
      {gridCircles}
      {axisLines}
      <polygon
        points={polygonPoints}
        fill="rgba(56, 189, 248, 0.3)"
        stroke="rgb(56, 189, 248)"
        strokeWidth="2"
      />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="4" fill="rgb(56, 189, 248)" />
      ))}
    </svg>
  );
}

// Axis Score Bar
function AxisBar({
  name,
  score,
  trend,
}: {
  name: string;
  score: number;
  trend: number;
}) {
  const trendIcon =
    trend > 0 ? (
      <HiOutlineArrowTrendingUp className="h-3 w-3 text-green-400" />
    ) : trend < 0 ? (
      <HiOutlineArrowTrendingDown className="h-3 w-3 text-red-400" />
    ) : null;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{AXIS_LABELS[name] || name}</span>
        <span className="flex items-center gap-1">
          {score.toFixed(0)}/100 {trendIcon}
        </span>
      </div>
      <div className="h-1.5 bg-muted/20 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// Simulation Result Display
function SimulationResultDisplay({
  result,
}: {
  result: TerritorialSimulationResult;
}) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-muted/10">
          <div className="text-xs text-muted-foreground">Entreprises</div>
          <div
            className={`text-lg font-bold ${
              result.summary.net_enterprise_change >= 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {result.summary.net_enterprise_change >= 0 ? '+' : ''}
            {result.summary.net_enterprise_change}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-muted/10">
          <div className="text-xs text-muted-foreground">Emplois</div>
          <div
            className={`text-lg font-bold ${
              result.summary.net_employment_change >= 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {result.summary.net_employment_change >= 0 ? '+' : ''}
            {result.summary.net_employment_change}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-muted/10">
          <div className="text-xs text-muted-foreground">Attractivité</div>
          <div
            className={`text-lg font-bold ${
              result.summary.attractiveness_change >= 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {result.summary.attractiveness_change >= 0 ? '+' : ''}
            {result.summary.attractiveness_change.toFixed(1)}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-muted/10">
          <div className="text-xs text-muted-foreground">Durée</div>
          <div className="text-lg font-bold">{result.duration_months} mois</div>
        </div>
      </div>

      {/* Effects */}
      {result.positive_effects.length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground mb-1">Effets positifs</div>
          <ul className="text-xs space-y-0.5">
            {result.positive_effects.slice(0, 3).map((effect, i) => (
              <li key={i} className="text-green-400">
                ✓ {effect}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.negative_effects.length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground mb-1">Risques</div>
          <ul className="text-xs space-y-0.5">
            {result.negative_effects.slice(0, 3).map((effect, i) => (
              <li key={i} className="text-red-400">
                ⚠ {effect}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendation */}
      <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
        <div className="text-xs font-medium">{result.recommendation}</div>
      </div>
    </div>
  );
}

export function TerritorialAnalyzerWidget() {
  const [selectedCode, setSelectedCode] = useState<string>('75');
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] =
    useState<TerritorialSimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  // Fetch attractiveness for selected department
  const { attractiveness, isLoading: attractivenessLoading, isError } = useAttractiveness(selectedCode);

  // Fetch available scenarios
  const { scenarios, isLoading: scenariosLoading } = useScenarios();

  // Run simulation handler
  const handleRunSimulation = async () => {
    if (!selectedCode) return;

    setIsSimulating(true);
    try {
      const result = await runSimulation(
        selectedCode,
        selectedScenario || undefined,
        36
      );
      setSimulationResult(result);
    } catch (error) {
      console.error('Simulation failed:', error);
    } finally {
      setIsSimulating(false);
    }
  };

  if (isError) {
    return (
      <GlassCard glow="red">
        <GlassCardHeader>
          <GlassCardTitle className="flex items-center gap-2">
            <HiOutlineExclamationTriangle className="h-5 w-5 text-red-400" />
            Analyse Territoriale
          </GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <p className="text-sm text-muted-foreground">Erreur de chargement</p>
        </GlassCardContent>
      </GlassCard>
    );
  }

  return (
    <GlassCard glow="cyan" hoverGlow className="col-span-2">
      <GlassCardHeader className="flex flex-row items-center justify-between pb-2">
        <GlassCardTitle className="flex items-center gap-2">
          <HiOutlineChartBar className="h-5 w-5 text-cyan-400" />
          Analyse Territoriale
        </GlassCardTitle>
        <Select value={selectedCode} onValueChange={setSelectedCode}>
          <SelectTrigger className="w-[160px] h-8 text-xs">
            <SelectValue placeholder="Département" />
          </SelectTrigger>
          <SelectContent>
            {DEPARTMENTS.map((dept) => (
              <SelectItem key={dept.code} value={dept.code}>
                {dept.code} - {dept.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </GlassCardHeader>

      <GlassCardContent>
        <Tabs defaultValue="attractiveness" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="attractiveness" className="text-xs">
              <HiOutlineChartBar className="h-4 w-4 mr-1" />
              Attractivité
            </TabsTrigger>
            <TabsTrigger value="competitors" className="text-xs">
              <HiOutlineUserGroup className="h-4 w-4 mr-1" />
              Concurrents
            </TabsTrigger>
            <TabsTrigger value="simulation" className="text-xs">
              <HiOutlinePlay className="h-4 w-4 mr-1" />
              Simulation
            </TabsTrigger>
          </TabsList>

          {/* Attractiveness Tab */}
          <TabsContent value="attractiveness">
            {attractivenessLoading ? (
              <div className="space-y-2">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="h-6 bg-muted/20 rounded animate-pulse" />
                ))}
              </div>
            ) : attractiveness ? (
              <div className="grid md:grid-cols-2 gap-4">
                {/* Radar Chart */}
                <div>
                  <AttractivenessRadar data={attractiveness} />
                  <div className="text-center mt-2">
                    <Badge variant="outline" className="text-lg px-3 py-1">
                      Score: {attractiveness.global_score.toFixed(1)}/100
                    </Badge>
                    <div className="text-xs text-muted-foreground mt-1">
                      Rang national: #{attractiveness.rank}
                    </div>
                  </div>
                </div>

                {/* Axis Bars */}
                <div className="space-y-3">
                  {Object.entries(attractiveness.axes).map(([name, axis]) => (
                    <AxisBar
                      key={name}
                      name={name}
                      score={axis.score}
                      trend={axis.trend}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Sélectionnez un département
              </p>
            )}
          </TabsContent>

          {/* Competitors Tab */}
          <TabsContent value="competitors">
            <div className="text-center py-8">
              <HiOutlineUserGroup className="h-12 w-12 mx-auto text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground mt-2">
                Analyse concurrentielle disponible via l&apos;agent TAJINE
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Utilisez le chat pour demander une analyse complète
              </p>
            </div>
          </TabsContent>

          {/* Simulation Tab */}
          <TabsContent value="simulation">
            <div className="space-y-4">
              {/* Scenario Selector */}
              <div className="flex gap-2">
                <Select
                  value={selectedScenario || ''}
                  onValueChange={(v) => setSelectedScenario(v || null)}
                >
                  <SelectTrigger className="flex-1 h-9">
                    <SelectValue placeholder="Scénario (optionnel)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Baseline (sans changement)</SelectItem>
                    {scenarios.map((scenario: WhatIfScenario) => (
                      <SelectItem key={scenario.id} value={scenario.id}>
                        {scenario.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={handleRunSimulation}
                  disabled={isSimulating || !selectedCode}
                  className="shrink-0"
                >
                  {isSimulating ? (
                    <span className="animate-spin">⏳</span>
                  ) : (
                    <HiOutlinePlay className="h-4 w-4 mr-1" />
                  )}
                  Simuler
                </Button>
              </div>

              {/* Selected Scenario Description */}
              {selectedScenario && scenarios.length > 0 && (
                <div className="p-3 rounded-lg bg-muted/10 text-xs">
                  <div className="font-medium">
                    {scenarios.find((s: WhatIfScenario) => s.id === selectedScenario)?.name}
                  </div>
                  <div className="text-muted-foreground mt-1">
                    {scenarios.find((s: WhatIfScenario) => s.id === selectedScenario)?.description}
                  </div>
                </div>
              )}

              {/* Simulation Result */}
              {simulationResult ? (
                <SimulationResultDisplay result={simulationResult} />
              ) : (
                <div className="text-center py-6">
                  <p className="text-sm text-muted-foreground">
                    Sélectionnez un scénario et lancez la simulation
                  </p>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </GlassCardContent>
    </GlassCard>
  );
}

export default TerritorialAnalyzerWidget;
