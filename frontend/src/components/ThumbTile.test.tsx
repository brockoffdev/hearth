import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ThumbTile } from './ThumbTile';

describe('ThumbTile', () => {
  it('renders a container element', () => {
    const { container } = render(<ThumbTile />);
    const tile = container.firstElementChild;
    expect(tile).not.toBeNull();
  });

  it('defaults to 56px size', () => {
    const { container } = render(<ThumbTile />);
    const tile = container.firstElementChild as HTMLElement;
    expect(tile.style.width).toBe('56px');
    expect(tile.style.height).toBe('56px');
  });

  it('respects size prop', () => {
    const { container } = render(<ThumbTile size={80} />);
    const tile = container.firstElementChild as HTMLElement;
    expect(tile.style.width).toBe('80px');
    expect(tile.style.height).toBe('80px');
  });

  it('renders children', () => {
    render(<ThumbTile>📷</ThumbTile>);
    expect(screen.getByText('📷')).not.toBeNull();
  });

  it('renders accent dot when accent prop is set', () => {
    const { container } = render(<ThumbTile accent="var(--accent)" />);
    const dot = container.querySelector('[data-testid="thumb-accent"]');
    expect(dot).not.toBeNull();
  });

  it('does not render accent dot when accent is not set', () => {
    const { container } = render(<ThumbTile />);
    const dot = container.querySelector('[data-testid="thumb-accent"]');
    expect(dot).toBeNull();
  });

  it('renders badge when provided', () => {
    render(<ThumbTile badge={<span data-testid="badge">1</span>} />);
    expect(screen.getByTestId('badge')).not.toBeNull();
  });

  it('does not render badge when not provided', () => {
    const { container } = render(<ThumbTile />);
    const badge = container.querySelector('[data-testid="thumb-badge"]');
    expect(badge).toBeNull();
  });

  it('forwards className', () => {
    const { container } = render(<ThumbTile className="my-thumb" />);
    const tile = container.firstElementChild;
    expect(tile?.classList.contains('my-thumb')).toBe(true);
  });
});
