import { MobileTabBar } from '../components/MobileTabBar';
import styles from './Placeholder.module.css';

export function ReviewPlaceholder(): JSX.Element {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <h1 className={styles.title}>Review</h1>
        <p className={styles.subtitle}>Coming in Phase 6.</p>
      </main>
      <MobileTabBar active="review" />
    </div>
  );
}
