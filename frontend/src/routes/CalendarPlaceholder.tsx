import { MobileTabBar } from '../components/MobileTabBar';
import styles from './Placeholder.module.css';

export function CalendarPlaceholder(): JSX.Element {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <h1 className={styles.title}>Calendar</h1>
        <p className={styles.subtitle}>Coming in Phase 8.</p>
      </main>
      <MobileTabBar active="calendar" />
    </div>
  );
}
