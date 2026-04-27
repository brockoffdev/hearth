/**
 * SetupFamily — Wizard step 3: Map family members to Google calendars.
 *
 * Fetches:
 *   GET /api/admin/family       — current family members with calendar mappings
 *   GET /api/google/calendars   — available calendars on the connected Google account
 *
 * Actions:
 *   PATCH /api/admin/family/{id}  — update a member's calendar immediately on select
 *   POST  /api/google/calendars   — create a new calendar, auto-apply to the row
 *   POST  /api/setup/complete-google — finalize wizard, then refresh + navigate to /
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DesktopShell } from '../components/DesktopShell';
import { HBtn } from '../components/HBtn';
import { WizardSteps } from '../components/WizardSteps';
import type { WizardStep } from '../components/WizardSteps';
import { useAuth } from '../auth/AuthProvider';
import styles from './SetupFamily.module.css';

// ---------------------------------------------------------------------------
// Wizard step configuration
// ---------------------------------------------------------------------------

const WIZARD_STEPS: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'done' },
  { key: 'google', label: 'Google', status: 'done' },
  { key: 'family', label: 'Family', status: 'active' },
];

// ---------------------------------------------------------------------------
// API types
// ---------------------------------------------------------------------------

interface FamilyMemberData {
  id: number;
  name: string;
  color_hex_center: string;
  google_calendar_id: string | null;
}

interface GoogleCalendarData {
  id: string;
  summary: string;
  primary?: boolean | null;
  access_role?: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SetupFamily() {
  const navigate = useNavigate();
  const { refresh } = useAuth();

  // Data state
  const [members, setMembers] = useState<FamilyMemberData[]>([]);
  const [calendars, setCalendars] = useState<GoogleCalendarData[]>([]);
  const [loading, setLoading] = useState(true);

  // Per-row create form state: which row's create form is open
  const [openCreateForId, setOpenCreateForId] = useState<number | null>(null);
  // Per-row create form input value (keyed by member id)
  const [createName, setCreateName] = useState<Record<number, string>>({});
  const [creating, setCreating] = useState(false);

  // Finish state
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);

  // Calendar load error state
  const [loadError, setLoadError] = useState<string | null>(null);

  // On mount: fetch family members and calendars in parallel.
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        const [familyRes, calendarsRes] = await Promise.all([
          fetch('/api/admin/family', { credentials: 'include' }),
          fetch('/api/google/calendars', { credentials: 'include' }),
        ]);
        if (cancelled) return;
        if (familyRes.ok) {
          const data = (await familyRes.json()) as FamilyMemberData[];
          setMembers(data);
        }
        if (calendarsRes.ok) {
          const data = (await calendarsRes.json()) as GoogleCalendarData[];
          setCalendars(data);
          setLoadError(null);
        } else {
          setLoadError(
            "Couldn't load your Google calendars. Use 'Create new' to add one — we'll create it on Google Calendar for you.",
          );
        }
      } catch {
        if (!cancelled) {
          setLoadError(
            "Couldn't load your Google calendars. Use 'Create new' to add one — we'll create it on Google Calendar for you.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  // Derived: how many members have a calendar mapped.
  const mappedCount = members.filter((m) => m.google_calendar_id !== null).length;
  const allMapped = mappedCount === 5;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleSelectCalendar(memberId: number, calendarId: string | null) {
    // Optimistic update.
    setMembers((prev) =>
      prev.map((m) =>
        m.id === memberId ? { ...m, google_calendar_id: calendarId } : m,
      ),
    );

    try {
      const res = await fetch(`/api/admin/family/${memberId}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ google_calendar_id: calendarId }),
      });
      if (res.ok) {
        const updated = (await res.json()) as FamilyMemberData;
        setMembers((prev) =>
          prev.map((m) => (m.id === updated.id ? updated : m)),
        );
      } else {
        // Revert optimistic update on failure.
        setMembers((prev) =>
          prev.map((m) =>
            m.id === memberId ? { ...m, google_calendar_id: null } : m,
          ),
        );
      }
    } catch {
      // Revert on network error.
      setMembers((prev) =>
        prev.map((m) =>
          m.id === memberId ? { ...m, google_calendar_id: null } : m,
        ),
      );
    }
  }

  async function handleCreateCalendar(memberId: number) {
    const name = (createName[memberId] ?? '').trim();
    if (!name) return;

    setCreating(true);
    try {
      const res = await fetch('/api/google/calendars', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: name }),
      });
      if (!res.ok) return;
      const newCal = (await res.json()) as GoogleCalendarData;
      // Add to local calendar list.
      setCalendars((prev) => [...prev, newCal]);
      // Close the form.
      setOpenCreateForId(null);
      setCreateName((prev) => ({ ...prev, [memberId]: '' }));
      // Auto-apply to this row.
      await handleSelectCalendar(memberId, newCal.id);
    } catch {
      // Non-fatal.
    } finally {
      setCreating(false);
    }
  }

  async function handleFinish() {
    setFinishError(null);
    setFinishing(true);
    try {
      const res = await fetch('/api/setup/complete-google', {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        await refresh();
        navigate('/');
      } else {
        let detail = 'Setup could not be completed — please try again';
        try {
          const data = (await res.json()) as { detail?: string };
          if (data.detail) detail = data.detail;
        } catch {
          // ignore
        }
        setFinishError(detail);
      }
    } catch {
      setFinishError('Network error — please try again');
    } finally {
      setFinishing(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <DesktopShell width={1100} height={780}>
      <div className={styles.outer}>
        <div className={styles.inner}>
          <div className={styles.breadcrumbRow}>
            <WizardSteps steps={WIZARD_STEPS} />
          </div>

          <div className={styles.stepLabel}>Step 3 of 3</div>
          <h1 className={styles.title}>
            Map family members to <em>Google calendars</em>
          </h1>
          <p className={styles.subtitle}>
            Each family member's hand-written events go to their own Google Calendar.
            We'll create them now if they don't exist yet.
          </p>

          <p className={styles.statusLine}>
            <strong>{mappedCount} of 5</strong> mapped
          </p>

          {loadError !== null && (
            <div className={styles.errorBanner} role="alert">
              {loadError}
            </div>
          )}

          {!loading && loadError === null && calendars.length === 0 && (
            <div className={styles.infoBanner} role="status">
              Your Google account has no calendars yet. Use &lsquo;Create new&rsquo; on each row
              to add the family&rsquo;s calendars.
            </div>
          )}

          <div className={styles.tableCard}>
            <div className={styles.tableHeader}>
              <span>Member</span>
              <span>Google Calendar</span>
              <span></span>
            </div>

            {loading ? (
              <div className={styles.tableRow}>
                <span className={styles.loadingText}>Loading…</span>
              </div>
            ) : (
              members.map((member) => {
                const isCreateOpen = openCreateForId === member.id;

                return (
                  <div key={member.id} className={styles.tableRow}>
                    {/* Member name cell — colored dot + name */}
                    <div className={styles.memberCell}>
                      <span
                        className={styles.familyDot}
                        style={{ background: member.color_hex_center }}
                      />
                      <span className={styles.familyName}>{member.name}</span>
                    </div>

                    {/* Calendar cell — dropdown + optional create form */}
                    <div className={styles.calendarCell}>
                      <div className={styles.selectRow}>
                        <select
                          className={styles.calSelect}
                          value={member.google_calendar_id ?? ''}
                          onChange={(e) => {
                            const val = e.target.value || null;
                            void handleSelectCalendar(member.id, val);
                          }}
                          aria-label={`Calendar for ${member.name}`}
                        >
                          <option value="">— select a calendar —</option>
                          {calendars.map((cal) => (
                            <option key={cal.id} value={cal.id}>
                              {cal.summary}
                            </option>
                          ))}
                        </select>
                      </div>

                      {isCreateOpen ? (
                        <div className={styles.createForm}>
                          <input
                            className={styles.createInput}
                            type="text"
                            placeholder="Calendar name"
                            value={createName[member.id] ?? member.name}
                            onChange={(e) =>
                              setCreateName((prev) => ({
                                ...prev,
                                [member.id]: e.target.value,
                              }))
                            }
                          />
                          <button
                            className={styles.createBtn}
                            type="button"
                            disabled={creating || !(createName[member.id] ?? member.name).trim()}
                            onClick={() => void handleCreateCalendar(member.id)}
                          >
                            Create
                          </button>
                          <button
                            className={styles.createCancelBtn}
                            type="button"
                            onClick={() => setOpenCreateForId(null)}
                          >
                            ✕
                          </button>
                        </div>
                      ) : null}
                    </div>

                    {/* Action cell — "Create new" button */}
                    <div className={styles.actionCell}>
                      {!isCreateOpen && (
                        <HBtn
                          size="sm"
                          onClick={() => {
                            setOpenCreateForId(member.id);
                            setCreateName((prev) => ({
                              ...prev,
                              [member.id]: prev[member.id] ?? member.name,
                            }));
                          }}
                        >
                          Create new
                        </HBtn>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {finishError && (
            <div className={styles.errorBanner} role="alert">
              {finishError}
            </div>
          )}

          <div className={styles.actions}>
            <span className={styles.spacer} />
            <HBtn onClick={() => navigate('/setup/google')}>Back</HBtn>
            <HBtn
              kind="primary"
              size="lg"
              disabled={!allMapped || finishing}
              onClick={() => void handleFinish()}
            >
              {finishing ? 'Finishing…' : 'Finish setup'}
            </HBtn>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}
