"""Process-wide serial pipeline queue for Hearth uploads.

Only one pipeline runs at a time on this server (one GPU = one pipeline).
Subsequent uploads queue up and receive a queue-position number exposed via
the API so the frontend can render numbered badges and estimated wait times.

**Durability limitation:** this queue is process-local.  If the API process
restarts (e.g. Docker container restart), any in-flight or queued uploads will
have their runner tasks lost.  Their DB rows remain with status='queued' or
status='processing' and will be stuck until manually reset.  Phase 4+ may
add startup recovery (re-enqueue unfinished rows on boot).  For Phase 3.5
(single-tenant LAN-only home server) a manual restart is acceptable.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

# Process-wide pipeline lock.  ONE pipeline runs at a time on this server.
_pipeline_lock: Final[asyncio.Lock] = asyncio.Lock()

# Process-wide queue of pending upload IDs (FIFO).
# The lock owner pops itself from the front before acquiring the lock.
_pending_queue: Final[list[int]] = []
_pending_set: Final[set[int]] = set()  # O(1) membership + queue-position computation


async def enqueue(upload_id: int) -> None:
    """Add an upload to the pending queue.

    Called immediately after POST /api/uploads creates the DB row.
    No-ops if the upload is already queued (idempotent).
    """
    if upload_id in _pending_set:
        return
    _pending_queue.append(upload_id)
    _pending_set.add(upload_id)


async def dequeue(upload_id: int) -> None:
    """Remove an upload from the queue before it starts.

    Used by DELETE /api/uploads/{id} to cancel a queued upload.
    No-ops if the upload is not in the queue.
    """
    if upload_id not in _pending_set:
        return
    _pending_queue.remove(upload_id)
    _pending_set.discard(upload_id)


@asynccontextmanager
async def acquire_pipeline_slot(upload_id: int) -> AsyncIterator[None]:
    """Async context manager: wait until this upload is at the head of the
    queue AND the pipeline lock is free, then yield.  Releases on exit.

    Spin-waits in 100ms increments until we reach the head.  Each check is
    cooperative, so other coroutines (SSE poll loops, etc.) can run.
    """
    # Spin until we're at the head of the queue.
    while _pending_queue and _pending_queue[0] != upload_id:
        await asyncio.sleep(0.1)

    async with _pipeline_lock:
        # Pop ourselves from the queue.
        if _pending_queue and _pending_queue[0] == upload_id:
            _pending_queue.pop(0)
            _pending_set.discard(upload_id)
        yield


def queue_position(upload_id: int) -> int | None:
    """Return the upload's position in the pending queue.

    Returns:
        0 if this upload is at the head (about to run or running).
        N (>0) if N uploads are ahead.
        None if the upload is not in the queue (not queued, or already running).
    """
    if upload_id not in _pending_set:
        return None
    try:
        return _pending_queue.index(upload_id)
    except ValueError:
        return None


def queued_count() -> int:
    """Return the number of uploads currently waiting in the queue."""
    return len(_pending_queue)


def _reset_for_tests() -> None:
    """Clear all queue state and reset the pipeline lock.

    Called by test fixtures to isolate tests.  Because asyncio.Lock is bound
    to the event loop on first use, and pytest-asyncio creates a new event
    loop per test, we must replace the lock object each time — otherwise the
    second+ test that uses the lock raises "bound to a different event loop".

    We reassign the module-level name via globals() because ``_pipeline_lock``
    is declared ``Final`` (typing annotation only; Python does not enforce it
    at runtime).
    """
    _pending_queue.clear()
    _pending_set.clear()
    globals()["_pipeline_lock"] = asyncio.Lock()
