import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NewCaptureSheetProvider, useNewCaptureSheet } from './NewCaptureSheetProvider';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function TestConsumer() {
  const { isOpen, open, close } = useNewCaptureSheet();
  return (
    <div>
      <span data-testid="state">{isOpen ? 'open' : 'closed'}</span>
      <button type="button" onClick={open}>Open</button>
      <button type="button" onClick={close}>Close</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <MemoryRouter>
      <NewCaptureSheetProvider>
        <TestConsumer />
      </NewCaptureSheetProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  document.body.style.overflow = '';
});

afterEach(() => {
  document.body.style.overflow = '';
});

describe('NewCaptureSheetProvider', () => {
  it('useNewCaptureSheet() outside provider throws', () => {
    // Suppress React error boundary noise in test output
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => {
      render(
        <MemoryRouter>
          <TestConsumer />
        </MemoryRouter>,
      );
    }).toThrow(/NewCaptureSheetProvider/);
    consoleSpy.mockRestore();
  });

  it('initial state: isOpen is false', () => {
    renderWithProvider();
    expect(screen.getByTestId('state').textContent).toBe('closed');
  });

  it('open() flips isOpen to true; close() flips back to false', () => {
    renderWithProvider();

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Open' })); });
    expect(screen.getByTestId('state').textContent).toBe('open');

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Close' })); });
    expect(screen.getByTestId('state').textContent).toBe('closed');
  });

  it('body overflow becomes "hidden" when open; restored when closed', () => {
    renderWithProvider();

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Open' })); });
    expect(document.body.style.overflow).toBe('hidden');

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Close' })); });
    expect(document.body.style.overflow).toBe('');
  });

  it('Escape key closes the sheet when open', () => {
    renderWithProvider();

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Open' })); });
    expect(screen.getByTestId('state').textContent).toBe('open');

    act(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    });
    expect(screen.getByTestId('state').textContent).toBe('closed');
  });

  it('Escape key does nothing when sheet is closed', () => {
    renderWithProvider();
    // State is already closed; fire Escape, should remain closed
    act(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    });
    expect(screen.getByTestId('state').textContent).toBe('closed');
  });

  it('sheet renders via portal (role="dialog") when open', () => {
    renderWithProvider();

    expect(screen.queryByRole('dialog')).toBeNull();

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Open' })); });
    expect(screen.getByRole('dialog')).not.toBeNull();

    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Close' })); });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
