import { useNavigate } from 'react-router-dom';
import { useUploads } from '../lib/useUploads';
import type { Upload } from '../lib/uploads';
import { formatETA, formatDuration } from '../lib/eta';
import { HEARTH_STAGES } from '../lib/stages';
import { Spinner } from '../components/Spinner';
import { ThumbTile } from '../components/ThumbTile';
import { SectionRule } from '../components/SectionRule';
import { Chevron } from '../components/Chevron';
import { HBtn } from '../components/HBtn';
import { MobileTabBar } from '../components/MobileTabBar';
import { useNewCaptureSheet } from '../components/NewCaptureSheet';
import styles from './Status.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** 9 stages that count toward progress (all except 'done') */
const TOTAL_STAGES = HEARTH_STAGES.length - 1;

function stageLabel(key: string): string {
  const stage = HEARTH_STAGES.find((s) => s.key === key);
  return stage ? stage.label : key;
}

// ---------------------------------------------------------------------------
// InflightRow — actively running (current_stage !== 'queued')
// (exported for DesignSmoke preview)
// ---------------------------------------------------------------------------

interface InflightRowProps {
  upload: Upload;
}

export function InflightRow({ upload }: InflightRowProps): JSX.Element {
  const navigate = useNavigate();
  const completed = (upload.completed_stages ?? []).length;
  const pct = Math.min(100, Math.round((completed / TOTAL_STAGES) * 100));
  const isCellStage = upload.current_stage === 'cell_progress' && upload.cellProgress != null;
  const headline = isCellStage
    ? `${stageLabel(upload.current_stage ?? '')} · ${upload.cellProgress} of ${upload.totalCells}`
    : stageLabel(upload.current_stage ?? '');

  return (
    <div
      className={styles.row}
      data-status="inflight"
      data-testid={`inflight-row-${upload.id}`}
    >
      <ThumbTile accent="var(--accent)">📷</ThumbTile>
      <div className={styles.rowBody}>
        <div className={styles.stageRow}>
          <Spinner size={12} className={styles.spinnerWrap} />
          <span className={styles.stageLabel}>{headline}</span>
        </div>
        <div className={styles.subtext}>
          {upload.thumbLabel} · started {upload.startedAt ?? '—'}
          {(upload.queuedBehind ?? 0) > 0 ? ` · waiting on ${upload.queuedBehind} ahead` : ''}
        </div>
        <div className={styles.progressTrack}>
          <div
            className={styles.progressFill}
            data-testid="progress-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className={styles.rowFooter}>
          <span className={styles.etaText}>
            <strong className={styles.etaMono}>{formatETA(upload.remaining_seconds)}</strong>
            {' '}remaining
          </span>
          <button
            type="button"
            className={styles.openLink}
            onClick={() => navigate(`/uploads/${upload.id}`)}
          >
            Open ↗
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// QueuedRow — waiting in queue (current_stage === 'queued')
// ---------------------------------------------------------------------------

interface QueuedRowProps {
  upload: Upload;
  position: number;
  cancel: (id: string) => void;
}

export function QueuedRow({ upload, position, cancel }: QueuedRowProps): JSX.Element {
  const queuedBehind = upload.queuedBehind ?? 0;
  const headline = `Waiting · ${queuedBehind} ${queuedBehind === 1 ? 'photo' : 'photos'} ahead`;

  return (
    <div
      className={styles.row}
      data-status="queued"
      data-testid={`queued-row-${upload.id}`}
    >
      <div className={styles.thumbWrap}>
        <ThumbTile>📷</ThumbTile>
        <div className={styles.posBadge} data-testid="pos-badge">
          {position}
        </div>
      </div>
      <div className={styles.rowBody}>
        <div className={styles.stageRow}>
          {/* Clock icon */}
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
            data-testid="clock-icon"
            className={styles.clockIcon}
          >
            <circle cx="12" cy="12" r="9" stroke="var(--fgSoft)" strokeWidth="1.8" />
            <path d="M12 7v5l3 2" stroke="var(--fgSoft)" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <span className={styles.stageLabel}>{headline}</span>
        </div>
        <div className={styles.subtext}>
          {upload.thumbLabel} · started {upload.startedAt ?? '—'}
        </div>
        <div className={styles.progressTrack}>
          <div className={styles.progressStripe} data-testid="progress-stripe" />
        </div>
        <div className={styles.rowFooter}>
          <span className={styles.etaText}>
            <strong className={styles.etaMono}>{formatETA(upload.remaining_seconds)}</strong>
            {' '}total
          </span>
          <button
            type="button"
            className={styles.cancelLink}
            onClick={() => void cancel(upload.id)}
          >
            Cancel ×
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CompletedRow
// ---------------------------------------------------------------------------

interface CompletedRowProps {
  upload: Upload;
}

export function CompletedRow({ upload }: CompletedRowProps): JSX.Element {
  const navigate = useNavigate();
  const found = upload.found ?? 0;
  const review = upload.review ?? 0;
  const titleText = `${found} events found${review > 0 ? `, ${review} need review` : ''}`;
  const durationText = upload.durationSec != null ? formatDuration(upload.durationSec) : null;

  return (
    <div
      role="link"
      aria-label={titleText}
      className={styles.row}
      data-status="completed"
      data-testid={`completed-row-${upload.id}`}
      onClick={() => navigate(`/uploads/${upload.id}`)}
      onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/uploads/${upload.id}`); }}
      tabIndex={0}
      style={{ cursor: 'pointer' }}
    >
      <ThumbTile>✓</ThumbTile>
      <div className={styles.rowBody}>
        <div className={styles.rowTitle}>{titleText}</div>
        <div className={styles.subtext}>
          {upload.thumbLabel}
          {upload.finishedAt ? ` · ${upload.finishedAt}` : ''}
          {durationText ? ` · took ${durationText}` : ''}
        </div>
      </div>
      <Chevron />
    </div>
  );
}

// ---------------------------------------------------------------------------
// FailedRow
// ---------------------------------------------------------------------------

interface FailedRowProps {
  upload: Upload;
  retry: (id: string) => void;
}

export function FailedRow({ upload, retry }: FailedRowProps): JSX.Element {
  return (
    <div
      className={styles.row}
      data-status="failed"
      data-testid={`failed-row-${upload.id}`}
    >
      <ThumbTile accent="var(--danger)">!</ThumbTile>
      <div className={styles.rowBody}>
        <div className={styles.rowTitle}>Couldn't read this one</div>
        <div className={styles.subtext}>
          {upload.thumbLabel}{upload.error ? ` · ${upload.error}` : ''}
        </div>
      </div>
      <HBtn
        kind="default"
        size="sm"
        onClick={() => void retry(upload.id)}
      >
        Retry
      </HBtn>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CTA button
// ---------------------------------------------------------------------------

interface CTAButtonProps {
  onClick: () => void;
}

function CTAButton({ onClick }: CTAButtonProps): JSX.Element {
  return (
    <div className={styles.ctaWrap}>
      <button
        type="button"
        className={styles.ctaBtn}
        onClick={onClick}
        aria-label="New capture"
      >
        <span className={styles.ctaIcon}>＋</span>
        <span className={styles.ctaText}>
          <span className={styles.ctaTitle}>New capture</span>
          <span className={styles.ctaSubtitle}>Camera or photo library</span>
        </span>
        <Chevron color="#fff" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status route
// ---------------------------------------------------------------------------

export function Status(): JSX.Element {
  const { uploads, inflightCount, longestETA, isLoading, loadError, retry, cancel } = useUploads();
  const sheet = useNewCaptureSheet();

  const inflight  = uploads.filter((u) => u.status === 'processing' && u.current_stage !== 'queued');
  const queued    = uploads.filter((u) => u.status === 'processing' && u.current_stage === 'queued');
  const completed = uploads.filter((u) => u.status === 'completed');
  const failed    = uploads.filter((u) => u.status === 'failed');

  const allInflight = [...inflight, ...queued]; // combined for section rule count
  const isEmpty = !isLoading && !loadError && uploads.length === 0;

  const handleRetry  = (id: string) => { void retry(id); };
  const handleCancel = (id: string) => { void cancel(id); };

  return (
    <div className={styles.page}>
      <div className={styles.scrollArea}>
        {/* Header bar */}
        <div className={styles.headerBar}>
          <span className={styles.headerSpacer} />
          <span className={styles.pullHint}>Pull to refresh</span>
        </div>

        {/* Title block */}
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Uploads</h1>
          {!isEmpty && (
            <p className={styles.subtitle}>
              {inflightCount > 0 ? (
                <>
                  <strong className={styles.subtitleProcessing}>{inflightCount} processing</strong>
                  {' · longest '}{formatETA(longestETA)}{' remaining'}
                </>
              ) : (
                `All caught up · ${completed.length} recent`
              )}
            </p>
          )}
          {isEmpty && (
            <p className={styles.subtitle}>Nothing here yet</p>
          )}
        </div>

        {/* + New capture CTA */}
        <CTAButton onClick={() => sheet.open()} />

        {/* Loading state */}
        {isLoading && uploads.length === 0 && (
          <div className={styles.centered}>
            <Spinner size={24} ariaLabel="Loading uploads" />
          </div>
        )}

        {/* Error state */}
        {loadError && (
          <div className={styles.errorBanner} role="alert">
            {loadError}
          </div>
        )}

        {/* Empty state */}
        {isEmpty && (
          <div className={styles.centered} data-testid="empty-state">
            <span className={styles.emptyIcon} role="img" aria-label="Calendar">📅</span>
            <p className={styles.emptyHint}>
              Take a photo of the wall calendar to get started.
            </p>
          </div>
        )}

        {/* In flight section */}
        {allInflight.length > 0 && (
          <>
            <SectionRule
              label="In flight"
              dotColor="var(--accent)"
              count={allInflight.length}
            />
            <div className={styles.sectionList}>
              {inflight.map((u) => (
                <InflightRow key={u.id} upload={u} />
              ))}
              {queued.map((u, idx) => (
                <QueuedRow
                  key={u.id}
                  upload={u}
                  position={inflight.length + idx + 1}
                  cancel={handleCancel}
                />
              ))}
            </div>
          </>
        )}

        {/* Done section */}
        {completed.length > 0 && (
          <>
            <SectionRule
              label="Done"
              dotColor="var(--success)"
              count={completed.length}
              marginTop={allInflight.length > 0 ? 18 : 6}
            />
            <div className={styles.sectionList}>
              {completed.map((u) => (
                <CompletedRow key={u.id} upload={u} />
              ))}
            </div>
          </>
        )}

        {/* Couldn't read section */}
        {failed.length > 0 && (
          <>
            <SectionRule
              label="Couldn't read"
              dotColor="var(--danger)"
              count={failed.length}
              marginTop={18}
            />
            <div className={styles.sectionListPadded}>
              {failed.map((u) => (
                <FailedRow key={u.id} upload={u} retry={handleRetry} />
              ))}
            </div>
          </>
        )}
      </div>

      <MobileTabBar active="uploads" />
    </div>
  );
}
