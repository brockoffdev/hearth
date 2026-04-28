import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getTvSnapshot } from './tv';

const MOCK_SNAPSHOT = {
  family_members: [{ id: 1, name: 'Bryant', color_hex: '#2E5BA8' }],
  events: [
    {
      id: 1,
      title: 'Soccer practice',
      start_dt: '2026-04-28T15:00:00',
      end_dt: null,
      all_day: false,
      family_member_id: 1,
      family_member_name: 'Bryant',
      family_member_color_hex: '#2E5BA8',
    },
  ],
  server_time: '2026-04-28T10:00:00Z',
};

describe('getTvSnapshot', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches from /api/tv/snapshot without credentials', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(MOCK_SNAPSHOT),
    } as Response);

    await getTvSnapshot();

    expect(mockFetch).toHaveBeenCalledWith('/api/tv/snapshot', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }));
    // Crucially: no `credentials: 'include'`
    const callArg = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(callArg?.credentials).toBeUndefined();
  });

  it('returns parsed snapshot data', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(MOCK_SNAPSHOT),
    } as Response);

    const result = await getTvSnapshot();

    expect(result.family_members).toHaveLength(1);
    expect(result.events).toHaveLength(1);
    expect(result.server_time).toBe('2026-04-28T10:00:00Z');
  });

  it('throws on non-ok response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    await expect(getTvSnapshot()).rejects.toThrow('TV snapshot fetch failed: 500');
  });
});
