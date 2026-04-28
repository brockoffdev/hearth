import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { AuthProvider } from '../auth/AuthProvider';
import { Upload } from './Upload';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeUploadResponse(id = 7) {
  return makeResponse(201, {
    id,
    status: 'queued',
    image_path: `uploads/${id}.jpg`,
    uploaded_at: '2026-04-27T10:00:00Z',
    url: `/api/uploads/${id}/photo`,
  });
}

function renderUpload() {
  return render(
    <MemoryRouter initialEntries={['/upload']}>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/upload" element={<Upload />} />
            <Route
              path="/"
              element={<div data-testid="home-page">Home</div>}
            />
            <Route
              path="/uploads/:id"
              element={<div data-testid="processing-page">Processing</div>}
            />
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
  // AuthProvider calls /api/auth/me on mount — stub it to return 401 (anonymous)
  // so we don't need a real session for upload route tests.
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(makeResponse(401, { detail: 'Unauthorized' })),
  );

  // jsdom doesn't implement URL.createObjectURL/revokeObjectURL.
  // Patch them as configurable properties on the real URL constructor so
  // they survive vi.unstubAllGlobals() but get re-applied each test, and so
  // the unmount cleanup in @testing-library/react's afterEach can call them.
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:fake-url'),
    configurable: true,
  });
  Object.defineProperty(URL, 'revokeObjectURL', {
    value: vi.fn(),
    configurable: true,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Upload route — idle state', () => {
  it('renders the shutter button and gallery option on mount', async () => {
    renderUpload();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );
    expect(screen.getByText(/pick from gallery/i)).not.toBeNull();
    expect(screen.getByText(/hearth/i)).not.toBeNull();
  });

  it('shows the orientation hint in idle state', async () => {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );
    expect(screen.getByText(/rotate to landscape/i)).not.toBeNull();
  });
});

describe('Upload route — file input triggers', () => {
  it('clicking the shutter calls click() on the camera input', async () => {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );

    // Grab the hidden camera input and spy on its click
    const cameraInput = document.querySelector(
      'input[capture="environment"]',
    ) as HTMLInputElement;
    expect(cameraInput).not.toBeNull();
    const clickSpy = vi.spyOn(cameraInput, 'click');

    fireEvent.click(screen.getByRole('button', { name: /take a photo/i }));
    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it('clicking "Pick from gallery" calls click() on the gallery input', async () => {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByText(/pick from gallery/i)).not.toBeNull(),
    );

    // The gallery input is the one WITHOUT capture
    const inputs = document.querySelectorAll('input[type="file"]');
    const galleryInput = Array.from(inputs).find(
      (el) => !(el as HTMLInputElement).hasAttribute('capture'),
    ) as HTMLInputElement;
    expect(galleryInput).not.toBeNull();
    const clickSpy = vi.spyOn(galleryInput, 'click');

    fireEvent.click(screen.getByText(/pick from gallery/i));
    expect(clickSpy).toHaveBeenCalledOnce();
  });
});

describe('Upload route — file validation', () => {
  /** Fire onChange on a file input directly, bypassing userEvent's accept filter. */
  function fireFileChange(input: HTMLInputElement, file: File) {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: { 0: file, length: 1, item: () => file },
    });
    fireEvent.change(input);
  }

  it('picking a non-image file shows an error banner and stays idle', async () => {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );

    const input = document.querySelector(
      'input[capture="environment"]',
    ) as HTMLInputElement;
    const nonImageFile = new File(['data'], 'doc.pdf', { type: 'application/pdf' });
    fireFileChange(input, nonImageFile);

    await waitFor(() =>
      expect(screen.getByRole('alert')).not.toBeNull(),
    );
    expect(screen.getByText(/please pick an image/i)).not.toBeNull();
    // In error state the "Try again" button is shown; clicking it returns to idle
    expect(screen.getByRole('button', { name: /try again/i })).not.toBeNull();
  });

  it('picking a file > 25 MB shows a size error banner', async () => {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );

    const input = document.querySelector(
      'input[capture="environment"]',
    ) as HTMLInputElement;
    const bigFile = new File(
      [new Uint8Array(26 * 1024 * 1024)],
      'big.jpg',
      { type: 'image/jpeg' },
    );
    fireFileChange(input, bigFile);

    await waitFor(() =>
      expect(screen.getByRole('alert')).not.toBeNull(),
    );
    expect(screen.getByText(/≤25MB/i)).not.toBeNull();
  });
});

describe('Upload route — preview state', () => {
  function fireFileChange(input: HTMLInputElement, file: File) {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: { 0: file, length: 1, item: () => file },
    });
    fireEvent.change(input);
  }

  async function pickValidFile() {
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );
    const input = document.querySelector(
      'input[capture="environment"]',
    ) as HTMLInputElement;
    const file = new File(['img-data'], 'photo.jpg', { type: 'image/jpeg' });
    fireFileChange(input, file);
    return file;
  }

  it('transitions to preview when a valid image is picked', async () => {
    await pickValidFile();

    await waitFor(() =>
      expect(screen.getByAltText(/photo preview/i)).not.toBeNull(),
    );
    expect(screen.getByRole('button', { name: /use this/i })).not.toBeNull();
    expect(screen.getByRole('button', { name: /retake/i })).not.toBeNull();
  });

  it('clicking Retake returns to idle state', async () => {
    await pickValidFile();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /retake/i })).not.toBeNull(),
    );
    fireEvent.click(screen.getByRole('button', { name: /retake/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );
    expect(screen.queryByAltText(/photo preview/i)).toBeNull();
  });
});

describe('Upload route — submit flow', () => {
  function fireFileChange(input: HTMLInputElement, file: File) {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: { 0: file, length: 1, item: () => file },
    });
    fireEvent.change(input);
  }

  async function getToPreview(fetchMock: ReturnType<typeof vi.fn>) {
    vi.stubGlobal('fetch', fetchMock);
    renderUpload();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /take a photo/i })).not.toBeNull(),
    );
    const input = document.querySelector(
      'input[capture="environment"]',
    ) as HTMLInputElement;
    const file = new File(['img-data'], 'photo.jpg', { type: 'image/jpeg' });
    fireFileChange(input, file);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /use this/i })).not.toBeNull(),
    );
  }

  it('clicking "Use this" posts to /api/uploads and navigates to /uploads/{id} on success', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockResolvedValueOnce(makeUploadResponse(7)); // POST /api/uploads

    await getToPreview(fetchMock);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /use this/i }));
    });

    await waitFor(() =>
      expect(screen.getByTestId('processing-page')).not.toBeNull(),
    );

    const uploadCalls = fetchMock.mock.calls.filter(
      (c) => typeof c[0] === 'string' && (c[0] as string).includes('/api/uploads'),
    );
    expect(uploadCalls.length).toBe(1);
    const [, init] = uploadCalls[0] as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
  });

  it('4xx response shows error banner and does NOT navigate', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockResolvedValueOnce(makeResponse(422, { detail: 'Validation error' }));

    await getToPreview(fetchMock);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /use this/i }));
    });

    await waitFor(() =>
      expect(screen.getByRole('alert')).not.toBeNull(),
    );
    expect(screen.getByText(/validation error/i)).not.toBeNull();
    expect(screen.queryByTestId('processing-page')).toBeNull();
  });

  it('413 response shows the "File too large" detail from the server', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(401, { detail: 'Unauthorized' })) // /me
      .mockResolvedValueOnce(makeResponse(413, { detail: 'File too large' }));

    await getToPreview(fetchMock);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /use this/i }));
    });

    await waitFor(() =>
      expect(screen.getByRole('alert')).not.toBeNull(),
    );
    expect(screen.getByText(/file too large/i)).not.toBeNull();
    expect(screen.queryByTestId('processing-page')).toBeNull();
  });
});
