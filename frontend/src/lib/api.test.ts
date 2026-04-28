import { describe, it, expect, vi, afterEach } from 'vitest';
import { apiFetch, ApiError } from './api';

function makeResponse(status: number, body?: unknown): Response {
  if (status === 204) {
    return new Response(null, { status });
  }
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiFetch', () => {
  it('returns parsed JSON on 200', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, { id: 1, name: 'test' })),
    );

    const result = await apiFetch<{ id: number; name: string }>('/api/test');
    expect(result).toEqual({ id: 1, name: 'test' });
  });

  it('includes credentials: include on every request', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);

    await apiFetch('/api/test');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('returns undefined on 204', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(204)),
    );

    const result = await apiFetch<undefined>('/api/test');
    expect(result).toBeUndefined();
  });

  it('throws ApiError with status and detail on 400', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(400, { detail: 'Bad request' })),
    );

    let error: ApiError | null = null;
    try {
      await apiFetch('/api/test');
    } catch (e) {
      error = e as ApiError;
    }
    expect(error).toBeInstanceOf(ApiError);
    expect(error?.status).toBe(400);
    expect(error?.message).toBe('Bad request');
  });

  it('throws ApiError with status and detail on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(404, { detail: 'Not found' })),
    );

    let error: ApiError | null = null;
    try {
      await apiFetch('/api/test');
    } catch (e) {
      error = e as ApiError;
    }
    expect(error).toBeInstanceOf(ApiError);
    expect(error?.status).toBe(404);
    expect(error?.message).toBe('Not found');
  });

  it('throws ApiError on 500 with fallback message when no detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(500, {})),
    );

    await expect(apiFetch('/api/test')).rejects.toMatchObject({
      status: 500,
      message: 'Request failed',
    });
  });

  it('passes additional headers through', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);

    await apiFetch('/api/test', {
      headers: { 'X-Custom': 'value' },
    });

    const calledHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(calledHeaders['X-Custom']).toBe('value');
    expect(calledHeaders['Content-Type']).toBe('application/json');
  });
});

describe('ApiError', () => {
  it('has name ApiError', () => {
    const e = new ApiError(422, 'Validation error');
    expect(e.name).toBe('ApiError');
    expect(e.status).toBe(422);
    expect(e.message).toBe('Validation error');
  });

  it('is an instance of Error', () => {
    const e = new ApiError(500, 'Server error');
    expect(e).toBeInstanceOf(Error);
  });
});
