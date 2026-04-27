import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { HearthWordmark } from '../components/HearthWordmark';
import { Input } from '../components/Input';
import { HBtn } from '../components/HBtn';
import styles from './Login.module.css';

export function Login() {
  const { state, login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // If already authenticated, redirect immediately
  useEffect(() => {
    if (state.status === 'authenticated') {
      navigate('/', { replace: true });
    }
  }, [state.status, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Client-side validation
    let hasError = false;
    if (!username.trim()) {
      setUsernameError('Username is required');
      hasError = true;
    } else {
      setUsernameError(null);
    }
    if (!password) {
      setPasswordError('Password is required');
      hasError = true;
    } else {
      setPasswordError(null);
    }
    if (hasError) return;

    setFormError(null);
    setLoading(true);

    const result = await login(username.trim(), password);

    setLoading(false);

    if (result.ok) {
      navigate('/', { replace: true });
    } else {
      setFormError(result.error);
    }
  }

  // Don't render the form while checking auth or after redirect
  if (state.status === 'loading' || state.status === 'authenticated') {
    return null;
  }

  return (
    <div className={styles.page}>
      {/* Left pane */}
      <div className={styles.left}>
        <HearthWordmark size={20} />
        <div>
          <h1 className={styles.headline}>
            The wall
            <br />
            <span className={styles.headlineAccent}>calendar,</span>
            <br />
            everywhere.
          </h1>
          <p className={styles.tagline}>
            Snap a photo of your family's whiteboard. Hearth reads the
            handwriting, sorts events by who wrote them, and pushes everything
            to Google Calendar.
          </p>
        </div>
        <p className={styles.footer}>v0.1.0 · self-hosted · LAN-only by default</p>
      </div>

      {/* Right pane */}
      <div className={styles.right}>
        <p className={styles.eyebrow}>Sign in</p>
        <h2 className={styles.welcomeHeading}>Welcome back</h2>
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <Input
            label="Username"
            value={username}
            onChange={setUsername}
            type="text"
            autoComplete="username"
            error={usernameError}
            required
          />
          <Input
            label="Password"
            value={password}
            onChange={setPassword}
            type="password"
            autoComplete="current-password"
            error={passwordError}
            required
          />
          {formError && (
            <p role="alert" aria-live="assertive" style={{ color: 'var(--danger)', fontSize: 13, margin: 0 }}>
              {formError}
            </p>
          )}
          <HBtn
            kind="primary"
            size="lg"
            type="submit"
            disabled={loading}
            className={styles.submitBtn}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </HBtn>
          <p className={styles.forgotLine}>Forgot? Ask your admin to reset.</p>
        </form>
      </div>
    </div>
  );
}
