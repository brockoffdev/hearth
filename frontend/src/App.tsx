import { Outlet, Routes, Route } from 'react-router-dom';
import { Index } from './routes/Index';
import { DesignSmoke } from './routes/DesignSmoke';
import { Login } from './routes/Login';
import { Setup } from './routes/Setup';
import { SetupGoogle } from './routes/SetupGoogle';
import { SetupFamily } from './routes/SetupFamily';
import { Upload } from './routes/Upload';
import { UploadDetail } from './routes/UploadDetail';
import { Status } from './routes/Status';
import { Review } from './routes/Review';
import { ReviewItem } from './routes/ReviewItem';
import { Calendar } from './routes/Calendar';
import { AdminUsers } from './routes/AdminUsers';
import { AdminSettings } from './routes/AdminSettings';
import { RequireAuth } from './auth/RequireAuth';
import { WizardGate } from './auth/WizardGate';
// TODO: Phase 8 Task C — add desktop sidebar with Admin sub-nav links

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
        <Route path="/uploads" element={<Status />} />
        <Route path="/uploads/:id" element={<UploadDetail />} />
        <Route path="/review" element={<Review />} />
        <Route path="/review/:id" element={<ReviewItem />} />
        <Route path="/calendar" element={<Calendar />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/settings" element={<AdminSettings />} />
        <Route path="/" element={<Index />} />
        <Route path="*" element={<Index />} />
      </Route>
    </Routes>
  );
}
