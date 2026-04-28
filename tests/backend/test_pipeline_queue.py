"""Tests for the process-wide serial pipeline queue (uploads/queue.py).

Each test calls _reset_for_tests() via a fixture to guarantee isolation, since
the queue is a module-level singleton (process-wide state).
"""

from __future__ import annotations

import asyncio

import pytest

from backend.app.uploads.queue import (
    _reset_for_tests,
    acquire_pipeline_slot,
    dequeue,
    enqueue,
    queue_position,
    queued_count,
)

# ---------------------------------------------------------------------------
# Fixture: reset queue state before every test.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_queue() -> None:
    """Wipe all queue state before each test for isolation."""
    _reset_for_tests()


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------


async def test_enqueue_appends_to_queue() -> None:
    """enqueue adds upload IDs to the pending queue in FIFO order."""
    await enqueue(1)
    await enqueue(2)
    await enqueue(3)

    assert queued_count() == 3
    assert queue_position(1) == 0
    assert queue_position(2) == 1
    assert queue_position(3) == 2


async def test_enqueue_is_idempotent() -> None:
    """Calling enqueue twice for the same ID is a no-op."""
    await enqueue(42)
    await enqueue(42)

    assert queued_count() == 1
    assert queue_position(42) == 0


# ---------------------------------------------------------------------------
# dequeue
# ---------------------------------------------------------------------------


async def test_dequeue_removes_from_queue() -> None:
    """dequeue removes a specific ID from the queue."""
    await enqueue(10)
    await enqueue(20)
    await enqueue(30)

    await dequeue(20)

    assert queued_count() == 2
    assert queue_position(10) == 0
    assert queue_position(30) == 1
    assert queue_position(20) is None


async def test_dequeue_noop_if_not_queued() -> None:
    """dequeue on an ID not in the queue does not raise."""
    await enqueue(5)
    await dequeue(999)  # should not raise

    assert queued_count() == 1


# ---------------------------------------------------------------------------
# queue_position
# ---------------------------------------------------------------------------


async def test_queue_position_returns_zero_for_head() -> None:
    """The first enqueued upload is at position 0."""
    await enqueue(100)
    assert queue_position(100) == 0


async def test_queue_position_returns_n_for_position() -> None:
    """Uploads behind the head have position > 0."""
    await enqueue(1)
    await enqueue(2)
    await enqueue(3)

    assert queue_position(2) == 1
    assert queue_position(3) == 2


async def test_queue_position_returns_none_for_unqueued() -> None:
    """An upload that was never enqueued returns None."""
    assert queue_position(9999) is None


async def test_queue_position_returns_none_after_dequeue() -> None:
    """After dequeue the upload is no longer findable."""
    await enqueue(77)
    await dequeue(77)
    assert queue_position(77) is None


# ---------------------------------------------------------------------------
# acquire_pipeline_slot — serial execution
# ---------------------------------------------------------------------------


async def test_acquire_lock_serial() -> None:
    """Two concurrent pipelines run serially: second waits for first to release."""
    events: list[str] = []

    await enqueue(1)
    await enqueue(2)

    async def pipeline_a() -> None:
        async with acquire_pipeline_slot(1):
            events.append("a_start")
            await asyncio.sleep(0)  # yield to let b try
            events.append("a_end")

    async def pipeline_b() -> None:
        async with acquire_pipeline_slot(2):
            events.append("b_start")
            events.append("b_end")

    # Run concurrently.
    await asyncio.gather(pipeline_a(), pipeline_b())

    # Pipeline A must fully complete before B starts.
    assert events == ["a_start", "a_end", "b_start", "b_end"]
