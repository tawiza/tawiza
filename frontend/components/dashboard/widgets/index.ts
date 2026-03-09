/**
 * Dashboard Widgets for Territorial Intelligence
 *
 * These widgets connect to the /api/v1/territorial/* endpoints
 * and display real-time data from multiple French data sources:
 * - SIRENE (enterprises)
 * - DVF (real estate)
 * - OFGL (local finances)
 * - France Travail (employment)
 * - INSEE (demographics)
 */

export { AlertsWidget, default as AlertsWidgetDefault } from './AlertsWidget';
export {
  ComparatorWidget,
  default as ComparatorWidgetDefault,
} from './ComparatorWidget';
export { TrendsWidget, default as TrendsWidgetDefault } from './TrendsWidget';
export {
  HealthScoreWidget,
  default as HealthScoreWidgetDefault,
} from './HealthScoreWidget';
export {
  TerritorialAnalyzerWidget,
  default as TerritorialAnalyzerWidgetDefault,
} from './TerritorialAnalyzerWidget';
export {
  default as TerritorialComparison,
} from './TerritorialComparison';
export {
  MicroSignalsSummaryWidget,
  RecentSignalsWidget,
} from './micro-signals';
export { SignalsTimelineChart } from './SignalsTimelineChart';
export { DepartmentBarChart } from './DepartmentBarChart';
export { AnomaliesWidget } from './AnomaliesWidget';
export { TerritorialRankingWidget } from './TerritorialRankingWidget';
export { SourcesOverviewWidget } from './SourcesOverviewWidget';
export { GoogleTrendsWidget } from './GoogleTrendsWidget';
