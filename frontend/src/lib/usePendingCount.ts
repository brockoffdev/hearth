import { useState, useEffect, useCallback, useRef } from 'react';
import { getPendingCount } from './events';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UsePendingCountResult {
  count: number;
  isLoading: boolean;
  refetch: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 30_000;

export function usePendingCount(): UsePendingCountResult {
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCount = useCallback(async (): Promise<void> => {
    try {
      const n = await getPendingCount();
      setCount(n);
    } catch {
      // Silently reset to 0 — badge just disappears on fetch error.
      setCount(0);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCount();

    intervalRef.current = setInterval(() => {
      void fetchCount();
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchCount]);

  return { count, isLoading, refetch: fetchCount };
}
