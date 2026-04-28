import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { Calendar } from './Calendar';
import type { Event, EventList } from '../lib/events';
import type { ApiFamilyMember } from '../lib/family';

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../lib/events', () => ({
  listEvents: vi.fn(),
}));

vi.mock('../lib/family', () => ({
  listFamily: vi.fn(),
}));

// Mock usePendingCount so it doesn't fire fetch requests in unit tests.
vi.mock('../lib/usePendingCount', () => ({
  usePendingCount: () => ({ count: 0, isLoading: false, refetch: vi.fn() }),
}));

import * as eventsModule from '../lib/events';
import * as familyModule from '../lib/family';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/**
 * Build an Event fixture. start_dt is ISO 8601; we use April 2026 as the
 * reference month since tests lock the clock to 2026-04-28.
 */
function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    upload_id: 5,
    family_member_id: 1,
    family_member_name: 'Bryant',
    family_member_color_hex: '#2E5BA8',
    title: 'Soccer practice',
    start_dt: '2026-04-15T15:00:00',
    end_dt: null,
    all_day: false,
    location: null,
    notes: null,
    confidence: 0.9,
    status: 'auto_published',
    google_event_id: 'gcal-1',
    cell_crop_path: null,
    has_cell_crop: false,
    raw_vlm_json: null,
    created_at: '2026-04-01T10:00:00Z',
    updated_at: '2026-04-01T10:00:00Z',
    published_at: '2026-04-01T10:00:00Z',
    ...overrides,
  };
}

const MOCK_FAMILY: ApiFamilyMember[] = [
  { id: 1, name: 'Bryant', color_hex_center: '#2E5BA8', google_calendar_id: null },
  { id: 2, name: 'Danya', color_hex_center: '#C0392B', google_calendar_id: null },
];

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderCalendar() {
  return render(
    <MemoryRouter initialEntries={['/calendar']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/review/:id" element={<div data-testid="review-item-page">Review Item</div>} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

/**
 * Get the desktop calendar container. Both desktop and mobile layouts are in
 * the DOM in jsdom (CSS @media not applied), so we scope desktop-only
 * assertions with within(desktop).
 */
function getDesktop() {
  return screen.getByTestId('desktop-calendar');
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

describe('Calendar route', () => {
  /**
   * Lock the tests to April 2026 so the component initialises to the same
   * month regardless of when the test suite runs. We only fake Date (not
   * timers) so waitFor's internal polling still works.
   */
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-04-28T12:00:00') });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── 1. Month name + year ───────────────────────────────────────────────

  it('test_calendar_renders_month_name_and_year', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    await waitFor(() => {
      expect(within(getDesktop()).getByText('April')).toBeInTheDocument();
    });
    expect(within(getDesktop()).getByText('2026')).toBeInTheDocument();
  });

  // ── 2. Weekday headers ─────────────────────────────────────────────────

  it('test_calendar_renders_weekday_headers', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    // Weekday headers are always rendered regardless of event state.
    // We wait for loading to settle by checking the spinner is gone.
    await waitFor(() => {
      expect(within(getDesktop()).queryByRole('img', { name: /loading calendar/i })).not.toBeInTheDocument();
    });

    const desktop = getDesktop();
    for (const day of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      expect(within(desktop).getByText(day)).toBeInTheDocument();
    }
  });

  // ── 3. Events in correct cells ─────────────────────────────────────────

  it('test_calendar_renders_events_in_correct_cells', async () => {
    const events: Event[] = [
      makeEvent({ id: 10, title: 'Piano lesson', start_dt: '2026-04-05T10:00:00' }),
      makeEvent({ id: 11, title: 'Soccer practice', start_dt: '2026-04-15T14:00:00' }),
      makeEvent({ id: 12, title: 'Dentist appointment', start_dt: '2026-04-22T09:00:00' }),
    ];
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: events, total: 3 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(within(desktop).getByText('Piano lesson')).toBeInTheDocument();
    });
    expect(within(desktop).getByText('Soccer practice')).toBeInTheDocument();
    expect(within(desktop).getByText('Dentist appointment')).toBeInTheDocument();
  });

  // ── 4. Today cell emphasis ─────────────────────────────────────────────

  it('test_calendar_today_cell_has_today_emphasis', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    // today-cell is inside the desktop MonthGrid, always rendered
    await waitFor(() => {
      expect(screen.getByTestId('today-cell')).toBeInTheDocument();
    });

    const todayCell = screen.getByTestId('today-cell');
    expect(todayCell.getAttribute('aria-current')).toBe('date');
    expect(within(todayCell).getByText('Today')).toBeInTheDocument();
  });

  // ── 5. Click event → navigate to /review/:id ──────────────────────────

  it('test_calendar_click_event_navigates_to_review', async () => {
    const events: Event[] = [
      makeEvent({ id: 99, title: 'Drama club', start_dt: '2026-04-10T16:00:00' }),
    ];
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: events, total: 1 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(within(desktop).getByText('Drama club')).toBeInTheDocument();
    });

    // Click the desktop event pill
    fireEvent.click(within(desktop).getByText('Drama club'));

    await waitFor(() => {
      expect(screen.getByTestId('review-item-page')).toBeInTheDocument();
    });
  });

  // ── 6. Prev/Next/Today navigation ─────────────────────────────────────

  it('test_calendar_prev_next_navigation', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();

    await waitFor(() => {
      expect(within(desktop).queryByRole('img', { name: /loading calendar/i })).not.toBeInTheDocument();
    });

    // Start: April 2026
    expect(within(desktop).getByText('April')).toBeInTheDocument();

    // Prev → March 2026
    fireEvent.click(within(desktop).getByRole('button', { name: /previous month/i }));
    expect(within(desktop).getByText('March')).toBeInTheDocument();

    // Next → April 2026
    fireEvent.click(within(desktop).getByRole('button', { name: /next month/i }));
    expect(within(desktop).getByText('April')).toBeInTheDocument();

    // Next again → May 2026
    fireEvent.click(within(desktop).getByRole('button', { name: /next month/i }));
    expect(within(desktop).getByText('May')).toBeInTheDocument();

    // Today → back to April 2026
    fireEvent.click(within(desktop).getByRole('button', { name: 'Today' }));
    expect(within(desktop).getByText('April')).toBeInTheDocument();
  });

  // ── 7. Overflow "+N more" indicator ────────────────────────────────────

  it('test_calendar_more_indicator_when_overflow', async () => {
    const events: Event[] = Array.from({ length: 5 }, (_, i) =>
      makeEvent({ id: i + 1, title: `Event ${i + 1}`, start_dt: '2026-04-07T09:00:00' }),
    );
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: events, total: 5 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(within(desktop).getByText('+2 more')).toBeInTheDocument();
    });
  });

  // ── 8. Empty state ─────────────────────────────────────────────────────

  it('test_calendar_empty_state', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(
        within(desktop).getByText(/no events yet — upload a photo to get started/i),
      ).toBeInTheDocument();
    });
  });

  // ── 9. Error state + retry ─────────────────────────────────────────────

  it('test_calendar_error_state', async () => {
    vi.mocked(eventsModule.listEvents).mockRejectedValue(new Error('Network error'));
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(within(desktop).getByRole('alert')).toBeInTheDocument();
    });

    expect(within(desktop).getByText(/failed to load events/i)).toBeInTheDocument();
    const retryBtn = within(desktop).getByRole('button', { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();

    // Clicking retry should re-fetch and resolve to empty state
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(
        within(desktop).getByText(/no events yet — upload a photo to get started/i),
      ).toBeInTheDocument();
    });
  });

  // ── 10. Family legend ──────────────────────────────────────────────────

  it('test_calendar_legend_renders_family_members', async () => {
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderCalendar();

    const desktop = getDesktop();
    await waitFor(() => {
      expect(within(desktop).getByText('Bryant')).toBeInTheDocument();
    });
    expect(within(desktop).getByText('Danya')).toBeInTheDocument();
  });
});
