import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode, JSX } from 'react';
import { NewCaptureSheet } from './NewCaptureSheet';

// ---------------------------------------------------------------------------
// Context + types
// ---------------------------------------------------------------------------

export interface NewCaptureSheetController {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

const NewCaptureSheetContext = createContext<NewCaptureSheetController | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function NewCaptureSheetProvider({ children }: { children: ReactNode }): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  // Body scroll-lock while open
  useEffect(() => {
    if (!isOpen) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = original;
    };
  }, [isOpen]);

  // Escape to close
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  return (
    <NewCaptureSheetContext.Provider value={{ isOpen, open, close }}>
      {children}
      {isOpen && createPortal(<NewCaptureSheet onClose={close} />, document.body)}
    </NewCaptureSheetContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNewCaptureSheet(): NewCaptureSheetController {
  const ctx = useContext(NewCaptureSheetContext);
  if (ctx === null) {
    throw new Error('useNewCaptureSheet must be used within a NewCaptureSheetProvider');
  }
  return ctx;
}
