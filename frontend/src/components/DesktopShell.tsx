import type React from 'react';
import type { ReactNode } from 'react';
import styles from './DesktopShell.module.css';

interface DesktopShellProps {
  width?: number;
  height?: number;
  children: ReactNode;
  className?: string;
}

export function DesktopShell({
  width = 1280,
  height = 800,
  children,
  className,
}: DesktopShellProps) {
  return (
    <div
      className={[styles.desktopShell, className].filter(Boolean).join(' ')}
      style={{
        '--desktop-width': `${width}px`,
        '--desktop-height': `${height}px`,
      } as React.CSSProperties}
    >
      {children}
    </div>
  );
}
