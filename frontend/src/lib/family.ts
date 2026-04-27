export type FamilyMemberId = 'bryant' | 'danielle' | 'isabella' | 'eliana' | 'family';

export interface FamilyMember {
  id: FamilyMemberId;
  name: string;
  role: string;
  hex: string;    // e.g. "#2E5BA8"
  label: string;  // e.g. "Blue"
}

export const HEARTH_FAMILY: readonly FamilyMember[] = [
  { id: 'bryant',   name: 'Bryant',   role: 'Dad',      hex: '#2E5BA8', label: 'Blue'   },
  { id: 'danielle', name: 'Danielle', role: 'Mom',       hex: '#C0392B', label: 'Red'    },
  { id: 'isabella', name: 'Izzy',     role: 'Age 3',     hex: '#7B4FB8', label: 'Purple' },
  { id: 'eliana',   name: 'Ellie',    role: 'Age 0',     hex: '#E17AA1', label: 'Pink'   },
  { id: 'family',   name: 'Family',   role: 'Everyone',  hex: '#D97A2C', label: 'Orange' },
] as const;
