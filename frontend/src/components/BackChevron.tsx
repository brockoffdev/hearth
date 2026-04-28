import type { CSSProperties } from 'react';
import { cn } from '../lib/cn';
import styles from './BackChevron.module.css';

interface BackChevronProps {
  size?: number;
  color?: string;
  className?: string;
  onClick?: () => void;
}

export function BackChevron({
  size = 32,
  color = 'var(--ink)',
  className,
  onClick,
}: BackChevronProps) {
  const wrapperStyle: CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
  };

  if (onClick) {
    return (
      <button
        type="button"
        className={cn(styles.wrapper, styles.clickable, className)}
        style={wrapperStyle}
        onClick={onClick}
        aria-label="Go back"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M15 6l-6 6 6 6"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>
    );
  }

  return (
    <div className={cn(styles.wrapper, className)} style={wrapperStyle}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M15 6l-6 6 6 6"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
