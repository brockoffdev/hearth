import { describe, it, expect, vi, afterEach } from 'vitest';
import { listUploads, getUpload, uploadPhoto } from './uploads';
import type { UploadSummary } from './uploads';

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const MOCK_UPLOAD: UploadSummary = {
  id: 1,
  status: 'completed',
  image_path: 'uploads/abc123.jpg',
  uploaded_at: '2026-04-27T10:00:00Z',
  url: '/api/uploads/1/photo',
};

describe('listUploads', () => {
  it('calls GET /api/uploads and returns typed array', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, [MOCK_UPLOAD]));
    vi.stubGlobal('fetch', fetchMock);

    const result = await listUploads();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/uploads',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual(MOCK_UPLOAD);
  });

  it('returns empty array when API returns []', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, [])),
    );

    const result = await listUploads();
    expect(result).toEqual([]);
  });

  it('propagates ApiError on non-OK response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
    );

    await expect(listUploads()).rejects.toMatchObject({ status: 401 });
  });
});

describe('getUpload', () => {
  it('calls GET /api/uploads/:id and returns upload', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, MOCK_UPLOAD));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getUpload(1);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/uploads/1',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result).toEqual(MOCK_UPLOAD);
  });

  it('calls the correct URL for different IDs', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(200, { ...MOCK_UPLOAD, id: 42 }));
    vi.stubGlobal('fetch', fetchMock);

    await getUpload(42);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/uploads/42',
      expect.anything(),
    );
  });

  it('propagates ApiError on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(404, { detail: 'Not found' })),
    );

    await expect(getUpload(999)).rejects.toMatchObject({ status: 404 });
  });
});

describe('uploadPhoto', () => {
  it('posts FormData with the file to /api/uploads', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(201, MOCK_UPLOAD));
    vi.stubGlobal('fetch', fetchMock);

    const file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' });
    const result = await uploadPhoto(file);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/uploads');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get('photo')).toBeInstanceOf(File);
    expect(result).toEqual(MOCK_UPLOAD);
  });

  it('does NOT set Content-Type header (lets browser set multipart boundary)', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(makeResponse(201, MOCK_UPLOAD));
    vi.stubGlobal('fetch', fetchMock);

    const file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' });
    await uploadPhoto(file);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // headers should be absent or not contain Content-Type
    const headers = init.headers as Record<string, string> | undefined;
    expect(headers?.['Content-Type']).toBeUndefined();
  });

  it('throws ApiError with detail on 4xx response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeResponse(413, { detail: 'File too large' }),
      ),
    );

    const file = new File(['data'], 'photo.jpg', { type: 'image/jpeg' });
    await expect(uploadPhoto(file)).rejects.toMatchObject({
      status: 413,
      message: 'File too large',
    });
  });
});
