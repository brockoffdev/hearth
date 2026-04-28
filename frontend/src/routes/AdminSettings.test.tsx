import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { AdminSettings } from './AdminSettings';
import type { AdminSettings as AdminSettingsData } from '../lib/adminSettings';
import * as adminSettingsLib from '../lib/adminSettings';

// ---------------------------------------------------------------------------
// Mock the adminSettings lib
// ---------------------------------------------------------------------------

vi.mock('../lib/adminSettings', () => ({
  getAdminSettings: vi.fn(),
  patchAdminSettings: vi.fn(),
}));

const mockedGetAdminSettings = vi.mocked(adminSettingsLib.getAdminSettings);
const mockedPatchAdminSettings = vi.mocked(adminSettingsLib.patchAdminSettings);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SETTINGS: AdminSettingsData = {
  confidence_threshold: 0.85,
  vision_provider: 'ollama',
  vision_model: 'qwen2.5-vl:7b',
  ollama_endpoint: 'http://localhost:11434',
  gemini_api_key_masked: '',
  anthropic_api_key_masked: '',
  gemini_api_key_set: false,
  anthropic_api_key_set: false,
  few_shot_correction_window: 10,
  use_real_pipeline: false,
  rocm_available: false,
};

const ADMIN_USER = {
  id: 1,
  username: 'testuser',
  role: 'admin' as const,
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

const REGULAR_USER = {
  id: 1,
  username: 'testuser',
  role: 'user' as const,
  must_change_password: false,
  must_complete_google_setup: false,
  created_at: '2026-01-01T00:00:00Z',
};

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function renderAsAdmin() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(200, ADMIN_USER)),
  );
  return render(
    <MemoryRouter initialEntries={['/admin/settings']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin/settings" element={<AdminSettings />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

function renderAsRegular() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(200, REGULAR_USER)),
  );
  return render(
    <MemoryRouter initialEntries={['/admin/settings']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/admin/settings" element={<AdminSettings />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AdminSettings', () => {
  beforeEach(() => {
    mockedGetAdminSettings.mockResolvedValue(MOCK_SETTINGS);
  });

  it('test_admin_settings_renders_current_values', async () => {
    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByDisplayValue('qwen2.5-vl:7b')).not.toBeNull();
      expect(screen.getByDisplayValue('http://localhost:11434')).not.toBeNull();
      expect(screen.getByText('85%')).not.toBeNull();
      expect(screen.getByText('10')).not.toBeNull();
    });
  });

  it('test_admin_settings_403_for_non_admin', async () => {
    mockedGetAdminSettings.mockResolvedValue(MOCK_SETTINGS);
    renderAsRegular();

    await waitFor(() => {
      expect(screen.getByText('403')).not.toBeNull();
      expect(screen.getByText(/admin access required/i)).not.toBeNull();
    });
  });

  it('test_admin_settings_changing_provider_shows_correct_field', async () => {
    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByDisplayValue('http://localhost:11434')).not.toBeNull();
    });

    // Switch to Gemini
    const geminiRadio = screen.getByRole('radio', { name: 'Gemini' });
    fireEvent.click(geminiRadio);

    await waitFor(() => {
      expect(screen.getByLabelText(/gemini api key/i)).not.toBeNull();
      expect(screen.queryByLabelText(/ollama endpoint/i)).toBeNull();
    });
  });

  it('test_admin_settings_save_calls_patch_with_diff', async () => {
    const updated = { ...MOCK_SETTINGS, confidence_threshold: 0.90 };
    mockedPatchAdminSettings.mockResolvedValue(updated);

    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByRole('slider', { name: /confidence threshold/i })).not.toBeNull();
    });

    const slider = screen.getByRole('slider', { name: /confidence threshold/i });
    fireEvent.change(slider, { target: { value: '90' } });

    await waitFor(() => {
      expect(screen.getByText('90%')).not.toBeNull();
    });

    const saveBtn = screen.getByRole('button', { name: /^save$/i });
    await act(async () => {
      fireEvent.click(saveBtn);
      await Promise.resolve();
    });

    expect(mockedPatchAdminSettings).toHaveBeenCalledWith(
      expect.objectContaining({ confidence_threshold: 0.90 }),
    );
  });

  it('test_admin_settings_save_disabled_when_no_changes', async () => {
    renderAsAdmin();

    await waitFor(() => {
      const saveBtn = screen.getByRole('button', { name: /^save$/i }) as HTMLButtonElement;
      expect(saveBtn.disabled).toBe(true);
    });
  });

  it('test_admin_settings_clears_api_key_via_clear_button', async () => {
    // Load with Gemini key set, switch to Gemini provider via UI, then clear key
    const settingsWithKey: AdminSettingsData = {
      ...MOCK_SETTINGS,
      gemini_api_key_set: true,
      gemini_api_key_masked: '•••• 1234',
    };
    mockedGetAdminSettings.mockResolvedValue(settingsWithKey);
    const updated = { ...settingsWithKey, gemini_api_key_set: false, gemini_api_key_masked: '' };
    mockedPatchAdminSettings.mockResolvedValue(updated);

    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByDisplayValue('qwen2.5-vl:7b')).not.toBeNull();
    });

    // Switch to Gemini — this reveals the key field with Clear key button
    fireEvent.click(screen.getByRole('radio', { name: 'Gemini' }));

    await waitFor(() => {
      expect(document.getElementById('gemini-api-key')).not.toBeNull();
    });

    const clearBtn = screen.getByRole('button', { name: /clear gemini api key/i });
    fireEvent.click(clearBtn);

    const saveBtn = screen.getByRole('button', { name: /^save$/i }) as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(saveBtn);
      await Promise.resolve();
    });

    expect(mockedPatchAdminSettings).toHaveBeenCalledWith(
      expect.objectContaining({ gemini_api_key: '' }),
    );
  });

  it('test_admin_settings_renders_masked_key_when_set', async () => {
    // Load with Anthropic key set; switch to Anthropic provider via UI; check masked placeholder
    const settingsWithKey: AdminSettingsData = {
      ...MOCK_SETTINGS,
      anthropic_api_key_set: true,
      anthropic_api_key_masked: '•••• abcd',
    };
    mockedGetAdminSettings.mockResolvedValue(settingsWithKey);

    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByDisplayValue('qwen2.5-vl:7b')).not.toBeNull();
    });

    // Switch to Anthropic — reveals the key field
    fireEvent.click(screen.getByRole('radio', { name: 'Anthropic' }));

    await waitFor(() => {
      const apiKeyInput = document.getElementById('anthropic-api-key') as HTMLInputElement | null;
      expect(apiKeyInput).not.toBeNull();
      expect(apiKeyInput?.placeholder).toContain('•••• abcd');
    });
  });

  it('test_admin_settings_confidence_slider_updates_displayed_pct', async () => {
    renderAsAdmin();

    await waitFor(() => {
      expect(screen.getByText('85%')).not.toBeNull();
    });

    const slider = screen.getByRole('slider', { name: /confidence threshold/i });
    fireEvent.change(slider, { target: { value: '70' } });

    await waitFor(() => {
      expect(screen.getByText('70%')).not.toBeNull();
    });
  });
});
