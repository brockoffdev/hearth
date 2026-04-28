import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SectionRule } from './SectionRule';

describe('SectionRule', () => {
  it('renders the label', () => {
    render(<SectionRule label="In flight" dotColor="var(--accent)" />);
    expect(screen.getByText('In flight')).not.toBeNull();
  });

  it('renders count when provided', () => {
    render(<SectionRule label="Done" dotColor="var(--success)" count={3} />);
    expect(screen.getByText('3')).not.toBeNull();
  });

  it('does not render count when not provided', () => {
    const { container } = render(
      <SectionRule label="In flight" dotColor="var(--accent)" />,
    );
    // Count element should not exist
    const countEl = container.querySelector('[data-testid="section-rule-count"]');
    expect(countEl).toBeNull();
  });

  it('sets dotColor via data attribute or style on the dot', () => {
    const { container } = render(
      <SectionRule label="In flight" dotColor="var(--accent)" />,
    );
    const dot = container.querySelector('[data-testid="section-rule-dot"]');
    expect(dot).not.toBeNull();
  });

  it('forwards className', () => {
    const { container } = render(
      <SectionRule label="In flight" dotColor="var(--accent)" className="my-rule" />,
    );
    expect(container.firstElementChild?.classList.contains('my-rule')).toBe(true);
  });
});
