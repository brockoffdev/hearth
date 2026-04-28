import { apiFetch } from './api';

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

// Backend-stored display names (e.g. "Izzy", "Ellie") don't match local
// FamilyMemberId keys ("isabella", "eliana"), so we resolve via the unique
// per-family color hex instead.
export function familyIdByHex(hex: string | null | undefined): FamilyMemberId | undefined {
  if (!hex) return undefined;
  const normalized = hex.toLowerCase();
  return HEARTH_FAMILY.find((m) => m.hex.toLowerCase() === normalized)?.id;
}

/** Shape returned by GET /api/family (mirrors the admin FamilyMemberResponse schema). */
export interface ApiFamilyMember {
  id: number;
  name: string;
  color_hex_center: string;
  google_calendar_id: string | null;
}

export async function listFamily(): Promise<ApiFamilyMember[]> {
  return apiFetch<ApiFamilyMember[]>('/api/family');
}
