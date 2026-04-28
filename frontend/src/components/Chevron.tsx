import { cn } from '../lib/cn';
import styles from './Chevron.module.css';

interface ChevronProps {
  size?: number;
  color?: string;
  className?: string;
}

export function Chevron({
  size = 14,
  color = 'var(--fgSoft)',
  className,
}: ChevronProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn(styles.chevron, className)}
    >
      <path
        d="M9 6l6 6-6 6"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
