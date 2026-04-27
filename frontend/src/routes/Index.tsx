import { useTheme } from '../design/ThemeProvider';
import { THEME_LABELS } from '../design/themeLabels';
import { HearthWordmark } from '../components/HearthWordmark';
import styles from './Index.module.css';

export function Index() {
  const { theme, cycleTheme } = useTheme();

  return (
    <main className={styles.page}>
      <HearthWordmark size={28} />

      <p className={styles.status}>Phase 1 scaffold ✓</p>

      <button className={styles.themeToggle} onClick={cycleTheme}>
        {THEME_LABELS[theme]} — click to cycle
      </button>
    </main>
  );
}
