import type { ReactNode } from 'react';
import styles from './PhoneShell.module.css';

interface PhoneShellProps {
  children: ReactNode;
  className?: string;
}

const PHONE_WIDTH = 390;
const PHONE_HEIGHT = 844;

export function PhoneShell({ children, className }: PhoneShellProps) {
  return (
    <div
      className={[styles.phoneShell, className].filter(Boolean).join(' ')}
      style={{ width: `${PHONE_WIDTH}px`, height: `${PHONE_HEIGHT}px` }}
    >
      {children}
    </div>
  );
}
