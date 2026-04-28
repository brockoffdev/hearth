import { Link } from 'react-router-dom';
import { cn } from '../lib/cn';
import styles from './MobileTabBar.module.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TabId = 'home' | 'uploads' | 'review' | 'calendar';

export interface Tab {
  id: TabId;
  label: string;
  icon: string;  // SVG path d= attribute
  href: string;  // route to navigate to
}

export interface MobileTabBarProps {
  active: TabId;
  className?: string;
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

export const TABS: readonly Tab[] = [
  { id: 'home',     label: 'Home',     href: '/',         icon: 'M3 12l9-9 9 9v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z' },
  { id: 'uploads',  label: 'Uploads',  href: '/uploads',  icon: 'M5 7h14M5 12h14M5 17h14' },
  { id: 'review',   label: 'Review',   href: '/review',   icon: 'M4 6h12M4 12h16M4 18h10' },
  { id: 'calendar', label: 'Calendar', href: '/calendar', icon: 'M3 8h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 2v4m8-4v4' },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MobileTabBar({ active, className }: MobileTabBarProps): JSX.Element {
  return (
    <nav className={cn(styles.bar, className)} aria-label="Primary">
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <Link
            key={tab.id}
            to={tab.href}
            className={styles.tab}
            data-active={isActive}
            aria-current={isActive ? 'page' : undefined}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d={tab.icon}
                stroke="currentColor"
                strokeWidth={isActive ? 2 : 1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span className={styles.label}>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
