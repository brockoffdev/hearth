import { describe, it, expect, vi, afterEach } from 'vitest';
import { getAdminSettings, patchAdminSettings } from './adminSettings';
import type { AdminSettings } from './adminSettings';

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const MOCK_SETTINGS: AdminSettings = {
  confidence_threshold: 0.85,
  vision_provider: 'ollama',
  vision_model: 'qwen2.5-vl:7b',
  ollama_endpoint: 'http://localhost:11434',
  gemini_api_key_masked: '',
  anthropic_api_key_masked: '',
  gemini_api_key_set: false,
  anthropic_api_key_set: false,
  few_shot_correction_window: 10,
  use_real_pipeline: false,
  rocm_available: false,
};

// ---------------------------------------------------------------------------
// getAdminSettings
// ---------------------------------------------------------------------------

describe('getAdminSettings', () => {
  it('calls GET /api/admin/settings and returns the settings', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_SETTINGS));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getAdminSettings();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/settings',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result.confidence_threshold).toBe(0.85);
    expect(result.vision_provider).toBe('ollama');
    expect(result.rocm_available).toBe(false);
  });

  it('propagates ApiError on 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Not authenticated' })),
    );

    await expect(getAdminSettings()).rejects.toMatchObject({ status: 401 });
  });

  it('propagates ApiError on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(403, { detail: 'Admin access required' })),
    );

    await expect(getAdminSettings()).rejects.toMatchObject({ status: 403 });
  });
});

// ---------------------------------------------------------------------------
// patchAdminSettings
// ---------------------------------------------------------------------------

describe('patchAdminSettings', () => {
  it('calls PATCH /api/admin/settings with body and returns updated settings', async () => {
    const updated = { ...MOCK_SETTINGS, confidence_threshold: 0.90 };
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, updated));
    vi.stubGlobal('fetch', fetchMock);

    const result = await patchAdminSettings({ confidence_threshold: 0.90 });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/admin/settings');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ confidence_threshold: 0.90 });
    expect(result.confidence_threshold).toBe(0.90);
  });

  it('can patch vision_provider and vision_model together', async () => {
    const updated = { ...MOCK_SETTINGS, vision_provider: 'gemini' as const, vision_model: 'gemini-2.5-flash' };
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, updated));
    vi.stubGlobal('fetch', fetchMock);

    const result = await patchAdminSettings({ vision_provider: 'gemini', vision_model: 'gemini-2.5-flash' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      vision_provider: 'gemini',
      vision_model: 'gemini-2.5-flash',
    });
    expect(result.vision_provider).toBe('gemini');
  });

  it('can send empty string to clear an api key', async () => {
    const updated = { ...MOCK_SETTINGS, gemini_api_key_set: false, gemini_api_key_masked: '' };
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, updated));
    vi.stubGlobal('fetch', fetchMock);

    await patchAdminSettings({ gemini_api_key: '' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ gemini_api_key: '' });
  });

  it('propagates ApiError on 422 (validation)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(422, { detail: 'confidence_threshold out of range' })),
    );

    await expect(patchAdminSettings({ confidence_threshold: 1.5 })).rejects.toMatchObject({
      status: 422,
    });
  });
});
