import type { JSX } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { MobileTabBar } from '../components/MobileTabBar';
import styles from './AdminIndex.module.css';

// ---------------------------------------------------------------------------
// 403 view (mirrors AdminUsers.tsx pattern)
// ---------------------------------------------------------------------------

function ForbiddenView(): JSX.Element {
  return (
    <div className={styles.forbidden}>
      <div className={styles.forbiddenCard}>
        <h1 className={styles.forbiddenTitle}>403</h1>
        <p className={styles.forbiddenText}>Admin access required.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin nav card
// ---------------------------------------------------------------------------

interface AdminCardProps {
  to: string;
  title: string;
  description: string;
}

function AdminCard({ to, title, description }: AdminCardProps): JSX.Element {
  return (
    <Link to={to} className={styles.card}>
      <span className={styles.cardTitle}>{title}</span>
      <span className={styles.cardDesc}>{description}</span>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// AdminIndex
// ---------------------------------------------------------------------------

export function AdminIndex(): JSX.Element {
  const { state } = useAuth();

  if (state.status === 'loading') {
    return <div className={styles.page} />;
  }

  if (state.status !== 'authenticated' || state.user.role !== 'admin') {
    return <ForbiddenView />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={styles.content}>
          <div className={styles.heading}>
            <div className={styles.adminLabel}>Admin</div>
            <h1 className={styles.title}>
              <span className={styles.titleAccent}>Admin</span>
            </h1>
          </div>

          <div className={styles.cards}>
            <AdminCard
              to="/admin/users"
              title="Users"
              description="Add and remove people who can use Hearth."
            />
            <AdminCard
              to="/admin/settings"
              title="Settings"
              description="Confidence threshold, vision provider."
            />
          </div>
        </div>
      </div>

      <MobileTabBar active="home" />
    </div>
  );
}
