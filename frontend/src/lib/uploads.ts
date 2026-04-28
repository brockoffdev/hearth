import { apiFetch } from './api';

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
