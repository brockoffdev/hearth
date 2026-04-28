import { apiFetch } from './api';

export type EventStatus =
  | 'pending_review'
  | 'auto_published'
  | 'published'
  | 'rejected'
  | 'superseded';

export interface Event {
  id: number;
  upload_id: number | null;
  family_member_id: number | null;
  family_member_name: string | null;
  family_member_color_hex: string | null;
  title: string;
  start_dt: string;
  end_dt: string | null;
  all_day: boolean;
  location: string | null;
  notes: string | null;
  confidence: number;
  status: EventStatus;
  google_event_id: string | null;
  cell_crop_path: string | null;
  has_cell_crop: boolean;
  raw_vlm_json: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface EventList {
  items: Event[];
  total: number;
}

export async function listEvents(params?: {
  status?: string | string[];
  upload_id?: number;
  limit?: number;
  offset?: number;
}): Promise<EventList> {
  const qs = new URLSearchParams();

  if (params?.status !== undefined) {
    const statusValue = Array.isArray(params.status)
      ? params.status.join(',')
      : params.status;
    qs.set('status', statusValue);
  }
  if (params?.upload_id !== undefined) qs.set('upload_id', String(params.upload_id));
  if (params?.limit !== undefined) qs.set('limit', String(params.limit));
  if (params?.offset !== undefined) qs.set('offset', String(params.offset));

  const query = qs.toString();
  return apiFetch<EventList>(`/api/events${query ? `?${query}` : ''}`);
}

export async function getEvent(id: number): Promise<Event> {
  return apiFetch<Event>(`/api/events/${id}`);
}

export async function patchEvent(
  id: number,
  body: Partial<
    Pick<Event, 'title' | 'start_dt' | 'end_dt' | 'all_day' | 'family_member_id' | 'location' | 'notes'>
  >,
): Promise<Event> {
  return apiFetch<Event>(`/api/events/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function rejectEvent(id: number): Promise<void> {
  return apiFetch<void>(`/api/events/${id}`, { method: 'DELETE' });
}

export async function getPendingCount(): Promise<number> {
  const data = await apiFetch<{ count: number }>('/api/events/pending-count');
  return data.count;
}

export async function republishEvent(id: number | string): Promise<Event> {
  return apiFetch<Event>(`/api/events/${id}/republish`, { method: 'POST' });
}

export function cellCropUrl(eventId: number): string {
  return `/api/events/${eventId}/cell-crop`;
}
