import type { Event } from '../lib/events';
import { cellCropUrl } from '../lib/events';
import { FamilyChip } from './FamilyChip';
import { familyIdByHex } from '../lib/family';
import { ConfidenceBadge } from './ConfidenceBadge';
import { cn } from '../lib/cn';
import styles from './EventCard.module.css';

interface EventCardProps {
  event: Event;
  showCellCrop?: boolean;
  onClick?: () => void;
  className?: string;
}

function formatEventDate(event: Event): string {
  const date = new Date(event.start_dt);

  const datePart = new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(date);

  if (event.all_day) {
    return `${datePart} · all day`;
  }

  const timePart = new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);

  return `${datePart} · ${timePart}`;
}

/** Map event status to the badge status expected by ConfidenceBadge. */
function badgeStatus(status: Event['status']): 'auto' | 'review' | 'skipped' {
  if (status === 'auto_published' || status === 'published') return 'auto';
  if (status === 'pending_review') return 'review';
  return 'skipped';
}

export function EventCard({ event, showCellCrop = false, onClick, className }: EventCardProps) {
  const chipWho = familyIdByHex(event.family_member_color_hex);

  return (
    <div
      className={cn(styles.card, onClick && styles.clickable, className)}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {showCellCrop && (
        event.has_cell_crop
          ? (
            <img
              src={cellCropUrl(event.id)}
              alt={`Cell crop for ${event.title}`}
              className={styles.cropThumb}
            />
          )
          : <div className={styles.cropPlaceholder} aria-hidden="true" />
      )}

      <div className={styles.content}>
        <div className={styles.topRow}>
          {chipWho && (
            <FamilyChip who={chipWho} size="sm" showLabel={false} />
          )}
          {event.family_member_name && (
            <span className={styles.memberName}>{event.family_member_name}</span>
          )}
          <span className={styles.spacer} />
          <ConfidenceBadge value={event.confidence} status={badgeStatus(event.status)} />
        </div>

        <p className={styles.title}>{event.title}</p>
        <p className={styles.dateSubtitle}>{formatEventDate(event)}</p>
      </div>
    </div>
  );
}
