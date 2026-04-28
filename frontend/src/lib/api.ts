export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new ApiError(res.status, (detail['detail'] as string | undefined) ?? 'Request failed');
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}
