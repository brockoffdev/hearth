/**
 * Format an ETA in seconds as a friendly string.
 * Returns "—" if seconds is null or undefined.
 * Returns "~N sec" for < 60, "~N min" for exact minutes,
 * "~N min M sec" for mixed.
 */
export function formatETA(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `~${Math.max(0, seconds)} sec`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `~${m} min ${s} sec` : `~${m} min`;
}

/**
 * Format a completed duration in seconds as a compact string.
 * Returns "Ns" for < 60, "Nm" for exact minutes, "Nm Ns" for mixed.
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}
