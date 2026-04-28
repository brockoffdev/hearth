import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BackChevron } from './BackChevron';

describe('BackChevron', () => {
  it('renders a container with an svg inside', () => {
    const { container } = render(<BackChevron />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('renders an arrow-left path', () => {
    const { container } = render(<BackChevron />);
    const path = container.querySelector('path');
    // Arrow-left: "M15 6l-6 6 6 6"
    expect(path?.getAttribute('d')).toContain('M15 6');
  });

  it('defaults to 32x32 container', () => {
    const { container } = render(<BackChevron />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.style.width).toBe('32px');
    expect(wrapper.style.height).toBe('32px');
  });

  it('respects size prop', () => {
    const { container } = render(<BackChevron size={40} />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.style.width).toBe('40px');
    expect(wrapper.style.height).toBe('40px');
  });

  it('forwards className to wrapper', () => {
    const { container } = render(<BackChevron className="my-back" />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.classList.contains('my-back')).toBe(true);
  });
});
