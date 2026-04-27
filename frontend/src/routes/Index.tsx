import { useTheme } from '../design/ThemeProvider';
import type { Theme } from '../design/ThemeProvider';
import styles from './Index.module.css';

const THEME_LABELS: Record<Theme, string> = {
  light: 'Light',
  dark: 'Dark',
  sepia: 'Sepia',
};

export function Index() {
  const { theme, cycleTheme } = useTheme();

  return (
    <main className={styles.page}>
      {/* Placeholder wordmark — Task C will replace with <HearthWordmark /> primitive */}
      <svg
        className={styles.wordmark}
        viewBox="0 0 200 48"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Hearth"
        role="img"
      >
        <text
          x="0"
          y="40"
          fontFamily="var(--fontDisplay)"
          fontSize="40"
          fontWeight="600"
          fill="var(--fg)"
        >
          Hearth
        </text>
      </svg>

      <p className={styles.status}>Phase 1 scaffold ✓</p>

      <button className={styles.themeToggle} onClick={cycleTheme}>
        {THEME_LABELS[theme]} — click to cycle
      </button>
    </main>
  );
}
