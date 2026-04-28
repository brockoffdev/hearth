import { describe, it, expect } from 'vitest';
import { formatRelativeTime } from './relativeTime';

function isoAt(offsetMs: number, from: Date = new Date('2026-04-27T12:00:00Z')): string {
  return new Date(from.getTime() + offsetMs).toISOString();
}

const NOW = new Date('2026-04-27T12:00:00Z');

describe('formatRelativeTime', () => {
  it('returns "Just now" for exactly now', () => {
    expect(formatRelativeTime(NOW.toISOString(), NOW)).toBe('Just now');
  });

  it('returns "Just now" for 30 seconds ago', () => {
    const ts = isoAt(-30_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('Just now');
  });

  it('returns "Just now" for 59 seconds ago', () => {
    const ts = isoAt(-59_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('Just now');
  });

  it('returns "1 minute ago" for exactly 1 minute ago', () => {
    const ts = isoAt(-60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('1 minute ago');
  });

  it('returns "5 minutes ago" for 5 minutes ago', () => {
    const ts = isoAt(-5 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('5 minutes ago');
  });

  it('returns "59 minutes ago" for 59 minutes ago', () => {
    const ts = isoAt(-59 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('59 minutes ago');
  });

  it('returns "1 hour ago" for exactly 1 hour ago', () => {
    const ts = isoAt(-60 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('1 hour ago');
  });

  it('returns "3 hours ago" for 3 hours ago', () => {
    const ts = isoAt(-3 * 60 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('3 hours ago');
  });

  it('returns "23 hours ago" for 23 hours ago', () => {
    const ts = isoAt(-23 * 60 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('23 hours ago');
  });

  it('returns "Yesterday" for exactly 24 hours ago', () => {
    const ts = isoAt(-24 * 60 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('Yesterday');
  });

  it('returns "Yesterday" for 47 hours ago', () => {
    const ts = isoAt(-47 * 60 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('Yesterday');
  });

  it('returns a formatted date for older timestamps', () => {
    // 3 days ago from Apr 27 = Apr 24
    const ts = isoAt(-3 * 24 * 60 * 60_000, NOW);
    const result = formatRelativeTime(ts, NOW);
    expect(result).toMatch(/apr/i);
  });

  it('returns "Just now" defensively for future timestamps', () => {
    const ts = isoAt(5 * 60_000, NOW);
    expect(formatRelativeTime(ts, NOW)).toBe('Just now');
  });

  it('handles singular "1 minute ago" correctly (not "1 minutes ago")', () => {
    const ts = isoAt(-90_000, NOW); // 1.5 min → 1 minute
    expect(formatRelativeTime(ts, NOW)).toBe('1 minute ago');
  });

  it('handles singular "1 hour ago" correctly (not "1 hours ago")', () => {
    const ts = isoAt(-90 * 60_000, NOW); // 1.5 hours → 1 hour
    expect(formatRelativeTime(ts, NOW)).toBe('1 hour ago');
  });
});
