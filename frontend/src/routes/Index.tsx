import { Link } from 'react-router-dom';
import { useTheme } from '../design/ThemeProvider';
import { THEME_LABELS } from '../design/themeLabels';
import { useAuth } from '../auth/AuthProvider';
import { HearthWordmark } from '../components/HearthWordmark';
import { useNewCaptureSheet } from '../components/NewCaptureSheet';
import { Spinner } from '../components/Spinner';
import { Chevron } from '../components/Chevron';
import { cn } from '../lib/cn';
import type { Upload } from '../lib/uploads';
import { formatRelativeTime } from '../lib/relativeTime';
import { formatETA } from '../lib/eta';
import { useUploads } from '../lib/useUploads';
import { MobileTabBar } from '../components/MobileTabBar';
import { OAuthHealthBanner } from '../components/OAuthHealthBanner';
import styles from './Index.module.css';

// ---------------------------------------------------------------------------
// Status indicator labels + classes
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<Upload['status'], string> = {
  processing: 'Processing',
  completed:  'Done',
  failed:     'Failed',
};

// ---------------------------------------------------------------------------
// UploadRow
// ---------------------------------------------------------------------------

function UploadRow({ upload }: { upload: Upload }) {
  return (
    <Link to={`/uploads/${upload.id}`} className={styles.uploadRow}>
      <img
        src={upload.url}
        alt="Wall calendar photo"
        loading="lazy"
        className={styles.thumbnail}
      />
      <div className={styles.rowContent}>
        <span className={styles.rowTime}>{formatRelativeTime(upload.uploaded_at)}</span>
      </div>
      <div className={styles.statusIndicator} data-status={upload.status}>
        <span className={styles.statusDot} data-status={upload.status} />
        <span className={styles.statusLabel}>{STATUS_LABELS[upload.status]}</span>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// SkeletonRow
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className={styles.skeletonRow} data-testid="skeleton-row">
      <div className={styles.skeletonThumb} />
      <div className={styles.skeletonContent}>
        <div className={styles.skeletonLine} style={{ '--w': '60%' } as React.CSSProperties} />
        <div className={styles.skeletonLine} style={{ '--w': '40%' } as React.CSSProperties} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// InflightBanner — renders only when inflightCount > 0
// ---------------------------------------------------------------------------

function InflightBanner({ count, longestETA }: { count: number; longestETA: number }) {
  if (count === 0) return null;

  return (
    <Link
      to="/uploads"
      className={styles.banner}
      data-testid="inflight-banner"
    >
      <Spinner size={18} ariaLabel="Processing" />
      <div className={styles.bannerText}>
        <strong>{count === 1 ? '1 photo processing…' : `${count} photos processing…`}</strong>
        <span className={styles.bannerSubtext}>
          {formatETA(longestETA)} remaining · we&apos;ll notify when done
        </span>
      </div>
      <span className={styles.bannerCTA}>View →</span>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// UploadsLink — always visible footer link
// ---------------------------------------------------------------------------

function UploadsLink({ hasInflight }: { hasInflight: boolean }) {
  return (
    <Link
      to="/uploads"
      className={cn(styles.uploadsLink, hasInflight && styles.uploadsLinkActive)}
    >
      <span>View all uploads</span>
      <Chevron />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Index (MobileHome)
// ---------------------------------------------------------------------------

export function Index(): JSX.Element {
  const { theme, cycleTheme } = useTheme();
  const { state, logout } = useAuth();
  const sheet = useNewCaptureSheet();

  const username =
    state.status === 'authenticated' ? state.user.username : '';

  const { uploads, isLoading, loadError, inflightCount, longestETA, lastFetchedAt } = useUploads();

  const visibleUploads = isLoading ? null : uploads.slice(0, 10);

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <HearthWordmark size={20} />
        <div className={styles.headerActions}>
          <button className={styles.themeToggle} onClick={cycleTheme}>
            {THEME_LABELS[theme]}
          </button>
          <button
            className={styles.logoutBtn}
            onClick={() => void logout()}
          >
            Log out
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className={styles.main}>
        {/* OAuth health banner — shown when Google Calendar is disconnected */}
        <OAuthHealthBanner />

        {/* Greeting */}
        <h1 className={styles.greeting}>{`Hi, ${username}.`}</h1>
        <p className={styles.subhead}>
          Snap a photo of the wall calendar — Hearth will read it and sort the
          events to your Google calendars.
        </p>

        {/* In-flight banner — only when uploads are processing */}
        <InflightBanner count={inflightCount} longestETA={longestETA} />

        {/* Take a photo CTA */}
        <button type="button" className={styles.ctaLink} onClick={sheet.open}>
          📷 Take a photo
        </button>

        {/* Recent uploads */}
        <section className={styles.recentSection}>
          <h2 className={styles.sectionTitle}>Recent uploads</h2>

          {/* Loading state */}
          {visibleUploads === null && !loadError && (
            <div className={styles.skeletonList}>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          )}

          {/* Error state */}
          {loadError && (
            <div className={styles.errorBanner} role="alert">
              Couldn&apos;t load uploads. Try refreshing.
            </div>
          )}

          {/* Empty state */}
          {visibleUploads !== null && visibleUploads.length === 0 && (
            <div className={styles.emptyState}>
              <span className={styles.emptyIcon}>📷</span>
              <p className={styles.emptyText}>
                No photos yet. Take your first one above!
              </p>
            </div>
          )}

          {/* Loaded: upload rows */}
          {visibleUploads !== null && visibleUploads.length > 0 && (
            <ul className={styles.uploadList}>
              {visibleUploads.map((upload) => (
                <li key={upload.id} className={styles.uploadListItem}>
                  <UploadRow upload={upload} />
                </li>
              ))}
            </ul>
          )}

          {/* Last sync */}
          {lastFetchedAt !== null && (
            <p className={styles.lastSync}>
              Last sync: {formatRelativeTime(lastFetchedAt.toISOString())}
            </p>
          )}
        </section>

        {/* View all uploads link — always visible */}
        <UploadsLink hasInflight={inflightCount > 0} />
      </main>

      <MobileTabBar active="home" />
    </div>
  );
}
