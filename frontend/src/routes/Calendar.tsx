import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';
import { listEvents } from '../lib/events';
import type { Event } from '../lib/events';
import { listFamily } from '../lib/family';
import type { ApiFamilyMember } from '../lib/family';
import { Spinner } from '../components/Spinner';
import { HBtn } from '../components/HBtn';
import { MobileTabBar } from '../components/MobileTabBar';
import { usePendingCount } from '../lib/usePendingCount';
import {
  buildMonthGrid,
  eventIsoDate,
  formatEventTime,
  MONTH_NAMES,
  toIsoDate,
  visibleRange,
} from '../lib/calendar';
import styles from './Calendar.module.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CalendarState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'ready'; events: Event[] };

type FamilyState = ApiFamilyMember[];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;
const VIEW_MODES = ['Month', 'Week', 'Day', 'Agenda'] as const;

function todayIsoDate(): string {
  return toIsoDate(new Date());
}

// ---------------------------------------------------------------------------
// Event pill
// ---------------------------------------------------------------------------

interface EventPillProps {
  event: Event;
  onClick: () => void;
}

function EventPill({ event, onClick }: EventPillProps): JSX.Element {
  const hex = event.family_member_color_hex ?? 'var(--fgSoft)';
  const time = formatEventTime(event.start_dt, event.all_day);

  return (
    <button
      type="button"
      className={styles.eventPill}
      style={{
        background: `color-mix(in oklab, ${hex} 14%, transparent)`,
        color: hex,
      }}
      onClick={onClick}
      title={event.title}
    >
      {time && (
        <span className={styles.eventTime}>{time}</span>
      )}
      <span className={styles.eventTitle}>{event.title}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Desktop month grid — always renders the weekday header row + day cells,
// overlays loading/error/empty in the body area beneath the header.
// ---------------------------------------------------------------------------

interface MonthGridProps {
  year: number;
  month: number;
  calState: CalendarState;
  todayStr: string;
  onRetry: () => void;
}

function MonthGrid({ year, month, calState, todayStr, onRetry }: MonthGridProps): JSX.Element {
  const navigate = useNavigate();
  const cells = buildMonthGrid(year, month);
  const { start, end } = visibleRange(year, month);

  const events: Event[] = calState.phase === 'ready' ? calState.events : [];

  const visibleEvents = events.filter((e) => {
    const d = eventIsoDate(e.start_dt);
    return d >= start && d <= end;
  });

  return (
    <div className={styles.gridWrapper}>
      {/* Weekday header row — always visible */}
      <div className={styles.weekdayRow}>
        {WEEKDAYS.map((wd) => (
          <div key={wd} className={styles.weekdayHeader} role="columnheader">
            {wd}
          </div>
        ))}
      </div>

      {/* Body: loading / error / empty / grid */}
      {calState.phase === 'loading' && (
        <div className={styles.gridOverlay}>
          <Spinner size={32} ariaLabel="Loading calendar" />
        </div>
      )}

      {calState.phase === 'error' && (
        <div className={styles.gridOverlay}>
          <div className={styles.errorBanner} role="alert">
            <span>{calState.message}</span>
            <button type="button" className={styles.retryBtn} onClick={onRetry}>
              Retry
            </button>
          </div>
        </div>
      )}

      {calState.phase === 'ready' && visibleEvents.length === 0 && (
        <div className={styles.gridOverlay}>
          <p className={styles.emptyHint}>
            No events yet — upload a photo to get started
          </p>
        </div>
      )}

      {/* Cell grid — always render so today-cell is in the DOM */}
      <div className={styles.grid} role="grid" aria-label="Calendar grid">
        {cells.map((cell, idx) => {
          if (!cell.inMonth || !cell.isoDate) {
            return (
              <div
                key={`pad-${idx}`}
                className={styles.cellMuted}
                role="gridcell"
                aria-hidden="true"
              />
            );
          }

          const isToday = cell.isoDate === todayStr;
          const dayEvents = visibleEvents.filter(
            (e) => eventIsoDate(e.start_dt) === cell.isoDate,
          );
          const overflow = dayEvents.length > 3 ? dayEvents.length - 3 : 0;
          const dayNum = cell.date!.getDate();

          return (
            <div
              key={cell.isoDate}
              className={isToday ? styles.cellToday : styles.cell}
              role="gridcell"
              aria-label={cell.isoDate}
              {...(isToday ? { 'data-testid': 'today-cell', 'aria-current': 'date' } : {})}
            >
              <div className={styles.dayHeader}>
                <span className={isToday ? styles.dayNumToday : styles.dayNum}>
                  {dayNum}
                </span>
                {isToday && (
                  <span className={styles.todayPill}>Today</span>
                )}
              </div>
              <div className={styles.eventStack}>
                {dayEvents.slice(0, 3).map((ev) => (
                  <EventPill
                    key={ev.id}
                    event={ev}
                    onClick={() => void navigate(`/review/${ev.id}`)}
                  />
                ))}
                {overflow > 0 && (
                  <span className={styles.overflowLabel}>+{overflow} more</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile agenda fallback
// ---------------------------------------------------------------------------

interface MobileAgendaProps {
  year: number;
  month: number;
  calState: CalendarState;
  onRetry: () => void;
}

function MobileAgenda({ year, month, calState, onRetry }: MobileAgendaProps): JSX.Element {
  const navigate = useNavigate();
  const { start, end } = visibleRange(year, month);

  if (calState.phase === 'loading') {
    return (
      <div className={styles.centered}>
        <Spinner size={28} ariaLabel="Loading calendar" />
      </div>
    );
  }

  if (calState.phase === 'error') {
    return (
      <div className={styles.errorBanner} role="alert">
        <span>{calState.message}</span>
        <button type="button" className={styles.retryBtn} onClick={onRetry}>
          Retry
        </button>
      </div>
    );
  }

  const monthEvents = calState.events.filter((e) => {
    const d = eventIsoDate(e.start_dt);
    return d >= start && d <= end;
  });

  if (monthEvents.length === 0) {
    return (
      <div className={styles.agendaEmpty}>
        <p className={styles.emptyHint}>
          No events yet — upload a photo to get started
        </p>
      </div>
    );
  }

  const grouped = new Map<string, Event[]>();
  for (const ev of monthEvents) {
    const d = eventIsoDate(ev.start_dt);
    if (!grouped.has(d)) grouped.set(d, []);
    grouped.get(d)!.push(ev);
  }

  const sortedDates = [...grouped.keys()].sort();

  return (
    <div className={styles.agendaList}>
      {sortedDates.map((dateStr) => {
        const dayEvs = grouped.get(dateStr)!;
        const d = new Date(dateStr + 'T00:00:00');
        const label = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
        return (
          <section key={dateStr} className={styles.agendaSection}>
            <h2 className={styles.agendaDate}>{label}</h2>
            {dayEvs.map((ev) => {
              const hex = ev.family_member_color_hex ?? 'var(--fgSoft)';
              const time = formatEventTime(ev.start_dt, ev.all_day);
              return (
                <button
                  key={ev.id}
                  type="button"
                  className={styles.agendaEvent}
                  style={{ borderLeftColor: hex }}
                  onClick={() => void navigate(`/review/${ev.id}`)}
                >
                  {time && <span className={styles.agendaTime}>{time}</span>}
                  <span className={styles.agendaTitle}>{ev.title}</span>
                  {ev.family_member_name && (
                    <span className={styles.agendaMember} style={{ color: hex }}>
                      {ev.family_member_name}
                    </span>
                  )}
                </button>
              );
            })}
          </section>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Calendar route
// ---------------------------------------------------------------------------

export function Calendar(): JSX.Element {
  const today = new Date();
  const todayStr = todayIsoDate();

  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [fetchTrigger, setFetchTrigger] = useState(0);

  const [calState, setCalState] = useState<CalendarState>({ phase: 'loading' });
  const [family, setFamily] = useState<FamilyState>([]);

  useEffect(() => {
    let cancelled = false;
    setCalState({ phase: 'loading' });

    void (async () => {
      try {
        const data = await listEvents();
        if (!cancelled) {
          setCalState({ phase: 'ready', events: data.items });
        }
      } catch {
        if (!cancelled) {
          setCalState({ phase: 'error', message: 'Failed to load events' });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // fetchTrigger forces re-fetch on retry
  }, [fetchTrigger]);

  useEffect(() => {
    void (async () => {
      try {
        const members = await listFamily();
        setFamily(members);
      } catch {
        // Family legend is non-critical
      }
    })();
  }, []);

  const { count: pendingCount } = usePendingCount();

  const handleRetry = () => setFetchTrigger((n) => n + 1);

  const handlePrev = () => {
    if (month === 0) {
      setYear((y) => y - 1);
      setMonth(11);
    } else {
      setMonth((m) => m - 1);
    }
  };

  const handleNext = () => {
    if (month === 11) {
      setYear((y) => y + 1);
      setMonth(0);
    } else {
      setMonth((m) => m + 1);
    }
  };

  const handleToday = () => {
    const now = new Date();
    setYear(now.getFullYear());
    setMonth(now.getMonth());
  };

  const monthName = MONTH_NAMES[month]!;

  return (
    <div className={styles.page}>
      {/* ── Desktop layout ─────────────────────────────────────────── */}
      <div className={styles.desktopLayout} data-testid="desktop-calendar">
        {/* Title bar */}
        <div className={styles.titleBar}>
          <div className={styles.titleLeft}>
            <div className={styles.tagline}>Hearth</div>
            <div className={styles.monthHeading}>
              <span className={styles.monthName}>{monthName}</span>
              {' '}
              <span className={styles.monthYear}>{year}</span>
            </div>
          </div>
          <div className={styles.titleRight}>
            <div className={styles.viewPills} role="tablist" aria-label="Calendar view">
              {VIEW_MODES.map((v) => (
                <div
                  key={v}
                  role="tab"
                  aria-selected={v === 'Month'}
                  className={v === 'Month' ? styles.viewPillActive : styles.viewPillInactive}
                >
                  {v}
                </div>
              ))}
            </div>
            <HBtn size="sm" onClick={handlePrev} aria-label="Previous month">‹</HBtn>
            <HBtn size="sm" onClick={handleToday}>Today</HBtn>
            <HBtn size="sm" onClick={handleNext} aria-label="Next month">›</HBtn>
          </div>
        </div>

        {/* Family-color legend */}
        {family.length > 0 && (
          <div className={styles.legend} aria-label="Family legend">
            {family.map((m) => (
              <span key={m.id} className={styles.legendChip}>
                <span
                  className={styles.legendDot}
                  style={{ background: m.color_hex_center }}
                  aria-hidden="true"
                />
                <span className={styles.legendName}>{m.name}</span>
              </span>
            ))}
          </div>
        )}

        {/* Month grid (always rendered — contains weekday headers + today cell) */}
        <div className={styles.body}>
          <MonthGrid
            year={year}
            month={month}
            calState={calState}
            todayStr={todayStr}
            onRetry={handleRetry}
          />
        </div>
      </div>

      {/* ── Mobile layout ──────────────────────────────────────────── */}
      <div className={styles.mobileLayout} data-testid="mobile-calendar">
        <div className={styles.mobileTitleBar}>
          <div className={styles.mobileTitleLeft}>
            <span className={styles.mobileMontName}>{monthName}</span>
            {' '}
            <span className={styles.mobileYear}>{year}</span>
          </div>
          <div className={styles.mobileNav}>
            <HBtn size="sm" onClick={handlePrev} aria-label="Previous month">‹</HBtn>
            <HBtn size="sm" onClick={handleToday}>Today</HBtn>
            <HBtn size="sm" onClick={handleNext} aria-label="Next month">›</HBtn>
          </div>
        </div>

        <div className={styles.mobileBody}>
          <MobileAgenda
            year={year}
            month={month}
            calState={calState}
            onRetry={handleRetry}
          />
        </div>

        <MobileTabBar active="calendar" badges={{ review: pendingCount }} />
      </div>
    </div>
  );
}
