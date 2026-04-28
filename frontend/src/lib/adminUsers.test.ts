import { describe, it, expect, vi, afterEach } from 'vitest';
import { listUsers, createUser, patchUser, deleteUser } from './adminUsers';
import type { AdminUser } from './adminUsers';

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

const MOCK_USER: AdminUser = {
  id: 1,
  username: 'admin',
  role: 'admin',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-04-27T10:00:00Z',
};

const MOCK_USER_2: AdminUser = {
  id: 2,
  username: 'alice',
  role: 'user',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-04-28T08:00:00Z',
};

// ---------------------------------------------------------------------------
// listUsers
// ---------------------------------------------------------------------------

describe('listUsers', () => {
  it('calls GET /api/admin/users and returns items array', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeResponse(200, { items: [MOCK_USER, MOCK_USER_2] }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await listUsers();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(result).toHaveLength(2);
    expect(result[0]?.username).toBe('admin');
    expect(result[1]?.username).toBe('alice');
  });

  it('propagates ApiError on 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Not authenticated' })),
    );

    await expect(listUsers()).rejects.toMatchObject({ status: 401 });
  });

  it('propagates ApiError on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(403, { detail: 'Admin access required' })),
    );

    await expect(listUsers()).rejects.toMatchObject({ status: 403 });
  });
});

// ---------------------------------------------------------------------------
// createUser
// ---------------------------------------------------------------------------

describe('createUser', () => {
  it('calls POST /api/admin/users with body and returns the new user', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(201, MOCK_USER_2));
    vi.stubGlobal('fetch', fetchMock);

    const result = await createUser({ username: 'alice', password: 'securepass' });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/admin/users');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      username: 'alice',
      password: 'securepass',
    });
    expect(result.username).toBe('alice');
  });

  it('includes role when provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(201, { ...MOCK_USER_2, role: 'admin' }));
    vi.stubGlobal('fetch', fetchMock);

    await createUser({ username: 'alice', password: 'securepass', role: 'admin' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string).role).toBe('admin');
  });

  it('propagates ApiError on 409 (duplicate username)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(409, { detail: 'Username already taken' })),
    );

    await expect(createUser({ username: 'admin', password: 'pass1234' })).rejects.toMatchObject({
      status: 409,
    });
  });

  it('propagates ApiError on 422 (validation)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(422, { detail: 'Validation error' })),
    );

    await expect(createUser({ username: 'x', password: 'short' })).rejects.toMatchObject({
      status: 422,
    });
  });
});

// ---------------------------------------------------------------------------
// patchUser
// ---------------------------------------------------------------------------

describe('patchUser', () => {
  it('calls PATCH /api/admin/users/:id with body', async () => {
    const updated = { ...MOCK_USER_2, role: 'admin' as const };
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, updated));
    vi.stubGlobal('fetch', fetchMock);

    const result = await patchUser(2, { role: 'admin' });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/admin/users/2');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ role: 'admin' });
    expect(result.role).toBe('admin');
  });

  it('can patch new_password', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, MOCK_USER_2));
    vi.stubGlobal('fetch', fetchMock);

    await patchUser(2, { new_password: 'newpassword123' });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ new_password: 'newpassword123' });
  });

  it('propagates ApiError on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(404, { detail: 'User not found' })),
    );

    await expect(patchUser(999, { role: 'user' })).rejects.toMatchObject({ status: 404 });
  });

  it('propagates ApiError on 400 (self-demote)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeResponse(400, { detail: 'Cannot demote yourself; ask another admin' }),
      ),
    );

    await expect(patchUser(1, { role: 'user' })).rejects.toMatchObject({ status: 400 });
  });
});

// ---------------------------------------------------------------------------
// deleteUser
// ---------------------------------------------------------------------------

describe('deleteUser', () => {
  it('calls DELETE /api/admin/users/:id and returns void on 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeEmptyResponse(204));
    vi.stubGlobal('fetch', fetchMock);

    const result = await deleteUser(2);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/admin/users/2',
      expect.objectContaining({ method: 'DELETE', credentials: 'include' }),
    );
    expect(result).toBeUndefined();
  });

  it('propagates ApiError on 400 (self-delete)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(400, { detail: 'Cannot delete yourself' })),
    );

    await expect(deleteUser(1)).rejects.toMatchObject({ status: 400 });
  });

  it('propagates ApiError on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(404, { detail: 'User not found' })),
    );

    await expect(deleteUser(999)).rejects.toMatchObject({ status: 404 });
  });
});
