export type StageKey =
  | 'received'
  | 'preprocessing'
  | 'grid_detected'
  | 'model_loading'
  | 'cell_progress'
  | 'color_matching'
  | 'date_normalization'
  | 'confidence_gating'
  | 'publishing'
  | 'done';

export interface Stage {
  key: StageKey;
  label: string;
  hint: string;
}

export const HEARTH_STAGES: readonly Stage[] = [
  { key: 'received',           label: 'Photo received',                   hint: 'Saved to local storage' },
  { key: 'preprocessing',      label: 'Preparing image',                  hint: 'Rotating, deskewing, perspective fix' },
  { key: 'grid_detected',      label: 'Reading the calendar grid',        hint: 'Found 5 weeks × 7 days' },
  { key: 'model_loading',      label: 'Loading vision model',             hint: 'First time can take 15–25 sec' },
  { key: 'cell_progress',      label: 'Reading cells',                    hint: 'Qwen2.5-VL 7B, ~8 sec / cell' },
  { key: 'color_matching',     label: 'Identifying writers by ink color', hint: 'HSV histogram → family member' },
  { key: 'date_normalization', label: 'Resolving dates',                  hint: 'Cell coords → ISO date' },
  { key: 'confidence_gating',  label: 'Reviewing confidence',             hint: 'Threshold = 85%' },
  { key: 'publishing',         label: 'Saving to Google Calendar',        hint: 'Auto-published events only' },
  { key: 'done',               label: 'Done',                             hint: '' },
] as const;
