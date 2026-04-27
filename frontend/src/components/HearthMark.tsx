import styles from './HearthMark.module.css';

interface HearthMarkProps {
  size?: number;
  className?: string;
  ariaLabel?: string;
}

export function HearthMark({ size = 22, className, ariaLabel }: HearthMarkProps) {
  const accessibilityProps = ariaLabel
    ? { 'aria-label': ariaLabel, role: 'img' as const }
    : { 'aria-hidden': 'true' as const };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={[styles.mark, className].filter(Boolean).join(' ')}
      {...accessibilityProps}
    >
      {/* Hearth arch */}
      <path
        d="M3 21V11a9 9 0 0 1 18 0v10"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M3 21h18"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      {/* Flame inside */}
      <path
        d="M12 18c2.2 0 4-1.7 4-3.8 0-1.6-1-2.4-1.8-3.4-.7-.9-.7-2-.7-2.8 0 0-1 .6-1.6 1.7-.6 1-.4 2-.4 2-1.2-.5-1.5-1.7-1.5-1.7s-2 1.6-2 4.1c0 2.1 1.8 3.9 4 3.9z"
        fill="currentColor"
      />
    </svg>
  );
}
