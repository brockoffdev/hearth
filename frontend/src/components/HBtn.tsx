import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '../lib/cn';
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

const KIND_CLASS: Record<HBtnKind, string> = {
  primary: styles['kind-primary']!,
  ghost:   styles['kind-ghost']!,
  default: styles['kind-default']!,
  danger:  styles['kind-danger']!,
};

const SIZE_CLASS: Record<HBtnSize, string> = {
  sm: styles['size-sm']!,
  md: styles['size-md']!,
  lg: styles['size-lg']!,
};

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
        KIND_CLASS[kind],
        SIZE_CLASS[size],
        disabled && styles.disabled,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
