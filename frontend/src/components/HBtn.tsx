import type { ButtonHTMLAttributes, ReactNode } from 'react';
import styles from './HBtn.module.css';

type HBtnKind = 'primary' | 'ghost' | 'default' | 'danger';
type HBtnSize = 'sm' | 'md' | 'lg';

interface HBtnProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type'> {
  kind?: HBtnKind;
  size?: HBtnSize;
  type?: 'button' | 'submit' | 'reset';
  children: ReactNode;
  className?: string;
}

function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function HBtn({
  kind = 'default',
  size = 'md',
  type = 'button',
  children,
  className,
  disabled,
  ...rest
}: HBtnProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        styles.btn,
        styles[`kind-${kind}`],
        styles[`size-${size}`],
        disabled && styles.disabled,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
