import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { NewCaptureSheetProvider } from '../components/NewCaptureSheet';
import { Index } from './Index';
import type { User } from '../auth/AuthProvider';
import type { Upload } from '../lib/uploads';
import { useUploads } from '../lib/useUploads';

// ---------------------------------------------------------------------------
// Mock useUploads — all Index tests use this instead of raw fetch
// ---------------------------------------------------------------------------

vi.mock('../lib/useUploads', () => ({
  useUploads: vi.fn(),
}));

// Mock useGoogleHealth so it doesn't fire a real fetch in unit tests.
vi.mock('../lib/useGoogleHealth', () => ({
  useGoogleHealth: () => ({
    connected: true,
    broken_reason: null,
    broken_at: null,
    isLoading: false,
    refetch: vi.fn(),
  }),
}));

// Mock usePendingCount so it doesn't fire fetch requests in unit tests.
vi.mock('../lib/usePendingCount', () => ({
  usePendingCount: () => ({ count: 0, isLoading: false, refetch: vi.fn() }),
}));

const mocked = vi.mocked(useUploads);

function makeUploadsResult(overrides: Partial<ReturnType<typeof useUploads>> = {}): ReturnType<typeof useUploads> {
  return {
    uploads: [],
    inflightCount: 0,
    longestETA: 0,
    isLoading: false,
    loadError: null,
    lastFetchedAt: new Date(),
    refetch: vi.fn(),
    retry: vi.fn(),
    cancel: vi.fn(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: User = {
  id: 1,
  username: 'testuser',
  role: 'admin',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

const MOCK_UPLOADS: Upload[] = [
  {
    id: '1',
    status: 'completed',
    image_path: 'uploads/abc.jpg',
    uploaded_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    url: '/api/uploads/1/photo',
    thumbLabel: 'Apr 27, 10:00 AM',
  },
  {
    id: '2',
    status: 'processing',
    image_path: 'uploads/def.jpg',
    uploaded_at: new Date(Date.now() - 30_000).toISOString(),
    url: '/api/uploads/2/photo',
    thumbLabel: 'Apr 27, 10:01 AM',
    remaining_seconds: 45,
  },
  {
    id: '3',
    status: 'failed',
    image_path: 'uploads/ghi.jpg',
    uploaded_at: new Date(Date.now() - 10_000).toISOString(),
    url: '/api/uploads/3/photo',
    thumbLabel: 'Apr 27, 10:02 AM',
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
});

const NON_ADMIN_USER: User = {
  id: 2,
  username: 'plainuser',
  role: 'user',
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function renderIndex() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <ThemeProvider>
        <AuthProvider>
          <NewCaptureSheetProvider>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/upload" element={<div data-testid="upload-page">Upload</div>} />
              <Route path="/uploads" element={<div data-testid="uploads-page">Uploads</div>} />
              <Route path="/uploads/:id" element={<div data-testid="upload-detail-page">Detail</div>} />
              <Route path="/admin" element={<div data-testid="admin-page">Admin</div>} />
            </Routes>
          </NewCaptureSheetProvider>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Index (MobileHome)', () => {
  beforeEach(() => {
    // Default: authenticated user via /me fetch; useUploads mocked
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, MOCK_USER)),
    );
    mocked.mockReturnValue(makeUploadsResult());
  });

  it('renders greeting with the authenticated username', async () => {
    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );
  });

  it('renders the "Take a photo" CTA as a button that opens the capture sheet', async () => {
    renderIndex();

    await waitFor(() => expect(screen.getByText(/take a photo/i)).not.toBeNull());

    // CTA is now a button (not a link)
    const ctaBtn = screen.getByRole('button', { name: /take a photo/i });
    expect(ctaBtn).not.toBeNull();

    // Clicking it opens the NewCaptureSheet (dialog)
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(ctaBtn);
    expect(screen.getByRole('dialog')).not.toBeNull();
  });

  it('shows loading skeleton rows when isLoading is true', async () => {
    mocked.mockReturnValue(makeUploadsResult({ isLoading: true, lastFetchedAt: null }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );

    const skeletons = document.querySelectorAll('[data-testid="skeleton-row"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows empty state when uploads is empty array', async () => {
    mocked.mockReturnValue(makeUploadsResult({ uploads: [], isLoading: false }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/no photos yet/i)).not.toBeNull(),
    );
  });

  it('renders 3 upload rows when hook returns 3 uploads', async () => {
    mocked.mockReturnValue(makeUploadsResult({ uploads: MOCK_UPLOADS }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('Done')).not.toBeNull(),
    );

    expect(screen.getByText('Done')).not.toBeNull();
    expect(screen.getByText('Processing')).not.toBeNull();
    expect(screen.getByText('Failed')).not.toBeNull();
  });

  it('shows error banner when loadError is set', async () => {
    mocked.mockReturnValue(makeUploadsResult({ loadError: 'Server error', isLoading: false }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/couldn't load/i)).not.toBeNull(),
    );
  });

  it('each upload row links to /uploads/:id', async () => {
    mocked.mockReturnValue(makeUploadsResult({ uploads: MOCK_UPLOADS }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('Done')).not.toBeNull(),
    );

    const rowLinks = document.querySelectorAll('a[href^="/uploads/"]');
    // 3 upload rows + 1 InflightBanner (not shown: inflightCount=0) + UploadsLink
    // UploadsLink links to /uploads, row links link to /uploads/1, /uploads/2, /uploads/3
    const uploadRowLinks = Array.from(rowLinks).filter(
      (a) => a.getAttribute('href')?.match(/\/uploads\/\d+$/),
    );
    expect(uploadRowLinks.length).toBe(3);
    expect(uploadRowLinks[0]?.getAttribute('href')).toBe('/uploads/1');
    expect(uploadRowLinks[1]?.getAttribute('href')).toBe('/uploads/2');
    expect(uploadRowLinks[2]?.getAttribute('href')).toBe('/uploads/3');
  });

  it('shows last-sync indicator after data loads (when lastFetchedAt is set)', async () => {
    mocked.mockReturnValue(makeUploadsResult({ lastFetchedAt: new Date() }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/last sync/i)).not.toBeNull(),
    );
  });

  it('does not show last-sync indicator when lastFetchedAt is null', async () => {
    mocked.mockReturnValue(makeUploadsResult({ lastFetchedAt: null }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );

    expect(screen.queryByText(/last sync/i)).toBeNull();
  });

  it('truncates list to 10 most recent when more than 10 uploads returned', async () => {
    const manyUploads: Upload[] = Array.from({ length: 15 }, (_, i) => ({
      id: String(i + 1),
      status: 'completed' as const,
      image_path: `uploads/${i + 1}.jpg`,
      uploaded_at: new Date(Date.now() - i * 60_000).toISOString(),
      url: `/api/uploads/${i + 1}/photo`,
      thumbLabel: `Apr 27, ${i}:00 AM`,
    }));

    mocked.mockReturnValue(makeUploadsResult({ uploads: manyUploads }));

    renderIndex();

    await waitFor(() => {
      const rowLinks = document.querySelectorAll('a[href^="/uploads/"]');
      // 10 upload rows + 1 UploadsLink (/uploads) = filter to /uploads/:id pattern
      const uploadRowLinks = Array.from(rowLinks).filter(
        (a) => a.getAttribute('href')?.match(/\/uploads\/\d+$/),
      );
      expect(uploadRowLinks.length).toBe(10);
    });
  });

  it('renders the wordmark in the header', async () => {
    renderIndex();

    await waitFor(() =>
      expect(screen.getAllByText('hearth').length).toBeGreaterThanOrEqual(1),
    );
  });

  it('renders a log out button', async () => {
    renderIndex();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /log out/i })).not.toBeNull(),
    );
  });

  // -------------------------------------------------------------------------
  // InflightBanner tests
  // -------------------------------------------------------------------------

  it('does not render InflightBanner when inflightCount is 0', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 0 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );

    expect(screen.queryByText(/photo.*processing/i)).toBeNull();
  });

  it('renders InflightBanner with singular text when inflightCount is 1', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 1, longestETA: 45 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('1 photo processing…')).not.toBeNull(),
    );
  });

  it('renders InflightBanner with plural text when inflightCount is 2', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 2, longestETA: 184 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('2 photos processing…')).not.toBeNull(),
    );
  });

  it('InflightBanner shows ETA subtext', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 1, longestETA: 45 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/remaining/i)).not.toBeNull(),
    );
  });

  it('InflightBanner links to /uploads', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 2, longestETA: 60 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('2 photos processing…')).not.toBeNull(),
    );

    const bannerLink = document.querySelector('a[href="/uploads"][data-testid="inflight-banner"]');
    expect(bannerLink).not.toBeNull();
  });

  // -------------------------------------------------------------------------
  // UploadsLink tests
  // -------------------------------------------------------------------------

  it('always renders UploadsLink', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 0 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('View all uploads')).not.toBeNull(),
    );
  });

  it('UploadsLink links to /uploads', async () => {
    mocked.mockReturnValue(makeUploadsResult());

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('View all uploads')).not.toBeNull(),
    );

    const link = screen.getByText('View all uploads').closest('a');
    expect(link?.getAttribute('href')).toBe('/uploads');
  });

  it('UploadsLink has active class when inflightCount > 0', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 2 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('View all uploads')).not.toBeNull(),
    );

    const link = screen.getByText('View all uploads').closest('a');
    expect(link?.className).toMatch(/uploadsLinkActive/);
  });

  it('UploadsLink does not have active class when inflightCount is 0', async () => {
    mocked.mockReturnValue(makeUploadsResult({ inflightCount: 0 }));

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('View all uploads')).not.toBeNull(),
    );

    const link = screen.getByText('View all uploads').closest('a');
    expect(link?.className).not.toMatch(/uploadsLinkActive/);
  });

  // -------------------------------------------------------------------------
  // Admin link tests
  // -------------------------------------------------------------------------

  it('admin users see the admin link', async () => {
    // MOCK_USER has role='admin' — set in beforeEach fetch stub
    mocked.mockReturnValue(makeUploadsResult());

    renderIndex();

    await waitFor(() =>
      expect(screen.getByTestId('admin-link')).not.toBeNull(),
    );

    const link = screen.getByTestId('admin-link');
    expect(link.getAttribute('href')).toBe('/admin');
  });

  it('non-admin users do not see the admin link', async () => {
    // Override fetch to return a non-admin user for this test
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeResponse(200, NON_ADMIN_USER)),
    );
    mocked.mockReturnValue(makeUploadsResult());

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*plainuser/i)).not.toBeNull(),
    );

    expect(screen.queryByTestId('admin-link')).toBeNull();
  });
});
