import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthProvider';

interface RequireAuthProps {
  children: ReactNode;
}

/**
 * Guards routes that require authentication.
 *
 * - loading  → render nothing (avoids flash of wrong content)
 * - anonymous → redirect to /login
 * - authenticated → render children
 *
 * Note: wizard gating (must_change_password → /setup) is Task D's job.
 */
export function RequireAuth({ children }: RequireAuthProps) {
  const { state } = useAuth();

  if (state.status === 'loading') {
    return null;
  }

  if (state.status === 'anonymous') {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
