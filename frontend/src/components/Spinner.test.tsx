import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Spinner } from './Spinner';

describe('Spinner', () => {
  it('renders an svg element', () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('has viewBox="0 0 24 24"', () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
  });

  it('defaults to size 14', () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('14');
    expect(svg?.getAttribute('height')).toBe('14');
  });

  it('respects size prop', () => {
    const { container } = render(<Spinner size={24} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('24');
    expect(svg?.getAttribute('height')).toBe('24');
  });

  it('has default aria-label "Loading"', () => {
    render(<Spinner />);
    expect(screen.getByRole('img', { name: 'Loading' })).not.toBeNull();
  });

  it('uses custom ariaLabel when provided', () => {
    render(<Spinner ariaLabel="Processing upload" />);
    expect(screen.getByRole('img', { name: 'Processing upload' })).not.toBeNull();
  });

  it('forwards className', () => {
    const { container } = render(<Spinner className="my-spinner" />);
    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('my-spinner')).toBe(true);
  });
});
