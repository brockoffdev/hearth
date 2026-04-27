import { describe, it, expect } from 'vitest';
import { HEARTH_STAGES } from './stages';

describe('HEARTH_STAGES', () => {
  it('has exactly 10 stages', () => {
    expect(HEARTH_STAGES).toHaveLength(10);
  });

  it('has the exact keys in order', () => {
    const keys = HEARTH_STAGES.map((s) => s.key);
    expect(keys).toEqual([
      'received',
      'preprocessing',
      'grid_detected',
      'model_loading',
      'cell_progress',
      'color_matching',
      'date_normalization',
      'confidence_gating',
      'publishing',
      'done',
    ]);
  });

  it('the last stage key is done', () => {
    const last = HEARTH_STAGES[HEARTH_STAGES.length - 1];
    expect(last?.key).toBe('done');
  });

  it('every key is unique', () => {
    const keys = HEARTH_STAGES.map((s) => s.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
