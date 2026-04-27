/**
 * ConfidenceBadge — renders a percentage + status pill.
 *
 * Component renders the % regardless of status. Consumers (e.g. the review queue)
 * decide whether to render this component for auto items at all.
 * Per design README: "Confidence is a gate, not a label. Don't show % on
 * auto-published items." — that gating is enforced at the consumer level, not here.
 */
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

export function ConfidenceBadge({ value, status, className }: ConfidenceBadgeProps) {
  const pct = Math.round(value * 100);

  return (
    <span
      className={[styles.badge, styles[`status-${status}`], className].filter(Boolean).join(' ')}
      data-status={status}
    >
      <span className={styles.glyph}>{STATUS_GLYPH[status]}</span>
      <span className={styles.value}>{pct}%</span>
    </span>
  );
}
