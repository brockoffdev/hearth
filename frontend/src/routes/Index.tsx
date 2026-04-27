import { useTheme } from '../design/ThemeProvider';
import { THEME_LABELS } from '../design/themeLabels';
import { useAuth } from '../auth/AuthProvider';
import { HearthWordmark } from '../components/HearthWordmark';
import { HBtn } from '../components/HBtn';
import styles from './Index.module.css';

export function Index() {
  const { theme, cycleTheme } = useTheme();
  const { state, logout } = useAuth();
  const username =
    state.status === 'authenticated' ? state.user.username : null;

  return (
    <main className={styles.page}>
      <div className={styles.topBar}>
        {username && (
          <span className={styles.signedIn}>Signed in as {username}</span>
        )}
        <HBtn kind="ghost" size="sm" onClick={() => void logout()}>
          Log out
        </HBtn>
      </div>

      <HearthWordmark size={28} />

      <p className={styles.status}>Phase 2 onboarding ✓</p>

      <button className={styles.themeToggle} onClick={cycleTheme}>
        {THEME_LABELS[theme]} — click to cycle
      </button>
    </main>
  );
}
