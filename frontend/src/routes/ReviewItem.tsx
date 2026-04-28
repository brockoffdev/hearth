import { useEffect, useState, useCallback, useMemo } from 'react';
import type { JSX } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getEvent, listEvents, patchEvent, rejectEvent, republishEvent, cellCropUrl } from '../lib/events';
import type { Event } from '../lib/events';
import { listFamily } from '../lib/family';
import type { ApiFamilyMember } from '../lib/family';
import { ApiError } from '../lib/api';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { HBtn } from '../components/HBtn';
import { Spinner } from '../components/Spinner';
import styles from './ReviewItem.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toDateInputValue(isoString: string): string {
  // Extract YYYY-MM-DD from ISO string, treating it as local date
  return isoString.slice(0, 10);
}

function toTimeInputValue(isoString: string): string {
  // Extract HH:MM from ISO string
  return isoString.slice(11, 16);
}

function buildStartDt(date: string, time: string, allDay: boolean): string {
  if (allDay) return `${date}T00:00:00`;
  return `${date}T${time}:00`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LoadPhase =
  | { phase: 'loading' }
  | { phase: 'error'; status: number }
  | { phase: 'ready'; event: Event };

interface FormState {
  title: string;
  familyMemberId: number | null;
  date: string;
  time: string;
  allDay: boolean;
  location: string;
}

// ---------------------------------------------------------------------------
// ReviewItem route
// ---------------------------------------------------------------------------

export function ReviewItem(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const eventId = Number(id);

  const [loadPhase, setLoadPhase] = useState<LoadPhase>({ phase: 'loading' });
  const [form, setForm] = useState<FormState>({
    title: '',
    familyMemberId: null,
    date: '',
    time: '',
    allDay: false,
    location: '',
  });
  const [originalEvent, setOriginalEvent] = useState<Event | null>(null);

  // Queue for position indicator ("Review · X of N") and next-item navigation
  const [queue, setQueue] = useState<Event[] | null>(null);
  const [familyMembers, setFamilyMembers] = useState<ApiFamilyMember[]>([]);
  const [saving, setSaving] = useState(false);
  const [republishing, setRepublishing] = useState(false);
  const [republishError, setRepublishError] = useState<string | null>(null);
  const [republishSuccess, setRepublishSuccess] = useState(false);

  // Load the event
  useEffect(() => {
    if (!eventId) return;
    let cancelled = false;

    void (async () => {
      try {
        const event = await getEvent(eventId);
        if (cancelled) return;
        setOriginalEvent(event);
        setForm({
          title: event.title,
          familyMemberId: event.family_member_id,
          date: toDateInputValue(event.start_dt),
          time: toTimeInputValue(event.start_dt),
          allDay: event.all_day,
          location: event.location ?? '',
        });
        setLoadPhase({ phase: 'ready', event });
      } catch (err) {
        if (cancelled) return;
        const status = err instanceof ApiError ? err.status : 500;
        setLoadPhase({ phase: 'error', status });
      }
    })();

    return () => { cancelled = true; };
  }, [eventId]);

  // Load the pending_review queue (for position indicator + next navigation)
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await listEvents({ status: 'pending_review' });
        if (!cancelled) setQueue(data.items);
      } catch {
        // Non-fatal: position indicator and next-nav fall back gracefully
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Load family members for the picker
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const members = await listFamily();
        if (!cancelled) setFamilyMembers(members);
      } catch {
        // Non-fatal: picker just won't show options
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Detect auto-publish demotion trailer in notes field
  const loadedEvent = loadPhase.phase === 'ready' ? loadPhase.event : null;
  const demotionMatch = useMemo(() => {
    if (!loadedEvent?.notes) return null;
    const m = loadedEvent.notes.match(/\[Auto-publish failed: ([^\]]*)\]\s*$/);
    return m ? m[1] : null;
  }, [loadedEvent?.notes]);

  // Navigate to the next pending_review item, or /review if none
  const navigateNext = useCallback(() => {
    if (!queue) {
      void navigate('/review');
      return;
    }
    const currentIndex = queue.findIndex((e) => e.id === eventId);
    const next = queue[currentIndex + 1] ?? null;
    if (next) {
      void navigate(`/review/${next.id}`);
    } else {
      void navigate('/review');
    }
  }, [queue, eventId, navigate]);

  // Position string: "Review · X of N" or just "Review" while loading
  const positionLabel = (() => {
    if (!queue) return 'Review';
    const idx = queue.findIndex((e) => e.id === eventId);
    if (idx === -1) return 'Review';
    return `Review · ${idx + 1} of ${queue.length}`;
  })();

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleSave = async () => {
    if (!originalEvent) return;
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      const newStartDt = buildStartDt(form.date, form.time, form.allDay);
      type PatchFields = Parameters<typeof patchEvent>[1];
      const diff: PatchFields = {};

      if (form.title !== originalEvent.title) diff.title = form.title;
      if (form.familyMemberId !== originalEvent.family_member_id) diff.family_member_id = form.familyMemberId;
      if (form.allDay !== originalEvent.all_day) diff.all_day = form.allDay;
      if (form.location !== (originalEvent.location ?? '')) diff.location = form.location || null;

      // Compare dates only if the components changed
      const origDate = toDateInputValue(originalEvent.start_dt);
      const origTime = toTimeInputValue(originalEvent.start_dt);
      if (form.date !== origDate || form.time !== origTime || form.allDay !== originalEvent.all_day) {
        diff.start_dt = newStartDt;
      }

      await patchEvent(eventId, diff);
      navigateNext();
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = () => {
    navigateNext();
  };

  const handleReject = async () => {
    if (!window.confirm("Reject this event? It won't be added to your calendar.")) return;
    try {
      await rejectEvent(eventId);
      navigateNext();
    } catch {
      // Stay on page if reject fails
    }
  };

  const handleRepublish = async () => {
    setRepublishing(true);
    setRepublishError(null);
    setRepublishSuccess(false);
    try {
      await republishEvent(eventId);
      setRepublishSuccess(true);
      setTimeout(() => navigateNext(), 800);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503) {
          setRepublishError('reconnect_google');
        } else if (err.status === 400) {
          setRepublishError('no_calendar');
        } else {
          setRepublishError('gcal');
        }
      } else {
        setRepublishError('gcal');
      }
    } finally {
      setRepublishing(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Error states
  // ---------------------------------------------------------------------------

  if (loadPhase.phase === 'loading') {
    return (
      <div className={styles.page}>
        <div className={styles.centered}>
          <Spinner size={24} ariaLabel="Loading event" />
        </div>
      </div>
    );
  }

  if (loadPhase.phase === 'error') {
    const message = loadPhase.status === 404
      ? 'Event not found'
      : loadPhase.status === 403
        ? 'Access denied'
        : 'Failed to load event';
    return (
      <div className={styles.page}>
        <div className={styles.centered}>
          <p className={styles.errorMsg}>{message}</p>
          <Link to="/review" className={styles.backLink}>Back to review queue</Link>
        </div>
      </div>
    );
  }

  const event = loadPhase.event;
  const saveDisabled = !form.title.trim() || saving;

  // Format cell label: "cell · Mon Apr 30"
  const cellDate = new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(new Date(event.start_dt));

  return (
    <div className={styles.page}>
      <div className={styles.scrollArea}>
        {/* Header */}
        <div className={styles.header}>
          <Link to="/review" className={styles.backBtn} aria-label="Back to review queue">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M15 6l-6 6 6 6" stroke="var(--fg)" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </Link>
          <span className={styles.positionLabel}>{positionLabel}</span>
          <span className={styles.spacer} />
          <ConfidenceBadge value={event.confidence} status="review" />
        </div>

        {/* Title */}
        <div className={styles.titleBlock}>
          <h1 className={styles.pageTitle}>What did the calendar say?</h1>
        </div>

        {/* Demotion warning + Republish affordance */}
        {demotionMatch !== null && (
          <div className={styles.demotedCard} data-testid="demoted-card">
            <div className={styles.demotedHeader}>
              <svg
                className={styles.demotedIcon}
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className={styles.demotedReason}>
                Auto-publish failed: {demotionMatch}
              </span>
            </div>
            {republishError === 'reconnect_google' && (
              <p className={styles.demotedError}>
                Reconnect Google in{' '}
                <Link to="/setup/google" className={styles.demotedLink}>/setup/google</Link>
              </p>
            )}
            {republishError === 'no_calendar' && (
              <p className={styles.demotedError}>
                This event has no family member assigned — pick one and save instead.
              </p>
            )}
            {republishError === 'gcal' && (
              <p className={styles.demotedError}>
                Google Calendar error — try again.
              </p>
            )}
            {republishSuccess && (
              <p className={styles.demotedReason}>Republished!</p>
            )}
            <HBtn
              kind="primary"
              size="lg"
              className={styles.saveBtn}
              onClick={() => void handleRepublish()}
              disabled={republishing || republishSuccess}
            >
              {republishing ? 'Republishing…' : 'Republish'}
            </HBtn>
          </div>
        )}

        {/* Cell crop */}
        {event.has_cell_crop && (
          <div className={styles.cellCard}>
            <span className={styles.cellLabel}>cell · {cellDate}</span>
            <img
              src={cellCropUrl(event.id)}
              alt="Calendar cell crop"
              className={styles.cellImage}
            />
          </div>
        )}

        {/* Form fields */}
        <div className={styles.fields}>
          {/* Title field */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="field-title">Title</label>
            <input
              id="field-title"
              type="text"
              className={styles.fieldInput}
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Event title"
              required
            />
          </div>

          {/* Who field */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="field-who">Who</label>
            <select
              id="field-who"
              className={styles.fieldInput}
              value={form.familyMemberId ?? ''}
              onChange={(e) => setForm((f) => ({
                ...f,
                familyMemberId: e.target.value ? Number(e.target.value) : null,
              }))}
            >
              <option value="">— unassigned —</option>
              {familyMembers.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>

          {/* Date + Time row */}
          <div className={styles.dateTimeRow}>
            <div className={styles.fieldFlex}>
              <label className={styles.fieldLabel} htmlFor="field-date">Date</label>
              <input
                id="field-date"
                type="date"
                className={styles.fieldInput}
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
              />
            </div>
            {!form.allDay && (
              <div className={styles.fieldFlex}>
                <label className={styles.fieldLabel} htmlFor="field-time">Time</label>
                <input
                  id="field-time"
                  type="time"
                  className={styles.fieldInput}
                  value={form.time}
                  onChange={(e) => setForm((f) => ({ ...f, time: e.target.value }))}
                />
              </div>
            )}
          </div>

          {/* All-day toggle */}
          <div className={styles.allDayRow}>
            <label className={styles.allDayLabel} htmlFor="field-allday">
              <input
                id="field-allday"
                type="checkbox"
                checked={form.allDay}
                onChange={(e) => setForm((f) => ({ ...f, allDay: e.target.checked }))}
              />
              All day
            </label>
          </div>

          {/* Location field */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="field-location">Location</label>
            <input
              id="field-location"
              type="text"
              className={styles.fieldInput}
              value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="Add location (optional)"
            />
          </div>
        </div>

        {/* VLM debug disclosure */}
        {event.raw_vlm_json && (
          <details className={styles.vlmDebug}>
            <summary className={styles.vlmSummary}>VLM debug</summary>
            <pre className={styles.vlmPre}>{event.raw_vlm_json}</pre>
          </details>
        )}
      </div>

      {/* Sticky bottom bar */}
      <div className={styles.stickyBottom}>
        <HBtn
          kind="primary"
          size="lg"
          className={styles.saveBtn}
          onClick={() => void handleSave()}
          disabled={saveDisabled}
        >
          Looks good — save
        </HBtn>
        <div className={styles.bottomRow}>
          <HBtn kind="ghost" className={styles.halfBtn} onClick={handleSkip}>
            Skip
          </HBtn>
          <HBtn kind="danger" className={styles.halfBtn} onClick={() => void handleReject()}>
            Reject
          </HBtn>
        </div>
      </div>
    </div>
  );
}
