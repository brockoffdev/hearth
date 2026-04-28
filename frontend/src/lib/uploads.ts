import { apiFetch, ApiError } from './api';

export type UploadStatus = 'processing' | 'completed' | 'failed';

export interface Upload {
  id: string;
  status: UploadStatus;
  // legacy (Phase 3 frontend)
  image_path: string;
  url: string;
  uploaded_at: string;
  // Phase 3.5 fields
  thumbLabel: string;
  startedAt?: string;
  finishedAt?: string;
  current_stage?: string;
  completed_stages?: string[];
  cellProgress?: number;
  totalCells?: number;
  remaining_seconds?: number;
  queuedBehind?: number;
  found?: number;
  review?: number;
  durationSec?: number;
  error?: string;
}

/** @deprecated Use {@link Upload} (Phase 3.5+ shape). */
export type UploadSummary = Upload;

export async function listUploads(): Promise<Upload[]> {
  return apiFetch<Upload[]>('/api/uploads');
}

export async function getUpload(id: string | number): Promise<Upload> {
  return apiFetch<Upload>(`/api/uploads/${id}`);
}

export async function retryUpload(id: string | number): Promise<Upload> {
  return apiFetch<Upload>(`/api/uploads/${id}/retry`, { method: 'POST' });
}

export async function cancelUpload(id: string | number): Promise<void> {
  return apiFetch<void>(`/api/uploads/${id}`, { method: 'DELETE' });
}

/**
 * Upload a photo file to /api/uploads.
 *
 * NOTE: cannot use apiFetch here because apiFetch unconditionally sets
 * Content-Type: application/json, which overrides the multipart/form-data
 * boundary that the browser needs to set automatically for FormData bodies.
 * We use fetch directly and let the browser handle the Content-Type header.
 */
export async function uploadPhoto(file: File): Promise<Upload> {
  const formData = new FormData();
  formData.append('photo', file, file.name);
  const res = await fetch('/api/uploads', {
    method: 'POST',
    credentials: 'include',
    body: formData,
    // NOTE: do NOT set Content-Type — let the browser set the multipart boundary
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new ApiError(res.status, (detail['detail'] as string | undefined) ?? 'Upload failed');
  }
  return res.json() as Promise<Upload>;
}
