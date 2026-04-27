import type { FamilyMemberId } from '../lib/family';
import { HEARTH_FAMILY } from '../lib/family';
import { cn } from '../lib/cn';
import styles from './FamilyChip.module.css';

type ChipSize = 'sm' | 'md' | 'lg';

interface FamilyChipProps {
  who: FamilyMemberId;
  size?: ChipSize;
  showLabel?: boolean;
  className?: string;
}

const SIZE_CLASS: Record<ChipSize, string> = {
  sm: styles['size-sm']!,
  md: styles['size-md']!,
  lg: styles['size-lg']!,
};

export function FamilyChip({
  who,
  size = 'md',
  showLabel = true,
  className,
}: FamilyChipProps) {
  const member = HEARTH_FAMILY.find((m) => m.id === who);

  if (!member) {
    console.warn(`FamilyChip: unknown family member id "${who}"`);
    // Render a neutral fallback chip
    return (
      <span className={cn(styles.chip, SIZE_CLASS[size], className)}>
        <span className={styles.dot} />
        {showLabel && <span className={styles.label}>Unknown</span>}
      </span>
    );
  }

  return (
    <span className={cn(styles.chip, SIZE_CLASS[size], className)}>
      <span
        className={styles.dot}
        data-who={member.id}
      />
      {showLabel && <span className={styles.label}>{member.name}</span>}
    </span>
  );
}
