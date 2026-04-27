import { Routes, Route } from 'react-router-dom';
import { Index } from './routes/Index';
import { DesignSmoke } from './routes/DesignSmoke';
import { Login } from './routes/Login';
import { RequireAuth } from './auth/RequireAuth';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/_design" element={<DesignSmoke />} />
      <Route path="/" element={<RequireAuth><Index /></RequireAuth>} />
      <Route path="*" element={<RequireAuth><Index /></RequireAuth>} />
    </Routes>
  );
}
