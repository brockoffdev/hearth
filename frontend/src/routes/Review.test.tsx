import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { Review } from './Review';
import type { Event, EventList } from '../lib/events';

// ---------------------------------------------------------------------------
// Module mock — vi.mock hoisted above imports, module resolved by Vitest
// ---------------------------------------------------------------------------

vi.mock('../lib/events', () => ({
  listEvents: vi.fn(),
  cellCropUrl: (id: number) => `/api/events/${id}/cell-crop`,
}));

import * as eventsModule from '../lib/events';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    upload_id: 5,
    family_member_id: null,
    family_member_name: 'Bryant',
    family_member_color_hex: '#2E5BA8',
    title: 'Soccer practice',
    start_dt: '2026-04-27T15:00:00Z',
    end_dt: null,
    all_day: false,
    location: null,
    notes: null,
    confidence: 0.72,
    status: 'pending_review',
    google_event_id: null,
    cell_crop_path: 'crops/1.jpg',
    has_cell_crop: true,
    raw_vlm_json: null,
    created_at: '2026-04-27T10:00:00Z',
    updated_at: '2026-04-27T10:00:00Z',
    published_at: null,
    ...overrides,
  };
}

const THREE_EVENTS: Event[] = [
  makeEvent({ id: 10, title: 'Soccer practice' }),
  makeEvent({ id: 11, title: 'Piano lesson' }),
  makeEvent({ id: 12, title: 'Dentist appointment' }),
];

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderReview() {
  return render(
    <MemoryRouter initialEntries={['/review']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/review" element={<Review />} />
            <Route path="/review/:id" element={<div data-testid="review-item-page">Review Item</div>} />
            <Route path="/uploads" element={<div data-testid="uploads-page">Uploads</div>} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Cleanup
// ---------------------------------------------------------------------------

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Review route — list', () => {
  it('test_review_list_renders_pending_review_events', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: THREE_EVENTS, total: 3 } as EventList);

    renderReview();

    await waitFor(() => {
      expect(screen.getByText('Soccer practice')).toBeInTheDocument();
    });
    expect(screen.getByText('Piano lesson')).toBeInTheDocument();
    expect(screen.getByText('Dentist appointment')).toBeInTheDocument();
  });

  it('test_review_list_count_in_header', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: THREE_EVENTS, total: 3 } as EventList);

    renderReview();

    await waitFor(() => {
      expect(screen.getByText('3 items')).toBeInTheDocument();
    });
  });

  it('test_review_list_empty_state', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);

    renderReview();

    await waitFor(() => {
      expect(screen.getByText(/all caught up — nothing to review/i)).toBeInTheDocument();
    });
    const viewLink = screen.getByText(/view uploads/i);
    expect(viewLink.closest('a')?.getAttribute('href')).toBe('/uploads');
  });

  it('test_review_list_loading_state', async () => {
    let resolvePromise!: (value: EventList) => void;
    const deferred = new Promise<EventList>((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(eventsModule.listEvents).mockReturnValue(deferred);

    renderReview();

    expect(screen.getByRole('img', { name: /loading review queue/i })).toBeInTheDocument();

    // Resolve so React doesn't warn about state updates after unmount
    resolvePromise({ items: [], total: 0 });
  });

  it('test_review_list_error_state', async () => {
    vi.mocked(eventsModule.listEvents).mockRejectedValue(new Error('Network error'));

    renderReview();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/failed to load review queue/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('test_review_list_error_state_retry_calls_listEvents_again', async () => {
    vi.mocked(eventsModule.listEvents)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue({ items: [], total: 0 } as EventList);

    renderReview();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText(/all caught up/i)).toBeInTheDocument();
    });

    expect(eventsModule.listEvents).toHaveBeenCalledTimes(2);
  });

  it('test_review_list_card_navigates_on_click', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({
      items: [makeEvent({ id: 55, title: 'Piano lesson' })],
      total: 1,
    } as EventList);

    renderReview();

    await waitFor(() => {
      expect(screen.getByText('Piano lesson')).toBeInTheDocument();
    });

    const card = screen.getByRole('button');
    fireEvent.click(card);

    await waitFor(() => {
      expect(screen.getByTestId('review-item-page')).toBeInTheDocument();
    });
  });
});
