'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';
import {
  Factory, Briefcase, Home, Coins, BarChart3, Newspaper,
  Search, ArrowUpDown, ArrowUp, ArrowDown, ChevronRight,
  Zap, MapPin, Users, Filter, Download, SlidersHorizontal
} from 'lucide-react';
import { DEPT_NAMES } from '@/lib/departments';

// ─── Types ───────────────────────────────────────────────────
interface DeptScore {
  code_dept: string;
  score_composite: number;
  alpha1_sante_entreprises: number;
  alpha2_tension_emploi: number;
  alpha3_dynamisme_immo: number;
  alpha4_sante_financiere: number;
  alpha5_declin_ratio: number;
  alpha6_sentiment: number;
  population: number;
}

interface MicroSignal {
  territory_code: string;
  signal_type: string;
  score: number;
  dimensions: string[];
  description: string;
}

interface SourceInfo {
  source: string;
  count: number;
}

// ─── Constants ───────────────────────────────────────────────
const DEPT_REGIONS: Record<string, string> = {
  '01':'Auvergne-Rhône-Alpes','02':'Hauts-de-France','03':'Auvergne-Rhône-Alpes',
  '04':'PACA','05':'PACA','06':'PACA','07':'Auvergne-Rhône-Alpes',
  '08':'Grand Est','09':'Occitanie','10':'Grand Est','11':'Occitanie','12':'Occitanie',
  '13':'PACA','14':'Normandie','15':'Auvergne-Rhône-Alpes','16':'Nouvelle-Aquitaine',
  '17':'Nouvelle-Aquitaine','18':'Centre-Val de Loire','19':'Nouvelle-Aquitaine',
  '2A':'Corse','2B':'Corse','21':'Bourgogne-Franche-Comté','22':'Bretagne',
  '23':'Nouvelle-Aquitaine','24':'Nouvelle-Aquitaine','25':'Bourgogne-Franche-Comté',
  '26':'Auvergne-Rhône-Alpes','27':'Normandie','28':'Centre-Val de Loire','29':'Bretagne',
  '30':'Occitanie','31':'Occitanie','32':'Occitanie','33':'Nouvelle-Aquitaine','34':'Occitanie',
  '35':'Bretagne','36':'Centre-Val de Loire','37':'Centre-Val de Loire','38':'Auvergne-Rhône-Alpes',
  '39':'Bourgogne-Franche-Comté','40':'Nouvelle-Aquitaine','41':'Centre-Val de Loire',
  '42':'Auvergne-Rhône-Alpes','43':'Auvergne-Rhône-Alpes','44':'Pays de la Loire',
  '45':'Centre-Val de Loire','46':'Occitanie','47':'Nouvelle-Aquitaine','48':'Occitanie',
  '49':'Pays de la Loire','50':'Normandie','51':'Grand Est','52':'Grand Est',
  '53':'Pays de la Loire','54':'Grand Est','55':'Grand Est','56':'Bretagne','57':'Grand Est',
  '58':'Bourgogne-Franche-Comté','59':'Hauts-de-France','60':'Hauts-de-France',
  '61':'Normandie','62':'Hauts-de-France','63':'Auvergne-Rhône-Alpes',
  '64':'Nouvelle-Aquitaine','65':'Occitanie','66':'Occitanie','67':'Grand Est','68':'Grand Est',
  '69':'Auvergne-Rhône-Alpes','70':'Bourgogne-Franche-Comté','71':'Bourgogne-Franche-Comté',
  '72':'Pays de la Loire','73':'Auvergne-Rhône-Alpes','74':'Auvergne-Rhône-Alpes',
  '75':'Île-de-France','76':'Normandie','77':'Île-de-France','78':'Île-de-France',
  '79':'Nouvelle-Aquitaine','80':'Hauts-de-France','81':'Occitanie','82':'Occitanie',
  '83':'PACA','84':'PACA','85':'Pays de la Loire','86':'Nouvelle-Aquitaine',
  '87':'Nouvelle-Aquitaine','88':'Grand Est','89':'Bourgogne-Franche-Comté',
  '90':'Bourgogne-Franche-Comté','91':'Île-de-France','92':'Île-de-France',
  '93':'Île-de-France','94':'Île-de-France','95':'Île-de-France',
  '971':'Outre-Mer','972':'Outre-Mer','973':'Outre-Mer','974':'Outre-Mer','976':'Outre-Mer'
};

const FACTORS = [
  { key: 'alpha1_sante_entreprises' as const, label: 'Entreprises', short: 'Entrep.', color: 'var(--success)', Icon: Factory },
  { key: 'alpha2_tension_emploi' as const, label: 'Emploi', short: 'Emploi', color: 'var(--chart-1)', Icon: Briefcase },
  { key: 'alpha3_dynamisme_immo' as const, label: 'Immobilier', short: 'Immo.', color: 'var(--chart-3)', Icon: Home },
  { key: 'alpha4_sante_financiere' as const, label: 'Finances', short: 'Fin.', color: 'var(--chart-5)', Icon: Coins },
  { key: 'alpha5_declin_ratio' as const, label: 'Ratio déclin', short: 'Déclin', color: 'var(--error)', Icon: BarChart3 },
  { key: 'alpha6_sentiment' as const, label: 'Sentiment', short: 'Sent.', color: 'var(--chart-2)', Icon: Newspaper },
];

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--success)';
  if (score >= 55) return 'var(--chart-4)';
  if (score >= 45) return 'var(--warning)';
  if (score >= 35) return 'var(--chart-5)';
  return 'var(--error)';
}

function scoreLabel(score: number): string {
  if (score >= 70) return 'Sain';
  if (score >= 55) return 'Correct';
  if (score >= 45) return 'Attention';
  if (score >= 35) return 'Vigilance';
  return 'Critique';
}

type SortField = 'score_composite' | 'alpha1_sante_entreprises' | 'alpha2_tension_emploi' |
  'alpha3_dynamisme_immo' | 'alpha4_sante_financiere' | 'alpha5_declin_ratio' |
  'alpha6_sentiment' | 'population' | 'code_dept' | 'microsignals';

// ─── Component ───────────────────────────────────────────────
export default function DepartmentsPage() {
  const router = useRouter();
  const [deptScores, setDeptScores] = useState<DeptScore[]>([]);
  const [microSignals, setMicroSignals] = useState<MicroSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('score_composite');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [regionFilter, setRegionFilter] = useState<string>('all');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [scoresRes, microRes] = await Promise.all([
          fetch('/api/v1/signals/departments/scores'),
          fetch('/api/v1/signals/microsignals'),
        ]);
        if (!scoresRes.ok) throw new Error(`Scores API: ${scoresRes.status}`);
        const scores: DeptScore[] = await scoresRes.json();
        const micros: MicroSignal[] = await microRes.json();
        setDeptScores(Array.isArray(scores) ? scores : []);
        setMicroSignals(Array.isArray(micros) ? micros : []);
      } catch (e) {
        console.error('Error fetching departments:', e);
        setError(e instanceof Error ? e.message : 'Erreur de chargement');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Microsignal count per dept
  const microByDept = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of microSignals) {
      map[m.territory_code] = (map[m.territory_code] || 0) + 1;
    }
    return map;
  }, [microSignals]);

  // Regions list
  const regions = useMemo(() => {
    const set = new Set(Object.values(DEPT_REGIONS));
    return ['all', ...Array.from(set).sort()];
  }, []);

  // Filter + sort
  const filtered = useMemo(() => {
    let list = [...deptScores];

    // Search
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(d =>
        d.code_dept.toLowerCase().includes(q) ||
        (DEPT_NAMES[d.code_dept] || '').toLowerCase().includes(q) ||
        (DEPT_REGIONS[d.code_dept] || '').toLowerCase().includes(q)
      );
    }

    // Region filter
    if (regionFilter !== 'all') {
      list = list.filter(d => DEPT_REGIONS[d.code_dept] === regionFilter);
    }

    // Sort
    list.sort((a, b) => {
      let va: number, vb: number;
      if (sortField === 'microsignals') {
        va = microByDept[a.code_dept] || 0;
        vb = microByDept[b.code_dept] || 0;
      } else if (sortField === 'code_dept') {
        return sortDir === 'asc'
          ? a.code_dept.localeCompare(b.code_dept)
          : b.code_dept.localeCompare(a.code_dept);
      } else {
        va = (a[sortField] as number) ?? 0;
        vb = (b[sortField] as number) ?? 0;
      }
      return sortDir === 'asc' ? va - vb : vb - va;
    });

    return list;
  }, [deptScores, search, sortField, sortDir, regionFilter, microByDept]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  // Stats
  const avgScore = deptScores.length > 0
    ? deptScores.reduce((s, d) => s + d.score_composite, 0) / deptScores.length
    : 0;
  const criticalCount = deptScores.filter(d => d.score_composite < 35).length;
  const alertDepts = Object.keys(microByDept).length;

  // Export
  const exportCSV = () => {
    const headers = ['Code','Département','Région','Score','Entreprises','Emploi','Immobilier','Finances','Ratio déclin','Sentiment','Population','Micro-signaux'];
    const rows = filtered.map(d => [
      d.code_dept, DEPT_NAMES[d.code_dept] || '', DEPT_REGIONS[d.code_dept] || '',
      d.score_composite.toFixed(1),
      (d.alpha1_sante_entreprises ?? 0).toFixed(1), (d.alpha2_tension_emploi ?? 0).toFixed(1),
      (d.alpha3_dynamisme_immo ?? 0).toFixed(1), (d.alpha4_sante_financiere ?? 0).toFixed(1),
      (d.alpha5_declin_ratio ?? 0).toFixed(1), (d.alpha6_sentiment ?? 0).toFixed(1),
      Math.round(d.population || 0).toString(), (microByDept[d.code_dept] || 0).toString()
    ]);
    const csv = [headers, ...rows].map(r => r.join(';')).join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'departements_tawiza.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 opacity-30" />;
    return sortDir === 'desc'
      ? <ArrowDown className="h-3 w-3 text-primary" />
      : <ArrowUp className="h-3 w-3 text-primary" />;
  };

  if (loading) {
    return (
      <DashboardLayout title="Départements" description="101 territoires français">
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <GlassCard key={i} className="h-16 animate-pulse bg-muted/10" />
          ))}
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout title="Départements" description="101 territoires français — Scores composites multi-facteurs">
      <div className="space-y-4">
        {/* Summary cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <MapPin className="h-5 w-5 text-primary" />
              <div>
                <p className="text-2xl font-bold text-primary">{deptScores.length}</p>
                <p className="text-xs text-muted-foreground">Départements scorés</p>
              </div>
            </div>
          </GlassCard>
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <BarChart3 className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-2xl font-bold" style={{ color: scoreColor(avgScore) }}>{avgScore.toFixed(1)}</p>
                <p className="text-xs text-muted-foreground">Score moyen</p>
              </div>
            </div>
          </GlassCard>
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <Zap className="h-5 w-5 text-red-500" />
              <div>
                <p className="text-2xl font-bold text-red-400">{alertDepts}</p>
                <p className="text-xs text-muted-foreground">Depts en alerte</p>
              </div>
            </div>
          </GlassCard>
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-2xl font-bold text-purple-400">
                  {(deptScores.reduce((s, d) => s + (d.population || 0), 0) / 1e6).toFixed(1)}M
                </p>
                <p className="text-xs text-muted-foreground">Population couverte</p>
              </div>
            </div>
          </GlassCard>
        </div>

        {/* Filters bar */}
        <GlassCard className="p-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Rechercher un département, code ou région..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-muted/30 border border-border rounded-lg text-sm focus:outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={regionFilter}
                onChange={(e) => setRegionFilter(e.target.value)}
                className="bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary"
              >
                <option value="all">Toutes les régions</option>
                {regions.filter(r => r !== 'all').map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <button
              onClick={exportCSV}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary/10 border border-primary/20 rounded-lg text-sm text-primary hover:bg-primary/20 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </button>
            <span className="text-xs text-muted-foreground">
              {filtered.length} résultat{filtered.length > 1 ? 's' : ''}
            </span>
          </div>
        </GlassCard>

        {/* Table */}
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-3 cursor-pointer hover:text-primary transition-colors" onClick={() => toggleSort('code_dept')}>
                    <div className="flex items-center gap-1"># <SortIcon field="code_dept" /></div>
                  </th>
                  <th className="text-left p-3">Département</th>
                  <th className="text-left p-3 hidden lg:table-cell">Région</th>
                  <th className="text-center p-3 cursor-pointer hover:text-primary transition-colors" onClick={() => toggleSort('score_composite')}>
                    <div className="flex items-center justify-center gap-1">Score <SortIcon field="score_composite" /></div>
                  </th>
                  {FACTORS.map(f => (
                    <th key={f.key} className="text-center p-3 cursor-pointer hover:text-primary transition-colors hidden xl:table-cell" onClick={() => toggleSort(f.key)}>
                      <div className="flex items-center justify-center gap-1" title={f.label}>
                        <f.Icon className="h-3.5 w-3.5" style={{ color: f.color }} />
                        <span className="hidden 2xl:inline text-[10px]">{f.short}</span>
                        <SortIcon field={f.key} />
                      </div>
                    </th>
                  ))}
                  <th className="text-center p-3 cursor-pointer hover:text-primary transition-colors" onClick={() => toggleSort('population')}>
                    <div className="flex items-center justify-center gap-1">Pop. <SortIcon field="population" /></div>
                  </th>
                  <th className="text-center p-3 cursor-pointer hover:text-primary transition-colors" onClick={() => toggleSort('microsignals')}>
                    <div className="flex items-center justify-center gap-1">
                      <Zap className="h-3.5 w-3.5 text-red-400" />
                      <SortIcon field="microsignals" />
                    </div>
                  </th>
                  <th className="p-3 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d, idx) => {
                  const nbMicro = microByDept[d.code_dept] || 0;
                  return (
                    <tr
                      key={d.code_dept}
                      onClick={() => router.push(`/dashboard/departments/${d.code_dept}`)}
                      className="border-b border-border hover:bg-primary/5 cursor-pointer transition-colors group"
                    >
                      <td className="p-3 font-mono text-xs text-muted-foreground">{d.code_dept}</td>
                      <td className="p-3">
                        <span className="font-medium text-foreground group-hover:text-primary transition-colors">
                          {DEPT_NAMES[d.code_dept] || d.code_dept}
                        </span>
                      </td>
                      <td className="p-3 text-xs text-muted-foreground hidden lg:table-cell">
                        {DEPT_REGIONS[d.code_dept] || '—'}
                      </td>
                      <td className="p-3 text-center">
                        <div className="inline-flex items-center gap-2">
                          <div className="w-12 h-2 bg-muted/40 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{ width: `${d.score_composite}%`, backgroundColor: scoreColor(d.score_composite) }}
                            />
                          </div>
                          <span className="font-bold text-xs min-w-[2.5rem] text-right" style={{ color: scoreColor(d.score_composite) }}>
                            {d.score_composite.toFixed(1)}
                          </span>
                        </div>
                      </td>
                      {FACTORS.map(f => {
                        const val = (d[f.key] as number) ?? 0;
                        return (
                          <td key={f.key} className="p-3 text-center hidden xl:table-cell">
                            <span className="text-xs font-mono" style={{
                              color: val >= 60 ? f.color : val >= 40 ? 'hsl(var(--muted-foreground))' : 'var(--error)',
                              opacity: val >= 60 ? 1 : 0.7
                            }}>
                              {val.toFixed(0)}
                            </span>
                          </td>
                        );
                      })}
                      <td className="p-3 text-center text-xs text-muted-foreground">
                        {d.population ? `${(d.population / 1000).toFixed(0)}k` : '—'}
                      </td>
                      <td className="p-3 text-center">
                        {nbMicro > 0 ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 text-[10px] font-bold">
                            <Zap className="h-2.5 w-2.5" />
                            {nbMicro}
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/30">—</span>
                        )}
                      </td>
                      <td className="p-3">
                        <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary transition-colors" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>
    </DashboardLayout>
  );
}
