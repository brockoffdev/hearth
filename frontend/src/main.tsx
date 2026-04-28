import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './design/ThemeProvider';
import { AuthProvider } from './auth/AuthProvider';
import { NewCaptureSheetProvider } from './components/NewCaptureSheet';
import { App } from './App';
import './design/reset.css';
import './design/tokens.css';
import './design/globals.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <NewCaptureSheetProvider>
            <App />
          </NewCaptureSheetProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
);
