import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { subscribeUploadEvents } from './sseClient';
import type { StageUpdate } from './sseClient';

// ---------------------------------------------------------------------------
// MockEventSource — minimal EventSource shim for tests
// ---------------------------------------------------------------------------

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  listeners: Record<string, Array<(e: MessageEvent | Event) => void>> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: (e: MessageEvent | Event) => void) {
    (this.listeners[type] ??= []).push(fn);
  }

  close() {
    this.closed = true;
  }

  /** Test helper — fires a named event with JSON-stringified data */
  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    (this.listeners[type] ?? []).forEach((fn) => fn(event));
  }

  /** Test helper — fires a bare error event */
  emitError() {
    const event = new Event('error');
    (this.listeners['error'] ?? []).forEach((fn) => fn(event));
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('subscribeUploadEvents', () => {
  it('creates an EventSource at the correct URL', () => {
    subscribeUploadEvents(42, { onStage: vi.fn() });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0]!.url).toBe('/api/uploads/42/events');
  });

  it('calls onStage with parsed update when stage_update fires', () => {
    const onStage = vi.fn();
    subscribeUploadEvents(1, { onStage });

    const source = MockEventSource.instances[0]!;
    const update: StageUpdate = {
      stage: 'preprocessing',
      message: null,
      progress: null,
    };
    source.emit('stage_update', update);

    expect(onStage).toHaveBeenCalledOnce();
    expect(onStage).toHaveBeenCalledWith(update);
  });

  it('parses cell_progress payload correctly', () => {
    const onStage = vi.fn();
    subscribeUploadEvents(1, { onStage });

    const source = MockEventSource.instances[0]!;
    const update: StageUpdate = {
      stage: 'cell_progress',
      message: null,
      progress: { cell: 7, total: 35 },
    };
    source.emit('stage_update', update);

    expect(onStage).toHaveBeenCalledWith(
      expect.objectContaining({ progress: { cell: 7, total: 35 } }),
    );
  });

  it('returns a cleanup function that closes the EventSource', () => {
    const cleanup = subscribeUploadEvents(5, { onStage: vi.fn() });

    const source = MockEventSource.instances[0]!;
    expect(source.closed).toBe(false);

    cleanup();

    expect(source.closed).toBe(true);
  });

  it('calls onError when the error event fires', () => {
    const onError = vi.fn();
    subscribeUploadEvents(1, { onStage: vi.fn(), onError });

    const source = MockEventSource.instances[0]!;
    source.emitError();

    expect(onError).toHaveBeenCalledOnce();
  });

  it('does not throw if onError is not provided', () => {
    subscribeUploadEvents(1, { onStage: vi.fn() });

    const source = MockEventSource.instances[0]!;
    expect(() => source.emitError()).not.toThrow();
  });

  it('does not call onStage for events other than stage_update', () => {
    const onStage = vi.fn();
    subscribeUploadEvents(1, { onStage });

    const source = MockEventSource.instances[0]!;
    // Fire an unrelated event type — onStage should not be called
    (source.listeners['open'] ?? []).forEach((fn) => fn(new Event('open')));

    expect(onStage).not.toHaveBeenCalled();
  });
});
