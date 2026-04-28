/**
 * Anonymous TV snapshot API client.
 * Uses plain fetch (NOT apiFetch) so no session cookie is sent — the /tv
 * route is intentionally unauthenticated.
 */

export interface TvFamilyMember {
  id: number;
  name: string;
  color_hex: string;
}

export interface TvEvent {
  id: number;
  title: string;
  start_dt: string;
  end_dt: string | null;
  all_day: boolean;
  family_member_id: number | null;
  family_member_name: string | null;
  family_member_color_hex: string | null;
}

export interface TvSnapshot {
  family_members: TvFamilyMember[];
  events: TvEvent[];
  server_time: string;
}

export async function getTvSnapshot(): Promise<TvSnapshot> {
  const res = await fetch('/api/tv/snapshot', {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`TV snapshot fetch failed: ${res.status}`);
  }
  return res.json() as Promise<TvSnapshot>;
}
