/**
 * ConfidenceBadge — renders a percentage + status pill.
 *
 * Component renders the % regardless of status. Consumers (e.g. the review queue)
 * decide whether to render this component for auto items at all.
 * Per design README: "Confidence is a gate, not a label. Don't show % on
 * auto-published items." — that gating is enforced at the consumer level, not here.
 */
import { cn } from '../lib/cn';
import styles from './ConfidenceBadge.module.css';

type BadgeStatus = 'auto' | 'review' | 'skipped';

interface ConfidenceBadgeProps {
  value: number;
  status: BadgeStatus;
  className?: string;
}

const STATUS_GLYPH: Record<BadgeStatus, string> = {
  auto: '✓',
  review: '!',
  skipped: '–',
};

const STATUS_CLASS: Record<BadgeStatus, string> = {
  auto: styles['status-auto']!,
  review: styles['status-review']!,
  skipped: styles['status-skipped']!,
};

export function ConfidenceBadge({ value, status, className }: ConfidenceBadgeProps) {
  const pct = Math.round(value * 100);

  return (
    <span
      className={cn(styles.badge, STATUS_CLASS[status], className)}
      data-status={status}
    >
      <span className={styles.glyph} aria-hidden="true">{STATUS_GLYPH[status]}</span>
      <span className={styles.value}>{pct}%</span>
    </span>
  );
}
