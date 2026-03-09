// TAJINE Dashboard Components - Barrel Export

// Map Components
export { default as FranceMap } from './FranceMap';
export { default as FranceMapLeaflet } from './FranceMapLeaflet';

// Immersive Layout Components
export { default as ImmersiveLayout } from './ImmersiveLayout';
export { default as FloatingChat } from './FloatingChat';
export { default as DepartmentPanel } from './DepartmentPanel';
export { default as ChartsDrawer } from './ChartsDrawer';
export { default as SourcesIndicator } from './SourcesIndicator';

// Analysis Components
export { default as PPDSLProgress } from './PPDSLProgress';
export { default as ConversationHistory } from './ConversationHistory';

// Filters & Drawers
export { default as TerritorialFilters } from './TerritorialFilters';
export { default as IndicatorDrawer } from './IndicatorDrawer';

// Re-export types
export type { IndicatorType, INDICATORS } from './FranceMap';
export type { ExtendedIndicatorType } from './IndicatorDrawer';
export type { TerritorialFilterState } from './TerritorialFilters';
