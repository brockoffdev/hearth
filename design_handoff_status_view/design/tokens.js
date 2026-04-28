// Hearth design tokens — three aesthetics, three themes, family colors

// Family member palette (ink-color attributions)
window.HEARTH_FAMILY_DEFAULT = [
  { id: 'bryant',    name: 'Bryant',    role: 'Dad',     hex: '#2E5BA8', label: 'Blue'   },
  { id: 'danielle',  name: 'Danielle',  role: 'Mom',     hex: '#C0392B', label: 'Red'    },
  { id: 'isabella',  name: 'Izzy',      role: 'Age 3',   hex: '#7B4FB8', label: 'Purple' },
  { id: 'eliana',    name: 'Ellie',     role: 'Age 0',   hex: '#E17AA1', label: 'Pink'   },
  { id: 'family',    name: 'Family',    role: 'Everyone',hex: '#D97A2C', label: 'Orange' },
];

// Three aesthetic directions — picked to feel "home-y", living-room, not enterprise.
window.HEARTH_AESTHETICS = {
  ember: {
    name: 'Ember',
    blurb: 'Warm editorial — cream paper, deep ink, terracotta accent',
    fontDisplay: '"Fraunces", "Source Serif Pro", Georgia, serif',
    fontBody: '"Inter", -apple-system, system-ui, sans-serif',
    fontMono: '"JetBrains Mono", "SF Mono", ui-monospace, monospace',
    radius: 14,
    radiusLg: 22,
    paper: '#F7F1E8',
    paperDeep: '#EFE6D6',
    ink: '#1F1B16',
    inkSoft: '#5C5246',
    rule: '#E2D6BF',
    accent: '#B0431F',     // terracotta
    accentSoft: '#E8D2C4',
    success: '#3F7A4A',
    warn: '#C97A1B',
    danger: '#A6342B',
  },
  hearthstone: {
    name: 'Hearthstone',
    blurb: 'Cozy modern — warm stone, soft sage, friendly geometry',
    fontDisplay: '"DM Serif Display", Georgia, serif',
    fontBody: '"DM Sans", -apple-system, system-ui, sans-serif',
    fontMono: '"DM Mono", "SF Mono", ui-monospace, monospace',
    radius: 18,
    radiusLg: 26,
    paper: '#F4EFE8',
    paperDeep: '#E8E0D2',
    ink: '#2A2722',
    inkSoft: '#6B635A',
    rule: '#D9CFBE',
    accent: '#6F8E5E',     // sage
    accentSoft: '#D6E0CB',
    success: '#5C8059',
    warn: '#C58A2E',
    danger: '#B14A3D',
  },
  whiteboard: {
    name: 'Whiteboard',
    blurb: 'Hand-drawn — paper grain, marker accents, calendar motif',
    fontDisplay: '"Caveat", "Patrick Hand", cursive',
    fontBody: '"Nunito", -apple-system, system-ui, sans-serif',
    fontMono: '"JetBrains Mono", "SF Mono", ui-monospace, monospace',
    radius: 12,
    radiusLg: 20,
    paper: '#FBF8F1',
    paperDeep: '#F2EAD8',
    ink: '#26221C',
    inkSoft: '#5E5447',
    rule: '#D9CFBC',
    accent: '#D97A2C',     // marker orange
    accentSoft: '#F3DAB8',
    success: '#467A52',
    warn: '#D08A1C',
    danger: '#B14228',
  },
};

window.HEARTH_THEMES = {
  light: {
    bg: 'var(--paper)',
    bgDeep: 'var(--paperDeep)',
    fg: 'var(--ink)',
    fgSoft: 'var(--inkSoft)',
    surface: '#FFFFFF',
    surfaceMuted: 'var(--paperDeep)',
    rule: 'var(--rule)',
  },
  dark: {
    bg: '#181513',
    bgDeep: '#0F0D0B',
    fg: '#F4EEE3',
    fgSoft: '#A89E8E',
    surface: '#22201D',
    surfaceMuted: '#15130F',
    rule: '#2C2925',
  },
  sepia: {
    bg: '#E9DBC2',
    bgDeep: '#D8C8AB',
    fg: '#3A2E1F',
    fgSoft: '#705A3F',
    surface: '#F1E5CF',
    surfaceMuted: '#DCCEB4',
    rule: '#C4B190',
  },
};

// Mock event data — a believable week for the Brock family
window.HEARTH_MOCK_EVENTS = [
  { id: 'e1',  title: 'Izzy preschool drop-off',  who: 'isabella',  date: '2026-04-27', time: '8:30',  conf: 0.93, status: 'auto' },
  { id: 'e2',  title: 'Pediatrician — Ellie',     who: 'eliana',    date: '2026-04-27', time: '10:15', conf: 0.88, status: 'auto' },
  { id: 'e3',  title: 'Bryant — dentist',         who: 'bryant',    date: '2026-04-28', time: '14:00', conf: 0.91, status: 'auto' },
  { id: 'e4',  title: 'Danielle book club',       who: 'danielle',  date: '2026-04-28', time: '19:00', conf: 0.82, status: 'review' },
  { id: 'e5',  title: 'Family dinner — Nana',     who: 'family',    date: '2026-04-29', time: '17:30', conf: 0.96, status: 'auto' },
  { id: 'e6',  title: 'Pikuapk Place?',           who: 'isabella',  date: '2026-04-30', time: '15:00', conf: 0.61, status: 'review', note: 'Read as "Pikuapk" — likely "Pineapple"?' },
  { id: 'e7',  title: 'Bryant 1:1',               who: 'bryant',    date: '2026-04-30', time: '11:00', conf: 0.89, status: 'auto' },
  { id: 'e8',  title: 'Swim class',               who: 'isabella',  date: '2026-05-01', time: '9:00',  conf: 0.95, status: 'auto' },
  { id: 'e9',  title: 'Date night',               who: 'family',    date: '2026-05-01', time: '19:30', conf: 0.78, status: 'review' },
  { id: 'e10', title: 'Park w/ Lila',             who: 'isabella',  date: '2026-05-02', time: '10:00', conf: 0.84, status: 'review' },
  { id: 'e11', title: 'Grocery run',              who: 'family',    date: '2026-05-02', time: '14:00', conf: 0.72, status: 'review' },
  { id: 'e12', title: 'Ellie 6-mo checkup',       who: 'eliana',    date: '2026-05-03', time: '11:00', conf: 0.97, status: 'auto' },
  { id: 'e13', title: 'Mother\u2019s Day brunch', who: 'family',    date: '2026-05-10', time: '11:00', conf: 0.94, status: 'auto' },
  { id: 'e14', title: 'Izzy birthday party',      who: 'isabella',  date: '2026-07-15', time: '14:00', conf: 0.99, status: 'auto' },
];

// SSE pipeline stages (from spec §6.5)
window.HEARTH_STAGES = [
  { key: 'received',          label: 'Photo received',                        hint: 'Saved to local storage' },
  { key: 'preprocessing',     label: 'Preparing image',                       hint: 'Rotating, deskewing, perspective fix' },
  { key: 'grid_detected',     label: 'Reading the calendar grid',             hint: 'Found 5 weeks \u00d7 7 days' },
  { key: 'model_loading',     label: 'Loading vision model',                  hint: 'First time can take 15\u201325 sec' },
  { key: 'cell_progress',     label: 'Reading cells',                         hint: 'Qwen2.5-VL 7B, ~8 sec / cell' },
  { key: 'color_matching',    label: 'Identifying writers by ink color',      hint: 'HSV histogram \u2192 family member' },
  { key: 'date_normalization',label: 'Resolving dates',                       hint: 'Cell coords \u2192 ISO date' },
  { key: 'confidence_gating', label: 'Reviewing confidence',                  hint: 'Threshold = 85%' },
  { key: 'publishing',        label: 'Saving to Google Calendar',             hint: 'Auto-published events only' },
  { key: 'done',              label: 'Done',                                  hint: '' },
];
