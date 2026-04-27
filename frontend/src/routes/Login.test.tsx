import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { Login } from './Login';
import type { User } from '../auth/AuthProvider';

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

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Wrapper: MemoryRouter + AuthProvider + Login route + home route
// ---------------------------------------------------------------------------

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={<div data-testid="home-page">Home</div>}
            />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Login route', () => {
  it('renders the form: wordmark, eyebrow, inputs, button, forgot line', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
    );

    renderLogin();

    // Wait for loading to finish (me returns 401 → anonymous)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeNull(),
    );

    expect(screen.getAllByText('hearth').length).toBeGreaterThanOrEqual(1);
    // Eyebrow text "SIGN IN" (uppercase via CSS, text node is "Sign in")
    expect(screen.getAllByText(/sign in/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/username/i)).not.toBeNull();
    expect(screen.getByLabelText(/password/i)).not.toBeNull();
    expect(screen.getByRole('button', { name: /sign in/i })).not.toBeNull();
    expect(screen.getByText(/forgot/i)).not.toBeNull();
    expect(screen.getByText(/self-hosted/i)).not.toBeNull();
  });

  it('empty submit → renders inline error, does NOT call fetch login', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' }));
    vi.stubGlobal('fetch', fetchMock);

    renderLogin();

    await waitFor(() => expect(screen.getByRole('button', { name: /sign in/i })).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText('Username is required')).not.toBeNull(),
    );
    expect(screen.getByText('Password is required')).not.toBeNull();

    // Only the /me call should have fired; no /login call
    const loginCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/login'),
    );
    expect(loginCalls.length).toBe(0);
  });

  it('valid login → calls POST /api/auth/login once with correct body, navigates to /', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockResolvedValueOnce(makeResponse(200, MOCK_USER)); // /login
    vi.stubGlobal('fetch', fetchMock);

    renderLogin();

    await waitFor(() => expect(screen.getByLabelText(/username/i)).not.toBeNull());

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'admin' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByTestId('home-page')).not.toBeNull(),
    );

    const loginCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/api/auth/login'),
    );
    expect(loginCalls.length).toBe(1);
    const body = JSON.parse(loginCalls[0]![1]!.body as string) as {
      username: string;
      password: string;
    };
    expect(body.username).toBe('admin');
    expect(body.password).toBe('admin');
  });

  it('invalid creds (401) → renders "Invalid credentials", button re-enables, no navigation', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Invalid credentials' })); // /login
    vi.stubGlobal('fetch', fetchMock);

    renderLogin();

    await waitFor(() => expect(screen.getByLabelText(/username/i)).not.toBeNull());

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrongpassword' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText('Invalid credentials')).not.toBeNull(),
    );

    // Button should be re-enabled
    expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled();

    // No navigation to home
    expect(screen.queryByTestId('home-page')).toBeNull();
  });

  it('already-authenticated user → redirects to / immediately', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, MOCK_USER)),
    );

    renderLogin();

    await waitFor(() =>
      expect(screen.getByTestId('home-page')).not.toBeNull(),
    );
    expect(screen.queryByLabelText(/username/i)).toBeNull();
  });

  it('Sign In button is disabled while request is in flight', async () => {
    // /me resolves immediately, /login never resolves (infinite pending)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockReturnValueOnce(new Promise(() => {})); // /login — hangs
    vi.stubGlobal('fetch', fetchMock);

    renderLogin();

    await waitFor(() => expect(screen.getByLabelText(/username/i)).not.toBeNull());

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'admin' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled(),
    );
  });
});
