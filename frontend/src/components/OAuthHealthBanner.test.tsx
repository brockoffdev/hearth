import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { OAuthHealthBanner } from './OAuthHealthBanner';

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockUseAuth = vi.fn();
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => mockUseAuth() }));

const mockUseGoogleHealth = vi.fn();
vi.mock('../lib/useGoogleHealth', () => ({ useGoogleHealth: () => mockUseGoogleHealth() }));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderBanner() {
  return render(
    <MemoryRouter>
      <OAuthHealthBanner />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OAuthHealthBanner', () => {
  it('test_banner_renders_nothing_when_connected', () => {
    mockUseGoogleHealth.mockReturnValue({
      connected: true,
      broken_reason: null,
      broken_at: null,
      isLoading: false,
      refetch: vi.fn(),
    });
    mockUseAuth.mockReturnValue({
      state: { status: 'authenticated', user: { role: 'admin' } },
    });

    const { container } = renderBanner();

    expect(container.firstChild).toBeNull();
  });

  it('test_banner_renders_warning_when_disconnected', () => {
    mockUseGoogleHealth.mockReturnValue({
      connected: false,
      broken_reason: 'revoked',
      broken_at: '2026-04-28T10:00:00Z',
      isLoading: false,
      refetch: vi.fn(),
    });
    mockUseAuth.mockReturnValue({
      state: { status: 'authenticated', user: { role: 'user' } },
    });

    renderBanner();

    expect(screen.getByRole('alert')).not.toBeNull();
    expect(screen.getByText(/Google Calendar disconnected/)).not.toBeNull();
  });

  it('test_admin_sees_reconnect_link', () => {
    mockUseGoogleHealth.mockReturnValue({
      connected: false,
      broken_reason: 'expired',
      broken_at: null,
      isLoading: false,
      refetch: vi.fn(),
    });
    mockUseAuth.mockReturnValue({
      state: { status: 'authenticated', user: { role: 'admin' } },
    });

    renderBanner();

    const btn = screen.getByRole('button', { name: /Reconnect/i });
    expect(btn).not.toBeNull();
    fireEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/setup/google');
  });

  it('test_non_admin_sees_ask_admin_copy', () => {
    mockUseGoogleHealth.mockReturnValue({
      connected: false,
      broken_reason: 'expired',
      broken_at: null,
      isLoading: false,
      refetch: vi.fn(),
    });
    mockUseAuth.mockReturnValue({
      state: { status: 'authenticated', user: { role: 'user' } },
    });

    renderBanner();

    expect(screen.getByText(/Ask your admin to reconnect/)).not.toBeNull();
    expect(screen.queryByRole('button', { name: /Reconnect/i })).toBeNull();
  });
});
