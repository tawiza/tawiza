// Hooks barrel export

// Territorial data hooks
export {
  useDepartmentDetails,
  useDepartmentStats,
  useAlerts,
  useTrends,
  useHealthScores,
  useCompareDepartments,
  useIndicator,
  useFilterOptions,
  useAnalyticsHistory,
} from './use-territorial-data';

export type {
  DepartmentStats,
  DepartmentDetail,
  Alert,
  TrendData,
  Trends,
  HealthScore,
  DepartmentComparison,
  FilterOptions,
  IndicatorData,
  AnalysisRecord,
} from './use-territorial-data';

// Sources health hooks
export {
  useSourcesHealth,
  useAdaptersList,
  useAdapterCategories,
  getStatusColor,
  getStatusIcon,
  getCategoryLabel,
  getCategoryIcon,
  calculateHealthPercentage,
} from './use-sources-health';

export type {
  AdapterHealth,
  SourcesHealthResponse,
  AdapterInfo,
  AdaptersListResponse,
  CategoryInfo,
} from './use-sources-health';

// Existing hooks
export { useTAJINEWebSocket } from './use-tajine-websocket';

// Relations hooks
export { useRelations } from './use-relations';

// Relations types re-export
export type {
  ActorType,
  RelationType,
  GraphNode,
  GraphLink,
  RelationGraphData,
  CoverageScore,
  GapItem,
  GapsReport,
  DiscoverResult,
} from '@/types/relations';

export {
  ACTOR_COLORS,
  ACTOR_SHAPES,
  RELATION_STYLES,
} from '@/types/relations';
