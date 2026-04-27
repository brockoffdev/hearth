import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { HearthWordmark } from './HearthWordmark';

describe('HearthWordmark', () => {
  it('renders the text "hearth"', () => {
    render(<HearthWordmark />);
    expect(screen.getByText('hearth')).not.toBeNull();
  });

  it('contains a HearthMark svg', () => {
    const { container } = render(<HearthWordmark />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('uses default size of 18', () => {
    const { container } = render(<HearthWordmark />);
    // HearthMark size = size + 4 = 22
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('22');
  });

  it('respects size prop — HearthMark gets size+4', () => {
    const { container } = render(<HearthWordmark size={28} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('32');
  });

  it('forwards className to wrapper', () => {
    const { container } = render(<HearthWordmark className="test-class" />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.classList.contains('test-class')).toBe(true);
  });
});
