import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { useGoogleHealth } from './useGoogleHealth';
import type { GoogleHealth } from './useGoogleHealth';

function makeHealthResponse(overrides: Partial<GoogleHealth> = {}): GoogleHealth {
  return {
    connected: true,
    broken_reason: null,
    broken_at: null,
    ...overrides,
  };
}

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useGoogleHealth', () => {
  it('fetches on mount and surfaces connected state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, makeHealthResponse({ connected: true }))),
    );

    const { result } = renderHook(() => useGoogleHealth());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.connected).toBe(true);
    expect(result.current.broken_reason).toBeNull();
  });

  it('surfaces disconnected state when API returns connected=false', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeResponse(200, makeHealthResponse({ connected: false, broken_reason: 'revoked' })),
      ),
    );

    const { result } = renderHook(() => useGoogleHealth());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.connected).toBe(false);
    expect(result.current.broken_reason).toBe('revoked');
  });

  it('refetch calls the API again and updates state', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse(200, makeHealthResponse({ connected: true })))
      .mockResolvedValueOnce(makeResponse(200, makeHealthResponse({ connected: false, broken_reason: 'expired' })));

    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useGoogleHealth());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.connected).toBe(true);

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.connected).toBe(false);
    expect(result.current.broken_reason).toBe('expired');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
