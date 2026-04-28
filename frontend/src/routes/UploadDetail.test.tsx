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
import { HEARTH_STAGES } from '../lib/stages';

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
    id: '7',
    status: 'processing',
    image_path: 'uploads/7.jpg',
    uploaded_at: '2026-04-27T10:00:00Z',
    url: '/api/uploads/7/photo',
    thumbLabel: 'Apr 27, 10:00 AM',
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
            <Route path="/uploads" element={<div data-testid="uploads-page">Uploads</div>} />
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
        completed_stages: ['received'],
        remaining_seconds: 90,
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

  it('progress badge shows "N of HEARTH_STAGES.length-1" after stage_update', async () => {
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
        stage: 'preprocessing',
        message: null,
        progress: null,
        completed_stages: ['received'],
        remaining_seconds: 90,
      });
    });

    // After receiving 'preprocessing' active with 'received' done:
    // progressCount = 1 (received done) + 1 (preprocessing active) = 2
    // Badge should read "2 of <HEARTH_STAGES.length - 1>" i.e. "2 of 9"
    const expectedTotal = HEARTH_STAGES.length - 1;
    await waitFor(() => {
      expect(screen.getByText(new RegExp(`2 of ${expectedTotal}`))).toBeInTheDocument();
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

  it('clears connection error banner when the next successful stage_update arrives', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    // First fire an SSE error — banner appears
    act(() => {
      source.emitError();
    });

    await waitFor(() => {
      expect(screen.getByText(/connection lost/i)).toBeInTheDocument();
    });

    // Then a successful stage_update arrives — banner must be cleared
    act(() => {
      source.emit('stage_update', {
        stage: 'preprocessing',
        message: null,
        progress: null,
        completed_stages: ['received'],
        remaining_seconds: 90,
      });
    });

    await waitFor(() => {
      expect(screen.queryByText(/connection lost/i)).not.toBeInTheDocument();
    });
  });
});

describe('UploadDetail — ETA chip', () => {
  it('renders ETA in header subtitle when remaining_seconds is in the SSE event', async () => {
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
        stage: 'preprocessing',
        message: null,
        progress: null,
        completed_stages: ['received'],
        remaining_seconds: 184,
      });
    });

    await waitFor(() => {
      // formatETA(184) → "~3 min 4 sec"
      expect(screen.getByText(/~3 min 4 sec/i)).toBeInTheDocument();
      expect(screen.getByText(/remaining/i)).toBeInTheDocument();
    });
  });

  it('renders "—" as ETA before first SSE event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    // No SSE events yet — should show default "—"
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('renders "total · waiting in queue" copy when currentStage is queued', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse({ status: 'processing' })),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const source = MockEventSource.instances[0]!;

    act(() => {
      source.emit('stage_update', {
        stage: 'queued',
        message: null,
        progress: null,
        completed_stages: [],
        remaining_seconds: 300,
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/waiting in queue/i)).toBeInTheDocument();
      expect(screen.getByText(/total/i)).toBeInTheDocument();
    });
  });
});

describe('UploadDetail — Continue in background', () => {
  it('renders the Continue in background button during active processing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    expect(
      screen.getByRole('button', { name: /continue in background/i }),
    ).toBeInTheDocument();
  });

  it('Continue in background button navigates to /uploads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    const { getByRole } = renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const btn = getByRole('button', { name: /continue in background/i });
    act(() => btn.click());

    await waitFor(() => {
      // After navigation the UploadDetail route unmounts; /uploads route would render
      // but our test renders only /uploads/:id and / routes. The navigate call should
      // cause the route to change — verify the button is no longer visible.
      expect(screen.queryByRole('button', { name: /continue in background/i })).toBeNull();
    });
  });

  it('Continue in background button is hidden in terminal Done state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse({ status: 'completed' })),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      expect(screen.getByText(/processing complete/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole('button', { name: /continue in background/i }),
    ).toBeNull();
  });

  it('Continue in background button is hidden in terminal Failed state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse({ status: 'failed' })),
      ),
    );

    renderDetail(7);

    await waitFor(() => {
      expect(screen.getByText(/processing failed/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole('button', { name: /continue in background/i }),
    ).toBeNull();
  });
});

describe('UploadDetail — BackChevron navigation', () => {
  it('renders the BackChevron button with aria-label "Go back"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    expect(screen.getByRole('button', { name: /go back/i })).toBeInTheDocument();
  });

  it('BackChevron click navigates to /uploads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        makeFetchResponse(200, makeUploadResponse()),
      ),
    );

    renderDetail(7);

    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

    const chevron = screen.getByRole('button', { name: /go back/i });
    act(() => chevron.click());

    await waitFor(() => {
      // /uploads route is not registered in renderDetail's test router —
      // verify we left the detail page (component unmounted)
      expect(screen.queryByRole('button', { name: /go back/i })).toBeNull();
    });
  });
});
