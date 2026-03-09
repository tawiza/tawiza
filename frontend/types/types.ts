import { ComponentType } from 'react';

// TAJINE Cognitive Levels
export type TAJINELevel =
  | 'reactive'
  | 'analytical'
  | 'strategic'
  | 'prospective'
  | 'theoretical';

// Chat message types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  level?: TAJINELevel;
}

// TAJINE analysis response
export interface TAJINEResponse {
  content: string;
  sources?: string[];
  confidence?: number;
  cognitiveLevel?: TAJINELevel;
}

// Route configuration
export interface IRoute {
  path: string;
  name: string;
  layout?: string;
  exact?: boolean;
  component?: ComponentType;
  disabled?: boolean;
  icon?: JSX.Element;
  secondary?: boolean;
  collapse?: boolean;
  items?: IRoute[];
  rightElement?: boolean;
  invisible?: boolean;
}

// Department data
export interface Department {
  code: string;
  name: string;
  region: string;
  population?: number;
  enterprises?: number;
  growthRate?: number;
}

// Data source configuration
export interface DataSource {
  id: string;
  name: string;
  type: 'api' | 'database' | 'file';
  status: 'active' | 'inactive' | 'error';
  lastSync?: Date;
}

// Analysis result
export interface AnalysisResult {
  id: string;
  query: string;
  level: TAJINELevel;
  result: string;
  sources: string[];
  createdAt: Date;
}
