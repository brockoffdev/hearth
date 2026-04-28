import { useState, useEffect, useCallback } from 'react';
import { listUploads, retryUpload, cancelUpload } from './uploads';
import type { Upload } from './uploads';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseUploadsResult {
  uploads: Upload[];
  inflightCount: number;
  longestETA: number;
  isLoading: boolean;
  loadError: string | null;
  lastFetchedAt: Date | null;
  refetch: () => Promise<void>;
  retry: (id: string | number) => Promise<Upload>;
  cancel: (id: string | number) => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Single-source-of-truth hook for uploads state.
 *
 * - Fetches on mount, exposes isLoading + loadError.
 * - Polls every 3s while any upload is in-flight (status === 'processing').
 * - Stops polling once no in-flight uploads remain.
 * - Cleans up on unmount.
 *
 * Phase 4+ may consolidate multiple instances via a Context if polling
 * overhead becomes a concern (≤2 instances at ~0.67 req/s is fine for
 * Phase 3.5).
 */
export function useUploads(): UseUploadsResult {
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);

  const fetchUploads = useCallback(async (): Promise<void> => {
    try {
      const data = await listUploads();
      setUploads(data);
      setLoadError(null);
      setLastFetchedAt(new Date());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load uploads');
    }
  }, []);

  const refetch = useCallback(async (): Promise<void> => {
    await fetchUploads();
  }, [fetchUploads]);

  // Initial fetch on mount
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const data = await listUploads();
        if (cancelled) return;
        setUploads(data);
        setLoadError(null);
        setLastFetchedAt(new Date());
      } catch (err) {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : 'Failed to load uploads');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // Polling — only when in-flight uploads exist
  useEffect(() => {
    const hasInflight = uploads.some((u) => u.status === 'processing');
    if (!hasInflight) return;

    const interval = setInterval(() => {
      void fetchUploads();
    }, 3000);

    return () => {
      clearInterval(interval);
    };
  }, [uploads, fetchUploads]);

  const retry = useCallback(
    async (id: string | number): Promise<Upload> => {
      const result = await retryUpload(id);
      await fetchUploads();
      return result;
    },
    [fetchUploads],
  );

  const cancel = useCallback(
    async (id: string | number): Promise<void> => {
      await cancelUpload(id);
      await fetchUploads();
    },
    [fetchUploads],
  );

  const inflightCount = uploads.filter((u) => u.status === 'processing').length;
  const longestETA = uploads
    .filter((u) => u.status === 'processing')
    .reduce((max, u) => Math.max(max, u.remaining_seconds ?? 0), 0);

  return {
    uploads,
    inflightCount,
    longestETA,
    isLoading,
    loadError,
    lastFetchedAt,
    refetch,
    retry,
    cancel,
  };
}
