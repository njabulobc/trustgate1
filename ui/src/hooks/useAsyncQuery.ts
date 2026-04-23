import { DependencyList, useCallback, useEffect, useState } from 'react';

type QueryState<T> = { data: T | null; loading: boolean; error: string | null };

export function useAsyncQuery<T>(fn: () => Promise<T>, deps: DependencyList, enabled = true) {
  const [state, setState] = useState<QueryState<T>>({ data: null, loading: enabled, error: null });

  const refetch = useCallback(async () => {
    setState((old) => ({ ...old, loading: true, error: null }));
    try {
      const data = await fn();
      setState({ data, loading: false, error: null });
    } catch (error) {
      setState({ data: null, loading: false, error: (error as Error).message });
    }
  }, deps);

  useEffect(() => {
    if (!enabled) return;
    refetch();
  }, [enabled, refetch]);

  return { ...state, refetch };
}
