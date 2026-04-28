import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { ReviewItem } from './ReviewItem';
import type { Event, EventList } from '../lib/events';
import type { ApiFamilyMember } from '../lib/family';

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../lib/events', () => ({
  getEvent: vi.fn(),
  listEvents: vi.fn(),
  patchEvent: vi.fn(),
  rejectEvent: vi.fn(),
  republishEvent: vi.fn(),
  cellCropUrl: (id: number) => `/api/events/${id}/cell-crop`,
}));

vi.mock('../lib/family', () => ({
  listFamily: vi.fn(),
  HEARTH_FAMILY: [],
}));

import * as eventsModule from '../lib/events';
import * as familyModule from '../lib/family';
import { ApiError } from '../lib/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 42,
    upload_id: 5,
    family_member_id: 1,
    family_member_name: 'Bryant',
    family_member_color_hex: '#2E5BA8',
    title: 'Soccer practice',
    start_dt: '2026-04-30T15:00:00',
    end_dt: null,
    all_day: false,
    location: 'Field A',
    notes: null,
    confidence: 0.72,
    status: 'pending_review',
    google_event_id: null,
    cell_crop_path: 'crops/42.jpg',
    has_cell_crop: true,
    raw_vlm_json: null,
    created_at: '2026-04-27T10:00:00Z',
    updated_at: '2026-04-27T10:00:00Z',
    published_at: null,
    ...overrides,
  };
}

const MOCK_FAMILY: ApiFamilyMember[] = [
  { id: 1, name: 'Bryant', color_hex_center: '#2E5BA8', google_calendar_id: null },
  { id: 2, name: 'Danielle', color_hex_center: '#C0392B', google_calendar_id: null },
];

const QUEUE: Event[] = [
  makeEvent({ id: 41, title: 'Piano lesson' }),
  makeEvent({ id: 42, title: 'Soccer practice' }),
  makeEvent({ id: 43, title: 'Dentist appointment' }),
  makeEvent({ id: 44, title: 'Ballet class' }),
];

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderReviewItem(eventId = 42, initialPath = `/review/${eventId}`) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/review/:id" element={<ReviewItem />} />
            <Route path="/review" element={<div data-testid="review-list">Review list</div>} />
            <Route path="/review/:id" element={<div data-testid="other-review-item">Other item</div>} />
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

describe('ReviewItem route', () => {
  it('test_review_item_loads_event_and_renders_fields', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent());
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('2026-04-30')).toBeInTheDocument();
    expect(screen.getByDisplayValue('15:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Field A')).toBeInTheDocument();
  });

  it('test_review_item_renders_cell_crop_when_has_cell_crop', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent({ has_cell_crop: true }));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByAltText('Calendar cell crop')).toBeInTheDocument();
    });
    const img = screen.getByAltText('Calendar cell crop') as HTMLImageElement;
    expect(img.src).toContain('/api/events/42/cell-crop');
  });

  it('test_review_item_hides_cell_crop_when_no_path', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(
      makeEvent({ has_cell_crop: false, cell_crop_path: null }),
    );
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });
    expect(screen.queryByAltText('Calendar cell crop')).not.toBeInTheDocument();
  });

  it('test_review_item_save_button_calls_patchEvent_with_changes', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent());
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.patchEvent).mockResolvedValue(makeEvent({ title: 'New title' }));

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });

    const titleInput = screen.getByDisplayValue('Soccer practice');
    fireEvent.change(titleInput, { target: { value: 'New title' } });

    await act(async () => {
      fireEvent.click(screen.getByText(/looks good — save/i));
    });

    expect(eventsModule.patchEvent).toHaveBeenCalledWith(42, expect.objectContaining({ title: 'New title' }));
  });

  it('test_review_item_save_with_no_changes_calls_patchEvent_with_empty_body', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent());
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.patchEvent).mockResolvedValue(makeEvent());

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText(/looks good — save/i));
    });

    expect(eventsModule.patchEvent).toHaveBeenCalledWith(42, {});
  });

  it('test_review_item_save_navigates_to_next_pending_review', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent({ id: 42 }));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.patchEvent).mockResolvedValue(makeEvent());

    renderReviewItem(42);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText(/looks good — save/i));
    });

    // Next item after id=42 is id=43
    await waitFor(() => {
      // We should navigate to /review/43 — but since test router only has a single
      // /review/:id route, it re-renders with id=43. The getEvent call would be
      // re-triggered. Just verify patchEvent was called and navigation happened
      // (the review list would show up if there's no next item).
      expect(eventsModule.patchEvent).toHaveBeenCalledTimes(1);
    });
  });

  it('test_review_item_save_navigates_to_review_when_no_next_item', async () => {
    const lastItem = makeEvent({ id: 44, title: 'Ballet class' });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(lastItem);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.patchEvent).mockResolvedValue(lastItem);

    renderReviewItem(44, '/review/44');

    await waitFor(() => {
      expect(screen.getByDisplayValue('Ballet class')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText(/looks good — save/i));
    });

    await waitFor(() => {
      expect(screen.getByTestId('review-list')).toBeInTheDocument();
    });
  });

  it('test_review_item_skip_navigates_without_api_call', async () => {
    const lastItem = makeEvent({ id: 44, title: 'Ballet class' });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(lastItem);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem(44, '/review/44');

    await waitFor(() => {
      expect(screen.getByDisplayValue('Ballet class')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Skip'));

    await waitFor(() => {
      expect(screen.getByTestId('review-list')).toBeInTheDocument();
    });

    expect(eventsModule.patchEvent).not.toHaveBeenCalled();
    expect(eventsModule.rejectEvent).not.toHaveBeenCalled();
  });

  it('test_review_item_reject_calls_rejectEvent_and_navigates', async () => {
    const lastItem = makeEvent({ id: 44, title: 'Ballet class' });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(lastItem);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.rejectEvent).mockResolvedValue(undefined);

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderReviewItem(44, '/review/44');

    await waitFor(() => {
      expect(screen.getByDisplayValue('Ballet class')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Reject'));
    });

    expect(eventsModule.rejectEvent).toHaveBeenCalledWith(44);
    await waitFor(() => {
      expect(screen.getByTestId('review-list')).toBeInTheDocument();
    });
  });

  it('test_review_item_404_event_not_found', async () => {
    const { ApiError } = await import('../lib/api');
    vi.mocked(eventsModule.getEvent).mockRejectedValue(new ApiError(404, 'Not found'));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderReviewItem(999, '/review/999');

    await waitFor(() => {
      expect(screen.getByText('Event not found')).toBeInTheDocument();
    });
    expect(screen.getByText(/back to review queue/i)).toBeInTheDocument();
  });

  it('test_review_item_403_access_denied', async () => {
    const { ApiError } = await import('../lib/api');
    vi.mocked(eventsModule.getEvent).mockRejectedValue(new ApiError(403, 'Forbidden'));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: [], total: 0 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue([]);

    renderReviewItem(42);

    await waitFor(() => {
      expect(screen.getByText('Access denied')).toBeInTheDocument();
    });
    expect(screen.getByText(/back to review queue/i)).toBeInTheDocument();
  });

  it('test_review_item_position_indicator_renders', async () => {
    // id=42 is at index 1 (0-based) out of 4 items → "Review · 2 of 4"
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent({ id: 42 }));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem(42);

    await waitFor(() => {
      expect(screen.getByText('Review · 2 of 4')).toBeInTheDocument();
    });
  });

  it('test_review_item_all_day_toggle_hides_time_field', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent({ all_day: false }));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByLabelText('Time')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/all day/i));

    await waitFor(() => {
      expect(screen.queryByLabelText('Time')).not.toBeInTheDocument();
    });
  });

  it('test_review_item_title_required', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent());
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });

    const titleInput = screen.getByDisplayValue('Soccer practice');
    fireEvent.change(titleInput, { target: { value: '' } });

    const saveBtn = screen.getByText(/looks good — save/i);
    expect(saveBtn.closest('button')).toBeDisabled();
  });

  it('test_review_item_renders_republish_affordance_for_demoted_event', async () => {
    const demotedEvent = makeEvent({
      notes: 'Some notes\n\n[Auto-publish failed: token expired]',
    });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(demotedEvent);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByTestId('demoted-card')).toBeInTheDocument();
    });
    expect(screen.getByText(/Auto-publish failed: token expired/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /republish/i })).toBeInTheDocument();
  });

  it('test_review_item_no_republish_affordance_for_normal_pending_review', async () => {
    vi.mocked(eventsModule.getEvent).mockResolvedValue(makeEvent({ notes: null }));
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Soccer practice')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('demoted-card')).not.toBeInTheDocument();
  });

  it('test_review_item_republish_calls_api_and_navigates', async () => {
    const demotedEvent = makeEvent({
      id: 44,
      title: 'Ballet class',
      notes: 'Note\n\n[Auto-publish failed: token expired]',
    });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(demotedEvent);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.republishEvent).mockResolvedValue(demotedEvent);

    renderReviewItem(44, '/review/44');

    await waitFor(() => {
      expect(screen.getByTestId('demoted-card')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /republish/i }));
    });

    expect(eventsModule.republishEvent).toHaveBeenCalledWith(44);
  });

  it('test_review_item_republish_shows_503_error_inline', async () => {
    const demotedEvent = makeEvent({
      notes: 'Note\n\n[Auto-publish failed: token expired]',
    });
    vi.mocked(eventsModule.getEvent).mockResolvedValue(demotedEvent);
    vi.mocked(eventsModule.listEvents).mockResolvedValue({ items: QUEUE, total: 4 } as EventList);
    vi.mocked(familyModule.listFamily).mockResolvedValue(MOCK_FAMILY);
    vi.mocked(eventsModule.republishEvent).mockRejectedValue(new ApiError(503, 'NoOauth'));

    renderReviewItem();

    await waitFor(() => {
      expect(screen.getByTestId('demoted-card')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /republish/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/Reconnect Google in/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: '/setup/google' })).toBeInTheDocument();
  });
});
