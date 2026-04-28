import { apiFetch } from './api';

export interface AdminUser {
  id: number;
  username: string;
  role: 'admin' | 'user';
  must_change_password: boolean;
  must_complete_google_setup: boolean;
  created_at: string;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role?: 'admin' | 'user';
}

export interface PatchUserPayload {
  role?: 'admin' | 'user';
  new_password?: string;
}

export async function listUsers(): Promise<AdminUser[]> {
  const data = await apiFetch<{ items: AdminUser[] }>('/api/admin/users');
  return data.items;
}

export async function createUser(body: CreateUserPayload): Promise<AdminUser> {
  return apiFetch<AdminUser>('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function patchUser(id: number, body: PatchUserPayload): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteUser(id: number): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${id}`, { method: 'DELETE' });
}
