import { describe, it, expect, vi, afterEach } from 'vitest';
import { listEvents, getEvent, patchEvent, rejectEvent, getPendingCount, republishEvent, cellCropUrl } from './events';
import type { Event, EventList } from './events';

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeEmptyResponse(status: number): Response {
  return new Response(null, { status });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const MOCK_EVENT: Event = {
  id: 42,
  upload_id: 7,
  family_member_id: null,
  family_member_name: 'Bryant',
  family_member_color_hex: '#2E5BA8',
  title: 'Soccer practice',
  start_dt: '2026-04-27T15:00:00Z',
  end_dt: '2026-04-27T16:00:00Z',
  all_day: false,
  location: 'Field A',
  notes: null,
  confidence: 0.92,
  status: 'pending_review',
  google_event_id: null,
  cell_crop_path: 'crops/42.jpg',
  has_cell_crop: true,
  raw_vlm_json: null,
  created_at: '2026-04-27T10:00:00Z',
  updated_at: '2026-04-27T10:00:00Z',
  published_at: null,
};

const MOCK_LIST: EventList = {
  items: [MOCK_EVENT],
  total: 1,
};

// ---------------------------------------------------------------------------
// listEvents
// ---------------------------------------------------------------------------

describe('listEvents', () => {
  it('calls GET /api/events with no params', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_LIST));
    vi.stubGlobal('fetch', fetchMock);

    const result = await listEvents();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/events',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it('appends upload_id query param', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_LIST));
    vi.stubGlobal('fetch', fetchMock);

    await listEvents({ upload_id: 7 });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe('/api/events?upload_id=7');
  });

  it('appends status as string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_LIST));
    vi.stubGlobal('fetch', fetchMock);

    await listEvents({ status: 'auto_published' });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('status=auto_published');
  });

  it('joins status array with commas', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_LIST));
    vi.stubGlobal('fetch', fetchMock);

    await listEvents({ status: ['auto_published', 'pending_review'] });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('status=auto_published%2Cpending_review');
  });

  it('appends limit and offset', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_LIST));
    vi.stubGlobal('fetch', fetchMock);

    await listEvents({ limit: 10, offset: 20 });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('limit=10');
    expect(url).toContain('offset=20');
  });

  it('propagates ApiError on non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })));

    await expect(listEvents()).rejects.toMatchObject({ status: 401 });
  });
});

// ---------------------------------------------------------------------------
// getEvent
// ---------------------------------------------------------------------------

describe('getEvent', () => {
  it('calls GET /api/events/:id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_EVENT));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getEvent(42);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/events/42',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result).toEqual(MOCK_EVENT);
  });

  it('propagates ApiError on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(404, { detail: 'Not found' })));

    await expect(getEvent(999)).rejects.toMatchObject({ status: 404 });
  });
});

// ---------------------------------------------------------------------------
// patchEvent
// ---------------------------------------------------------------------------

describe('patchEvent', () => {
  it('calls PATCH /api/events/:id with body', async () => {
    const updated = { ...MOCK_EVENT, title: 'Updated title' };
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, updated));
    vi.stubGlobal('fetch', fetchMock);

    const result = await patchEvent(42, { title: 'Updated title' });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/events/42');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ title: 'Updated title' });
    expect(result.title).toBe('Updated title');
  });

  it('can patch multiple fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_EVENT));
    vi.stubGlobal('fetch', fetchMock);

    await patchEvent(42, { title: 'New', all_day: true, location: 'Home' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      title: 'New',
      all_day: true,
      location: 'Home',
    });
  });

  it('propagates ApiError on 422', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(422, { detail: 'Validation error' })));

    await expect(patchEvent(42, { title: '' })).rejects.toMatchObject({ status: 422 });
  });
});

// ---------------------------------------------------------------------------
// rejectEvent
// ---------------------------------------------------------------------------

describe('rejectEvent', () => {
  it('calls DELETE /api/events/:id and returns void on 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeEmptyResponse(204));
    vi.stubGlobal('fetch', fetchMock);

    const result = await rejectEvent(42);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/events/42',
      expect.objectContaining({ method: 'DELETE', credentials: 'include' }),
    );
    expect(result).toBeUndefined();
  });

  it('propagates ApiError on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(404, { detail: 'Not found' })));

    await expect(rejectEvent(999)).rejects.toMatchObject({ status: 404 });
  });
});

// ---------------------------------------------------------------------------
// getPendingCount
// ---------------------------------------------------------------------------

describe('getPendingCount', () => {
  it('calls GET /api/events/pending-count and returns the count', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, { count: 5 }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getPendingCount();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/events/pending-count',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result).toBe(5);
  });

  it('returns 0 when count is 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(200, { count: 0 })));
    expect(await getPendingCount()).toBe(0);
  });

  it('propagates ApiError on non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })));
    await expect(getPendingCount()).rejects.toMatchObject({ status: 401 });
  });
});

// ---------------------------------------------------------------------------
// republishEvent
// ---------------------------------------------------------------------------

describe('republishEvent', () => {
  it('calls POST /api/events/:id/republish and returns the event', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_EVENT));
    vi.stubGlobal('fetch', fetchMock);

    const result = await republishEvent(42);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/events/42/republish');
    expect(init.method).toBe('POST');
    expect(result).toEqual(MOCK_EVENT);
  });

  it('accepts a string id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_EVENT));
    vi.stubGlobal('fetch', fetchMock);

    await republishEvent('42');

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe('/api/events/42/republish');
  });

  it('propagates ApiError on 503', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(503, { detail: 'NoOauth' })));
    await expect(republishEvent(42)).rejects.toMatchObject({ status: 503 });
  });

  it('propagates ApiError on 400', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(400, { detail: 'NoCalendar' })));
    await expect(republishEvent(42)).rejects.toMatchObject({ status: 400 });
  });

  it('propagates ApiError on 502', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeResponse(502, { detail: 'GcalError' })));
    await expect(republishEvent(42)).rejects.toMatchObject({ status: 502 });
  });
});

// ---------------------------------------------------------------------------
// cellCropUrl
// ---------------------------------------------------------------------------

describe('cellCropUrl', () => {
  it('returns the correct URL for an event id', () => {
    expect(cellCropUrl(42)).toBe('/api/events/42/cell-crop');
    expect(cellCropUrl(1)).toBe('/api/events/1/cell-crop');
  });
});
