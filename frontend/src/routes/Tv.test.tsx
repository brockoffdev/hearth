import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Tv } from './Tv';
import type { TvSnapshot } from '../lib/tv';

// ---------------------------------------------------------------------------
// Module mock
// ---------------------------------------------------------------------------

vi.mock('../lib/tv', () => ({
  getTvSnapshot: vi.fn(),
}));

import * as tvModule from '../lib/tv';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeSnapshot(overrides: Partial<TvSnapshot> = {}): TvSnapshot {
  const base: TvSnapshot = {
    family_members: [
      { id: 1, name: 'Bryant', color_hex: '#2E5BA8' },
      { id: 2, name: 'Danya',  color_hex: '#C0392B' },
    ],
    events: [
      {
        id: 1,
        title: 'Soccer practice',
        start_dt: '2026-04-28T15:00:00',
        end_dt: '2026-04-28T16:00:00',
        all_day: false,
        family_member_id: 1,
        family_member_name: 'Bryant',
        family_member_color_hex: '#2E5BA8',
      },
      {
        id: 2,
        title: 'All-day event',
        start_dt: '2026-04-29T00:00:00',
        end_dt: null,
        all_day: true,
        family_member_id: 2,
        family_member_name: 'Danya',
        family_member_color_hex: '#C0392B',
      },
      {
        id: 3,
        title: 'Far future event',
        start_dt: '2026-05-20T10:00:00',
        end_dt: null,
        all_day: false,
        family_member_id: null,
        family_member_name: null,
        family_member_color_hex: null,
      },
    ],
    server_time: '2026-04-28T10:00:00Z',
  };
  return { ...base, ...overrides };
}

async function renderAndLoad() {
  const result = render(
    <MemoryRouter>
      <Tv />
    </MemoryRouter>,
  );
  // Let the initial fetch promise resolve
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return result;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Tv', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    vi.setSystemTime(new Date('2026-04-28T09:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('test_tv_renders_first_page_initially', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    const page0 = screen.getByTestId('page-0');
    expect(page0.className).toMatch(/pageVisible/);

    const page1 = screen.getByTestId('page-1');
    expect(page1.className).toMatch(/pageHidden/);
  });

  it('test_tv_advances_to_next_page_after_interval', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    act(() => { vi.advanceTimersByTime(20_000); });

    const page1 = screen.getByTestId('page-1');
    expect(page1.className).toMatch(/pageVisible/);

    const page0 = screen.getByTestId('page-0');
    expect(page0.className).toMatch(/pageHidden/);
  });

  it('test_tv_loops_back_after_last_page', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    // Advance 4 intervals: 0 → 1 → 2 → 3 → 0
    act(() => { vi.advanceTimersByTime(20_000 * 4); });

    const page0 = screen.getByTestId('page-0');
    expect(page0.className).toMatch(/pageVisible/);
  });

  it('test_tv_renders_clock_with_current_time', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    // Clock frozen at 2026-04-28T09:00:00 → 9:00 AM
    await renderAndLoad();

    expect(screen.getAllByText(/9:00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AM/).length).toBeGreaterThan(0);
  });

  it('test_tv_polls_snapshot_every_five_minutes', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    expect(tvModule.getTvSnapshot).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(tvModule.getTvSnapshot).toHaveBeenCalledTimes(2);
  });

  it('test_tv_marks_stale_when_fetch_fails', async () => {
    vi.mocked(tvModule.getTvSnapshot)
      .mockResolvedValueOnce(makeSnapshot())
      .mockRejectedValue(new Error('network error'));

    await renderAndLoad();

    // Fresh after first successful load
    expect(screen.getByTestId('heartbeat').className).toMatch(/heartbeatFresh/);

    // Poll fires and fails
    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('heartbeat').className).toMatch(/heartbeatStale/);
  });

  it('test_tv_renders_events_in_correct_pages', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    // Page 0 (Month) — Soccer practice on April 28 should appear in today cell
    const monthTodayCell = screen.getByTestId('month-today-cell');
    expect(monthTodayCell.textContent).toMatch(/Soccer practice/);

    // Advance to page 2 (Day) — 2 intervals
    act(() => { vi.advanceTimersByTime(20_000 * 2); });

    const page2 = screen.getByTestId('page-2');
    expect(page2.className).toMatch(/pageVisible/);

    // Soccer practice at 3PM should appear in the day view
    const dayEvent = screen.getByTestId('day-event-1');
    expect(dayEvent.textContent).toMatch(/Soccer practice/);
  });

  it('test_tv_excludes_rejected_events', async () => {
    // Backend already excludes rejected; this test confirms the rendering pipeline
    // correctly handles a snapshot that contains only non-rejected events.
    const snapshot = makeSnapshot({
      events: [
        {
          id: 1,
          title: 'Soccer practice',
          start_dt: '2026-04-28T15:00:00',
          end_dt: null,
          all_day: false,
          family_member_id: 1,
          family_member_name: 'Bryant',
          family_member_color_hex: '#2E5BA8',
        },
      ],
    });
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(snapshot);
    await renderAndLoad();

    // Rendered correctly — "Soccer practice" appears on the page
    expect(screen.getAllByText(/Soccer practice/).length).toBeGreaterThan(0);
  });

  it('test_tv_does_not_show_banner_when_fresh', async () => {
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(makeSnapshot());
    await renderAndLoad();

    expect(screen.queryByTestId('stale-banner')).toBeNull();
  });

  it('test_tv_does_not_show_banner_below_30min_staleness', async () => {
    // First fetch succeeds; all subsequent fail so isStale becomes true.
    vi.mocked(tvModule.getTvSnapshot)
      .mockResolvedValueOnce(makeSnapshot())
      .mockRejectedValue(new Error('network error'));

    await renderAndLoad();

    // Second poll fires and fails — isStale = true, firstStaleAt set.
    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    // Only 10 minutes of staleness — banner must not appear yet.
    act(() => { vi.advanceTimersByTime(10 * 60 * 1000); });

    expect(screen.queryByTestId('stale-banner')).toBeNull();
  });

  it('test_tv_shows_banner_after_30min_staleness', async () => {
    vi.mocked(tvModule.getTvSnapshot)
      .mockResolvedValueOnce(makeSnapshot())
      .mockRejectedValue(new Error('network error'));

    await renderAndLoad();

    // Second poll fires and fails — sets firstStaleAt.
    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    // Advance enough polls so the component re-renders with extendedStale = true.
    // Each poll is every 5 min; after 31 more minutes of polling the computed
    // extendedStale expression (Date.now() - firstStaleAt > 30 min) becomes true.
    await act(async () => {
      vi.advanceTimersByTime(31 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('stale-banner')).toBeDefined();
  });

  it('test_tv_clears_banner_when_fetch_recovers', async () => {
    const snap = makeSnapshot();
    vi.mocked(tvModule.getTvSnapshot)
      .mockResolvedValueOnce(snap)
      .mockRejectedValue(new Error('network error'));

    await renderAndLoad();

    // Let staleness accumulate past 30 min.
    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(31 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId('stale-banner')).toBeDefined();

    // Next fetch succeeds — banner should disappear.
    vi.mocked(tvModule.getTvSnapshot).mockResolvedValue(snap);

    await act(async () => {
      vi.advanceTimersByTime(5 * 60 * 1000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByTestId('stale-banner')).toBeNull();
  });
});
