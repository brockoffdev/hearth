import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { HearthMark } from './HearthMark';

describe('HearthMark', () => {
  it('renders an svg element', () => {
    const { container } = render(<HearthMark />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('has the expected viewBox', () => {
    const { container } = render(<HearthMark />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
  });

  it('uses default size of 22', () => {
    const { container } = render(<HearthMark />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('22');
    expect(svg?.getAttribute('height')).toBe('22');
  });

  it('respects size prop', () => {
    const { container } = render(<HearthMark size={48} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('48');
    expect(svg?.getAttribute('height')).toBe('48');
  });

  it('is aria-hidden when no ariaLabel provided', () => {
    const { container } = render(<HearthMark />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
  });

  it('uses ariaLabel when provided', () => {
    render(<HearthMark ariaLabel="Hearth logo" />);
    const svg = screen.getByLabelText('Hearth logo');
    expect(svg).not.toBeNull();
  });

  it('does not set aria-hidden when ariaLabel is provided', () => {
    const { container } = render(<HearthMark ariaLabel="Hearth" />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBeNull();
  });

  it('forwards className', () => {
    const { container } = render(<HearthMark className="custom" />);
    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('custom')).toBe(true);
  });
});
