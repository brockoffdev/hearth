/**
 * AuthProvider — owns the current-user state for the app.
 *
 * On mount, calls GET /api/auth/me once to hydrate state.
 * React StrictMode double-fires effects in dev; the second call sees the same
 * cookie and is a benign no-op. A ref guard is used to prevent double-firing
 * in the common case.
 */

import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  username: string;
  role: 'admin' | 'user';
  must_change_password: boolean;
  must_complete_google_setup: boolean;
  created_at: string; // ISO string from the API
}

export type AuthState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'authenticated'; user: User };

export interface AuthContextValue {
  state: AuthState;
  login: (
    username: string,
    password: string,
  ) => Promise<{ ok: true } | { ok: false; error: string }>;
  logout: () => Promise<void>;
  /** Re-fetch /api/auth/me; useful after change-password. */
  refresh: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function fetchMe(): Promise<User | null> {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (res.status === 401) return null;
    if (!res.ok) {
      console.error('[AuthProvider] /api/auth/me returned', res.status);
      return null;
    }
    return (await res.json()) as User;
  } catch (err) {
    console.error('[AuthProvider] network error on /api/auth/me', err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [state, setState] = useState<AuthState>({ status: 'loading' });
  // Guard against double-fire in StrictMode / React 18 concurrent mode.
  const bootstrapped = useRef(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    fetchMe().then((user) => {
      if (user) {
        setState({ status: 'authenticated', user });
      } else {
        setState({ status: 'anonymous' });
      }
    });
  }, []);

  async function login(
    username: string,
    password: string,
  ): Promise<{ ok: true } | { ok: false; error: string }> {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (res.ok) {
        const user = (await res.json()) as User;
        setState({ status: 'authenticated', user });
        return { ok: true };
      }

      if (res.status === 401) {
        return { ok: false, error: 'Invalid credentials' };
      }

      return { ok: false, error: 'Login failed — try again' };
    } catch {
      return { ok: false, error: 'Login failed — try again' };
    }
  }

  async function logout(): Promise<void> {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Idempotent — always treat as success.
    }
    setState({ status: 'anonymous' });
  }

  async function refresh(): Promise<void> {
    const user = await fetchMe();
    if (user) {
      setState({ status: 'authenticated', user });
    } else {
      setState({ status: 'anonymous' });
    }
  }

  return (
    <AuthContext.Provider value={{ state, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
