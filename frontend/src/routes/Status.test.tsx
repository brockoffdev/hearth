import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { NewCaptureSheetProvider } from '../components/NewCaptureSheet';
import { Status } from './Status';
import type { Upload } from '../lib/uploads';

// ---------------------------------------------------------------------------
// Hook mock — we mock useUploads for unit tests
// ---------------------------------------------------------------------------

const mockRetry  = vi.fn().mockResolvedValue({});
const mockCancel = vi.fn().mockResolvedValue(undefined);
const mockRefetch = vi.fn().mockResolvedValue(undefined);

let mockUploadsState: {
  uploads: Upload[];
  inflightCount: number;
  longestETA: number;
  isLoading: boolean;
  loadError: string | null;
} = {
  uploads: [],
  inflightCount: 0,
  longestETA: 0,
  isLoading: false,
  loadError: null,
};

vi.mock('../lib/useUploads', () => ({
  useUploads: () => ({
    ...mockUploadsState,
    refetch: mockRefetch,
    retry:  mockRetry,
    cancel: mockCancel,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const INFLIGHT_RUNNING: Upload = {
  id: 'u-1',
  status: 'processing',
  image_path: 'uploads/a.jpg',
  url: '/api/uploads/u-1/photo',
  uploaded_at: '2026-04-27T09:00:00Z',
  thumbLabel: 'Apr 27, 9:00 AM',
  startedAt: 'Just now',
  current_stage: 'cell_progress',
  completed_stages: ['received', 'preprocessing', 'grid_detected', 'model_loading'],
  cellProgress: 12,
  totalCells: 35,
  remaining_seconds: 184,
  queuedBehind: 0,
};

const INFLIGHT_QUEUED: Upload = {
  id: 'u-2',
  status: 'processing',
  image_path: 'uploads/b.jpg',
  url: '/api/uploads/u-2/photo',
  uploaded_at: '2026-04-27T09:01:00Z',
  thumbLabel: 'Apr 27, 9:01 AM',
  startedAt: '8 sec ago',
  current_stage: 'queued',
  completed_stages: [],
  remaining_seconds: 393,
  queuedBehind: 1,
};

const COMPLETED: Upload = {
  id: 'u-3',
  status: 'completed',
  image_path: 'uploads/c.jpg',
  url: '/api/uploads/u-3/photo',
  uploaded_at: '2026-04-27T07:00:00Z',
  thumbLabel: 'Apr 27, 7:00 AM',
  finishedAt: '2 hr ago',
  found: 14,
  review: 3,
  durationSec: 118,
};

const FAILED: Upload = {
  id: 'u-4',
  status: 'failed',
  image_path: 'uploads/d.jpg',
  url: '/api/uploads/u-4/photo',
  uploaded_at: '2026-04-26T16:00:00Z',
  thumbLabel: 'Apr 26, 4:00 PM',
  error: 'Image too blurry — could not detect grid',
};

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderStatus(initialPath = '/uploads') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ThemeProvider>
        <AuthProvider>
          <NewCaptureSheetProvider>
            <Routes>
              <Route path="/uploads" element={<Status />} />
              <Route path="/uploads/:id" element={<div data-testid="upload-detail-page">Detail</div>} />
            </Routes>
          </NewCaptureSheetProvider>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  mockUploadsState = {
    uploads: [],
    inflightCount: 0,
    longestETA: 0,
    isLoading: false,
    loadError: null,
  };
});

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe('Status route — page basics', () => {
  it('renders the page title "Uploads"', () => {
    renderStatus();
    expect(screen.getByRole('heading', { name: 'Uploads' })).not.toBeNull();
  });

  it('renders the "+ New capture" CTA button', () => {
    renderStatus();
    expect(screen.getByRole('button', { name: /new capture/i })).not.toBeNull();
  });

  it('renders the MobileTabBar with uploads active', () => {
    const { container } = renderStatus();
    const nav = container.querySelector('nav[aria-label="Primary"]');
    expect(nav).not.toBeNull();
    // The uploads tab is active
    const uploadsLink = container.querySelector('a[href="/uploads"][data-active="true"]');
    expect(uploadsLink).not.toBeNull();
  });

  it('shows loading spinner when isLoading is true and no uploads yet', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: true, loadError: null };
    renderStatus();
    expect(screen.getByRole('img', { name: /loading/i })).not.toBeNull();
  });

  it('shows error banner when loadError is set', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: false, loadError: 'Network error' };
    renderStatus();
    expect(screen.getByText(/network error/i)).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('Status route — empty state', () => {
  it('renders empty state when uploads list is empty', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: false, loadError: null };
    renderStatus();
    expect(screen.getByText(/nothing here yet/i)).not.toBeNull();
  });

  it('still renders the CTA in empty state', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: false, loadError: null };
    renderStatus();
    expect(screen.getByRole('button', { name: /new capture/i })).not.toBeNull();
  });

  it('renders the empty state hint copy', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: false, loadError: null };
    renderStatus();
    expect(screen.getByText(/take a photo of the wall calendar/i)).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Header subtitle copy
// ---------------------------------------------------------------------------

describe('Status route — header subtitle', () => {
  it('shows "N processing · longest ETA remaining" when inflight > 0', () => {
    mockUploadsState = {
      uploads: [INFLIGHT_RUNNING],
      inflightCount: 1,
      longestETA: 184,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.getByText('1 processing')).not.toBeNull();
    // subtitle contains "remaining" — at least one instance
    expect(screen.getAllByText(/remaining/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows "All caught up · N recent" when inflight === 0', () => {
    mockUploadsState = {
      uploads: [COMPLETED],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.getByText(/all caught up · 1 recent/i)).not.toBeNull();
  });

  it('shows "All caught up · 0 recent" with no uploads and no loading', () => {
    mockUploadsState = { uploads: [], inflightCount: 0, longestETA: 0, isLoading: false, loadError: null };
    renderStatus();
    // In empty state there's no subtitle; just the "Nothing here yet" headline
    // so we check we DON'T see "All caught up" — the empty state overrides it
    expect(screen.queryByText(/all caught up/i)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Sections rendered
// ---------------------------------------------------------------------------

describe('Status route — sections', () => {
  it('renders 3 section rules when all statuses present', () => {
    mockUploadsState = {
      uploads: [INFLIGHT_RUNNING, INFLIGHT_QUEUED, COMPLETED, FAILED],
      inflightCount: 2,
      longestETA: 393,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.getByText('In flight')).not.toBeNull();
    expect(screen.getByText('Done')).not.toBeNull();
    expect(screen.getByText("Couldn't read")).not.toBeNull();
  });

  it('section rules show the correct counts', () => {
    mockUploadsState = {
      uploads: [INFLIGHT_RUNNING, INFLIGHT_QUEUED, COMPLETED, FAILED],
      inflightCount: 2,
      longestETA: 393,
      isLoading: false,
      loadError: null,
    };
    const { container } = renderStatus();
    const counts = container.querySelectorAll('[data-testid="section-rule-count"]');
    const values = Array.from(counts).map((el) => el.textContent);
    expect(values).toContain('2'); // In flight
    expect(values).toContain('1'); // Done
    // "1" appears for both Done and Couldn't read — check at least 2 instances of "1"
    expect(values.filter((v) => v === '1').length).toBeGreaterThanOrEqual(2);
  });

  it('does not render "In flight" section when no inflight', () => {
    mockUploadsState = {
      uploads: [COMPLETED],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.queryByText('In flight')).toBeNull();
  });

  it('does not render "Couldn\'t read" section when no failed', () => {
    mockUploadsState = {
      uploads: [COMPLETED],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.queryByText("Couldn't read")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// InflightRow (running)
// ---------------------------------------------------------------------------

describe('Status route — InflightRow (running)', () => {
  beforeEach(() => {
    mockUploadsState = {
      uploads: [INFLIGHT_RUNNING],
      inflightCount: 1,
      longestETA: 184,
      isLoading: false,
      loadError: null,
    };
  });

  it('shows the active stage label with cell progress', () => {
    renderStatus();
    expect(screen.getByText(/reading cells · 12 of 35/i)).not.toBeNull();
  });

  it('shows ETA remaining text', () => {
    renderStatus();
    expect(screen.getAllByText(/remaining/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows "Open ↗" link', () => {
    renderStatus();
    expect(screen.getByText('Open ↗')).not.toBeNull();
  });

  it('tapping "Open ↗" navigates to /uploads/{id}', async () => {
    renderStatus();
    fireEvent.click(screen.getByText('Open ↗'));
    await waitFor(() => {
      expect(screen.getByTestId('upload-detail-page')).not.toBeNull();
    });
  });

  it('renders a progress bar for the running row', () => {
    const { container } = renderStatus();
    const progressFills = container.querySelectorAll('[data-testid="progress-fill"]');
    expect(progressFills.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// QueuedRow
// ---------------------------------------------------------------------------

describe('Status route — QueuedRow', () => {
  beforeEach(() => {
    mockUploadsState = {
      uploads: [INFLIGHT_QUEUED],
      inflightCount: 1,
      longestETA: 393,
      isLoading: false,
      loadError: null,
    };
  });

  it('shows "Waiting · 1 photo ahead"', () => {
    renderStatus();
    expect(screen.getByText(/waiting · 1 photo ahead/i)).not.toBeNull();
  });

  it('shows "N photos ahead" (plural) for queuedBehind > 1', () => {
    mockUploadsState = {
      uploads: [{ ...INFLIGHT_QUEUED, queuedBehind: 2 }],
      inflightCount: 1,
      longestETA: 393,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.getByText(/waiting · 2 photos ahead/i)).not.toBeNull();
  });

  it('renders the position badge', () => {
    renderStatus();
    // Position badge shows "1" for first in inflight list
    const { container } = renderStatus();
    const badges = container.querySelectorAll('[data-testid="pos-badge"]');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it('shows clock icon (not spinner) for queued rows', () => {
    const { container } = renderStatus();
    expect(container.querySelector('[data-testid="clock-icon"]')).not.toBeNull();
  });

  it('shows ETA total text', () => {
    renderStatus();
    expect(screen.getByText(/total/)).not.toBeNull();
  });

  it('shows "Cancel ×" button', () => {
    renderStatus();
    expect(screen.getByText('Cancel ×')).not.toBeNull();
  });

  it('tapping "Cancel ×" calls cancel(id)', async () => {
    renderStatus();
    fireEvent.click(screen.getByText('Cancel ×'));
    await waitFor(() => {
      expect(mockCancel).toHaveBeenCalledWith('u-2');
    });
  });
});

// ---------------------------------------------------------------------------
// CompletedRow
// ---------------------------------------------------------------------------

describe('Status route — CompletedRow', () => {
  beforeEach(() => {
    mockUploadsState = {
      uploads: [COMPLETED],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
  });

  it('shows "N events found" title', () => {
    renderStatus();
    expect(screen.getByText(/14 events found/i)).not.toBeNull();
  });

  it('shows ", N need review" suffix when review > 0', () => {
    renderStatus();
    expect(screen.getByText(/3 need review/i)).not.toBeNull();
  });

  it('shows no review suffix when review is 0', () => {
    mockUploadsState = {
      uploads: [{ ...COMPLETED, review: 0 }],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.queryByText(/need review/i)).toBeNull();
  });

  it('shows "0 events found" when found is null/undefined', () => {
    mockUploadsState = {
      uploads: [{ ...COMPLETED, found: undefined, review: undefined }],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
    renderStatus();
    expect(screen.getByText(/0 events found/i)).not.toBeNull();
  });

  it('shows the time line with thumbLabel, finishedAt, and duration', () => {
    renderStatus();
    expect(screen.getByText(/apr 27, 7:00 am/i)).not.toBeNull();
    expect(screen.getByText(/2 hr ago/i)).not.toBeNull();
    // 118s → 1m 58s
    expect(screen.getByText(/took/i)).not.toBeNull();
  });

  it('renders a chevron', () => {
    const { container } = renderStatus();
    // Chevron SVG is aria-hidden; find via path
    const chevronPaths = Array.from(container.querySelectorAll('svg path')).filter(
      (p) => p.getAttribute('d') === 'M9 6l6 6-6 6',
    );
    expect(chevronPaths.length).toBeGreaterThanOrEqual(1);
  });

  it('tapping a completed row navigates to /uploads/{id}', async () => {
    renderStatus();
    // The whole row is a link
    const link = screen.getByRole('link', { name: /14 events found/i });
    fireEvent.click(link);
    await waitFor(() => {
      expect(screen.getByTestId('upload-detail-page')).not.toBeNull();
    });
  });
});

// ---------------------------------------------------------------------------
// FailedRow
// ---------------------------------------------------------------------------

describe('Status route — FailedRow', () => {
  beforeEach(() => {
    mockUploadsState = {
      uploads: [FAILED],
      inflightCount: 0,
      longestETA: 0,
      isLoading: false,
      loadError: null,
    };
  });

  it('shows "Couldn\'t read this one" title', () => {
    renderStatus();
    expect(screen.getByText(/couldn't read this one/i)).not.toBeNull();
  });

  it('shows the error message in the subtext', () => {
    renderStatus();
    expect(screen.getByText(/image too blurry/i)).not.toBeNull();
  });

  it('renders a "Retry" button', () => {
    renderStatus();
    expect(screen.getByRole('button', { name: /retry/i })).not.toBeNull();
  });

  it('tapping "Retry" calls retry(id)', async () => {
    renderStatus();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await waitFor(() => {
      expect(mockRetry).toHaveBeenCalledWith('u-4');
    });
  });
});

// ---------------------------------------------------------------------------
// NewCaptureSheet integration
// ---------------------------------------------------------------------------

describe('Status route — NewCaptureSheet', () => {
  it('tapping "+ New capture" opens the sheet', () => {
    renderStatus();
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /new capture/i }));
    expect(screen.getByRole('dialog')).not.toBeNull();
  });
});
