import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthProvider';
import type { User } from './AuthProvider';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: User = {
  id: 1,
  username: 'admin',
  role: 'admin',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// ---------------------------------------------------------------------------
// Test helper components
// ---------------------------------------------------------------------------

function AuthConsumer() {
  const { state, login, logout, refresh } = useAuth();
  return (
    <div>
      <span data-testid="status">{state.status}</span>
      {state.status === 'authenticated' && (
        <span data-testid="username">{state.user.username}</span>
      )}
      {state.status === 'authenticated' && (
        <span data-testid="mcp">{String(state.user.must_change_password)}</span>
      )}
      <button
        onClick={() => login('admin', 'admin')}
        data-testid="login-btn"
      >
        Login
      </button>
      <button onClick={() => logout()} data-testid="logout-btn">
        Logout
      </button>
      <button onClick={() => refresh()} data-testid="refresh-btn">
        Refresh
      </button>
    </div>
  );
}

function AuthErrorConsumer() {
  const { login, logout } = useAuth();
  return (
    <div>
      <button onClick={() => login('x', 'y')} data-testid="login-btn">Login</button>
      <button onClick={() => logout()} data-testid="logout-btn">Logout</button>
    </div>
  );
}

function renderWithProvider(ui: React.ReactElement = <AuthConsumer />) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthProvider', () => {
  it('on mount, calls /api/auth/me exactly once', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' }));
    vi.stubGlobal('fetch', fetchMock);

    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('anonymous');
    });

    // /me is called once (ref guard prevents double-fire)
    const meCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/api/auth/me'),
    );
    expect(meCalls.length).toBe(1);
  });

  it('after 200 from /me, state is authenticated with fetched user', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, MOCK_USER)),
    );

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('authenticated'),
    );
    expect(screen.getByTestId('username').textContent).toBe('admin');
  });

  it('after 401 from /me, state is anonymous', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
    );

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('anonymous'),
    );
  });

  it('login() with valid creds → state authenticated, returns {ok: true}', async () => {
    // /me → 401, then /login → 200
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' }))
      .mockResolvedValueOnce(makeResponse(200, MOCK_USER));
    vi.stubGlobal('fetch', fetchMock);

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('anonymous'),
    );

    let loginResult: { ok: boolean } | undefined;
    await act(async () => {
      // Directly call login through a second consumer approach
      const btn = screen.getByTestId('login-btn');
      btn.click();
    });

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('authenticated'),
    );
    expect(screen.getByTestId('username').textContent).toBe('admin');
    // Suppress unused warning
    void loginResult;
  });

  it('login() returns {ok: true} value', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' }))
      .mockResolvedValueOnce(makeResponse(200, MOCK_USER));
    vi.stubGlobal('fetch', fetchMock);

    let capturedResult: { ok: true } | { ok: false; error: string } | undefined;

    function CapturingConsumer() {
      const { login, state } = useAuth();
      return (
        <div>
          <span data-testid="status">{state.status}</span>
          <button
            data-testid="login-btn"
            onClick={async () => {
              capturedResult = await login('admin', 'admin');
            }}
          >
            Login
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <CapturingConsumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('anonymous'),
    );

    await act(async () => {
      screen.getByTestId('login-btn').click();
    });

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('authenticated'),
    );
    expect(capturedResult).toEqual({ ok: true });
  });

  it('login() with bad creds → returns {ok: false, error: "Invalid credentials"}, state stays anonymous', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' }))
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Invalid credentials' }));
    vi.stubGlobal('fetch', fetchMock);

    let capturedResult: { ok: true } | { ok: false; error: string } | undefined;

    function CapturingConsumer() {
      const { login, state } = useAuth();
      return (
        <div>
          <span data-testid="status">{state.status}</span>
          <button
            data-testid="login-btn"
            onClick={async () => {
              capturedResult = await login('admin', 'wrong');
            }}
          >
            Login
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <CapturingConsumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('anonymous'),
    );

    await act(async () => {
      screen.getByTestId('login-btn').click();
    });

    await waitFor(() => expect(capturedResult).toBeDefined());
    expect(capturedResult).toEqual({ ok: false, error: 'Invalid credentials' });
    expect(screen.getByTestId('status').textContent).toBe('anonymous');
  });

  it('logout() → state anonymous, even if backend errors', async () => {
    // Start authenticated
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(200, MOCK_USER)) // /me
      .mockRejectedValueOnce(new Error('Network error')); // /logout
    vi.stubGlobal('fetch', fetchMock);

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('authenticated'),
    );

    await act(async () => {
      screen.getByTestId('logout-btn').click();
    });

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('anonymous'),
    );
  });

  it('refresh() → state updates to match new /me response', async () => {
    const updatedUser: User = { ...MOCK_USER, must_change_password: true };

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(200, MOCK_USER)) // initial /me
      .mockResolvedValueOnce(makeResponse(200, updatedUser)); // refresh /me
    vi.stubGlobal('fetch', fetchMock);

    renderWithProvider();

    await waitFor(() =>
      expect(screen.getByTestId('status').textContent).toBe('authenticated'),
    );
    expect(screen.getByTestId('mcp').textContent).toBe('false');

    await act(async () => {
      screen.getByTestId('refresh-btn').click();
    });

    await waitFor(() =>
      expect(screen.getByTestId('mcp').textContent).toBe('true'),
    );
  });

  it('useAuth() outside provider throws with a clear error', () => {
    const consoleError = console.error;
    console.error = () => {};
    expect(() => {
      render(<AuthErrorConsumer />);
    }).toThrow('useAuth must be used within an AuthProvider');
    console.error = consoleError;
  });
});
