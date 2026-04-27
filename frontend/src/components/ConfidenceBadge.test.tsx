import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ConfidenceBadge } from './ConfidenceBadge';

describe('ConfidenceBadge', () => {
  it('rounds value to nearest percent', () => {
    render(<ConfidenceBadge value={0.847} status="auto" />);
    expect(screen.getByText(/85%/)).not.toBeNull();
  });

  it('renders 100% for value=1.0', () => {
    render(<ConfidenceBadge value={1.0} status="auto" />);
    expect(screen.getByText(/100%/)).not.toBeNull();
  });

  it('renders 0% for value=0', () => {
    render(<ConfidenceBadge value={0} status="review" />);
    expect(screen.getByText(/0%/)).not.toBeNull();
  });

  it('renders ✓ glyph for status="auto"', () => {
    render(<ConfidenceBadge value={0.95} status="auto" />);
    expect(screen.getByText(/✓/)).not.toBeNull();
  });

  it('glyph span has aria-hidden="true" so screen readers skip it', () => {
    render(<ConfidenceBadge value={0.95} status="auto" />);
    const glyph = screen.getByText('✓').closest('span');
    expect(glyph?.getAttribute('aria-hidden')).toBe('true');
  });

  it('renders ! glyph for status="review"', () => {
    render(<ConfidenceBadge value={0.61} status="review" />);
    expect(screen.getByText(/!/)).not.toBeNull();
  });

  it('renders – glyph for status="skipped"', () => {
    render(<ConfidenceBadge value={0.5} status="skipped" />);
    expect(screen.getByText(/–/)).not.toBeNull();
  });

  it('sets data-status="auto" attribute', () => {
    const { container } = render(<ConfidenceBadge value={0.9} status="auto" />);
    const badge = container.firstElementChild;
    expect(badge?.getAttribute('data-status')).toBe('auto');
  });

  it('sets data-status="review" attribute', () => {
    const { container } = render(<ConfidenceBadge value={0.6} status="review" />);
    const badge = container.firstElementChild;
    expect(badge?.getAttribute('data-status')).toBe('review');
  });

  it('sets data-status="skipped" attribute', () => {
    const { container } = render(<ConfidenceBadge value={0.4} status="skipped" />);
    const badge = container.firstElementChild;
    expect(badge?.getAttribute('data-status')).toBe('skipped');
  });
});
