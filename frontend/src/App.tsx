import { Routes, Route } from 'react-router-dom';
import { Index } from './routes/Index';
import { DesignSmoke } from './routes/DesignSmoke';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/_design" element={<DesignSmoke />} />
      <Route path="*" element={<Index />} />
    </Routes>
  );
}
