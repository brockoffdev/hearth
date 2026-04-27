import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { AuthProvider } from './AuthProvider';
import { RequireAuth } from './RequireAuth';
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

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Helper: render wrapped in MemoryRouter + AuthProvider
// ---------------------------------------------------------------------------

function renderWithRouter(initialPath = '/protected') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/protected"
            element={
              <RequireAuth>
                <div data-testid="protected-content">Protected Content</div>
              </RequireAuth>
            }
          />
          <Route
            path="/login"
            element={<div data-testid="login-page">Login Page</div>}
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RequireAuth', () => {
  it('renders children when /me returns 200 (authenticated)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, MOCK_USER)),
    );

    renderWithRouter();

    await waitFor(() =>
      expect(screen.getByTestId('protected-content')).not.toBeNull(),
    );
  });

  it('renders nothing while loading (before /me resolves)', () => {
    // Use a promise that never resolves so we stay in loading
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(new Promise(() => {})),
    );

    const { container } = renderWithRouter();

    // Nothing rendered yet
    expect(container.textContent).toBe('');
    expect(screen.queryByTestId('protected-content')).toBeNull();
    expect(screen.queryByTestId('login-page')).toBeNull();
  });

  it('redirects to /login when /me returns 401 (anonymous)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
    );

    renderWithRouter();

    await waitFor(() =>
      expect(screen.getByTestId('login-page')).not.toBeNull(),
    );
    expect(screen.queryByTestId('protected-content')).toBeNull();
  });
});
