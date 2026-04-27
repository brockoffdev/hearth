import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DesktopShell } from './DesktopShell';

describe('DesktopShell', () => {
  it('renders children', () => {
    render(<DesktopShell><span>desktop content</span></DesktopShell>);
    expect(screen.getByText('desktop content')).not.toBeNull();
  });

  it('applies default --desktop-width of 1280px', () => {
    const { container } = render(<DesktopShell><span>content</span></DesktopShell>);
    const shell = container.firstElementChild as HTMLElement;
    expect(shell.style.getPropertyValue('--desktop-width')).toBe('1280px');
  });

  it('applies default --desktop-height of 800px', () => {
    const { container } = render(<DesktopShell><span>content</span></DesktopShell>);
    const shell = container.firstElementChild as HTMLElement;
    expect(shell.style.getPropertyValue('--desktop-height')).toBe('800px');
  });

  it('respects custom width prop', () => {
    const { container } = render(<DesktopShell width={1440}><span>content</span></DesktopShell>);
    const shell = container.firstElementChild as HTMLElement;
    expect(shell.style.getPropertyValue('--desktop-width')).toBe('1440px');
  });

  it('respects custom height prop', () => {
    const { container } = render(<DesktopShell height={900}><span>content</span></DesktopShell>);
    const shell = container.firstElementChild as HTMLElement;
    expect(shell.style.getPropertyValue('--desktop-height')).toBe('900px');
  });

  it('forwards className', () => {
    const { container } = render(<DesktopShell className="extra"><span>x</span></DesktopShell>);
    const shell = container.firstElementChild;
    expect(shell?.classList.contains('extra')).toBe(true);
  });
});
