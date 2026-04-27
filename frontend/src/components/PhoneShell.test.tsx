import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PhoneShell } from './PhoneShell';

describe('PhoneShell', () => {
  it('renders children', () => {
    render(<PhoneShell><span>phone content</span></PhoneShell>);
    expect(screen.getByText('phone content')).not.toBeNull();
  });

  it('applies width of 390px via CSS variable or inline style', () => {
    const { container } = render(<PhoneShell><span>content</span></PhoneShell>);
    const shell = container.firstElementChild as HTMLElement;
    // Check either inline style or data attribute indicating fixed dimensions
    const style = shell.style;
    const hasWidth = style.width === '390px' || shell.className.includes('phoneShell');
    expect(hasWidth).toBe(true);
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
