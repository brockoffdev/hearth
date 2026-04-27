import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { AuthProvider } from '../auth/AuthProvider';
import { Setup } from './Setup';
import type { User } from '../auth/AuthProvider';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: 'admin',
    role: 'admin',
    must_change_password: true,
    must_complete_google_setup: true,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderSetup(user: User) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(200, user)),
  );

  return render(
    <MemoryRouter initialEntries={['/setup']}>
      <AuthProvider>
        <Routes>
          <Route path="/setup" element={<Setup />} />
          <Route path="/setup/google" element={<div data-testid="setup-google-page">google</div>} />
          <Route path="/" element={<div data-testid="home-page">home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function setupFetchMocks(responses: Response[]) {
  const mock = vi.fn();
  responses.forEach((r) => mock.mockResolvedValueOnce(r));
  vi.stubGlobal('fetch', mock);
  return mock;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Setup (wizard step 1)', () => {
  it('renders the WizardSteps breadcrumb with Account=active', async () => {
    const user = makeUser();
    renderSetup(user);

    await waitFor(() => screen.getByText('Account'));
    // Account step should be active, Google and Family upcoming
    const activeSteps = document.querySelectorAll('[data-status="active"]');
    expect(activeSteps.length).toBeGreaterThan(0);
    const upcomingSteps = document.querySelectorAll('[data-status="upcoming"]');
    expect(upcomingSteps.length).toBe(2);
  });

  it('username input is disabled and pre-filled with current user username', async () => {
    const user = makeUser({ username: 'admin' });
    renderSetup(user);

    await waitFor(() => screen.getByDisplayValue('admin'));
    const usernameInput = screen.getByDisplayValue('admin') as HTMLInputElement;
    expect(usernameInput.disabled).toBe(true);
  });

  it('mismatched confirm password → shows error, does NOT call fetch for change-password', async () => {
    const user = makeUser();
    const fetchMock = setupFetchMocks([
      makeResponse(200, user), // /api/auth/me on mount
    ]);

    render(
      <MemoryRouter initialEntries={['/setup']}>
        <AuthProvider>
          <Routes>
            <Route path="/setup" element={<Setup />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText('Save and continue'));

    // Fill in passwords
    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'oldpassword' },
    });
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'newpassword1' },
    });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'differentpassword' },
    });

    fireEvent.click(screen.getByText('Save and continue'));

    await waitFor(() =>
      expect(screen.getByText('Passwords do not match')).not.toBeNull(),
    );

    // Only 1 fetch call (the /me call), no change-password call
    const changePwCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/change-password'),
    );
    expect(changePwCalls.length).toBe(0);
  });

  it('new password < 8 chars → shows error, does NOT call fetch for change-password', async () => {
    const user = makeUser();
    const fetchMock = setupFetchMocks([
      makeResponse(200, user), // /api/auth/me
    ]);

    render(
      <MemoryRouter initialEntries={['/setup']}>
        <AuthProvider>
          <Routes>
            <Route path="/setup" element={<Setup />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText('Save and continue'));

    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'oldpassword' },
    });
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'short' },
    });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'short' },
    });

    fireEvent.click(screen.getByText('Save and continue'));

    await waitFor(() =>
      expect(screen.getByText('Password must be at least 8 characters')).not.toBeNull(),
    );

    const changePwCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && c[0].includes('/change-password'),
    );
    expect(changePwCalls.length).toBe(0);
  });

  it('server returns 400 "must differ" → shows inline error', async () => {
    const user = makeUser();
    setupFetchMocks([
      makeResponse(200, user), // /api/auth/me
      makeResponse(400, { detail: 'New password must differ from current' }),
    ]);

    render(
      <MemoryRouter initialEntries={['/setup']}>
        <AuthProvider>
          <Routes>
            <Route path="/setup" element={<Setup />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText('Save and continue'));

    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'samepassword' },
    });
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'samepassword' },
    });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'samepassword' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Save and continue'));
    });

    await waitFor(() =>
      expect(screen.getByText('New password must differ from current')).not.toBeNull(),
    );
  });

  it('wrong current password → server 400 → shows inline error', async () => {
    const user = makeUser();
    setupFetchMocks([
      makeResponse(200, user), // /api/auth/me
      makeResponse(400, { detail: 'Current password is incorrect' }),
    ]);

    render(
      <MemoryRouter initialEntries={['/setup']}>
        <AuthProvider>
          <Routes>
            <Route path="/setup" element={<Setup />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText('Save and continue'));

    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'wrongpassword' },
    });
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'newpassword1' },
    });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'newpassword1' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Save and continue'));
    });

    await waitFor(() =>
      expect(screen.getByText('Current password is incorrect')).not.toBeNull(),
    );
  });

  it('valid submit → POSTs correct body, calls refresh(), navigates to /setup/google', async () => {
    const user = makeUser();
    const updatedUser = makeUser({ must_change_password: false });

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse(200, user))          // /api/auth/me (initial)
      .mockResolvedValueOnce(makeResponse(200, updatedUser))   // /api/auth/change-password
      .mockResolvedValueOnce(makeResponse(200, updatedUser));  // /api/auth/me (after refresh)

    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/setup']}>
        <AuthProvider>
          <Routes>
            <Route path="/setup" element={<Setup />} />
            <Route path="/setup/google" element={<div data-testid="setup-google-page">google</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText('Save and continue'));

    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'newpassword1' },
    });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'newpassword1' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Save and continue'));
    });

    // Verify POST body
    const changePwCall = fetchMock.mock.calls.find(
      (c) => typeof c[0] === 'string' && c[0].includes('/change-password'),
    );
    expect(changePwCall).toBeDefined();
    const body = JSON.parse(changePwCall![1].body as string);
    expect(body).toEqual({ current_password: 'admin', new_password: 'newpassword1' });
    // confirm_password is NOT sent to the backend
    expect(body.confirm_password).toBeUndefined();

    // Navigated to /setup/google
    await waitFor(() =>
      expect(screen.getByTestId('setup-google-page')).not.toBeNull(),
    );
  });

  it('must_change_password=false → shows "all done" page with button to /', async () => {
    const user = makeUser({ must_change_password: false, must_complete_google_setup: false });
    renderSetup(user);

    await waitFor(() =>
      expect(screen.getByText(/all done/i)).not.toBeNull(),
    );
    // Should show a link/button to go home
    expect(screen.getByText(/go to home/i)).not.toBeNull();
  });
});
