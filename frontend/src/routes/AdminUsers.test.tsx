import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { AdminUsers } from './AdminUsers';
import type { AdminUser } from '../lib/adminUsers';
import * as adminUsersLib from '../lib/adminUsers';

// ---------------------------------------------------------------------------
// Mock the adminUsers lib
// ---------------------------------------------------------------------------

vi.mock('../lib/adminUsers', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  patchUser: vi.fn(),
  deleteUser: vi.fn(),
}));

const mockedListUsers = vi.mocked(adminUsersLib.listUsers);
const mockedCreateUser = vi.mocked(adminUsersLib.createUser);
const mockedPatchUser = vi.mocked(adminUsersLib.patchUser);
const mockedDeleteUser = vi.mocked(adminUsersLib.deleteUser);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ADMIN_USER = {
  id: 1,
  username: 'testuser',
  role: 'admin' as const,
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

const REGULAR_USER = {
  id: 1,
  username: 'testuser',
  role: 'user' as const,
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

// testuser (id=1) is the current user (admin); alice (id=2) is another user.
const MOCK_USERS: AdminUser[] = [
  {
    id: 1,
    username: 'testuser',
    role: 'admin',
    must_change_password: false,
    must_complete_google_setup: false,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    username: 'alice',
    role: 'user',
    must_change_password: false,
    must_complete_google_setup: false,
    created_at: '2026-02-01T00:00:00Z',
  },
];

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
// Wrapper helpers
// ---------------------------------------------------------------------------

function renderAsAdmin() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(200, ADMIN_USER)),
  );
  return render(
    <MemoryRouter initialEntries={['/admin/users']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin/users" element={<AdminUsers />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

function renderAsRegular() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(200, REGULAR_USER)),
  );
  return render(
    <MemoryRouter initialEntries={['/admin/users']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin/users" element={<AdminUsers />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AdminUsers', () => {
  beforeEach(() => {
    mockedListUsers.mockResolvedValue(MOCK_USERS);
  });

  it('test_admin_users_lists_users', async () => {
    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByText('testuser')).not.toBeNull();
      expect(screen.getByText('alice')).not.toBeNull();
    });
  });

  it('test_admin_users_403_for_non_admin', async () => {
    mockedListUsers.mockResolvedValue([]);
    renderAsRegular();

    await waitFor(() => {
      expect(screen.getByText('403')).not.toBeNull();
      expect(screen.getByText(/admin access required/i)).not.toBeNull();
    });
  });

  it('test_admin_users_create_user_calls_api_and_prepends_to_list', async () => {
    const newUser: AdminUser = {
      id: 3,
      username: 'newbie',
      role: 'user',
      must_change_password: false,
      must_complete_google_setup: false,
      created_at: '2026-03-01T00:00:00Z',
    };
    mockedCreateUser.mockResolvedValue(newUser);

    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('testuser')).not.toBeNull());

    // Open modal
    fireEvent.click(screen.getByRole('button', { name: /add user/i }));

    // Fill form — use label text exactly to avoid ambiguity
    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'newbie' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'securepass' },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /create user/i }));
      await Promise.resolve();
    });

    expect(mockedCreateUser).toHaveBeenCalledWith({
      username: 'newbie',
      password: 'securepass',
      role: 'user',
    });

    await waitFor(() => {
      expect(screen.getByText('newbie')).not.toBeNull();
    });
  });

  it('test_admin_users_create_user_shows_inline_error_on_409', async () => {
    const { ApiError } = await import('../lib/api');
    mockedCreateUser.mockRejectedValue(new ApiError(409, 'Username already taken'));

    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('testuser')).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: /add user/i }));

    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'testuser' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'securepass' },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /create user/i }));
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.getByText(/username already taken/i)).not.toBeNull();
    });
  });

  it('test_admin_users_reset_password_calls_patch_with_new_password', async () => {
    const updated = { ...MOCK_USERS[1]! };
    mockedPatchUser.mockResolvedValue(updated);

    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('alice')).not.toBeNull());

    // Click "Reset password for alice" — aria-label on the button
    fireEvent.click(
      screen.getByRole('button', { name: 'Reset password for alice' }),
    );

    const pwField = document.querySelector(
      'input[aria-label="New password"]',
    ) as HTMLInputElement;
    expect(pwField).not.toBeNull();
    fireEvent.change(pwField, { target: { value: 'mynewpass' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^save$/i }));
      await Promise.resolve();
    });

    expect(mockedPatchUser).toHaveBeenCalledWith(2, { new_password: 'mynewpass' });
  });

  it('test_admin_users_toggle_role_calls_patch_with_new_role', async () => {
    const updated = { ...MOCK_USERS[1]!, role: 'admin' as const };
    mockedPatchUser.mockResolvedValue(updated);

    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('alice')).not.toBeNull());

    // "Toggle role for alice"
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Toggle role for alice' }));
      await Promise.resolve();
    });

    expect(mockedPatchUser).toHaveBeenCalledWith(2, { role: 'admin' });
  });

  it('test_admin_users_delete_user_calls_delete_after_confirm', async () => {
    mockedDeleteUser.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('alice')).not.toBeNull());

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Delete alice' }));
      await Promise.resolve();
    });

    expect(mockedDeleteUser).toHaveBeenCalledWith(2);
    await waitFor(() => {
      expect(screen.queryByText('alice')).toBeNull();
    });
  });

  it('test_admin_users_self_actions_disabled', async () => {
    // testuser (id=1) is the current user — their toggle-role and delete buttons must be disabled.
    renderAsAdmin();

    await waitFor(() => expect(screen.getByText('testuser')).not.toBeNull());

    const toggleSelf = screen.getByRole('button', {
      name: 'Toggle role for testuser',
    }) as HTMLButtonElement;
    const deleteSelf = screen.getByRole('button', {
      name: 'Delete testuser',
    }) as HTMLButtonElement;
    const toggleAlice = screen.getByRole('button', {
      name: 'Toggle role for alice',
    }) as HTMLButtonElement;
    const deleteAlice = screen.getByRole('button', {
      name: 'Delete alice',
    }) as HTMLButtonElement;

    expect(toggleSelf.disabled).toBe(true);
    expect(deleteSelf.disabled).toBe(true);
    expect(toggleAlice.disabled).toBe(false);
    expect(deleteAlice.disabled).toBe(false);
  });
});
