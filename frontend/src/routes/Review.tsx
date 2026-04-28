import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { listEvents } from '../lib/events';
import type { Event } from '../lib/events';
import { Spinner } from '../components/Spinner';
import { EventCard } from '../components/EventCard';
import { MobileTabBar } from '../components/MobileTabBar';
import styles from './Review.module.css';

// ---------------------------------------------------------------------------
// useReviewQueue — fetch pending_review events
// ---------------------------------------------------------------------------

type QueueState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'ready'; events: Event[] };

function useReviewQueue(fetchTrigger: number): QueueState {
  const [state, setState] = useState<QueueState>({ phase: 'loading' });

  useEffect(() => {
    let cancelled = false;
    setState({ phase: 'loading' });

    void (async () => {
      try {
        const data = await listEvents({ status: 'pending_review' });
        if (!cancelled) {
          setState({ phase: 'ready', events: data.items });
        }
      } catch {
        if (!cancelled) {
          setState({ phase: 'error', message: 'Failed to load review queue' });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchTrigger]);

  return state;
}

// ---------------------------------------------------------------------------
// Review route
// ---------------------------------------------------------------------------

export function Review(): JSX.Element {
  const navigate = useNavigate();
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const state = useReviewQueue(fetchTrigger);

  const handleRetry = () => setFetchTrigger((n) => n + 1);

  const eventCount = state.phase === 'ready' ? state.events.length : null;

  return (
    <div className={styles.page}>
      <div className={styles.scrollArea}>
        <div className={styles.titleBlock}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>Review</h1>
            {eventCount !== null && (
              <span className={styles.count}>{eventCount} {eventCount === 1 ? 'item' : 'items'}</span>
            )}
          </div>
          <p className={styles.subtitle}>Below 85% confidence. Tap to confirm or fix.</p>
        </div>

        {state.phase === 'loading' && (
          <div className={styles.centered}>
            <Spinner size={24} ariaLabel="Loading review queue" />
          </div>
        )}

        {state.phase === 'error' && (
          <div className={styles.errorBanner} role="alert">
            <span>{state.message}</span>
            <button type="button" className={styles.retryBtn} onClick={handleRetry}>
              Retry
            </button>
          </div>
        )}

        {state.phase === 'ready' && state.events.length === 0 && (
          <div className={styles.emptyCard}>
            <p className={styles.emptyHint}>All caught up — nothing to review.</p>
            <Link to="/uploads" className={styles.emptyLink}>View uploads</Link>
          </div>
        )}

        {state.phase === 'ready' && state.events.length > 0 && (
          <div className={styles.cardList}>
            {state.events.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                showCellCrop={true}
                onClick={() => void navigate(`/review/${event.id}`)}
              />
            ))}
          </div>
        )}
      </div>

      <MobileTabBar active="review" />
    </div>
  );
}
