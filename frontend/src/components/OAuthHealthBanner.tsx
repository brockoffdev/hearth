import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { useGoogleHealth } from '../lib/useGoogleHealth';
import styles from './OAuthHealthBanner.module.css';

interface OAuthHealthBannerProps {
  className?: string;
}

function WarningIcon(): JSX.Element {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={styles.icon}
    >
      <path
        d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <line x1="12" y1="9" x2="12" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="12" y1="17" x2="12.01" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function OAuthHealthBanner({ className }: OAuthHealthBannerProps): JSX.Element | null {
  const { connected, isLoading } = useGoogleHealth();
  const { state } = useAuth();
  const navigate = useNavigate();

  if (isLoading || connected) return null;

  const isAdmin =
    state.status === 'authenticated' && state.user.role === 'admin';

  return (
    <div className={`${styles.banner}${className ? ` ${className}` : ''}`} role="alert">
      <WarningIcon />
      <div className={styles.body}>
        <div className={styles.message}>
          Google Calendar disconnected — events won&apos;t sync.
        </div>
        <div className={styles.action}>
          {isAdmin ? (
            <button
              type="button"
              className={styles.link}
              onClick={() => navigate('/setup/google')}
            >
              Reconnect →
            </button>
          ) : (
            <span>Ask your admin to reconnect.</span>
          )}
        </div>
      </div>
    </div>
  );
}
