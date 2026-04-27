import { useId } from 'react';
import { cn } from '../lib/cn';
import styles from './Input.module.css';

interface InputProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  type?: 'text' | 'password' | 'email';
  mono?: boolean;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
  disabled?: boolean;
  error?: string | null;
  /** Explicit id; defaults to a useId()-generated one. */
  id?: string;
  className?: string;
}

export function Input({
  label,
  value,
  onChange,
  type = 'text',
  mono = false,
  placeholder,
  required,
  autoComplete,
  disabled,
  error,
  id: idProp,
  className,
}: InputProps) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const hasError = Boolean(error);

  return (
    <div className={cn(styles.wrapper, className)}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
        disabled={disabled}
        className={cn(
          styles.input,
          mono && styles.mono,
          hasError && styles.hasError,
        )}
      />
      {hasError && (
        <span className={styles.errorText} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
