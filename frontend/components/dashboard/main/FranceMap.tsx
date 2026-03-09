'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip as LTooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import {
  Factory, Briefcase, Home, Coins, BarChart3, Newspaper,
  AlertTriangle, Flame, Zap, TrendingDown, TrendingUp,
  MapPin, Radio, X, Activity, Shield
} from 'lucide-react';

// Fix for default markers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

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

interface HeatmapDept {
  code: string;
  total_signals: number;
  sources: Record<string, number>;
  anomalies: number;
  latest_signal: string;
}

interface MicroSignal {
  id: number;
  territory_code: string;
  signal_type: string;
  dimensions: string[];
  score: number;
  description: string;
}

interface DeptFullData {
  score: DeptScore | null;
  heatmap: HeatmapDept | null;
  microsignals: MicroSignal[];
}

// ─── Department centroids ────────────────────────────────────
const DEPT_CENTROIDS: Record<string, [number, number]> = {
  '01':[46.2,5.3],'02':[49.5,3.6],'03':[46.3,3.2],'04':[44.1,6.2],'05':[44.7,6.3],
  '06':[43.9,7.2],'07':[44.7,4.6],'08':[49.6,4.6],'09':[42.9,1.5],'10':[48.3,4.1],
  '11':[43.1,2.4],'12':[44.3,2.6],'13':[43.5,5.1],'14':[49.1,-0.4],'15':[45.0,2.7],
  '16':[45.7,0.2],'17':[45.8,-0.8],'18':[47.0,2.5],'19':[45.3,1.8],'2A':[41.9,9.0],
  '2B':[42.4,9.2],'21':[47.3,4.8],'22':[48.4,-3.0],'23':[46.1,2.0],'24':[45.1,0.7],
  '25':[47.2,6.4],'26':[44.7,5.2],'27':[49.1,1.2],'28':[48.3,1.3],'29':[48.4,-4.2],
  '30':[43.9,4.2],'31':[43.4,1.2],'32':[43.7,0.6],'33':[44.8,-0.6],'34':[43.6,3.5],
  '35':[48.1,-1.7],'36':[46.8,1.6],'37':[47.3,0.7],'38':[45.3,5.6],'39':[46.7,5.7],
  '40':[43.9,-0.8],'41':[47.6,1.3],'42':[45.7,4.2],'43':[45.1,3.7],'44':[47.3,-1.6],
  '45':[47.9,2.2],'46':[44.6,1.6],'47':[44.3,0.5],'48':[44.5,3.5],'49':[47.4,-0.6],
  '50':[48.9,-1.3],'51':[48.9,3.9],'52':[48.1,5.3],'53':[48.1,-0.8],'54':[48.7,6.2],
  '55':[49.0,5.4],'56':[47.8,-2.8],'57':[49.0,6.6],'58':[47.1,3.5],'59':[50.4,3.2],
  '60':[49.4,2.4],'61':[48.6,0.1],'62':[50.5,2.3],'63':[45.7,3.1],'64':[43.3,-0.8],
  '65':[43.1,0.1],'66':[42.6,2.5],'67':[48.6,7.5],'68':[47.9,7.2],'69':[45.8,4.6],
  '70':[47.6,6.2],'71':[46.6,4.4],'72':[47.9,0.2],'73':[45.5,6.4],'74':[46.0,6.3],
  '75':[48.86,2.35],'76':[49.6,1.1],'77':[48.6,2.9],'78':[48.8,1.9],'79':[46.5,-0.3],
  '80':[49.9,2.3],'81':[43.8,2.1],'82':[44.0,1.3],'83':[43.5,6.2],'84':[44.0,5.1],
  '85':[46.7,-1.3],'86':[46.6,0.5],'87':[45.9,1.2],'88':[48.2,6.4],'89':[47.8,3.6],
  '90':[47.6,6.9],'91':[48.5,2.2],'92':[48.8,2.2],'93':[48.9,2.5],'94':[48.8,2.5],
  '95':[49.1,2.2],'971':[16.2,-61.6],'972':[14.6,-61.0],'973':[4.0,-53.0],'974':[-21.1,55.5],
  '976':[-12.8,45.2]
};

const DEPT_NAMES: Record<string, string> = {
  '01':'Ain','02':'Aisne','03':'Allier','04':'Alpes-de-Hte-Prov.','05':'Hautes-Alpes',
  '06':'Alpes-Maritimes','07':'Ardèche','08':'Ardennes','09':'Ariège','10':'Aube',
  '11':'Aude','12':'Aveyron','13':'Bouches-du-Rhône','14':'Calvados','15':'Cantal',
  '16':'Charente','17':'Charente-Maritime','18':'Cher','19':'Corrèze','2A':'Corse-du-Sud',
  '2B':'Haute-Corse','21':"Côte-d'Or",'22':"Côtes-d'Armor",'23':'Creuse','24':'Dordogne',
  '25':'Doubs','26':'Drôme','27':'Eure','28':'Eure-et-Loir','29':'Finistère',
  '30':'Gard','31':'Haute-Garonne','32':'Gers','33':'Gironde','34':'Hérault',
  '35':'Ille-et-Vilaine','36':'Indre','37':'Indre-et-Loire','38':'Isère','39':'Jura',
  '40':'Landes','41':'Loir-et-Cher','42':'Loire','43':'Haute-Loire','44':'Loire-Atlantique',
  '45':'Loiret','46':'Lot','47':'Lot-et-Garonne','48':'Lozère','49':'Maine-et-Loire',
  '50':'Manche','51':'Marne','52':'Haute-Marne','53':'Mayenne','54':'Meurthe-et-Moselle',
  '55':'Meuse','56':'Morbihan','57':'Moselle','58':'Nièvre','59':'Nord',
  '60':'Oise','61':'Orne','62':'Pas-de-Calais','63':'Puy-de-Dôme','64':'Pyrénées-Atl.',
  '65':'Hautes-Pyrénées','66':'Pyrénées-Or.','67':'Bas-Rhin','68':'Haut-Rhin','69':'Rhône',
  '70':'Haute-Saône','71':'Saône-et-Loire','72':'Sarthe','73':'Savoie','74':'Haute-Savoie',
  '75':'Paris','76':'Seine-Maritime','77':'Seine-et-Marne','78':'Yvelines','79':'Deux-Sèvres',
  '80':'Somme','81':'Tarn','82':'Tarn-et-Garonne','83':'Var','84':'Vaucluse',
  '85':'Vendée','86':'Vienne','87':'Haute-Vienne','88':'Vosges','89':'Yonne',
  '90':'Belfort','91':'Essonne','92':'Hauts-de-Seine','93':'Seine-Saint-Denis','94':'Val-de-Marne',
  '95':"Val-d'Oise",'971':'Guadeloupe','972':'Martinique','973':'Guyane','974':'Réunion',
  '976':'Mayotte'
};

// ─── Color scales ────────────────────────────────────────────
function scoreToColor(score: number): string {
  if (score >= 70) return 'var(--success)';
  if (score >= 55) return 'var(--success)';
  if (score >= 45) return 'var(--warning)';
  if (score >= 35) return 'var(--chart-5)';
  if (score > 0)   return 'var(--error)';
  return 'hsl(var(--muted))';
}

function scoreToFillOpacity(score: number): number {
  if (score <= 0) return 0.15;
  return 0.3 + (score / 100) * 0.5;
}

// ─── Inline SVG icons (for Leaflet HTML tooltips) ────────────
// Small 12x12 SVG strings that replace emojis in raw HTML tooltips
const SVG = {
  factory: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1"/><path d="M12 18h1"/><path d="M7 18h1"/></svg>`,
  briefcase: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--chart-1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg>`,
  home: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--chart-3)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  coins: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/></svg>`,
  chart: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/></svg>`,
  newspaper: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--chart-5)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>`,
  signal: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground))" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/></svg>`,
  radio: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground))" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M4.93 19.07a10 10 0 0 1 0-14.14"/><path d="M7.76 16.24a6 6 0 0 1 0-8.48"/><path d="M16.24 7.76a6 6 0 0 1 0 8.48"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`,
  zap: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>`,
  alertTriangle: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  flame: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--chart-5)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
  trendDown: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>`,
  trendUp: `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
};

// Map signal type to SVG icon
const TYPE_SVG: Record<string, string> = {
  anomaly: SVG.alertTriangle,
  convergence: SVG.flame,
  alert: SVG.zap,
  trend_degradation: SVG.trendDown,
  trend_amelioration: SVG.trendUp,
};

// ─── Mini bar for tooltip ────────────────────────────────────
function miniBar(label: string, icon: string, value: number, color: string): string {
  const pct = Math.min(100, Math.max(0, value));
  return `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
    <span style="display:inline-flex;flex-shrink:0">${icon}</span>
    <span style="font-size:10px;color:hsl(var(--muted-foreground));min-width:55px">${label}</span>
    <div style="flex:1;height:5px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:${color};border-radius:3px"></div>
    </div>
    <span style="font-size:10px;color:${color};font-weight:600;min-width:22px;text-align:right">${value.toFixed(0)}</span>
  </div>`;
}

// ─── Component ───────────────────────────────────────────────
export default function FranceMap() {
  const [geoData, setGeoData] = useState<any>(null);
  const [deptData, setDeptData] = useState<Record<string, DeptFullData>>({});
  const [loading, setLoading] = useState(true);
  const [selectedDept, setSelectedDept] = useState<string | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const selectedDeptRef = useRef<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [geoRes, heatmapRes, scoresRes, microRes] = await Promise.all([
          fetch('/data/france-departments.json'),
          fetch('/api/collector/departments/heatmap'),
          fetch('/api/v1/signals/departments/scores'),
          fetch('/api/v1/signals/microsignals'),
        ]);

        const geoJson = await geoRes.json();
        const heatmapJson = await heatmapRes.json();
        const scoresJson: DeptScore[] = await scoresRes.json();
        const microJson: MicroSignal[] = await microRes.json();

        const data: Record<string, DeptFullData> = {};
        for (const s of (Array.isArray(scoresJson) ? scoresJson : [])) {
          data[s.code_dept] = { score: s, heatmap: null, microsignals: [] };
        }
        for (const h of (heatmapJson?.departments || [])) {
          if (!data[h.code]) data[h.code] = { score: null, heatmap: null, microsignals: [] };
          data[h.code].heatmap = h;
        }
        for (const m of (Array.isArray(microJson) ? microJson : [])) {
          if (!data[m.territory_code]) data[m.territory_code] = { score: null, heatmap: null, microsignals: [] };
          data[m.territory_code].microsignals.push(m);
        }

        setGeoData(geoJson);
        setDeptData(data);
      } catch (error) {
        console.error('Error fetching map data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const onEachFeature = useCallback((feature: any, layer: L.Layer) => {
    const code = feature.properties.code;
    const name = feature.properties.nom;
    const d = deptData[code];
    const score = d?.score?.score_composite ?? 0;
    const signals = d?.heatmap?.total_signals ?? 0;
    const sources = d?.heatmap?.sources || {};
    const nbSources = Object.keys(sources).length;
    const nbMicro = d?.microsignals?.length ?? 0;
    const pop = d?.score?.population;

    if (layer instanceof L.Path) {
      layer.setStyle({
        fillColor: scoreToColor(score),
        weight: 1,
        opacity: 0.9,
        color: 'hsl(var(--card))',
        fillOpacity: scoreToFillOpacity(score),
      });
    }

    // ─── Rich tooltip with SVG icons ─────────────────────
    const sourcesHtml = Object.entries(sources)
      .sort(([,a], [,b]) => (b as number) - (a as number))
      .slice(0, 4)
      .map(([src, count]) => `<span style="color:var(--warning)">${(src as string).replace('_',' ')}</span>: ${count}`)
      .join(' · ');

    const factorsHtml = d?.score ? [
      miniBar('Entreprises', SVG.factory, d.score.alpha1_sante_entreprises ?? 0, 'var(--success)'),
      miniBar('Emploi', SVG.briefcase, d.score.alpha2_tension_emploi ?? 0, 'var(--chart-1)'),
      miniBar('Immobilier', SVG.home, d.score.alpha3_dynamisme_immo ?? 0, 'var(--chart-3)'),
      miniBar('Finances', SVG.coins, d.score.alpha4_sante_financiere ?? 0, 'var(--warning)'),
      miniBar('Ratio déclin', SVG.chart, d.score.alpha5_declin_ratio ?? 0, 'var(--error)'),
      miniBar('Sentiment', SVG.newspaper, d.score.alpha6_sentiment ?? 0, 'var(--chart-5)'),
    ].join('') : '<div style="font-size:10px;color:hsl(var(--muted-foreground))">Score non calculé</div>';

    const microHtml = d?.microsignals?.length
      ? d.microsignals.slice(0, 3).map(m => {
          const icon = TYPE_SVG[m.signal_type] || SVG.alertTriangle;
          return `<div style="font-size:10px;padding:3px 0;border-top:1px solid rgba(255,255,255,0.05);display:flex;align-items:flex-start;gap:4px">
            <span style="flex-shrink:0;margin-top:1px">${icon}</span>
            <span>
              <span style="color:${m.score >= 0.8 ? 'var(--error)' : 'var(--warning)'};font-weight:600">${(m.score*100).toFixed(0)}%</span>
              <span style="color:hsl(var(--foreground))"> ${(m.description || '').replace(/^[^\w]*\d+:\s*/i, '').substring(0, 55)}</span>
            </span>
          </div>`;
        }).join('')
      : '';

    const tooltipContent = `
      <div style="min-width:240px;max-width:320px;font-family:system-ui,-apple-system,sans-serif">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <div>
            <strong style="font-size:13px;color:hsl(var(--foreground))">${name.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</strong>
            <span style="font-size:11px;color:hsl(var(--muted-foreground));margin-left:4px">(${code})</span>
          </div>
          ${score > 0 ? `<span style="font-size:18px;font-weight:800;color:${scoreToColor(score)}">${score.toFixed(1)}</span>` : ''}
        </div>

        ${pop ? `<div style="font-size:10px;color:hsl(var(--muted-foreground));margin-bottom:6px">${Math.round(pop).toLocaleString('fr-FR')} habitants</div>` : ''}

        <div style="margin-bottom:6px">${factorsHtml}</div>

        <div style="display:flex;gap:10px;font-size:11px;color:hsl(var(--foreground));padding:5px 0;border-top:1px solid rgba(255,255,255,0.1);align-items:center">
          <span style="display:inline-flex;align-items:center;gap:3px">${SVG.signal} ${signals.toLocaleString('fr-FR')} signaux</span>
          <span style="display:inline-flex;align-items:center;gap:3px">${SVG.radio} ${nbSources} sources</span>
          ${nbMicro > 0 ? `<span style="display:inline-flex;align-items:center;gap:3px;color:var(--error)">${SVG.zap} ${nbMicro} alertes</span>` : ''}
        </div>

        ${sourcesHtml ? `<div style="font-size:10px;color:hsl(var(--muted-foreground));margin-top:2px">${sourcesHtml}</div>` : ''}
        ${microHtml ? `<div style="margin-top:4px">${microHtml}</div>` : ''}
      </div>
    `;

    layer.bindTooltip(tooltipContent, {
      permanent: false,
      sticky: true,
      className: 'rich-tooltip',
      direction: 'auto',
    });

    layer.on('mouseover', (e) => {
      e.target.setStyle({ weight: 2.5, color: 'var(--warning)', fillOpacity: Math.min(0.85, scoreToFillOpacity(score) + 0.15) });
      e.target.bringToFront();
    });
    layer.on('mouseout', (e) => {
      e.target.setStyle({ weight: 1, color: 'hsl(var(--card))', fillOpacity: scoreToFillOpacity(score) });
    });
    layer.on('click', () => {
      setSelectedDept(prev => prev === code ? null : code);
    });
  }, [deptData]);

  const microDepts = Object.entries(deptData)
    .filter(([code, d]) => d.microsignals.length > 0 && DEPT_CENTROIDS[code])
    .map(([code, d]) => ({
      code,
      position: DEPT_CENTROIDS[code],
      count: d.microsignals.length,
      maxScore: Math.max(...d.microsignals.map(m => m.score)),
    }));

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-black/20 rounded-lg">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
          <p className="text-sm text-muted-foreground">Chargement de la carte...</p>
        </div>
      </div>
    );
  }

  if (!geoData) {
    return (
      <div className="h-full flex items-center justify-center bg-black/20 rounded-lg">
        <p className="text-sm text-muted-foreground">Erreur de chargement des données</p>
      </div>
    );
  }

  selectedDeptRef.current = selectedDept;
  const selData = selectedDept ? deptData[selectedDept] : null;

  // Factor config for the detail panel (Lucide icons)
  const FACTORS = [
    { label: 'Entreprises', key: 'alpha1_sante_entreprises' as const, color: 'var(--success)', Icon: Factory },
    { label: 'Emploi', key: 'alpha2_tension_emploi' as const, color: 'var(--chart-1)', Icon: Briefcase },
    { label: 'Immobilier', key: 'alpha3_dynamisme_immo' as const, color: 'var(--chart-3)', Icon: Home },
    { label: 'Finances', key: 'alpha4_sante_financiere' as const, color: 'var(--warning)', Icon: Coins },
    { label: 'Ratio déclin', key: 'alpha5_declin_ratio' as const, color: 'var(--error)', Icon: BarChart3 },
    { label: 'Sentiment', key: 'alpha6_sentiment' as const, color: 'var(--chart-5)', Icon: Newspaper },
  ];

  const TYPE_LUCIDE: Record<string, typeof AlertTriangle> = {
    anomaly: AlertTriangle,
    convergence: Flame,
    alert: Zap,
    trend_degradation: TrendingDown,
    trend_amelioration: TrendingUp,
  };

  return (
    <div className="h-full w-full rounded-lg overflow-hidden relative">
      <MapContainer
        center={[46.603354, 1.888334]}
        zoom={6}
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
        scrollWheelZoom={true}
        ref={mapRef}
      >
        <TileLayer
          attribution='&copy; OSM'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <GeoJSON key={JSON.stringify(Object.keys(deptData).length)} data={geoData} onEachFeature={onEachFeature} />

        {microDepts.map(({ code, position, count, maxScore }) => (
          <CircleMarker
            key={code}
            center={position}
            radius={4 + count * 2}
            pathOptions={{
              color: maxScore >= 0.8 ? 'var(--error)' : 'var(--warning)',
              fillColor: maxScore >= 0.8 ? 'var(--error)' : 'var(--warning)',
              fillOpacity: 0.6,
              weight: 2,
              className: 'pulse-marker'
            }}
          >
            <LTooltip direction="top" offset={[0, -8]} className="rich-tooltip">
              <div className="flex items-center gap-1.5 text-[11px]">
                <Zap className="h-3 w-3 text-red-400" />
                <strong>{DEPT_NAMES[code] || code}</strong>
                <span className="text-muted-foreground">: {count} micro-signal{count > 1 ? 'x' : ''}</span>
              </div>
            </LTooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Detail panel */}
      {selData && selectedDept && (
        <div className="absolute top-3 left-3 z-[1000] bg-zinc-900 rounded-xl p-4 text-white text-xs w-64 border border-primary/20 shadow-2xl">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-bold text-sm text-primary">{DEPT_NAMES[selectedDept] || selectedDept}</h3>
              <span className="text-[10px] text-gray-500">Département {selectedDept}</span>
            </div>
            <button onClick={() => setSelectedDept(null)} className="p-1 rounded-md hover:bg-white/10 transition-colors">
              <X className="h-3.5 w-3.5 text-gray-400" />
            </button>
          </div>

          {selData.score && (
            <>
              <div className="text-center mb-3">
                <span className="text-3xl font-bold" style={{ color: scoreToColor(selData.score.score_composite) }}>
                  {selData.score.score_composite.toFixed(1)}
                </span>
                <span className="text-gray-500 text-sm">/100</span>
              </div>

              <div className="space-y-2 mb-3">
                {FACTORS.map(({ label, key, color, Icon }) => {
                  const val = selData.score?.[key] ?? 0;
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <Icon className="h-3 w-3 flex-shrink-0" style={{ color }} />
                      <span className="w-[70px] text-gray-400 text-[10px]">{label}</span>
                      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${val}%`, backgroundColor: color }}
                        />
                      </div>
                      <span className="w-7 text-right font-mono text-[10px]" style={{ color }}>
                        {val.toFixed(0)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {selData.heatmap && (
            <div className="flex items-center gap-3 border-t border-border pt-2 mb-2 text-[10px]">
              <span className="flex items-center gap-1 text-gray-400">
                <Activity className="h-3 w-3" />
                {selData.heatmap.total_signals.toLocaleString('fr-FR')} signaux
              </span>
              <span className="flex items-center gap-1 text-gray-500">
                <Radio className="h-3 w-3" />
                {Object.keys(selData.heatmap.sources).length} sources
              </span>
            </div>
          )}

          {selData.microsignals.length > 0 && (
            <div className="border-t border-border pt-2 space-y-1.5">
              <div className="flex items-center gap-1.5 text-red-400 font-medium text-[11px]">
                <Zap className="h-3 w-3" />
                {selData.microsignals.length} micro-signal{selData.microsignals.length > 1 ? 'x' : ''}
              </div>
              {selData.microsignals.slice(0, 4).map((m, i) => {
                const TypeIcon = TYPE_LUCIDE[m.signal_type] || AlertTriangle;
                return (
                  <div key={i} className="text-[10px] text-gray-300 pl-2 border-l-2 flex items-start gap-1.5" style={{
                    borderColor: m.score >= 0.8 ? 'var(--error)' : 'var(--warning)'
                  }}>
                    <TypeIcon className="h-3 w-3 flex-shrink-0 mt-0.5" style={{
                      color: m.score >= 0.8 ? 'var(--error)' : 'var(--warning)'
                    }} />
                    <span>
                      {(m.description || '').replace(/^[^\w]*\d+:\s*/i, '').substring(0, 75)}
                      <span className="text-gray-500 ml-1">({(m.score * 100).toFixed(0)}%)</span>
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 right-3 z-[1000] bg-zinc-900 rounded-lg p-3 text-white text-[10px] border border-border">
        <div className="mb-2 font-semibold text-primary text-xs flex items-center gap-1.5">
          <Shield className="h-3 w-3" />
          Score Composite
        </div>
        <div className="space-y-0.5">
          {[
            { color: 'var(--success)', label: '≥ 70 — sain' },
            { color: 'var(--success)', label: '55-70 — correct' },
            { color: 'var(--warning)', label: '45-55 — attention' },
            { color: 'var(--chart-5)', label: '35-45 — vigilance' },
            { color: 'var(--error)', label: '< 35 — critique' },
          ].map(({ color, label }) => (
            <div key={color} className="flex items-center gap-1.5">
              <div className="w-3 h-2 rounded-sm" style={{ backgroundColor: color }} />
              <span>{label}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 border-t border-border flex items-center gap-1.5">
          <Zap className="h-3 w-3 text-red-500 animate-pulse" />
          <span>Micro-signal actif</span>
        </div>
      </div>

      {/* Stats badge */}
      <div className="absolute top-3 right-3 z-[1000] bg-zinc-900 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 border border-border flex items-center gap-2">
        <MapPin className="h-3 w-3 text-primary" />
        {Object.keys(deptData).length} départements · {microDepts.length} en alerte
      </div>

      <style jsx global>{`
        .rich-tooltip {
          background: rgba(0, 0, 0, 0.92) !important;
          border: 1px solid rgba(245, 158, 11, 0.3) !important;
          border-radius: 10px !important;
          color: white !important;
          font-size: 11px !important;
          padding: 8px 12px !important;
          box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
          max-width: 340px !important;
        }
        .rich-tooltip .leaflet-tooltip-content {
          margin: 0 !important;
        }
        .pulse-marker {
          animation: pulse-ring 2s ease-out infinite;
        }
        @keyframes pulse-ring {
          0% { opacity: 0.8; }
          50% { opacity: 0.4; }
          100% { opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}
