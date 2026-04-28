import { cn } from '../lib/cn';
import styles from './Spinner.module.css';

interface SpinnerProps {
  size?: number;
  className?: string;
  ariaLabel?: string;
}

export function Spinner({ size = 14, className, ariaLabel = 'Loading' }: SpinnerProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label={ariaLabel}
      className={cn(styles.spinner, className)}
    >
      <circle cx="12" cy="12" r="9" stroke="var(--rule)" strokeWidth="2.5" />
      <path
        d="M12 3a9 9 0 0 1 9 9"
        stroke="var(--accent)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
