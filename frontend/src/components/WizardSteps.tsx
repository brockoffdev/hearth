import { Fragment } from 'react';
import { cn } from '../lib/cn';
import styles from './WizardSteps.module.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StepKey = 'account' | 'google' | 'family';

export interface WizardStep {
  key: StepKey;
  label: string;
  status: 'done' | 'active' | 'upcoming';
}

export interface WizardStepsProps {
  steps: readonly WizardStep[];
  className?: string;
}

// Step order is always fixed; positions come from this mapping.
const STEP_NUMBERS: Record<StepKey, number> = {
  account: 1,
  google: 2,
  family: 3,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WizardSteps({ steps, className }: WizardStepsProps) {
  return (
    <div className={cn(styles.root, className)}>
      {steps.map((step, i) => (
        <Fragment key={step.key}>
          {i > 0 && (
            <span
              className={styles.connector}
              data-testid="step-connector"
            />
          )}
          <div
            className={styles.step}
            data-status={step.status}
          >
            <span
              className={styles.badge}
              data-testid="step-badge"
            >
              {step.status === 'done' ? '✓' : STEP_NUMBERS[step.key]}
            </span>
            <span className={styles.label}>{step.label}</span>
          </div>
        </Fragment>
      ))}
    </div>
  );
}
