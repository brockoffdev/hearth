import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { usePendingCount } from './usePendingCount';

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('usePendingCount', () => {
  it('fetches on mount and surfaces count', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, { count: 3 })),
    );

    const { result } = renderHook(() => usePendingCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.count).toBe(3);
  });

  it('starts with isLoading true, then false after fetch', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, { count: 1 })),
    );

    const { result } = renderHook(() => usePendingCount());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it('silently sets count to 0 on fetch error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('Network error')),
    );

    const { result } = renderHook(() => usePendingCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.count).toBe(0);
  });

  it('silently sets count to 0 on API error response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
    );

    const { result } = renderHook(() => usePendingCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.count).toBe(0);
  });

  it('refetch calls the API again and updates count', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse(200, { count: 2 }))
      .mockResolvedValueOnce(makeResponse(200, { count: 7 }));

    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => usePendingCount());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.count).toBe(2);

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.count).toBe(7);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('polls every 30 seconds using setInterval', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const fetchMock = vi.fn()
      .mockResolvedValue(makeResponse(200, { count: 1 }));

    vi.stubGlobal('fetch', fetchMock);

    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

    const { unmount } = renderHook(() => usePendingCount());

    // setInterval should have been called with 30_000ms
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 30_000);

    unmount();
    vi.useRealTimers();
  });

  it('clears the interval on unmount', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, { count: 0 })),
    );

    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

    const { unmount } = renderHook(() => usePendingCount());

    await waitFor(() => expect(clearIntervalSpy).not.toHaveBeenCalled());

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
