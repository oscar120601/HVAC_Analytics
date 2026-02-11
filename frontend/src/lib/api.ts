/**
 * API client for HVAC Analytics Backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch(path: string, options?: RequestInit): Promise<any> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health Check
  async healthCheck() {
    return this.fetch('/api/health');
  }

  // File Management
  async listFiles(dataDir: string = 'data/CGMH-TY') {
    return this.fetch(`/api/files?data_dir=${encodeURIComponent(dataDir)}`);
  }

  // Data Processing
  async parseFiles(files: string[], dataDir: string = 'data/CGMH-TY') {
    return this.fetch('/api/parse', {
      method: 'POST',
      body: JSON.stringify({ files, data_dir: dataDir }),
    });
  }

  async cleanData(config: {
    resample_interval?: string;
    detect_frozen?: boolean;
    apply_steady_state?: boolean;
    apply_heat_balance?: boolean;
    apply_affinity?: boolean;
    filter_invalid?: boolean;
  }) {
    return this.fetch('/api/clean', {
      method: 'POST',
      body: JSON.stringify({
        resample_interval: '5m',
        detect_frozen: true,
        apply_steady_state: false,
        apply_heat_balance: false,
        apply_affinity: false,
        filter_invalid: false,
        ...config,
      }),
    });
  }

  async getDataPreview(rows: number = 50) {
    return this.fetch(`/api/data/preview?rows=${rows}`);
  }

  async getColumnStats(column: string) {
    return this.fetch(`/api/data/stats?column=${encodeURIComponent(column)}`);
  }

  // Model Management
  async listModels() {
    return this.fetch('/api/models');
  }

  async trainModel(modelName: string, featureMapping: Record<string, any>) {
    return this.fetch('/api/models/train', {
      method: 'POST',
      body: JSON.stringify({
        model_name: modelName,
        feature_mapping: featureMapping,
      }),
    });
  }

  // Optimization
  async optimize(modelName: string, inputData: Record<string, number>) {
    return this.fetch('/api/optimize', {
      method: 'POST',
      body: JSON.stringify({
        model_name: modelName,
        input_data: inputData,
      }),
    });
  }
}

export const api = new ApiClient();
export default api;
