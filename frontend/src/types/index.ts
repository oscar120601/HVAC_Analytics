export interface DataFrame {
  columns: string[];
  data: any[];
  rowCount: number;
}

export interface ProcessingStatus {
  isProcessing: boolean;
  progress: number;
  message: string;
}

export interface BatchConfig {
  resampleInterval: string;
  detectFrozen: boolean;
  applySteadyState: boolean;
  applyHeatBalance: boolean;
  applyAffinity: boolean;
  filterInvalid: boolean;
}

export interface ModelInfo {
  name: string;
  mape?: number;
  r2?: number;
  featureCount: number;
  trainingDate?: string;
}

export interface FeatureMapping {
  targetCol: string;
  chilledWaterSide: Record<string, string[]>;
  condenserWaterSide: Record<string, string[]>;
  coolingTowerSystem: Record<string, string[]>;
  environment: Record<string, string[]>;
  systemLevel: Record<string, string[]>;
}

export type BatchSubPage = 
  | 'batch_parse'
  | 'batch_clean'
  | 'batch_stats'
  | 'batch_timeseries'
  | 'batch_correlation'
  | 'batch_quality'
  | 'batch_export';

export type OptimizationSubPage =
  | 'opt_mapping'
  | 'opt_realtime'
  | 'opt_importance'
  | 'opt_history'
  | 'opt_training';

export type ProcessingMode = 'batch' | 'optimization';
