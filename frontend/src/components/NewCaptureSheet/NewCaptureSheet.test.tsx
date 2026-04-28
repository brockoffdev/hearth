import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NewCaptureSheet } from './NewCaptureSheet';

// ---------------------------------------------------------------------------
// navigate mock
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSheet(onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <NewCaptureSheet onClose={onClose} />
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockNavigate.mockReset();
});

describe('NewCaptureSheet', () => {
  it('renders title, subtitle, two options, tip, and cancel link', () => {
    renderSheet();

    expect(screen.getByText('New capture')).not.toBeNull();
    expect(screen.getByText(/what does the calendar look like/i)).not.toBeNull();
    expect(screen.getByText('Take a photo')).not.toBeNull();
    expect(screen.getByText('Choose from library')).not.toBeNull();
    expect(screen.getByText(/hearth reads even messy handwriting/i)).not.toBeNull();
    expect(screen.getByRole('button', { name: /cancel/i })).not.toBeNull();
  });

  it('has role="dialog", aria-modal="true", and aria-labelledby pointing to the title', () => {
    renderSheet();

    const dialog = screen.getByRole('dialog');
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(labelId).not.toBeNull();
    const labelEl = document.getElementById(labelId!);
    expect(labelEl).not.toBeNull();
    expect(labelEl!.textContent).toContain('New capture');
  });

  it('clicking the camera option calls navigate(/upload?source=camera) and onClose', () => {
    const onClose = vi.fn();
    renderSheet(onClose);

    fireEvent.click(screen.getByText('Take a photo'));

    expect(mockNavigate).toHaveBeenCalledWith('/upload?source=camera');
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('clicking the library option calls navigate(/upload?source=library) and onClose', () => {
    const onClose = vi.fn();
    renderSheet(onClose);

    fireEvent.click(screen.getByText('Choose from library'));

    expect(mockNavigate).toHaveBeenCalledWith('/upload?source=library');
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('clicking backdrop calls onClose', () => {
    const onClose = vi.fn();
    renderSheet(onClose);

    const backdrop = document.querySelector('[role="presentation"]') as HTMLElement;
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it('clicking Cancel calls onClose', () => {
    const onClose = vi.fn();
    renderSheet(onClose);

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
