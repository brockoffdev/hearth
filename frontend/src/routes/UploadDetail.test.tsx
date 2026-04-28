import {
  render,
  screen,
  waitFor,
  act,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { UploadDetail } from './UploadDetail';
import type { UploadSummary } from '../lib/uploads';

// ---------------------------------------------------------------------------
// MockEventSource
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

  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    (this.listeners[type] ?? []).forEach((fn) => fn(event));
  }

  emitError() {
    const event = new Event('error');
    (this.listeners['error'] ?? []).forEach((fn) => fn(event));
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeUploadResponse(
  overrides: Partial<UploadSummary> = {},
): UploadSummary {
  return {
    id: 7,
    status: 'processing',
    image_path: 'uploads/7.jpg',
    uploaded_at: '2026-04-27T10:00:00Z',
    url: '/api/uploads/7/photo',
    ...overrides,
  };
}

function makeFetchResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderDetail(id: string | number = 7) {
  return render(
    <MemoryRouter initialEntries={[`/uploads/${id}`]}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/uploads/:id" element={<UploadDetail />} />
            <Route path="/" element={<div data-testid="home-page">Home</div>} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
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
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('UploadDetail — invalid id', () => {
  it('navigates to / when id is not a number', async () => {
    // fetch should not be called; render with a non-numeric id
    vi.stubGlobal('fetch', vi.fn());

    renderDetail('notanumber');

    await waitFor(() => {
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });
  });

  it('navigates to / when id is zero', async () => {
    vi.stubGlobal('fetch', vi.fn());

    renderDetail(0);

    await waitFor(() => {
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });
  });
});

describe('UploadDetail — 404 upload', () => {
  it('shows "Upload not found" with a back button', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(404, { detail: 'Not found' }),
      ),
    );

    renderDetail(999);

    await waitFor(() => {
      expect(screen.getByText(/upload not found/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
  });
});

describe('UploadDetail — processing state', () => {
  it('renders the photo thumbnail with src ending in /photo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      const img = screen.getByRole('img', { name: /calendar photo/i });
      expect(img.getAttribute('src')).toMatch(/\/api\/uploads\/7\/photo$/);
    });
  });

  it('renders all 10 HEARTH_STAGES on initial render', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      // Check a few representative stage labels
      expect(screen.getByText('Photo received')).toBeInTheDocument();
      expect(screen.getByText('Reading cells')).toBeInTheDocument();
      expect(screen.getByText('Saving to Google Calendar')).toBeInTheDocument();
    });
  });

  it('marks a stage active and previous stages done on stage_update', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    // Wait for SSE connection
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emit('stage_update', {
        stage: 'preprocessing',
        message: null,
        progress: null,
      });
    });

    await waitFor(() => {
      const activeRow = document.querySelector('[data-status="active"]');
      expect(activeRow).toBeInTheDocument();
      expect(activeRow!.textContent).toMatch(/preparing image/i);

      const doneRows = document.querySelectorAll('[data-status="done"]');
      // "received" should be done
      expect(doneRows.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('updates hint text with cell progress', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emit('stage_update', {
        stage: 'cell_progress',
        message: null,
        progress: { cell: 7, total: 35 },
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/reading cell 7 of 35/i)).toBeInTheDocument();
    });
  });

  it('subscribes to SSE at the correct URL', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    expect(MockEventSource.instances[0]!.url).toBe('/api/uploads/7/events');
  });
});

describe('UploadDetail — done event', () => {
  it('transitions to Done view with Back home button', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emit('stage_update', {
        stage: 'done',
        message: null,
        progress: null,
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/done/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /back home/i }),
      ).toBeInTheDocument();
    });
  });

  it('closes the EventSource when done event arrives', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emit('stage_update', {
        stage: 'done',
        message: null,
        progress: null,
      });
    });

    await waitFor(() => {
      expect(source.closed).toBe(true);
    });
  });
});

describe('UploadDetail — already-completed upload', () => {
  it('shows Done view immediately without SSE subscription', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse({ status: 'completed' })),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      expect(screen.getByText(/processing complete/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /back home/i }),
      ).toBeInTheDocument();
    });

    // No SSE connection should have been opened
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('shows Done view for failed status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse({ status: 'failed' })),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      expect(screen.getByText(/processing failed/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /back home/i }),
      ).toBeInTheDocument();
    });

    expect(MockEventSource.instances).toHaveLength(0);
  });
});

describe('UploadDetail — SSE error', () => {
  it('shows connection error banner on SSE error event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emitError();
    });

    await waitFor(() => {
      expect(screen.getByText(/connection lost/i)).toBeInTheDocument();
    });
  });
});
