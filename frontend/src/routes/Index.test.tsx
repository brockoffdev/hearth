import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { NewCaptureSheetProvider } from '../components/NewCaptureSheet';
import { Index } from './Index';
import type { User } from '../auth/AuthProvider';
import type { UploadSummary } from '../lib/uploads';

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

const MOCK_UPLOADS: UploadSummary[] = [
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
              <Route path="/uploads/:id" element={<div data-testid="upload-detail-page">Detail</div>} />
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
  it('renders greeting with the authenticated username', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, [])),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );
  });

  it('renders the "Take a photo" CTA as a button that opens the capture sheet', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, [])),
    );

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

  it('shows loading skeleton rows before data loads', async () => {
    // Stub fetch: /me resolves instantly, /api/uploads never resolves
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockReturnValueOnce(new Promise(() => {})),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/hi,\s*testuser/i)).not.toBeNull(),
    );

    // Skeleton rows should be present
    const skeletons = document.querySelectorAll('[data-testid="skeleton-row"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows empty state when API returns empty array', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, [])),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/no photos yet/i)).not.toBeNull(),
    );
  });

  it('renders 3 upload rows when API returns 3 uploads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, MOCK_UPLOADS)),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('Done')).not.toBeNull(),
    );

    expect(screen.getByText('Done')).not.toBeNull();
    expect(screen.getByText('Processing')).not.toBeNull();
    expect(screen.getByText('Failed')).not.toBeNull();
  });

  it('shows error banner when the API request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(500, { detail: 'Server error' })),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/couldn't load/i)).not.toBeNull(),
    );
  });

  it('each upload row links to /uploads/:id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, MOCK_UPLOADS)),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText('Done')).not.toBeNull(),
    );

    const rowLinks = document.querySelectorAll('a[href^="/uploads/"]');
    expect(rowLinks.length).toBe(3);
    expect(rowLinks[0]?.getAttribute('href')).toBe('/uploads/1');
    expect(rowLinks[1]?.getAttribute('href')).toBe('/uploads/2');
    expect(rowLinks[2]?.getAttribute('href')).toBe('/uploads/3');
  });

  it('shows last-sync indicator after data loads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, MOCK_UPLOADS)),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByText(/last sync/i)).not.toBeNull(),
    );
  });

  it('truncates list to 10 most recent when more than 10 uploads returned', async () => {
    const manyUploads: UploadSummary[] = Array.from({ length: 15 }, (_, i) => ({
      id: String(i + 1),
      status: 'completed' as const,
      image_path: `uploads/${i + 1}.jpg`,
      uploaded_at: new Date(Date.now() - i * 60_000).toISOString(),
      url: `/api/uploads/${i + 1}/photo`,
      thumbLabel: `Apr 27, ${i}:00 AM`,
    }));

    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, manyUploads)),
    );

    renderIndex();

    await waitFor(() => {
      const rowLinks = document.querySelectorAll('a[href^="/uploads/"]');
      expect(rowLinks.length).toBe(10);
    });
  });

  it('renders the wordmark in the header', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, [])),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getAllByText('hearth').length).toBeGreaterThanOrEqual(1),
    );
  });

  it('renders a log out button', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(makeResponse(200, MOCK_USER))
        .mockResolvedValueOnce(makeResponse(200, [])),
    );

    renderIndex();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /log out/i })).not.toBeNull(),
    );
  });
});
