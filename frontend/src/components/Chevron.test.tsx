import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Chevron } from './Chevron';

describe('Chevron', () => {
  it('renders an svg element', () => {
    const { container } = render(<Chevron />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('defaults to 14x14', () => {
    const { container } = render(<Chevron />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('14');
    expect(svg?.getAttribute('height')).toBe('14');
  });

  it('respects size prop', () => {
    const { container } = render(<Chevron size={20} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('20');
    expect(svg?.getAttribute('height')).toBe('20');
  });

  it('forwards className', () => {
    const { container } = render(<Chevron className="my-chevron" />);
    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('my-chevron')).toBe(true);
  });
});
