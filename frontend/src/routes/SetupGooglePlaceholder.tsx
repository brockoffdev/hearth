/**
 * SetupGooglePlaceholder — temporary route for /setup/google.
 *
 * TODO Phase 2 Task E: Replace this entire file with the real Google OAuth
 * onboarding step (SetupGoogle). This placeholder exists only to avoid
 * an infinite-redirect loop after wizard step 1 completes — WizardGate
 * would redirect to /setup/google, but without a route it would bounce.
 *
 * Inline styles are intentional here: this component is throwaway scaffolding
 * and CSS modules would be misleading overhead.
 */
export function SetupGooglePlaceholder() {
  return (
    // eslint-disable-next-line react/forbid-dom-props
    <div style={{ padding: 40 }}>
      <h1>Wizard Step 2 — Coming in Phase 2 Task E</h1>
      <p>Google OAuth onboarding will live here.</p>
    </div>
  );
}
