/**
 * SetupGoogle — Wizard step 2: Google OAuth onboarding.
 *
 * Three UI states:
 *
 * 1. Initial — credentials not yet provided (or ?status=error after a failed
 *    OAuth flow). Shows the credentials form.
 *
 * 2. Connected — ?status=ok in the query string OR connected=true from the
 *    state endpoint. Shows the success CTA to continue to /setup/family.
 *
 * 3. Error — ?status=error query param. Same as Initial, plus an error banner
 *    above the credentials form so the user can retry.
 *
 * The OAuth callback redirects the browser to:
 *   /setup/google?status=ok     — on success
 *   /setup/google?status=error&detail=<msg> — on failure
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { DesktopShell } from '../components/DesktopShell';
import { HBtn } from '../components/HBtn';
import { Input } from '../components/Input';
import { WizardSteps } from '../components/WizardSteps';
import type { WizardStep } from '../components/WizardSteps';
import styles from './SetupGoogle.module.css';

// ---------------------------------------------------------------------------
// Wizard step configurations
// ---------------------------------------------------------------------------

const STEPS_INITIAL: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'done' },
  { key: 'google', label: 'Google', status: 'active' },
  { key: 'family', label: 'Family', status: 'upcoming' },
];

const STEPS_CONNECTED: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'done' },
  { key: 'google', label: 'Google', status: 'done' },
  { key: 'family', label: 'Family', status: 'active' },
];

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

interface OauthStateResponse {
  connected: boolean;
  calendars_mapped: boolean;
  refresh_token_present: boolean;
  scopes: string[] | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SetupGoogle() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const statusParam = searchParams.get('status');
  const detailParam = searchParams.get('detail');

  // Remote OAuth connection state — null while loading.
  const [oauthState, setOauthState] = useState<OauthStateResponse | null>(null);

  // Credentials form
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Derive the redirect URI from the current origin so it always matches.
  const redirectUri = `${window.location.origin}/api/google/oauth/callback`;

  // On mount: fetch the current OAuth state from the backend.
  useEffect(() => {
    let cancelled = false;

    async function fetchState() {
      try {
        const res = await fetch('/api/google/oauth/state', {
          credentials: 'include',
        });
        if (!cancelled && res.ok) {
          const data = (await res.json()) as OauthStateResponse;
          setOauthState(data);
        }
      } catch {
        // Non-fatal — UI degrades to the initial form state.
      }
    }

    void fetchState();
    return () => {
      cancelled = true;
    };
  }, []);

  // The connected state is true if:
  //   - the URL has ?status=ok (just returned from Google consent), OR
  //   - the backend reports connected=true.
  const isConnected = statusParam === 'ok' || oauthState?.connected === true;

  // Show the initial form if we're in error state or not yet connected.
  const isError = statusParam === 'error';

  // ---------------------------------------------------------------------------
  // Connected state
  // ---------------------------------------------------------------------------

  if (isConnected) {
    return (
      <DesktopShell width={1100} height={780}>
        <div className={styles.outer}>
          <div className={styles.inner}>
            <div className={styles.breadcrumbRow}>
              <WizardSteps steps={STEPS_CONNECTED} />
            </div>

            <div className={styles.stepLabel}>Step 2 of 3</div>
            <h1 className={styles.title}>
              Connected to <em>Google Calendar</em>
            </h1>
            <p className={styles.subtitle}>
              Hearth has permission to read and write your Google Calendar.
              Next, map each family member to their calendar.
            </p>

            <div className={styles.successCard}>
              <span className={styles.checkmark} aria-hidden="true">✓</span>
              <span className={styles.successText}>Connected to Google Calendar</span>
            </div>

            <div className={styles.actions}>
              <span className={styles.savedNote}>
                Tokens stored locally — only the admin can read these.
              </span>
              <HBtn
                kind="primary"
                size="lg"
                onClick={() => navigate('/setup/family')}
              >
                Continue to family setup
              </HBtn>
            </div>
          </div>
        </div>
      </DesktopShell>
    );
  }

  // ---------------------------------------------------------------------------
  // Initial / error state
  // ---------------------------------------------------------------------------

  async function handleContinue() {
    setError(null);

    if (!clientId.trim() || !clientSecret.trim()) {
      setError('Client ID and Client Secret are required');
      return;
    }

    setSubmitting(true);
    try {
      // 1. Persist credentials to settings.
      const credsRes = await fetch('/api/google/oauth/credentials', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
        }),
      });
      if (!credsRes.ok) {
        let detail = 'Failed to save credentials — please try again';
        try {
          const data = (await credsRes.json()) as { detail?: string };
          if (data.detail) detail = data.detail;
        } catch {
          // Ignore JSON parse error
        }
        setError(detail);
        return;
      }

      // 2. Generate the Google consent URL.
      const initRes = await fetch('/api/google/oauth/init', {
        method: 'POST',
        credentials: 'include',
      });
      if (!initRes.ok) {
        let detail = 'Failed to start OAuth flow — please try again';
        try {
          const data = (await initRes.json()) as { detail?: string };
          if (data.detail) detail = data.detail;
        } catch {
          // Ignore JSON parse error
        }
        setError(detail);
        return;
      }

      const initData = (await initRes.json()) as { authorization_url: string };

      // 3. Navigate the browser to Google consent. The callback will redirect
      //    back to /setup/google?status=ok|error.
      window.location.assign(initData.authorization_url);
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
          <div className={styles.breadcrumbRow}>
            <WizardSteps steps={STEPS_INITIAL} />
          </div>

          <div className={styles.stepLabel}>Step 2 of 3</div>
          <h1 className={styles.title}>
            Connect to <em>Google Calendar</em>
          </h1>
          <p className={styles.subtitle}>
            Hearth pushes confirmed events to one Google account. You will need
            OAuth credentials from Google Cloud — about 5 minutes if it is your
            first time.{' '}
            <a
              href="/docs/google-oauth-setup.md"
              className={styles.setupLink}
              target="_blank"
              rel="noreferrer"
            >
              Read the setup guide ↗
            </a>
          </p>

          {/* Error banner — shown when ?status=error or after a failed submission */}
          {(isError || error) && (
            <div className={styles.errorBanner} role="alert">
              {isError && detailParam
                ? detailParam
                : (error ?? 'An error occurred — please try again')}
            </div>
          )}

          <div className={styles.card}>
            <p className={styles.cardTitle}>Paste your OAuth credentials</p>
            <div className={styles.cardForm}>
              <Input
                label="Client ID"
                value={clientId}
                onChange={setClientId}
                mono
                placeholder="123456789012-abc…apps.googleusercontent.com"
              />
              <Input
                label="Client Secret"
                value={clientSecret}
                onChange={setClientSecret}
                mono
                placeholder="GOCSPX-…"
              />
              <p className={styles.redirectHint}>
                Authorized redirect URI:{' '}
                <span className={styles.redirectUri}>{redirectUri}</span>
              </p>
            </div>
          </div>

          <div className={styles.actions}>
            <span className={styles.savedNote}>
              Saved locally — only the admin can read these.
            </span>
            <HBtn onClick={() => navigate('/setup')}>Back</HBtn>
            <HBtn
              kind="primary"
              size="lg"
              disabled={submitting}
              onClick={() => void handleContinue()}
            >
              {submitting ? 'Redirecting…' : 'Continue with Google'}
            </HBtn>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}
