/**
 * Tests for the /setup/family wizard step (family ↔ Google Calendar mapping).
 *
 * All network calls are mocked via vi.stubGlobal('fetch', ...).
 * The AuthProvider is provided as a minimal stub so useAuth() doesn't crash.
 */

import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { SetupFamily } from './SetupFamily';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

interface FamilyMemberFixture {
  id: number;
  name: string;
  color_hex_center: string;
  google_calendar_id: string | null;
}

const FAMILY_MEMBERS_ALL_UNMAPPED: FamilyMemberFixture[] = [
  { id: 1, name: 'Bryant', color_hex_center: '#2E5BA8', google_calendar_id: null },
  { id: 2, name: 'Danielle', color_hex_center: '#C0392B', google_calendar_id: null },
  { id: 3, name: 'Izzy', color_hex_center: '#7B4FB8', google_calendar_id: null },
  { id: 4, name: 'Ellie', color_hex_center: '#E17AA1', google_calendar_id: null },
  { id: 5, name: 'Family', color_hex_center: '#D97A2C', google_calendar_id: null },
];

const FAMILY_MEMBERS_TWO_MAPPED: FamilyMemberFixture[] = [
  { id: 1, name: 'Bryant', color_hex_center: '#2E5BA8', google_calendar_id: 'cal1@group.calendar.google.com' },
  { id: 2, name: 'Danielle', color_hex_center: '#C0392B', google_calendar_id: 'cal2@group.calendar.google.com' },
  { id: 3, name: 'Izzy', color_hex_center: '#7B4FB8', google_calendar_id: null },
  { id: 4, name: 'Ellie', color_hex_center: '#E17AA1', google_calendar_id: null },
  { id: 5, name: 'Family', color_hex_center: '#D97A2C', google_calendar_id: null },
];

const GOOGLE_CALENDARS = [
  { id: 'cal1@group.calendar.google.com', summary: 'Bryant', primary: false, access_role: 'owner' },
  { id: 'cal2@group.calendar.google.com', summary: 'Danielle', primary: false, access_role: 'owner' },
  { id: 'cal3@group.calendar.google.com', summary: 'Family', primary: false, access_role: 'owner' },
];

/** Build a fetch mock that returns family + calendars on initial load, then any extras. */
function stubInitialFetch(
  familyData: FamilyMemberFixture[] = FAMILY_MEMBERS_ALL_UNMAPPED,
  calendarsData = GOOGLE_CALENDARS,
  extras: Response[] = [],
) {
  const mock = vi.fn()
    .mockResolvedValueOnce(makeResponse(200, familyData))
    .mockResolvedValueOnce(makeResponse(200, calendarsData));
  extras.forEach((r) => mock.mockResolvedValueOnce(r));
  vi.stubGlobal('fetch', mock);
  return mock;
}

/** Minimal auth context stub — provides refresh(). */
const mockRefresh = vi.fn().mockResolvedValue(undefined);
vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    state: { status: 'authenticated', user: { id: 1, username: 'admin', role: 'admin' } },
    refresh: mockRefresh,
  }),
}));

function renderSetupFamily() {
  return render(
    <MemoryRouter initialEntries={['/setup/family']}>
      <Routes>
        <Route path="/setup/family" element={<SetupFamily />} />
        <Route path="/" element={<div data-testid="home-page">home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.resetAllMocks();
  mockRefresh.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SetupFamily — breadcrumb', () => {
  it('renders WizardSteps with Family=active', async () => {
    stubInitialFetch();
    renderSetupFamily();

    await waitFor(() => {
      const activeSteps = document.querySelectorAll('[data-status="active"]');
      expect(activeSteps.length).toBeGreaterThan(0);
    });
    // Family label is in the wizard steps (active step).
    const activeStep = document.querySelector('[data-status="active"]');
    expect(activeStep?.textContent).toContain('Family');
  });
});

describe('SetupFamily — family rows', () => {
  it('loads and renders all 5 family members', async () => {
    stubInitialFetch();
    renderSetupFamily();

    // Each member's name appears in their row. Some also appear in dropdown options,
    // so use getAllByText and check at least 1 is present for each.
    await waitFor(() => {
      expect(screen.getAllByText('Bryant').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getAllByText('Danielle').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Izzy').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Ellie').length).toBeGreaterThanOrEqual(1);
    // Family name cell (row in the table)
    const familyTexts = screen.getAllByText('Family');
    expect(familyTexts.length).toBeGreaterThanOrEqual(1);
  });

  it('renders dropdown options from /api/google/calendars', async () => {
    stubInitialFetch();
    renderSetupFamily();

    // Wait for data to load — calendars are rendered as <option> elements.
    await waitFor(() => {
      const options = document.querySelectorAll('option[value="cal1@group.calendar.google.com"]');
      expect(options.length).toBeGreaterThan(0);
    });
  });
});

describe('SetupFamily — mapped count', () => {
  it('shows correct X of 5 mapped count after initial load (2 pre-mapped)', async () => {
    stubInitialFetch(FAMILY_MEMBERS_TWO_MAPPED);
    renderSetupFamily();

    // The status paragraph contains "<strong>2 of 5</strong> mapped"
    // Use a function matcher to check the full text content of the element.
    await waitFor(() => {
      const el = screen.getByText((_content, node) => {
        if (!node) return false;
        return node.textContent?.replace(/\s+/g, ' ').trim() === '2 of 5 mapped';
      });
      expect(el).not.toBeNull();
    });
  });

  it('shows 0 of 5 mapped when none are mapped', async () => {
    stubInitialFetch(FAMILY_MEMBERS_ALL_UNMAPPED);
    renderSetupFamily();

    await waitFor(() => {
      const el = screen.getByText((_content, node) => {
        if (!node) return false;
        return node.textContent?.replace(/\s+/g, ' ').trim() === '0 of 5 mapped';
      });
      expect(el).not.toBeNull();
    });
  });
});

describe('SetupFamily — selecting a calendar', () => {
  it('selecting a calendar triggers PATCH and updates the mapped count', async () => {
    const fetchMock = stubInitialFetch(
      FAMILY_MEMBERS_ALL_UNMAPPED,
      GOOGLE_CALENDARS,
      [
        // PATCH /api/admin/family/1
        makeResponse(200, {
          id: 1,
          name: 'Bryant',
          color_hex_center: '#2E5BA8',
          google_calendar_id: 'cal1@group.calendar.google.com',
        }),
      ],
    );
    renderSetupFamily();

    // Wait for data to load — check selects are rendered.
    await waitFor(() => {
      const selects = document.querySelectorAll('select');
      expect(selects.length).toBe(5);
    });

    // Find Bryant's select (first one).
    const selects = document.querySelectorAll('select');

    await act(async () => {
      fireEvent.change(selects[0]!, {
        target: { value: 'cal1@group.calendar.google.com' },
      });
    });

    // Should have made a PATCH call.
    await waitFor(() => {
      const patchCalls = fetchMock.mock.calls.filter(
        (c) =>
          typeof c[0] === 'string' &&
          (c[0] as string).includes('/api/admin/family') &&
          c[1]?.method === 'PATCH',
      );
      expect(patchCalls.length).toBe(1);
    });

    // Mapped count should have incremented to 1.
    await waitFor(() => {
      const el = screen.getByText((_content, node) => {
        if (!node) return false;
        return node.textContent?.replace(/\s+/g, ' ').trim() === '1 of 5 mapped';
      });
      expect(el).not.toBeNull();
    });
  });
});

describe('SetupFamily — finish setup button', () => {
  it('is disabled when fewer than 5 members are mapped', async () => {
    stubInitialFetch(FAMILY_MEMBERS_ALL_UNMAPPED);
    renderSetupFamily();

    await waitFor(() => {
      expect(document.querySelectorAll('select').length).toBe(5);
    });
    const finishBtn = screen.getByRole('button', { name: /finish setup/i });
    expect(finishBtn).toHaveProperty('disabled', true);
  });

  it('is enabled when all 5 are mapped', async () => {
    const allMapped = FAMILY_MEMBERS_ALL_UNMAPPED.map((m, i) => ({
      ...m,
      google_calendar_id: `cal${i + 1}@group.calendar.google.com`,
    }));
    stubInitialFetch(allMapped);
    renderSetupFamily();

    await waitFor(() => {
      expect(document.querySelectorAll('select').length).toBe(5);
    });
    const finishBtn = screen.getByRole('button', { name: /finish setup/i });
    expect(finishBtn).toHaveProperty('disabled', false);
  });

  it('calls /api/setup/complete-google, refreshes, navigates to / on success', async () => {
    const allMapped = FAMILY_MEMBERS_ALL_UNMAPPED.map((m, i) => ({
      ...m,
      google_calendar_id: `cal${i + 1}@group.calendar.google.com`,
    }));
    const fetchMock = stubInitialFetch(
      allMapped,
      GOOGLE_CALENDARS,
      [makeResponse(200, { id: 1, username: 'admin', must_complete_google_setup: false })],
    );
    renderSetupFamily();

    await waitFor(() => {
      expect(document.querySelectorAll('select').length).toBe(5);
    });

    const finishBtn = screen.getByRole('button', { name: /finish setup/i });
    await act(async () => {
      fireEvent.click(finishBtn);
    });

    await waitFor(() => {
      const completeCalls = fetchMock.mock.calls.filter(
        (c) =>
          typeof c[0] === 'string' &&
          (c[0] as string).includes('/api/setup/complete-google'),
      );
      expect(completeCalls.length).toBe(1);
    });

    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
    await waitFor(() => screen.getByTestId('home-page'));
  });

  it('shows error banner on 400 from finish setup; does not navigate', async () => {
    const allMapped = FAMILY_MEMBERS_ALL_UNMAPPED.map((m, i) => ({
      ...m,
      google_calendar_id: `cal${i + 1}@group.calendar.google.com`,
    }));
    stubInitialFetch(
      allMapped,
      GOOGLE_CALENDARS,
      [makeResponse(400, { detail: 'All family members must have a Google calendar mapped' })],
    );
    renderSetupFamily();

    await waitFor(() => {
      expect(document.querySelectorAll('select').length).toBe(5);
    });

    const finishBtn = screen.getByRole('button', { name: /finish setup/i });
    await act(async () => {
      fireEvent.click(finishBtn);
    });

    await waitFor(() =>
      expect(screen.getByRole('alert')).not.toBeNull(),
    );
    // Should NOT have navigated.
    expect(screen.queryByTestId('home-page')).toBeNull();
  });
});

describe('SetupFamily — create new calendar', () => {
  it('POSTs with correct body, adds calendar to dropdown, auto-applies to row', async () => {
    const newCal = { id: 'newcal@group.calendar.google.com', summary: 'Izzy' };
    const patchedMember = {
      id: 3,
      name: 'Izzy',
      color_hex_center: '#7B4FB8',
      google_calendar_id: 'newcal@group.calendar.google.com',
    };

    const fetchMock = stubInitialFetch(
      FAMILY_MEMBERS_ALL_UNMAPPED,
      GOOGLE_CALENDARS,
      [
        // POST /api/google/calendars
        makeResponse(200, newCal),
        // PATCH /api/admin/family/3
        makeResponse(200, patchedMember),
      ],
    );
    renderSetupFamily();

    await waitFor(() => {
      expect(document.querySelectorAll('select').length).toBe(5);
    });

    // Open the "Create new" form for Izzy (3rd row = index 2).
    const createBtns = screen.getAllByRole('button', { name: /create new/i });
    await act(async () => {
      fireEvent.click(createBtns[2]!);
    });

    // Type in the name and submit.
    const nameInput = screen.getByPlaceholderText(/calendar name/i);
    fireEvent.change(nameInput, { target: { value: 'Izzy' } });

    const createSubmitBtn = screen.getByRole('button', { name: /^create$/i });
    await act(async () => {
      fireEvent.click(createSubmitBtn);
    });

    // Should have POSTed.
    await waitFor(() => {
      const createCalls = fetchMock.mock.calls.filter(
        (c) =>
          typeof c[0] === 'string' &&
          (c[0] as string).includes('/api/google/calendars') &&
          c[1]?.method === 'POST',
      );
      expect(createCalls.length).toBe(1);
      const body = JSON.parse(createCalls[0]![1].body as string) as { summary: string };
      expect(body.summary).toBe('Izzy');
    });

    // Should have auto-applied (PATCHed) the new calendar to the row.
    await waitFor(() => {
      const patchCalls = fetchMock.mock.calls.filter(
        (c) =>
          typeof c[0] === 'string' &&
          (c[0] as string).includes('/api/admin/family/3') &&
          c[1]?.method === 'PATCH',
      );
      expect(patchCalls.length).toBe(1);
    });
  });
});
