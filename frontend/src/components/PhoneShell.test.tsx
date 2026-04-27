import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PhoneShell } from './PhoneShell';

describe('PhoneShell', () => {
  it('renders children', () => {
    render(<PhoneShell><span>phone content</span></PhoneShell>);
    expect(screen.getByText('phone content')).not.toBeNull();
  });

  it('has the phoneShell CSS class (which applies 390x844 dimensions)', () => {
    const { container } = render(<PhoneShell><span>content</span></PhoneShell>);
    const shell = container.firstElementChild as HTMLElement;
    // Width/height are set in CSS (phoneShell class) — not inline style
    expect(shell.className).toMatch(/phoneShell/);
  });

  it('applies shell class', () => {
    const { container } = render(<PhoneShell><span>content</span></PhoneShell>);
    const shell = container.firstElementChild;
    // should have some class from module css
    expect(shell?.className).toBeTruthy();
  });

  it('forwards className', () => {
    const { container } = render(<PhoneShell className="extra"><span>x</span></PhoneShell>);
    const shell = container.firstElementChild;
    expect(shell?.classList.contains('extra')).toBe(true);
  });
});
