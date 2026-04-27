import { HearthMark } from './HearthMark';
import styles from './HearthWordmark.module.css';

interface HearthWordmarkProps {
  size?: number;
  className?: string;
}

export function HearthWordmark({ size = 18, className }: HearthWordmarkProps) {
  const markSize = size + 4;

  return (
    <span
      className={[styles.wordmark, className].filter(Boolean).join(' ')}
      style={{ fontSize: `${markSize}px` }}
    >
      <HearthMark size={markSize} />
      <span className={styles.text}>hearth</span>
    </span>
  );
}
