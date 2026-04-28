/**
 * Formats an ISO timestamp as a human-readable relative time string.
 * No external dependencies — pure branching logic.
 */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();

  // Defensive: future timestamp or < 1 minute
  if (diffMs < 60_000) return 'Just now';

  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 60) {
    return diffMins === 1 ? '1 minute ago' : `${diffMins} minutes ago`;
  }

  const diffHours = Math.floor(diffMs / (60 * 60_000));
  if (diffHours < 24) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
  }

  const diffDays = Math.floor(diffMs / (24 * 60 * 60_000));
  if (diffDays < 2) return 'Yesterday';

  // Older: show "Mon, Apr 27" style
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
