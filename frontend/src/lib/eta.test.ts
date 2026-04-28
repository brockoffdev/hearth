import { describe, it, expect } from 'vitest';
import { formatETA, formatDuration } from './eta';

describe('formatETA', () => {
  it('returns — for null', () => {
    expect(formatETA(null)).toBe('—');
  });

  it('returns — for undefined', () => {
    expect(formatETA(undefined)).toBe('—');
  });

  it('returns ~0 sec for 0', () => {
    expect(formatETA(0)).toBe('~0 sec');
  });

  it('returns ~45 sec for 45', () => {
    expect(formatETA(45)).toBe('~45 sec');
  });

  it('returns ~1 min for 60', () => {
    expect(formatETA(60)).toBe('~1 min');
  });

  it('returns ~2 min 5 sec for 125', () => {
    expect(formatETA(125)).toBe('~2 min 5 sec');
  });

  it('returns ~3 min 4 sec for 184', () => {
    expect(formatETA(184)).toBe('~3 min 4 sec');
  });

  it('returns ~60 min for 3600', () => {
    expect(formatETA(3600)).toBe('~60 min');
  });

  it('does not show zero seconds in minute form', () => {
    expect(formatETA(120)).toBe('~2 min');
  });
});

describe('formatDuration', () => {
  it('returns 45s for 45', () => {
    expect(formatDuration(45)).toBe('45s');
  });

  it('returns 1m 4s for 64', () => {
    expect(formatDuration(64)).toBe('1m 4s');
  });

  it('returns 2m for 120', () => {
    expect(formatDuration(120)).toBe('2m');
  });

  it('returns 61m 1s for 3661', () => {
    expect(formatDuration(3661)).toBe('61m 1s');
  });

  it('returns 0s for 0', () => {
    expect(formatDuration(0)).toBe('0s');
  });
});
