import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FamilyChip } from './FamilyChip';

describe('FamilyChip', () => {
  it('renders Bryant\'s name for who="bryant"', () => {
    render(<FamilyChip who="bryant" />);
    expect(screen.getByText('Bryant')).not.toBeNull();
  });

  it('renders all family member names', () => {
    const { rerender } = render(<FamilyChip who="danielle" />);
    expect(screen.getByText('Danielle')).not.toBeNull();

    rerender(<FamilyChip who="isabella" />);
    expect(screen.getByText('Izzy')).not.toBeNull();

    rerender(<FamilyChip who="eliana" />);
    expect(screen.getByText('Ellie')).not.toBeNull();

    rerender(<FamilyChip who="family" />);
    expect(screen.getByText('Family')).not.toBeNull();
  });

  it('does not render text when showLabel={false}', () => {
    render(<FamilyChip who="bryant" showLabel={false} />);
    expect(screen.queryByText('Bryant')).toBeNull();
  });

  it('renders a dot element', () => {
    const { container } = render(<FamilyChip who="bryant" />);
    const dot = container.querySelector('[class*="dot"]');
    expect(dot).not.toBeNull();
  });

  it('applies size-sm class for sm size', () => {
    const { container } = render(<FamilyChip who="bryant" size="sm" />);
    const chip = container.firstElementChild;
    expect(chip?.className).toMatch(/size-sm/);
  });

  it('applies size-lg class for lg size', () => {
    const { container } = render(<FamilyChip who="bryant" size="lg" />);
    const chip = container.firstElementChild;
    expect(chip?.className).toMatch(/size-lg/);
  });

  it('does not crash on unknown id and logs warn', () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    // @ts-expect-error intentionally passing invalid id for test
    expect(() => render(<FamilyChip who="unknown-person" />)).not.toThrow();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
