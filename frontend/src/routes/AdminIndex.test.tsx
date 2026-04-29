import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { AdminIndex } from './AdminIndex';
import type { User } from '../auth/AuthProvider';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ADMIN_USER: User = {
  id: 1,
  username: 'admin',
  role: 'admin',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

const REGULAR_USER: User = {
  id: 2,
  username: 'regular',
  role: 'user',
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
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function renderAdminIndex() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin" element={<AdminIndex />} />
            <Route
              path="/admin/users"
              element={<div data-testid="admin-users-page">Admin Users</div>}
            />
            <Route
              path="/admin/settings"
              element={<div data-testid="admin-settings-page">Admin Settings</div>}
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

describe('AdminIndex', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, ADMIN_USER)),
    );
  });

  it('renders admin page title when user is admin', async () => {
    renderAdminIndex();

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).not.toBeNull(),
    );

    // Should show the Admin label and the h1 title
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toMatch(/admin/i);
  });

  it('renders the Users card with correct link', async () => {
    renderAdminIndex();

    await waitFor(() =>
      expect(screen.getByText('Users')).not.toBeNull(),
    );

    const usersLink = screen.getByText('Users').closest('a');
    expect(usersLink?.getAttribute('href')).toBe('/admin/users');
    expect(screen.getByText(/Add and remove people/i)).not.toBeNull();
  });

  it('renders the Settings card with correct link', async () => {
    renderAdminIndex();

    await waitFor(() =>
      expect(screen.getByText('Settings')).not.toBeNull(),
    );

    const settingsLink = screen.getByText('Settings').closest('a');
    expect(settingsLink?.getAttribute('href')).toBe('/admin/settings');
    expect(screen.getByText(/confidence threshold/i)).not.toBeNull();
  });

  it('shows 403 when user is not an admin', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, REGULAR_USER)),
    );

    renderAdminIndex();

    await waitFor(() =>
      expect(screen.getByText('403')).not.toBeNull(),
    );

    expect(screen.getByText(/admin access required/i)).not.toBeNull();
  });
});
