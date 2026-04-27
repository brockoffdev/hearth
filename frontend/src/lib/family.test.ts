import { describe, it, expect } from 'vitest';
import { HEARTH_FAMILY } from './family';

describe('HEARTH_FAMILY', () => {
  it('has exactly 5 members', () => {
    expect(HEARTH_FAMILY).toHaveLength(5);
  });

  it('each member has a valid 6-digit hex color', () => {
    for (const member of HEARTH_FAMILY) {
      expect(member.hex).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('has the exact IDs in order', () => {
    const ids = HEARTH_FAMILY.map((m) => m.id);
    expect(ids).toEqual(['bryant', 'danielle', 'isabella', 'eliana', 'family']);
  });

  it('every member has a unique hex', () => {
    const hexes = HEARTH_FAMILY.map((m) => m.hex.toLowerCase());
    expect(new Set(hexes).size).toBe(hexes.length);
  });

  it('every member has a unique id', () => {
    const ids = HEARTH_FAMILY.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
