import type { CSSProperties } from 'react';
import { cn } from '../lib/cn';
import styles from './SectionRule.module.css';

interface SectionRuleProps {
  label: string;
  dotColor: string;
  count?: number;
  marginTop?: number;
  className?: string;
}

export function SectionRule({
  label,
  dotColor,
  count,
  marginTop,
  className,
}: SectionRuleProps) {
  const ruleStyle: CSSProperties = marginTop !== undefined
    ? { paddingTop: `${marginTop}px` }
    : {};

  return (
    <div className={cn(styles.rule, className)} style={ruleStyle}>
      <span
        className={styles.dot}
        data-testid="section-rule-dot"
        style={{ background: dotColor }}
      />
      <span className={styles.label}>{label}</span>
      {count !== undefined && (
        <span className={styles.count} data-testid="section-rule-count">
          {count}
        </span>
      )}
      <span className={styles.line} />
    </div>
  );
}
