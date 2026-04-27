import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { SetupGoogle } from './SetupGoogle';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** Render SetupGoogle at the given initialPath. */
function renderSetupGoogle(initialPath = '/setup/google') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/setup/google" element={<SetupGoogle />} />
        <Route
          path="/setup/family"
          element={<div data-testid="setup-family-page">family</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** Stub fetch to resolve state query with {connected: false, ...} then any extras. */
function stubFetchWithState(
  stateBody: Record<string, unknown>,
  extraResponses: Response[] = [],
) {
  const mock = vi.fn()
    .mockResolvedValueOnce(makeResponse(200, stateBody));
  extraResponses.forEach((r) => mock.mockResolvedValueOnce(r));
  vi.stubGlobal('fetch', mock);
  return mock;
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
  // Provide a default window.location.assign stub so tests don't crash on it.
  vi.stubGlobal('location', {
    ...window.location,
    assign: vi.fn(),
    origin: 'http://localhost:8080',
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Initial state (not yet connected)
// ---------------------------------------------------------------------------

describe('SetupGoogle — initial state (not connected)', () => {
  it('renders both Client ID and Client Secret input fields', async () => {
    stubFetchWithState({ connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null });
    renderSetupGoogle();

    await waitFor(() => screen.getByLabelText('Client ID'));
    expect(screen.getByLabelText('Client Secret')).not.toBeNull();
  });

  it('renders the redirect URI hint line', async () => {
    stubFetchWithState({ connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null });
    renderSetupGoogle();

    await waitFor(() => screen.getByText(/api\/google\/oauth\/callback/i));
  });

  it('renders WizardSteps with Google=active', async () => {
    stubFetchWithState({ connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null });
    renderSetupGoogle();

    await waitFor(() => screen.getByText('Google'));
    const activeSteps = document.querySelectorAll('[data-status="active"]');
    expect(activeSteps.length).toBeGreaterThan(0);
  });

  it('renders "Continue with Google" button', async () => {
    stubFetchWithState({ connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null });
    renderSetupGoogle();

    await waitFor(() => screen.getByText(/Continue with Google/i));
  });
});

// ---------------------------------------------------------------------------
// Client-side validation
// ---------------------------------------------------------------------------

describe('SetupGoogle — client-side validation', () => {
  it('empty inputs → no fetch call beyond state check', async () => {
    const fetchMock = stubFetchWithState({
      connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null,
    });

    renderSetupGoogle();
    await waitFor(() => screen.getByText(/Continue with Google/i));

    await act(async () => {
      fireEvent.click(screen.getByText(/Continue with Google/i));
    });

    // Only the initial state fetch was called; no credentials or init calls.
    const credentialsCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && (c[0] as string).includes('/credentials'),
    );
    expect(credentialsCalls.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Happy path: POST credentials → POST init → window.location.assign
// ---------------------------------------------------------------------------

describe('SetupGoogle — clicking "Continue with Google"', () => {
  it('POSTs /credentials then /init and calls window.location.assign with authorization_url', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse(200, {
        connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null,
      }))
      .mockResolvedValueOnce(makeResponse(200, { ok: true }))           // /credentials
      .mockResolvedValueOnce(makeResponse(200, {                        // /init
        authorization_url: 'https://accounts.google.com/o/oauth2/auth?test=1',
      }));
    vi.stubGlobal('fetch', fetchMock);

    renderSetupGoogle();
    await waitFor(() => screen.getByLabelText('Client ID'));

    fireEvent.change(screen.getByLabelText('Client ID'), {
      target: { value: 'my-client-id' },
    });
    fireEvent.change(screen.getByLabelText('Client Secret'), {
      target: { value: 'my-client-secret' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText(/Continue with Google/i));
    });

    await waitFor(() =>
      expect(window.location.assign).toHaveBeenCalledWith(
        'https://accounts.google.com/o/oauth2/auth?test=1',
      ),
    );

    // Verify credentials POST body.
    const credsCall = fetchMock.mock.calls.find(
      (c) => typeof c[0] === 'string' && (c[0] as string).includes('/credentials'),
    );
    expect(credsCall).toBeDefined();
    const body = JSON.parse(credsCall![1].body as string) as Record<string, string>;
    expect(body.client_id).toBe('my-client-id');
    expect(body.client_secret).toBe('my-client-secret');
  });

  it('400 from /init renders error inline', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse(200, {
        connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null,
      }))
      .mockResolvedValueOnce(makeResponse(200, { ok: true }))    // /credentials
      .mockResolvedValueOnce(makeResponse(400, {                  // /init fails
        detail: 'OAuth credentials not configured',
      }));
    vi.stubGlobal('fetch', fetchMock);

    renderSetupGoogle();
    await waitFor(() => screen.getByLabelText('Client ID'));

    fireEvent.change(screen.getByLabelText('Client ID'), {
      target: { value: 'id' },
    });
    fireEvent.change(screen.getByLabelText('Client Secret'), {
      target: { value: 'secret' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText(/Continue with Google/i));
    });

    await waitFor(() =>
      expect(screen.getByText(/OAuth credentials not configured/i)).not.toBeNull(),
    );
  });
});

// ---------------------------------------------------------------------------
// ?status=ok — connected state
// ---------------------------------------------------------------------------

describe('SetupGoogle — ?status=ok (connected)', () => {
  it('renders "Connected" success state', async () => {
    stubFetchWithState({ connected: true, calendars_mapped: false, refresh_token_present: true, scopes: ['https://www.googleapis.com/auth/calendar'] });
    renderSetupGoogle('/setup/google?status=ok');

    // Wait for the Connected success text in the success card specifically.
    await waitFor(() => screen.getByText('Connected to Google Calendar'));
    expect(screen.getByText(/Continue to family setup/i)).not.toBeNull();
  });

  it('"Continue to family setup" navigates to /setup/family', async () => {
    stubFetchWithState({ connected: true, calendars_mapped: false, refresh_token_present: true, scopes: null });
    renderSetupGoogle('/setup/google?status=ok');

    await waitFor(() => screen.getByText(/Continue to family setup/i));

    await act(async () => {
      fireEvent.click(screen.getByText(/Continue to family setup/i));
    });

    await waitFor(() =>
      expect(screen.getByTestId('setup-family-page')).not.toBeNull(),
    );
  });
});

// ---------------------------------------------------------------------------
// ?status=error — error state
// ---------------------------------------------------------------------------

describe('SetupGoogle — ?status=error', () => {
  it('renders error banner with the detail message', async () => {
    stubFetchWithState({ connected: false, calendars_mapped: false, refresh_token_present: false, scopes: null });
    renderSetupGoogle('/setup/google?status=error&detail=Redirect+URI+mismatch');

    await waitFor(() =>
      expect(screen.getByText(/Redirect URI mismatch/i)).not.toBeNull(),
    );

    // Also renders the form so user can retry.
    await waitFor(() => screen.getByLabelText('Client ID'));
  });
});
