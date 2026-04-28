import type { StageKey } from './stages';

export interface StageUpdate {
  stage: StageKey;
  message: string | null;
  progress: { cell: number; total: number } | null;
}

export interface SSEHandlers {
  onStage: (update: StageUpdate) => void;
  onError?: (event: Event) => void;
  onClose?: () => void;
}

/**
 * Subscribe to the SSE stream for a given upload.
 *
 * Returns a cleanup function that closes the EventSource; pass it directly
 * as the return value of a useEffect callback.
 *
 * EventSource sends cookies automatically on same-origin requests — no
 * `withCredentials` flag needed for cookie auth.
 */
export function subscribeUploadEvents(
  uploadId: number,
  handlers: SSEHandlers,
): () => void {
  const url = `/api/uploads/${uploadId}/events`;
  const source = new EventSource(url);

  source.addEventListener('stage_update', (e: MessageEvent) => {
    const update = JSON.parse(e.data) as StageUpdate;
    handlers.onStage(update);
  });

  source.addEventListener('error', (e: Event) => {
    handlers.onError?.(e);
    // EventSource auto-reconnects on transient errors.
    // The caller (UploadDetail) decides whether to close.
  });

  return () => source.close();
}
