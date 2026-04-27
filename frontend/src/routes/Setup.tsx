import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { WizardSteps } from '../components/WizardSteps';
import type { WizardStep } from '../components/WizardSteps';
import { Input } from '../components/Input';
import { HBtn } from '../components/HBtn';
import { DesktopShell } from '../components/DesktopShell';
import styles from './Setup.module.css';

// Wizard step 1 — Account / password change.
// Step 1's breadcrumb is always: Account=active, Google=upcoming, Family=upcoming.
const WIZARD_STEPS: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'active' },
  { key: 'google',  label: 'Google',  status: 'upcoming' },
  { key: 'family',  label: 'Family',  status: 'upcoming' },
];

export function Setup() {
  const auth = useAuth();
  const navigate = useNavigate();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Render authenticated state only — WizardGate / RequireAuth handle the rest.
  // If the flag is already cleared (user manually navigated here), show "all done".
  if (auth.state.status === 'authenticated' && !auth.state.user.must_change_password) {
    return (
      <div className={styles.allDone}>
        <p className={styles.allDoneText}>All done — you are already past this step.</p>
        <HBtn kind="primary" onClick={() => navigate('/')}>
          Go to home
        </HBtn>
      </div>
    );
  }

  // While loading or anonymous (shouldn't normally reach here behind RequireAuth + WizardGate)
  if (auth.state.status !== 'authenticated') {
    return null;
  }

  const { username } = auth.state.user;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (res.ok) {
        // Refresh auth state so WizardGate picks up the cleared flag.
        await auth.refresh();
        navigate('/setup/google');
        return;
      }

      // Server-side error — show the detail message inline.
      let detail = 'An error occurred — please try again';
      try {
        const data = (await res.json()) as { detail?: string };
        if (data.detail) detail = data.detail;
      } catch {
        // Ignore JSON parse error
      }
      setError(detail);
    } catch {
      setError('Network error — please try again');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DesktopShell width={1100} height={780}>
      <div className={styles.outer}>
        <div className={styles.inner}>
          {/* Wizard breadcrumb row */}
          <div className={styles.breadcrumbRow}>
            <WizardSteps steps={WIZARD_STEPS} />
          </div>

          <div className={styles.stepLabel}>Step 1 of 3</div>
          <h1 className={styles.title}>Set your password</h1>
          <p className={styles.subtitle}>
            Choose a strong password for your admin account. You will use this to log in.
          </p>

          <div className={styles.card}>
            <form onSubmit={handleSubmit} className={styles.form} noValidate>
              <Input
                label="Username"
                value={username}
                onChange={() => {}}
                disabled
                autoComplete="username"
              />
              <Input
                label="Current password"
                value={currentPassword}
                onChange={setCurrentPassword}
                type="password"
                placeholder="Current password"
                autoComplete="current-password"
                required
              />
              <Input
                label="New password"
                value={newPassword}
                onChange={setNewPassword}
                type="password"
                placeholder="New password"
                autoComplete="new-password"
                required
                error={
                  error === 'Password must be at least 8 characters' ? error : null
                }
              />
              <p className={styles.hint}>At least 8 characters</p>
              <Input
                label="Confirm new password"
                value={confirmPassword}
                onChange={setConfirmPassword}
                type="password"
                placeholder="Confirm new password"
                autoComplete="new-password"
                required
                error={error === 'Passwords do not match' ? error : null}
              />

              {/* Server-side or other errors */}
              {error &&
                error !== 'Passwords do not match' &&
                error !== 'Password must be at least 8 characters' && (
                  <p className={styles.formError} role="alert">
                    {error}
                  </p>
                )}

              <div className={styles.actions}>
                <HBtn
                  kind="primary"
                  size="lg"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? 'Saving…' : 'Save and continue'}
                </HBtn>
              </div>
            </form>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}
