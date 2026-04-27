import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WizardSteps } from './WizardSteps';
import type { WizardStep } from './WizardSteps';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const STEPS_STEP1: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'active' },
  { key: 'google',  label: 'Google',  status: 'upcoming' },
  { key: 'family',  label: 'Family',  status: 'upcoming' },
];

const STEPS_STEP2: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'done' },
  { key: 'google',  label: 'Google',  status: 'active' },
  { key: 'family',  label: 'Family',  status: 'upcoming' },
];

const STEPS_ALL_DONE: readonly WizardStep[] = [
  { key: 'account', label: 'Account', status: 'done' },
  { key: 'google',  label: 'Google',  status: 'done' },
  { key: 'family',  label: 'Family',  status: 'done' },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WizardSteps', () => {
  it('renders all 3 step labels', () => {
    render(<WizardSteps steps={STEPS_STEP1} />);
    expect(screen.getByText('Account')).not.toBeNull();
    expect(screen.getByText('Google')).not.toBeNull();
    expect(screen.getByText('Family')).not.toBeNull();
  });

  it('active step has data-status="active"', () => {
    render(<WizardSteps steps={STEPS_STEP1} />);
    // The "Account" step wrapper should have data-status=active
    const activeSteps = document.querySelectorAll('[data-status="active"]');
    expect(activeSteps.length).toBeGreaterThan(0);
  });

  it('done step renders ✓ instead of the step number', () => {
    render(<WizardSteps steps={STEPS_STEP2} />);
    // Account is done — should show checkmark
    expect(screen.getByText('✓')).not.toBeNull();
    // The number 1 should NOT appear for account step
    // (but 2 appears for active Google, 3 for upcoming Family)
    const badges = document.querySelectorAll('[data-status="done"] [data-testid="step-badge"]');
    expect(badges.length).toBe(1);
    expect(badges[0]!.textContent).toBe('✓');
  });

  it('upcoming step has data-status="upcoming"', () => {
    render(<WizardSteps steps={STEPS_STEP1} />);
    const upcomingSteps = document.querySelectorAll('[data-status="upcoming"]');
    // Google and Family are upcoming
    expect(upcomingSteps.length).toBe(2);
  });

  it('passes through className to root element', () => {
    const { container } = render(
      <WizardSteps steps={STEPS_STEP1} className="extra-class" />,
    );
    expect(container.firstElementChild!.className).toContain('extra-class');
  });

  it('numbering is always position-based: Account=1, Google=2, Family=3', () => {
    // All upcoming — badges should show 1, 2, 3
    const allUpcoming: readonly WizardStep[] = [
      { key: 'account', label: 'Account', status: 'upcoming' },
      { key: 'google',  label: 'Google',  status: 'upcoming' },
      { key: 'family',  label: 'Family',  status: 'upcoming' },
    ];
    render(<WizardSteps steps={allUpcoming} />);
    const badges = document.querySelectorAll('[data-testid="step-badge"]');
    expect(badges[0]!.textContent).toBe('1');
    expect(badges[1]!.textContent).toBe('2');
    expect(badges[2]!.textContent).toBe('3');
  });

  it('all-done: all three steps have data-status="done"', () => {
    render(<WizardSteps steps={STEPS_ALL_DONE} />);
    const doneSteps = document.querySelectorAll('[data-status="done"]');
    expect(doneSteps.length).toBe(3);
  });

  it('connecting lines exist between steps (2 lines for 3 steps)', () => {
    render(<WizardSteps steps={STEPS_STEP1} />);
    const connectors = document.querySelectorAll('[data-testid="step-connector"]');
    expect(connectors.length).toBe(2);
  });
});
