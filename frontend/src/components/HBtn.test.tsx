import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { HBtn } from './HBtn';

describe('HBtn', () => {
  it('renders children', () => {
    render(<HBtn>Click me</HBtn>);
    expect(screen.getByText('Click me')).not.toBeNull();
  });

  it('renders as a button element', () => {
    render(<HBtn>Button</HBtn>);
    expect(screen.getByRole('button')).not.toBeNull();
  });

  it('defaults to type="button"', () => {
    render(<HBtn>Submit</HBtn>);
    expect(screen.getByRole('button').getAttribute('type')).toBe('button');
  });

  it('accepts type="submit"', () => {
    render(<HBtn type="submit">Submit</HBtn>);
    expect(screen.getByRole('button').getAttribute('type')).toBe('submit');
  });

  it('renders each kind variant', () => {
    const { rerender } = render(<HBtn kind="primary">Primary</HBtn>);
    let btn = screen.getByRole('button');
    expect(btn.className).toMatch(/kind-primary/);

    rerender(<HBtn kind="ghost">Ghost</HBtn>);
    btn = screen.getByRole('button');
    expect(btn.className).toMatch(/kind-ghost/);

    rerender(<HBtn kind="default">Default</HBtn>);
    btn = screen.getByRole('button');
    expect(btn.className).toMatch(/kind-default/);

    rerender(<HBtn kind="danger">Danger</HBtn>);
    btn = screen.getByRole('button');
    expect(btn.className).toMatch(/kind-danger/);
  });

  it('renders each size variant', () => {
    const { rerender } = render(<HBtn size="sm">Small</HBtn>);
    let btn = screen.getByRole('button');
    expect(btn.className).toMatch(/size-sm/);

    rerender(<HBtn size="md">Medium</HBtn>);
    btn = screen.getByRole('button');
    expect(btn.className).toMatch(/size-md/);

    rerender(<HBtn size="lg">Large</HBtn>);
    btn = screen.getByRole('button');
    expect(btn.className).toMatch(/size-lg/);
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<HBtn onClick={onClick}>Click</HBtn>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled when disabled prop is true', () => {
    render(<HBtn disabled>Disabled</HBtn>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('passes through native attrs like aria-label', () => {
    render(<HBtn aria-label="action">Go</HBtn>);
    expect(screen.getByLabelText('action')).not.toBeNull();
  });

  it('forwards className', () => {
    render(<HBtn className="extra">Button</HBtn>);
    expect(screen.getByRole('button').classList.contains('extra')).toBe(true);
  });
});
