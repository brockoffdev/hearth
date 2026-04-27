import type { ReactNode } from 'react';
import { cn } from '../lib/cn';
import styles from './PhoneShell.module.css';

interface PhoneShellProps {
  children: ReactNode;
  className?: string;
}

export function PhoneShell({ children, className }: PhoneShellProps) {
  return (
    <div className={cn(styles.phoneShell, className)}>
      {children}
    </div>
  );
}
