import { useState, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GoogleHealth {
  connected: boolean;
  broken_reason: string | null;
  broken_at: string | null;
}

interface UseGoogleHealthResult {
  connected: boolean;
  broken_reason: string | null;
  broken_at: string | null;
  isLoading: boolean;
  refetch: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export async function getGoogleHealth(): Promise<GoogleHealth> {
  const res = await fetch('/api/google/health', { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`Google health check failed: ${res.status}`);
  }
  return (await res.json()) as GoogleHealth;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGoogleHealth(): UseGoogleHealthResult {
  const [health, setHealth] = useState<GoogleHealth>({
    connected: true,
    broken_reason: null,
    broken_at: null,
  });
  const [isLoading, setIsLoading] = useState(true);

  const fetchHealth = useCallback(async (): Promise<void> => {
    try {
      const data = await getGoogleHealth();
      setHealth(data);
    } catch {
      // Network or auth failure — don't show a false broken state; stay silent.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHealth();
  }, [fetchHealth]);

  return {
    connected: health.connected,
    broken_reason: health.broken_reason,
    broken_at: health.broken_at,
    isLoading,
    refetch: fetchHealth,
  };
}
