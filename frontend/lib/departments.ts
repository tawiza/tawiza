/**
 * Shared constants and types for territorial/department features.
 * Single source of truth — do NOT duplicate these in individual components.
 */

import {
  Factory, Briefcase, Home, Coins, BarChart3, Newspaper,
  AlertTriangle, Flame, Zap, TrendingDown, TrendingUp,
} from 'lucide-react';

// ─── Types ───────────────────────────────────────────────────

export interface DeptScore {
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

export interface MicroSignal {
  id: number;
  territory_code: string;
  signal_type: string;
  sources?: string[];
  dimensions: string[];
  score: number;
  confidence?: number;
  impact?: number;
  novelty?: number;
  description: string;
  detected_at?: string;
}

export interface Convergence {
  territory_code: string;
  score: number;
  dimensions: string[];
  sources: string[];
  description: string;
  detected_at: string;
}

export interface HeatmapDept {
  code: string;
  total_signals: number;
  sources: Record<string, number>;
  anomalies: number;
  latest_signal: string;
}

// ─── Alpha factor definitions ────────────────────────────────

export const FACTORS = [
  { key: 'alpha1_sante_entreprises' as const, label: 'Entreprises', short: 'Entrep.', color: '#22C55E', Icon: Factory },
  { key: 'alpha2_tension_emploi' as const, label: 'Emploi', short: 'Emploi', color: '#3B82F6', Icon: Briefcase },
  { key: 'alpha3_dynamisme_immo' as const, label: 'Immobilier', short: 'Immo.', color: '#A855F7', Icon: Home },
  { key: 'alpha4_sante_financiere' as const, label: 'Finances', short: 'Fin.', color: '#F59E0B', Icon: Coins },
  { key: 'alpha5_declin_ratio' as const, label: 'Ratio déclin', short: 'Déclin', color: '#EF4444', Icon: BarChart3 },
  { key: 'alpha6_sentiment' as const, label: 'Sentiment', short: 'Sent.', color: '#EC4899', Icon: Newspaper },
] as const;

export type AlphaKey = typeof FACTORS[number]['key'];

// ─── Signal type → icon mapping ──────────────────────────────

export const SIGNAL_TYPE_ICONS: Record<string, typeof AlertTriangle> = {
  anomaly: AlertTriangle,
  convergence: Flame,
  alert: Zap,
  trend_degradation: TrendingDown,
  trend_amelioration: TrendingUp,
};

// ─── Score utilities ─────────────────────────────────────────

export function scoreColor(score: number): string {
  if (score >= 70) return '#22C55E';
  if (score >= 55) return '#84CC16';
  if (score >= 45) return '#EAB308';
  if (score >= 35) return '#F97316';
  return '#EF4444';
}

export function scoreLabel(score: number): string {
  if (score >= 70) return 'Sain';
  if (score >= 55) return 'Correct';
  if (score >= 45) return 'Attention';
  if (score >= 35) return 'Vigilance';
  return 'Critique';
}

export function scoreFillOpacity(score: number): number {
  if (score <= 0) return 0.15;
  return 0.3 + (score / 100) * 0.5;
}

// ─── HTML escaping for Leaflet tooltips ──────────────────────

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ─── Department names (101 + DOM-TOM) ────────────────────────

export const DEPT_NAMES: Record<string, string> = {
  '01':'Ain','02':'Aisne','03':'Allier','04':'Alpes-de-Haute-Provence','05':'Hautes-Alpes',
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
  '60':'Oise','61':'Orne','62':'Pas-de-Calais','63':'Puy-de-Dôme','64':'Pyrénées-Atlantiques',
  '65':'Hautes-Pyrénées','66':'Pyrénées-Orientales','67':'Bas-Rhin','68':'Haut-Rhin','69':'Rhône',
  '70':'Haute-Saône','71':'Saône-et-Loire','72':'Sarthe','73':'Savoie','74':'Haute-Savoie',
  '75':'Paris','76':'Seine-Maritime','77':'Seine-et-Marne','78':'Yvelines','79':'Deux-Sèvres',
  '80':'Somme','81':'Tarn','82':'Tarn-et-Garonne','83':'Var','84':'Vaucluse',
  '85':'Vendée','86':'Vienne','87':'Haute-Vienne','88':'Vosges','89':'Yonne',
  '90':'Territoire de Belfort','91':'Essonne','92':'Hauts-de-Seine','93':'Seine-Saint-Denis',
  '94':'Val-de-Marne','95':"Val-d'Oise",
  '971':'Guadeloupe','972':'Martinique','973':'Guyane','974':'La Réunion','976':'Mayotte',
};

// Short names for map labels
export const DEPT_NAMES_SHORT: Record<string, string> = {
  ...DEPT_NAMES,
  '04':'Alpes-de-Hte-Prov.','64':'Pyrénées-Atl.','66':'Pyrénées-Or.',
  '90':'Belfort','974':'Réunion',
};

// ─── Department → region mapping ─────────────────────────────

export const DEPT_REGIONS: Record<string, string> = {
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
  '971':'Outre-Mer','972':'Outre-Mer','973':'Outre-Mer','974':'Outre-Mer','976':'Outre-Mer',
};

// ─── Department centroids (for map markers) ──────────────────

export const DEPT_CENTROIDS: Record<string, [number, number]> = {
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
  '976':[-12.8,45.2],
};
