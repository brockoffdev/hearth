import type { ReactNode, CSSProperties } from 'react';
import { cn } from '../lib/cn';
import styles from './ThumbTile.module.css';

interface ThumbTileProps {
  size?: number;
  accent?: string;
  badge?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function ThumbTile({
  size = 56,
  accent,
  badge,
  children,
  className,
}: ThumbTileProps) {
  const tileStyle: CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
  };

  return (
    <div className={cn(styles.tile, className)} style={tileStyle}>
      {accent && (
        <span
          className={styles.accent}
          data-testid="thumb-accent"
          style={{ background: accent }}
        />
      )}
      {badge && (
        <span className={styles.badge}>
          {badge}
        </span>
      )}
      {children}
    </div>
  );
}
