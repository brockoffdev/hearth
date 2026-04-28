import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getUpload } from '../lib/uploads';
import type { UploadSummary } from '../lib/uploads';
import { subscribeUploadEvents } from '../lib/sseClient';
import type { StageUpdate } from '../lib/sseClient';
import { HEARTH_STAGES } from '../lib/stages';
import type { StageKey } from '../lib/stages';
import { formatETA } from '../lib/eta';
import { HBtn } from '../components/HBtn';
import { BackChevron } from '../components/BackChevron';
import { HearthWordmark } from '../components/HearthWordmark';
import { cn } from '../lib/cn';
import { ApiError } from '../lib/api';
import styles from './UploadDetail.module.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StageStatus = 'upcoming' | 'active' | 'done';

interface ProcessingState {
  upload: UploadSummary | null;
  loadError: string | null;
  currentStage: StageKey | null;
  cellProgress: { cell: number; total: number } | null;
  completedStages: string[];
  remainingSeconds: number | null;
  isComplete: boolean;
  isFailed: boolean;
  sseError: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive status for each stage given completed_stages + current active stage. */
function getStageStatus(
  key: string,
  currentStage: StageKey | null,
  completedStages: string[],
): StageStatus {
  if (completedStages.includes(key)) return 'done';
  if (key === currentStage) return 'active';
  return 'upcoming';
}

/** Count of completed stages for the "X of 10" header badge. */
function progressCount(
  currentStage: StageKey | null,
  completedStages: string[],
): number {
  const doneCount = completedStages.filter((k) =>
    HEARTH_STAGES.some((s) => s.key === k),
  ).length;
  // If currentStage is a real processing stage, count it as 1 active step
  const isActiveRealStage =
    currentStage !== null &&
    currentStage !== 'queued' &&
    currentStage !== 'done' &&
    !completedStages.includes(currentStage);
  return doneCount + (isActiveRealStage ? 1 : 0);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StageIcon({ status }: { status: StageStatus }) {
  if (status === 'done') {
    return (
      <span className={styles.stageIcon} aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" fill="var(--success)" />
          <path
            d="M7 12l3.5 3.5L17 9"
            stroke="#fff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    );
  }

  if (status === 'active') {
    return (
      <span className={cn(styles.stageIcon, styles.spinnerIcon)} aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke="var(--rule)"
            strokeWidth="2"
          />
          <path
            d="M12 3a9 9 0 0 1 9 9"
            stroke="var(--accent)"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      </span>
    );
  }

  // upcoming
  return (
    <span className={styles.stageIcon} aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="var(--rule)" strokeWidth="1.5" />
      </svg>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function UploadDetail(): JSX.Element {
  const { id: rawId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<ProcessingState>({
    upload: null,
    loadError: null,
    currentStage: null,
    cellProgress: null,
    completedStages: [],
    remainingSeconds: null,
    isComplete: false,
    isFailed: false,
    sseError: null,
  });

  const parsedId = rawId !== undefined ? parseInt(rawId, 10) : NaN;
  const isValidId = !isNaN(parsedId) && parsedId > 0;

  // Navigate away immediately if id is invalid
  useEffect(() => {
    if (!isValidId) {
      void navigate('/');
    }
  }, [isValidId, navigate]);

  // Fetch upload metadata and conditionally subscribe to SSE
  useEffect(() => {
    if (!isValidId) return;

    let cancelled = false;
    let sseCleanup: (() => void) | null = null;

    void (async () => {
      try {
        const upload = await getUpload(parsedId);
        if (cancelled) return;

        // Already in a terminal state — skip SSE
        if (upload.status === 'completed') {
          setState((prev) => ({ ...prev, upload, isComplete: true }));
          return;
        }
        if (upload.status === 'failed') {
          setState((prev) => ({ ...prev, upload, isFailed: true }));
          return;
        }

        setState((prev) => ({ ...prev, upload }));

        // Subscribe to SSE
        sseCleanup = subscribeUploadEvents(parsedId, {
          onStage: (update: StageUpdate) => {
            if (cancelled) return;

            if (update.stage === 'done') {
              setState((prev) => ({ ...prev, isComplete: true, sseError: null }));
              sseCleanup?.();
              sseCleanup = null;
              return;
            }

            setState((prev) => ({
              ...prev,
              currentStage: update.stage,
              cellProgress:
                update.progress !== null ? update.progress : prev.cellProgress,
              completedStages:
                update.completed_stages !== undefined
                  ? update.completed_stages
                  : prev.completedStages,
              remainingSeconds:
                update.remaining_seconds !== undefined
                  ? update.remaining_seconds
                  : prev.remainingSeconds,
              sseError: null,
            }));
          },
          onError: () => {
            if (cancelled) return;
            setState((prev) => ({ ...prev, sseError: 'Connection lost' }));
          },
        });
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof ApiError && err.status === 404
            ? 'not_found'
            : 'load_error';
        setState((prev) => ({ ...prev, loadError: message }));
      }
    })();

    return () => {
      cancelled = true;
      sseCleanup?.();
    };
  }, [parsedId, isValidId]);

  // ── Render guards ──────────────────────────────────────────────────────────

  if (!isValidId) {
    // Will redirect via useEffect; render nothing in the meantime
    return <div className={styles.page} />;
  }

  if (state.loadError === 'not_found') {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <HearthWordmark size={20} />
        </header>
        <div className={styles.errorView} role="alert">
          <p className={styles.errorTitle}>Upload not found</p>
          <HBtn kind="ghost" onClick={() => void navigate('/')}>
            Back home
          </HBtn>
        </div>
      </div>
    );
  }

  if (state.loadError === 'load_error') {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <HearthWordmark size={20} />
        </header>
        <div className={styles.errorView} role="alert">
          <p className={styles.errorTitle}>Failed to load upload</p>
          <HBtn kind="ghost" onClick={() => void navigate('/')}>
            Back home
          </HBtn>
        </div>
      </div>
    );
  }

  // ── Terminal: failed upload ────────────────────────────────────────────────

  if (state.isFailed) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <HearthWordmark size={20} />
        </header>
        <div className={styles.errorView}>
          <div className={styles.terminalIcon} aria-label="Failed">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" fill="var(--danger)" opacity="0.15" />
              <path
                d="M8 8l8 8M16 8l-8 8"
                stroke="var(--danger)"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <p className={styles.errorTitle}>Processing failed</p>
          <p className={styles.errorHint}>Something went wrong. Please try again.</p>
          <HBtn kind="primary" onClick={() => void navigate('/')}>
            Back home
          </HBtn>
        </div>
      </div>
    );
  }

  // ── Terminal: complete ─────────────────────────────────────────────────────

  if (state.isComplete) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <HearthWordmark size={20} />
        </header>
        <div className={styles.completeView}>
          <div className={styles.terminalIcon} aria-label="Complete">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="11" fill="var(--success)" opacity="0.15" />
              <circle cx="12" cy="12" r="10" stroke="var(--success)" strokeWidth="1.5" />
              <path
                d="M7 12l3.5 3.5L17 9"
                stroke="var(--success)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <p className={styles.completeTitle}>Done!</p>
          <p className={styles.completeHint}>
            Processing complete — your calendar has been read.
          </p>
          <HBtn kind="primary" onClick={() => void navigate('/')}>
            Back home
          </HBtn>
        </div>
      </div>
    );
  }

  // ── Processing view ────────────────────────────────────────────────────────

  const count = progressCount(state.currentStage, state.completedStages);
  // All stages except 'done' are shown in the checklist (9 processing stages + done = 10 total)
  const displayStages = HEARTH_STAGES;

  // Queued state: currentStage is 'queued', all real stages are upcoming
  const isQueued = state.currentStage === 'queued';

  // Subtitle copy differs for queued vs processing
  const subtitleNode = isQueued ? (
    <p className={styles.subtitle}>
      <strong>{formatETA(state.remainingSeconds)}</strong> total · waiting in queue
    </p>
  ) : (
    <p className={styles.subtitle}>
      <strong>{formatETA(state.remainingSeconds)}</strong> remaining · we&apos;ll let you know when it&apos;s done.
    </p>
  );

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <BackChevron onClick={() => void navigate('/uploads')} />
        <span className={styles.headerMeta}>Upload #{parsedId} · started {state.upload?.thumbLabel ?? '…'}</span>
        <span className={styles.progressBadge} aria-live="polite">
          {count > 0 ? `${count} of ${HEARTH_STAGES.length - 1}` : 'Starting…'}
        </span>
      </header>

      {/* Title block */}
      <div className={styles.titleBlock}>
        <h1 className={styles.titleHeading}>Reading your<br />wall calendar…</h1>
        {subtitleNode}
      </div>

      {/* Photo thumbnail */}
      {state.upload && (
        <div className={styles.thumbWrap}>
          <img
            src={`/api/uploads/${parsedId}/photo`}
            alt="Your calendar photo"
            className={styles.photoThumb}
          />
        </div>
      )}

      {/* SSE error banner */}
      {state.sseError && (
        <div className={styles.sseErrorBanner} role="alert">
          {state.sseError}
        </div>
      )}

      {/* Stage checklist */}
      <ol className={styles.stageList} aria-label="Processing stages">
        {displayStages.map((stage) => {
          // Skip 'done' sentinel in checklist when queued (all are upcoming)
          const status = isQueued
            ? 'upcoming'
            : getStageStatus(stage.key, state.currentStage, state.completedStages);

          // For the active cell_progress stage, replace hint with dynamic text
          const hintText =
            status === 'active' &&
            stage.key === 'cell_progress' &&
            state.cellProgress !== null
              ? `Reading cell ${state.cellProgress.cell} of ${state.cellProgress.total}`
              : stage.hint;

          return (
            <li
              key={stage.key}
              className={styles.stageRow}
              data-status={status}
            >
              <StageIcon status={status} />
              <div className={styles.stageText}>
                <span className={styles.stageLabel}>{stage.label}</span>
                {hintText && (
                  <span className={styles.stageHint}>{hintText}</span>
                )}
                {status === 'active' &&
                  stage.key === 'cell_progress' &&
                  state.cellProgress !== null && (
                    <div
                      className={styles.cellBar}
                      role="progressbar"
                      aria-valuenow={state.cellProgress.cell}
                      aria-valuemax={state.cellProgress.total}
                    >
                      <div
                        className={styles.cellBarFill}
                        style={{
                          // CSS custom property — allowed by spec
                          ['--cell-pct' as string]: `${(state.cellProgress.cell / state.cellProgress.total) * 100}%`,
                        }}
                      />
                    </div>
                  )}
              </div>
            </li>
          );
        })}
      </ol>

      {/* Sticky bottom bar — only during active processing/queued */}
      <div className={styles.stickyBottom}>
        <HBtn
          kind="primary"
          size="lg"
          className={styles.continueButton}
          onClick={() => void navigate('/uploads')}
        >
          Continue in background
        </HBtn>
        <p className={styles.continueExplain}>
          Keeps running on the server. Check back from Uploads.
        </p>
      </div>
    </div>
  );
}
