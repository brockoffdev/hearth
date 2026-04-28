import { useEffect, useRef, useState, useCallback } from 'react';
import type { JSX } from 'react';
import { getTvSnapshot } from '../lib/tv';
import type { TvSnapshot, TvEvent, TvFamilyMember } from '../lib/tv';
import {
  buildMonthGrid,
  eventIsoDate,
  formatEventTime,
  MONTH_NAMES,
  toIsoDate,
} from '../lib/calendar';
import styles from './Tv.module.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_INTERVAL_MS = 20_000;
const POLL_INTERVAL_MS = 5 * 60 * 1000;
const STALE_THRESHOLD_MS = 6 * 60 * 1000;
const TV_PAGES = ['Month', 'Week', 'Day', 'Coming up'] as const;
const WEEKDAY_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;
const WEEK_HOURS = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22] as const;

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

function useRotation(pageCount: number, intervalMs: number): [number, () => void, () => void] {
  const [current, setCurrent] = useState(0);
  const paused = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const start = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      if (!paused.current) {
        setCurrent((c) => (c + 1) % pageCount);
      }
    }, intervalMs);
  }, [pageCount, intervalMs]);

  useEffect(() => {
    start();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [start]);

  const pause = useCallback(() => { paused.current = true; }, []);
  const resume = useCallback(() => { paused.current = false; }, []);

  return [current, pause, resume];
}

function useTvSnapshot(): {
  snapshot: TvSnapshot | null;
  lastFetchedAt: number | null;
  isStale: boolean;
} {
  const [snapshot, setSnapshot] = useState<TvSnapshot | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [fetchFailed, setFetchFailed] = useState(false);

  const doFetch = useCallback(async () => {
    try {
      const data = await getTvSnapshot();
      setSnapshot(data);
      setLastFetchedAt(Date.now());
      setFetchFailed(false);
    } catch {
      setFetchFailed(true);
    }
  }, []);

  useEffect(() => {
    void doFetch();
    const timer = setInterval(() => { void doFetch(); }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [doFetch]);

  const isStale =
    fetchFailed ||
    (lastFetchedAt !== null && Date.now() - lastFetchedAt > STALE_THRESHOLD_MS);

  return { snapshot, lastFetchedAt, isStale };
}

// ---------------------------------------------------------------------------
// Time helpers
// ---------------------------------------------------------------------------

function formatClock(d: Date): { time: string; period: string } {
  const h = d.getHours();
  const m = d.getMinutes();
  const hh = String(h % 12 || 12);
  const mm = String(m).padStart(2, '0');
  const period = h < 12 ? 'AM' : 'PM';
  return { time: `${hh}:${mm}`, period };
}

function formatDayDate(d: Date): { dayName: string; dateStr: string } {
  const dayName = d.toLocaleDateString(undefined, { weekday: 'long' });
  const month = MONTH_NAMES[d.getMonth()]!;
  const day = d.getDate();
  return { dayName, dateStr: `${month} ${day}.` };
}

function isoWeekNumber(d: Date): number {
  const jan4 = new Date(d.getFullYear(), 0, 4);
  const startOfWeek1 = new Date(jan4);
  startOfWeek1.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7));
  const diff = d.getTime() - startOfWeek1.getTime();
  return Math.floor(diff / (7 * 86400000)) + 1;
}

function hourLabel(h: number): string {
  if (h === 0) return '12 AM';
  if (h === 12) return '12 PM';
  return h < 12 ? `${h} AM` : `${h - 12} PM`;
}

function getWeekStart(d: Date): Date {
  const s = new Date(d);
  s.setDate(s.getDate() - s.getDay());
  s.setHours(0, 0, 0, 0);
  return s;
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

// ---------------------------------------------------------------------------
// Masthead — shared across pages
// ---------------------------------------------------------------------------

interface MastheadProps {
  now: Date;
  weekNumber: number;
  compact?: boolean;
}

function Masthead({ now, weekNumber, compact = false }: MastheadProps): JSX.Element {
  const { dayName, dateStr } = formatDayDate(now);
  const { time, period } = formatClock(now);

  return (
    <div className={styles.masthead}>
      <div className={styles.mastheadLeft}>
        <div className={styles.tagline}>
          The Brock Family · Vol. IV · No. {weekNumber}
        </div>
        {!compact && (
          <div className={styles.bigDate}>
            <span className={styles.bigDateItalic}>{dayName},</span>
            <br />
            {dateStr}
          </div>
        )}
        {compact && (
          <div style={{ fontFamily: 'var(--fontDisplay, Georgia, serif)', fontSize: 32, lineHeight: 1.1 }}>
            <span style={{ fontStyle: 'italic' }}>{dayName},</span>{' '}{dateStr}
          </div>
        )}
      </div>
      <div className={styles.clock}>
        {time}
        <span className={styles.clockPeriod}>{period}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page footer
// ---------------------------------------------------------------------------

function PageFooter({ currentPage }: { currentPage: number }): JSX.Element {
  return (
    <div className={styles.pageFooter}>
      <span className={styles.pageFooterLabel}>Now showing</span>
      {TV_PAGES.map((p, i) => (
        <span
          key={p}
          className={i === currentPage ? styles.pageTabActive : styles.pageTabInactive}
        >
          {p}
        </span>
      ))}
      <span className={styles.pageFooterRight}>
        refreshes every 5 min · cycles every 20s
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Family color legend
// ---------------------------------------------------------------------------

function Legend({ members }: { members: TvFamilyMember[] }): JSX.Element {
  return (
    <div className={styles.legend}>
      {members.map((m) => (
        <span key={m.id} className={styles.legendChip}>
          <span
            className={styles.legendDot}
            style={{ background: m.color_hex }}
            aria-hidden="true"
          />
          <span>{m.name}</span>
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page 1: Month
// ---------------------------------------------------------------------------

function MonthPage({ snapshot, now }: { snapshot: TvSnapshot; now: Date }): JSX.Element {
  const year = now.getFullYear();
  const month = now.getMonth();
  const todayStr = toIsoDate(now);
  const cells = buildMonthGrid(year, month);

  const eventsForMonth = snapshot.events.filter((e) => {
    const d = new Date(e.start_dt);
    return d.getFullYear() === year && d.getMonth() === month;
  });

  return (
    <>
      <div className={styles.monthBody}>
        <div className={styles.monthWeekdayRow}>
          {WEEKDAY_SHORT.map((wd) => (
            <div key={wd} className={styles.monthWeekdayHeader}>{wd}</div>
          ))}
        </div>
        <div className={styles.monthGrid} role="grid" aria-label="Month calendar">
          {cells.map((cell, idx) => {
            if (!cell.inMonth || !cell.isoDate) {
              return <div key={`pad-${idx}`} className={styles.monthCellPad} role="gridcell" aria-hidden="true" />;
            }
            const isToday = cell.isoDate === todayStr;
            const dayEvents = eventsForMonth.filter(
              (e) => eventIsoDate(e.start_dt) === cell.isoDate,
            );
            const overflow = dayEvents.length > 2 ? dayEvents.length - 2 : 0;
            return (
              <div
                key={cell.isoDate}
                className={isToday ? styles.monthCellToday : styles.monthCell}
                role="gridcell"
                aria-label={cell.isoDate}
                {...(isToday ? { 'data-testid': 'month-today-cell' } : {})}
              >
                <div className={isToday ? styles.monthDayNumToday : styles.monthDayNum}>
                  {cell.date!.getDate()}
                </div>
                {dayEvents.slice(0, 2).map((ev) => (
                  <div
                    key={ev.id}
                    className={styles.monthEventPill}
                    style={{
                      background: ev.family_member_color_hex
                        ? `color-mix(in oklab, ${ev.family_member_color_hex} 20%, transparent)`
                        : 'rgba(244,238,227,.12)',
                      color: ev.family_member_color_hex ?? '#F4EEE3',
                    }}
                  >
                    {!ev.all_day && (
                      <span style={{ opacity: 0.65, marginRight: 3, fontSize: 10 }}>
                        {formatEventTime(ev.start_dt, ev.all_day)}
                      </span>
                    )}
                    {ev.title}
                  </div>
                ))}
                {overflow > 0 && (
                  <div className={styles.monthOverflow}>+{overflow} more</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <Legend members={snapshot.family_members} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Page 2: Week
// ---------------------------------------------------------------------------

function WeekPage({ snapshot, now }: { snapshot: TvSnapshot; now: Date }): JSX.Element {
  const weekStart = getWeekStart(now);
  const todayStr = toIsoDate(now);
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  return (
    <div className={styles.weekBody}>
      <div
        className={styles.weekGrid}
        style={{ display: 'grid', gridTemplateColumns: '48px repeat(7, 1fr)', gridTemplateRows: 'auto auto 1fr' }}
      >
        {/* Header row */}
        <div />
        {days.map((d) => {
          const isoDate = toIsoDate(d);
          const isToday = isoDate === todayStr;
          const label = `${WEEKDAY_SHORT[d.getDay()]} ${d.getDate()}`;
          return (
            <div
              key={isoDate}
              className={isToday ? styles.weekDayHeaderToday : styles.weekDayHeader}
              data-testid={isToday ? 'week-today-col' : undefined}
            >
              {label}
            </div>
          );
        })}

        {/* All-day row */}
        <div style={{ fontSize: 10, opacity: 0.35, paddingRight: 4, textAlign: 'right', paddingTop: 2 }}>all day</div>
        {days.map((d) => {
          const isoDate = toIsoDate(d);
          const allDayEvs = snapshot.events.filter(
            (e) => e.all_day && eventIsoDate(e.start_dt) === isoDate,
          );
          return (
            <div key={`ad-${isoDate}`} style={{ borderLeft: '1px solid rgba(244,238,227,.06)', padding: '2px 2px 4px' }}>
              {allDayEvs.map((ev) => (
                <div
                  key={ev.id}
                  className={styles.weekAllDayStrip}
                  style={{
                    background: ev.family_member_color_hex
                      ? `color-mix(in oklab, ${ev.family_member_color_hex} 22%, transparent)`
                      : 'rgba(244,238,227,.12)',
                    color: ev.family_member_color_hex ?? '#F4EEE3',
                  }}
                >
                  {ev.title}
                </div>
              ))}
            </div>
          );
        })}

        {/* Hour rows */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {WEEK_HOURS.map((h) => (
            <div key={h} className={styles.weekTimeLabel}>{hourLabel(h)}</div>
          ))}
        </div>
        {days.map((d) => {
          const isoDate = toIsoDate(d);
          const timedEvs = snapshot.events.filter(
            (e) => !e.all_day && eventIsoDate(e.start_dt) === isoDate,
          );
          return (
            <div key={`col-${isoDate}`} className={styles.weekDayCol}>
              {WEEK_HOURS.map((h) => (
                <div key={h} className={styles.weekHourRow} style={{ height: `${100 / WEEK_HOURS.length}%` }} />
              ))}
              {timedEvs.map((ev) => {
                const start = new Date(ev.start_dt);
                const startH = start.getHours() + start.getMinutes() / 60;
                const endH = ev.end_dt
                  ? (() => { const e = new Date(ev.end_dt); return e.getHours() + e.getMinutes() / 60; })()
                  : startH + 1;
                const minH = WEEK_HOURS[0]!;
                const maxH = WEEK_HOURS[WEEK_HOURS.length - 1]! + 1;
                const topPct = ((startH - minH) / (maxH - minH)) * 100;
                const heightPct = ((endH - startH) / (maxH - minH)) * 100;
                if (topPct < 0 || topPct > 100) return null;
                return (
                  <div
                    key={ev.id}
                    className={styles.weekEventBlock}
                    style={{
                      top: `${topPct}%`,
                      height: `${Math.max(heightPct, 3)}%`,
                      background: ev.family_member_color_hex
                        ? `color-mix(in oklab, ${ev.family_member_color_hex} 28%, transparent)`
                        : 'rgba(244,238,227,.14)',
                      color: ev.family_member_color_hex ?? '#F4EEE3',
                      borderLeft: `2px solid ${ev.family_member_color_hex ?? 'rgba(244,238,227,.4)'}`,
                    }}
                  >
                    {ev.title}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page 3: Day
// ---------------------------------------------------------------------------

function DayPage({ snapshot, now }: { snapshot: TvSnapshot; now: Date }): JSX.Element {
  const todayStr = toIsoDate(now);

  const todayEvents = snapshot.events.filter(
    (e) => eventIsoDate(e.start_dt) === todayStr && !e.all_day,
  );

  const nowMs = now.getTime();
  const nextEvent = todayEvents.find((e) => new Date(e.start_dt).getTime() >= nowMs);

  return (
    <div className={styles.dayPageBody}>
      {/* Left: hour-by-hour list */}
      <div>
        <div className={styles.dayHeadline}>Today · hour by hour</div>
        <div className={styles.dayHourList}>
          {WEEK_HOURS.map((h) => {
            const hourEvents = todayEvents.filter((e) => {
              const eh = new Date(e.start_dt).getHours();
              return eh === h;
            });
            return (
              <div key={h} className={styles.dayHourRow}>
                <div className={styles.dayHourLabel}>{hourLabel(h)}</div>
                <div className={styles.dayHourEvents}>
                  {hourEvents.map((ev) => (
                    <div
                      key={ev.id}
                      className={styles.dayHourEvent}
                      style={{
                        background: ev.family_member_color_hex
                          ? `color-mix(in oklab, ${ev.family_member_color_hex} 20%, transparent)`
                          : 'rgba(244,238,227,.1)',
                        color: ev.family_member_color_hex ?? '#F4EEE3',
                      }}
                      data-testid={`day-event-${ev.id}`}
                    >
                      {ev.title}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: next/upcoming event card */}
      <div>
        <div className={styles.dayHeadline}>Up next</div>
        {nextEvent ? (
          <div
            className={styles.dayNextCard}
            style={{
              borderColor: nextEvent.family_member_color_hex
                ? `${nextEvent.family_member_color_hex}60`
                : 'rgba(244,238,227,.1)',
            }}
          >
            <div className={styles.dayNextLabel}>Next event</div>
            <div
              className={styles.dayNextTitle}
              style={{ color: nextEvent.family_member_color_hex ?? '#F4EEE3' }}
            >
              {nextEvent.title}
            </div>
            <div className={styles.dayNextTime}>
              {formatEventTime(nextEvent.start_dt, nextEvent.all_day)}
            </div>
            {nextEvent.family_member_name && (
              <div className={styles.dayNextMember}>{nextEvent.family_member_name}</div>
            )}
          </div>
        ) : (
          <div className={styles.dayNoneCard}>Nothing more today.</div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page 4: Coming up
// ---------------------------------------------------------------------------

function ComingUpPage({ snapshot, now }: { snapshot: TvSnapshot; now: Date }): JSX.Element {
  const cutoff = new Date(now);
  cutoff.setDate(cutoff.getDate() + 7);
  const cutoffStr = toIsoDate(cutoff);

  const upcoming = snapshot.events
    .filter((e) => eventIsoDate(e.start_dt) >= cutoffStr)
    .slice(0, 25);

  const byMonth = new Map<string, TvEvent[]>();
  for (const ev of upcoming) {
    const d = new Date(ev.start_dt);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key)!.push(ev);
  }

  const monthKeys = [...byMonth.keys()].sort();

  return (
    <div className={styles.comingUpBody} data-testid="coming-up-page">
      <div className={styles.comingUpHeadline}>Coming up</div>
      {monthKeys.length === 0 && (
        <div style={{ opacity: 0.35, fontStyle: 'italic', fontSize: 16 }}>Nothing on the horizon.</div>
      )}
      {monthKeys.map((key) => {
        const [year, monthIdx] = key.split('-').map(Number) as [number, number];
        const monthName = MONTH_NAMES[monthIdx - 1]!;
        const evs = byMonth.get(key)!;
        return (
          <div key={key} className={styles.comingUpMonthSection}>
            <div className={styles.comingUpMonthLabel}>{monthName} {year}</div>
            {evs.map((ev) => {
              const d = new Date(ev.start_dt);
              const dateLabel = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
              return (
                <div key={ev.id} className={styles.comingUpEventRow}>
                  <div className={styles.comingUpEventDate}>{dateLabel}</div>
                  <div
                    className={styles.comingUpEventDot}
                    style={{ background: ev.family_member_color_hex ?? 'rgba(244,238,227,.4)' }}
                  />
                  <div className={styles.comingUpEventTitle}>{ev.title}</div>
                  {ev.family_member_name && (
                    <div className={styles.comingUpEventMember}>{ev.family_member_name}</div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root Tv component
// ---------------------------------------------------------------------------

export function Tv(): JSX.Element {
  const { snapshot, isStale } = useTvSnapshot();
  const [currentPage, pauseRotation, resumeRotation] = useRotation(TV_PAGES.length, PAGE_INTERVAL_MS);

  const [clockNow, setClockNow] = useState(() => new Date());

  useEffect(() => {
    const tick = () => setClockNow(new Date());
    // Align to the next minute boundary
    const msToNextMinute = (60 - new Date().getSeconds()) * 1000 - new Date().getMilliseconds();
    const initial = setTimeout(() => {
      tick();
      const interval = setInterval(tick, 60_000);
      return () => clearInterval(interval);
    }, msToNextMinute);
    return () => clearTimeout(initial);
  }, []);

  const weekNumber = isoWeekNumber(clockNow);

  const renderPage = (pageIndex: number): JSX.Element | null => {
    if (!snapshot) return null;
    switch (pageIndex) {
      case 0:
        return <MonthPage snapshot={snapshot} now={clockNow} />;
      case 1:
        return <WeekPage snapshot={snapshot} now={clockNow} />;
      case 2:
        return <DayPage snapshot={snapshot} now={clockNow} />;
      case 3:
        return <ComingUpPage snapshot={snapshot} now={clockNow} />;
      default:
        return null;
    }
  };

  return (
    <div
      className={styles.shell}
      data-testid="tv-shell"
      onMouseEnter={pauseRotation}
      onMouseLeave={resumeRotation}
      onTouchStart={pauseRotation}
      onTouchEnd={resumeRotation}
    >
      {/* Heartbeat freshness indicator */}
      <div
        className={isStale ? styles.heartbeatStale : styles.heartbeatFresh}
        data-testid="heartbeat"
        aria-label={isStale ? 'Data stale' : 'Data fresh'}
        role="status"
      />

      {/* Loading state before first fetch */}
      {!snapshot && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: 0.4,
            fontSize: 14,
            fontFamily: 'var(--fontMono, monospace)',
            letterSpacing: 2,
          }}
        >
          Loading…
        </div>
      )}

      {/* Pages */}
      {snapshot && TV_PAGES.map((_, pageIndex) => (
        <div
          key={pageIndex}
          className={pageIndex === currentPage ? styles.pageVisible : styles.pageHidden}
          data-testid={`page-${pageIndex}`}
        >
          <div className={styles.pageWrap}>
            <Masthead now={clockNow} weekNumber={weekNumber} compact={pageIndex !== 0} />
            {renderPage(pageIndex)}
            <PageFooter currentPage={pageIndex} />
          </div>
        </div>
      ))}
    </div>
  );
}
