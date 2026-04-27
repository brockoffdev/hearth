/**
 * WizardGate — second gating layer, on top of RequireAuth.
 *
 * Checks wizard-completion flags on the current user and redirects to the
 * appropriate wizard step if any are pending.
 *
 * Gate logic (in priority order):
 *   1. Not authenticated → no-op (RequireAuth above us handles this).
 *   2. must_change_password=true AND not on /setup → redirect to /setup.
 *   3. must_complete_google_setup=true AND not on a /setup/* sub-path → redirect to /setup/google.
 *      NOTE: bare "/setup" is wizard step 1; it does NOT satisfy step 2's path check.
 *            The startsWith('/setup/') check (with trailing slash) is intentional.
 *   4. Otherwise → render children.
 *
 * TODO Task E: /setup/google route will be implemented in Phase 2 Task E.
 *              Until then, the redirect lands on the placeholder route.
 * TODO Task F: /setup/family route will be implemented in Phase 2 Task F.
 */

import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';

interface WizardGateProps {
  children: ReactNode;
}

export function WizardGate({ children }: WizardGateProps) {
  const { state } = useAuth();
  const location = useLocation();

  // Not yet authenticated — RequireAuth at a higher layer handles this case.
  // WizardGate is intentionally a no-op here.
  if (state.status !== 'authenticated') {
    return <>{children}</>;
  }

  const { must_change_password, must_complete_google_setup } = state.user;
  const path = location.pathname;

  // Step 1: password change required.
  if (must_change_password) {
    if (path !== '/setup') {
      return <Navigate to="/setup" replace />;
    }
    return <>{children}</>;
  }

  // Step 2: Google OAuth setup required.
  // Note: bare "/setup" is step 1's path — it does NOT count as a valid step-2+ location.
  // Only "/setup/google", "/setup/family", etc. (paths starting with "/setup/") are valid here.
  if (must_complete_google_setup) {
    if (!path.startsWith('/setup/')) {
      return <Navigate to="/setup/google" replace />;
    }
    return <>{children}</>;
  }

  // All wizard steps complete — render normally.
  return <>{children}</>;
}
