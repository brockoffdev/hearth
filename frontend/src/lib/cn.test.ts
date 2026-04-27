import { describe, it, expect } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
  it('joins two class names with a space', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('drops falsy values (false, undefined, null)', () => {
    expect(cn('a', false, undefined, null, 'c')).toBe('a c');
  });

  it('returns empty string when called with no arguments', () => {
    expect(cn()).toBe('');
  });
});
