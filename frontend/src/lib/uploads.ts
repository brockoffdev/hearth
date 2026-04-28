import { apiFetch, ApiError } from './api';

export type UploadStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface UploadSummary {
  id: number;
  status: UploadStatus;
  image_path: string;
  uploaded_at: string; // ISO
  url: string;         // /api/uploads/{id}/photo
}

export async function listUploads(): Promise<UploadSummary[]> {
  return apiFetch<UploadSummary[]>('/api/uploads');
}

export async function getUpload(id: number): Promise<UploadSummary> {
  return apiFetch<UploadSummary>(`/api/uploads/${id}`);
}

/**
 * Upload a photo file to /api/uploads.
 *
 * NOTE: cannot use apiFetch here because apiFetch unconditionally sets
 * Content-Type: application/json, which overrides the multipart/form-data
 * boundary that the browser needs to set automatically for FormData bodies.
 * We use fetch directly and let the browser handle the Content-Type header.
 */
export async function uploadPhoto(file: File): Promise<UploadSummary> {
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
  return res.json() as Promise<UploadSummary>;
}
