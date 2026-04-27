import type React from 'react';
import { HearthMark } from './HearthMark';
import { cn } from '../lib/cn';
import styles from './HearthWordmark.module.css';

interface HearthWordmarkProps {
  size?: number;
  className?: string;
}

export function HearthWordmark({ size = 18, className }: HearthWordmarkProps) {
  const markSize = size + 4;

  return (
    <span
      className={cn(styles.wordmark, className)}
      style={{ '--wordmark-size': `${markSize}px` } as React.CSSProperties}
    >
      <HearthMark size={markSize} />
      <span className={styles.text}>hearth</span>
    </span>
  );
}
