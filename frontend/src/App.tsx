import { Outlet, Routes, Route } from 'react-router-dom';
import { Index } from './routes/Index';
import { DesignSmoke } from './routes/DesignSmoke';
import { Login } from './routes/Login';
import { Setup } from './routes/Setup';
import { SetupGoogle } from './routes/SetupGoogle';
import { SetupFamily } from './routes/SetupFamily';
import { Upload } from './routes/Upload';
import { RequireAuth } from './auth/RequireAuth';
import { WizardGate } from './auth/WizardGate';

/**
 * Route structure:
 *   /login       — always accessible (anonymous)
 *   /_design     — always accessible (design smoke test)
 *   all others   — RequireAuth (must be logged in) → WizardGate (must complete wizard)
 *
 * WizardGate redirects:
 *   must_change_password=true      → /setup
 *   must_complete_google_setup=true → /setup/google
 */
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/_design" element={<DesignSmoke />} />
      <Route
        element={
          <RequireAuth>
            <WizardGate>
              <Outlet />
            </WizardGate>
          </RequireAuth>
        }
      >
        <Route path="/setup" element={<Setup />} />
        <Route path="/setup/google" element={<SetupGoogle />} />
        <Route path="/setup/family" element={<SetupFamily />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/" element={<Index />} />
        <Route path="*" element={<Index />} />
      </Route>
    </Routes>
  );
}
