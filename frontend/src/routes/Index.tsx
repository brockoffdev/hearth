import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../design/ThemeProvider';
import { THEME_LABELS } from '../design/themeLabels';
import { useAuth } from '../auth/AuthProvider';
import { HearthWordmark } from '../components/HearthWordmark';
import { listUploads } from '../lib/uploads';
import type { UploadSummary } from '../lib/uploads';
import { formatRelativeTime } from '../lib/relativeTime';
import styles from './Index.module.css';

// ---------------------------------------------------------------------------
// Status indicator labels + classes
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<UploadSummary['status'], string> = {
  queued:     'Queued',
  processing: 'Processing',
  completed:  'Done',
  failed:     'Failed',
};

// ---------------------------------------------------------------------------
// UploadRow
// ---------------------------------------------------------------------------

function UploadRow({ upload }: { upload: UploadSummary }) {
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
// Index (MobileHome)
// ---------------------------------------------------------------------------

export function Index(): JSX.Element {
  const { theme, cycleTheme } = useTheme();
  const { state, logout } = useAuth();

  const username =
    state.status === 'authenticated' ? state.user.username : '';

  const [uploads, setUploads] = useState<UploadSummary[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);

  useEffect(() => {
    // Only fetch once we know the user is authenticated
    if (state.status !== 'authenticated') return;

    let cancelled = false;
    setUploads(null);
    setLoadError(false);

    listUploads()
      .then((data) => {
        if (cancelled) return;
        setUploads(data);
        setLastSyncTime(new Date());
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [state.status]);

  const visibleUploads = Array.isArray(uploads) ? uploads.slice(0, 10) : null;

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
        {/* Greeting */}
        <h1 className={styles.greeting}>{`Hi, ${username}.`}</h1>
        <p className={styles.subhead}>
          Snap a photo of the wall calendar — Hearth will read it and sort the
          events to your Google calendars.
        </p>

        {/* Take a photo CTA */}
        <Link to="/upload" className={styles.ctaLink}>
          📷 Take a photo
        </Link>

        {/* Recent uploads */}
        <section className={styles.recentSection}>
          <h2 className={styles.sectionTitle}>Recent uploads</h2>

          {/* Loading state */}
          {uploads === null && !loadError && (
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
          {lastSyncTime !== null && (
            <p className={styles.lastSync}>
              Last sync: {formatRelativeTime(lastSyncTime.toISOString())}
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
