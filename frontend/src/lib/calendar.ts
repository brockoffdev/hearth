/**
 * Date-math helpers for the month-grid calendar view.
 * All computations are in local time (no UTC shifting needed — events store
 * ISO strings that include offset, but we display by local calendar month).
 */

export interface CalendarDay {
  /** null = padding cell (day from prev/next month) */
  date: Date | null;
  /** ISO date string YYYY-MM-DD, or null for padding cells */
  isoDate: string | null;
  /** true for the current month */
  inMonth: boolean;
}

/** Return the ISO date string YYYY-MM-DD for a Date in local time. */
export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * Build the 35–42 day cells (5–6 weeks × 7) needed to render a month grid.
 * The grid always starts on Sunday of the week containing the 1st.
 */
export function buildMonthGrid(year: number, month: number): CalendarDay[] {
  const firstOfMonth = new Date(year, month, 1);
  const lastOfMonth = new Date(year, month + 1, 0);

  const startOffset = firstOfMonth.getDay(); // 0=Sun
  const totalCells = Math.ceil((startOffset + lastOfMonth.getDate()) / 7) * 7;

  const cells: CalendarDay[] = [];
  for (let i = 0; i < totalCells; i++) {
    const dayNum = i - startOffset + 1;
    if (dayNum < 1 || dayNum > lastOfMonth.getDate()) {
      cells.push({ date: null, isoDate: null, inMonth: false });
    } else {
      const d = new Date(year, month, dayNum);
      cells.push({ date: d, isoDate: toIsoDate(d), inMonth: true });
    }
  }
  return cells;
}

/**
 * The ISO-date range [rangeStart, rangeEnd] that should be fetched for a
 * visible month grid. We extend by one week on each side so events that
 * fall in the padding cells are also visible.
 */
export function visibleRange(year: number, month: number): { start: string; end: string } {
  const firstOfMonth = new Date(year, month, 1);
  const lastOfMonth = new Date(year, month + 1, 0);

  const gridStart = new Date(firstOfMonth);
  gridStart.setDate(gridStart.getDate() - firstOfMonth.getDay());

  const gridEnd = new Date(lastOfMonth);
  const tail = 6 - lastOfMonth.getDay();
  gridEnd.setDate(gridEnd.getDate() + tail);

  return { start: toIsoDate(gridStart), end: toIsoDate(gridEnd) };
}

/** Format a time portion for the event pill label.  Input: ISO datetime string. */
export function formatEventTime(startDt: string, allDay: boolean): string {
  if (allDay) return '';
  const d = new Date(startDt);
  const h = d.getHours();
  const m = d.getMinutes();
  const hh = String(h % 12 || 12).padStart(2, '0');
  const mm = String(m).padStart(2, '0');
  const ampm = h < 12 ? 'a' : 'p';
  return `${hh}:${mm}${ampm}`;
}

/** Extract YYYY-MM-DD from an ISO datetime string (local interpretation). */
export function eventIsoDate(startDt: string): string {
  return toIsoDate(new Date(startDt));
}

/** Long month name, e.g. "April". */
export const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
] as const;
