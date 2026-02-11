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
  const { data, loading, error, execute } = useApi<{ files: string[]; count: number }>();
  
  const listFiles = useCallback(async (dataDir?: string) => {
    return execute(() => api.listFiles(dataDir));
  }, [execute]);

  return { files: data?.files || [], count: data?.count || 0, loading, error, listFiles };
}

export function useParseFiles() {
  const { data, loading, error, execute } = useApi<any>();
  
  const parseFiles = useCallback(async (files: string[], dataDir?: string) => {
    return execute(() => api.parseFiles(files, dataDir));
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
  const { data, loading, error, execute } = useApi<any[]>();
  
  const listModels = useCallback(async () => {
    return execute(() => api.listModels());
  }, [execute]);

  return { models: data || [], loading, error, listModels };
}
