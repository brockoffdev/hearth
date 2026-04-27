import type { ReactNode } from 'react';
import styles from './PhoneShell.module.css';

interface PhoneShellProps {
  children: ReactNode;
  className?: string;
}

export function PhoneShell({ children, className }: PhoneShellProps) {
  return (
    <div className={[styles.phoneShell, className].filter(Boolean).join(' ')}>
      {children}
    </div>
  );
}
