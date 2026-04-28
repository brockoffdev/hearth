import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { useUploads } from './useUploads';
import type { Upload } from './uploads';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeUpload(overrides: Partial<Upload> = {}): Upload {
  return {
    id: '1',
    status: 'completed',
    image_path: 'uploads/1.jpg',
    url: '/api/uploads/1/photo',
    uploaded_at: '2026-04-27T10:00:00Z',
    thumbLabel: 'Apr 27, 10:00 AM',
    ...overrides,
  };
}

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeEmptyResponse(status: number): Response {
  return new Response(null, { status });
}

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useUploads — initial load', () => {
  it('starts in loading state', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})), // never resolves
    );

    const { result } = renderHook(() => useUploads());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.uploads).toEqual([]);
    expect(result.current.loadError).toBeNull();
  });

  it('transitions to loaded state with uploads', async () => {
    const uploads: Upload[] = [
      makeUpload({ id: '1', status: 'completed' }),
      makeUpload({ id: '2', status: 'processing', remaining_seconds: 120 }),
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, uploads)),
    );

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.uploads).toHaveLength(2);
    expect(result.current.loadError).toBeNull();
  });

  it('sets loadError on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(500, { detail: 'Server error' })),
    );

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.loadError).not.toBeNull();
    expect(result.current.uploads).toEqual([]);
  });
});

describe('useUploads — inflightCount + longestETA', () => {
  it('counts processing uploads as inflightCount', async () => {
    const uploads: Upload[] = [
      makeUpload({ id: '1', status: 'processing' }),
      makeUpload({ id: '2', status: 'processing' }),
      makeUpload({ id: '3', status: 'completed' }),
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, uploads)),
    );

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.inflightCount).toBe(2));
  });

  it('computes longestETA as max of remaining_seconds across in-flight', async () => {
    const uploads: Upload[] = [
      makeUpload({ id: '1', status: 'processing', remaining_seconds: 184 }),
      makeUpload({ id: '2', status: 'processing', remaining_seconds: 235 }),
      makeUpload({ id: '3', status: 'completed' }),
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, uploads)),
    );

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.longestETA).toBe(235));
  });

  it('longestETA is 0 when no in-flight uploads', async () => {
    const uploads: Upload[] = [
      makeUpload({ id: '1', status: 'completed' }),
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, uploads)),
    );

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.longestETA).toBe(0);
    expect(result.current.inflightCount).toBe(0);
  });
});

describe('useUploads — polling', () => {
  it('polls every 3s when in-flight uploads exist', async () => {
    vi.useFakeTimers();

    const processingUpload = makeUpload({ id: '1', status: 'processing', remaining_seconds: 60 });
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, [processingUpload]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    // Wait for the initial fetch to complete by advancing microtasks
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.isLoading).toBe(false);
    const callsAfterLoad = fetchMock.mock.calls.length;
    expect(callsAfterLoad).toBeGreaterThanOrEqual(1);

    // Advance 3 seconds — should trigger one poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(fetchMock.mock.calls.length).toBeGreaterThan(callsAfterLoad);
  });

  it('stops polling when all uploads are no longer in-flight', async () => {
    vi.useFakeTimers();

    const processingUpload = makeUpload({ id: '1', status: 'processing', remaining_seconds: 5 });
    const completedUpload = makeUpload({ id: '1', status: 'completed' });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(200, [processingUpload]))
      .mockResolvedValue(makeResponse(200, [completedUpload]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    // Initial load
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.inflightCount).toBe(1);

    // First poll at 3s — transitions to completed
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(result.current.inflightCount).toBe(0);

    const callsWhenComplete = fetchMock.mock.calls.length;

    // Advance more time — no more polling
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });

    expect(fetchMock.mock.calls.length).toBe(callsWhenComplete);
  });

  it('does not poll when there are no in-flight uploads', async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, [makeUpload({ status: 'completed' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.isLoading).toBe(false);

    const callsAfterLoad = fetchMock.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });

    expect(fetchMock.mock.calls.length).toBe(callsAfterLoad);
  });
});

describe('useUploads — cleanup on unmount', () => {
  it('stops polling after unmount', async () => {
    vi.useFakeTimers();

    const processingUpload = makeUpload({ id: '1', status: 'processing', remaining_seconds: 60 });
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, [processingUpload]));
    vi.stubGlobal('fetch', fetchMock);

    const { result, unmount } = renderHook(() => useUploads());

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.isLoading).toBe(false);

    const callsBeforeUnmount = fetchMock.mock.calls.length;
    unmount();

    // Advance timer — should not trigger more fetches after unmount
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });

    expect(fetchMock.mock.calls.length).toBe(callsBeforeUnmount);
  });
});

describe('useUploads — retry', () => {
  it('calls retryUpload and then refetches', async () => {
    const original = makeUpload({ id: '1', status: 'failed' });
    const retried = makeUpload({ id: '2', status: 'processing', remaining_seconds: 100 });

    const fetchMock = vi
      .fn()
      // Initial list load
      .mockResolvedValueOnce(makeResponse(200, [original]))
      // retry POST
      .mockResolvedValueOnce(makeResponse(201, retried))
      // refetch list
      .mockResolvedValue(makeResponse(200, [retried]));

    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    let retryResult: Upload | undefined;
    await act(async () => {
      retryResult = await result.current.retry('1');
    });

    // Should have called POST /api/uploads/1/retry
    const postCall = fetchMock.mock.calls.find((call: unknown[]) => {
      const [url, init] = call as [string, RequestInit];
      return url === '/api/uploads/1/retry' && init.method === 'POST';
    });
    expect(postCall).toBeTruthy();

    // retryResult should be the new upload
    expect(retryResult?.id).toBe('2');

    // After refetch, uploads list updated
    await waitFor(() =>
      expect(result.current.uploads.some((u) => u.status === 'processing')).toBe(true),
    );
  });
});

describe('useUploads — cancel', () => {
  it('calls cancelUpload and then refetches', async () => {
    const queuedUpload = makeUpload({ id: '1', status: 'processing', remaining_seconds: 100 });

    const fetchMock = vi
      .fn()
      // Initial list load
      .mockResolvedValueOnce(makeResponse(200, [queuedUpload]))
      // DELETE (cancel)
      .mockResolvedValueOnce(makeEmptyResponse(204))
      // refetch list
      .mockResolvedValue(makeResponse(200, []));

    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.cancel('1');
    });

    // Should have called DELETE /api/uploads/1
    const deleteCall = fetchMock.mock.calls.find((call: unknown[]) => {
      const [url, init] = call as [string, RequestInit];
      return url === '/api/uploads/1' && init.method === 'DELETE';
    });
    expect(deleteCall).toBeTruthy();

    // After refetch, uploads list is empty
    await waitFor(() => expect(result.current.uploads).toHaveLength(0));
  });
});

describe('useUploads — refetch', () => {
  it('refetch updates uploads', async () => {
    const first: Upload[] = [makeUpload({ id: '1', status: 'processing' })];
    const second: Upload[] = [makeUpload({ id: '1', status: 'completed' })];

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(200, first))
      .mockResolvedValue(makeResponse(200, second));

    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useUploads());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.uploads[0]?.status).toBe('processing');

    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() =>
      expect(result.current.uploads[0]?.status).toBe('completed'),
    );
  });
});
