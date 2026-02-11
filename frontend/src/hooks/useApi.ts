import { useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApi<T>() {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(async (apiCall: () => Promise<T>) => {
    setState({ data: null, loading: true, error: null });
    try {
      const data = await apiCall();
      setState({ data, loading: false, error: null });
      return data;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Unknown error';
      setState({ data: null, loading: false, error });
      throw err;
    }
  }, []);

  return { ...state, execute };
}

// Specific hooks for common operations
export function useListFiles() {
  const { data, loading, error, execute } = useApi<{ 
    files: string[]; 
    folders: string[];
    folder_counts: Record<string, number>;
    total_files: number;
    count: number;
    current_folder?: string;
  }>();
  
  const listFiles = useCallback(async (dataDir?: string, subfolder?: string) => {
    return execute(() => api.listFiles(dataDir, subfolder));
  }, [execute]);

  return { 
    files: data?.files || [], 
    folders: data?.folders || [],
    folderCounts: data?.folder_counts || {},
    totalFiles: data?.total_files || 0,
    count: data?.count || 0,
    currentFolder: data?.current_folder,
    loading, 
    error, 
    listFiles 
  };
}

export function useParseFiles() {
  const { data, loading, error, execute } = useApi<any>();
  
  const parseFiles = useCallback(async (files: string[], dataDir?: string, subfolder?: string) => {
    return execute(() => api.parseFiles(files, dataDir, subfolder));
  }, [execute]);

  return { data, loading, error, parseFiles };
}

export function useCleanData() {
  const { data, loading, error, execute } = useApi<any>();
  
  const cleanData = useCallback(async (config?: Parameters<typeof api.cleanData>[0]) => {
    return execute(() => api.cleanData(config || {}));
  }, [execute]);

  return { data, loading, error, cleanData };
}

export function useListModels() {
  const { data, loading, error, execute } = useApi<{
    folders: string[];
    models: any[];
    folder_counts: Record<string, number>;
    total_models: number;
    current_folder?: string;
  }>();
  
  const listModels = useCallback(async (subfolder?: string) => {
    return execute(() => api.listModels(subfolder));
  }, [execute]);

  return { 
    models: data?.models || [],
    folders: data?.folders || [],
    folderCounts: data?.folder_counts || {},
    totalModels: data?.total_models || 0,
    currentFolder: data?.current_folder,
    loading, 
    error, 
    listModels 
  };
}
