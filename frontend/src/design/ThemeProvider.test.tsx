import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ThemeProvider, useTheme } from './ThemeProvider';

// Helper component to expose the theme context
function ThemeConsumer() {
  const { theme, setTheme, cycleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={() => setTheme('dark')}>Set Dark</button>
      <button onClick={() => setTheme('sepia')}>Set Sepia</button>
      <button onClick={() => setTheme('light')}>Set Light</button>
      <button onClick={() => cycleTheme()}>Cycle</button>
    </div>
  );
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    document.documentElement.dataset['theme'] = '';
    window.localStorage.clear();
  });

  it('starts with light theme by default', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('light');
    expect(document.documentElement.dataset['theme']).toBe('light');
  });

  it('setTheme updates theme state and data-theme attribute', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    act(() => {
      screen.getByText('Set Dark').click();
    });
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(document.documentElement.dataset['theme']).toBe('dark');
  });

  it('persists theme to localStorage', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    act(() => {
      screen.getByText('Set Dark').click();
    });
    expect(window.localStorage.getItem('hearth.theme')).toBe('dark');
  });

  it('restores theme from localStorage on mount', () => {
    window.localStorage.setItem('hearth.theme', 'dark');
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(document.documentElement.dataset['theme']).toBe('dark');
  });

  it('falls back to light if localStorage has invalid value', () => {
    window.localStorage.setItem('hearth.theme', 'neon-pink');
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('light');
  });

  it('cycleTheme goes dark -> sepia', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    act(() => {
      screen.getByText('Set Dark').click();
    });
    act(() => {
      screen.getByText('Cycle').click();
    });
    expect(screen.getByTestId('theme').textContent).toBe('sepia');
  });

  it('cycleTheme goes sepia -> light', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    act(() => {
      screen.getByText('Set Sepia').click();
    });
    act(() => {
      screen.getByText('Cycle').click();
    });
    expect(screen.getByTestId('theme').textContent).toBe('light');
  });

  it('cycleTheme goes light -> dark', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    act(() => {
      screen.getByText('Cycle').click();
    });
    expect(screen.getByTestId('theme').textContent).toBe('dark');
  });

  it('throws when useTheme is used outside provider', () => {
    // Suppress the error boundary output in test console
    const consoleError = console.error;
    console.error = () => {};
    expect(() => {
      render(<ThemeConsumer />);
    }).toThrow('useTheme must be used within a ThemeProvider');
    console.error = consoleError;
  });

  it('respects data-theme attribute pre-set before React mounts (inline-script path)', () => {
    // Simulate what the module-evaluation IIFE in ThemeProvider.tsx does at first
    // page load: set data-theme on <html> synchronously before React hydrates,
    // so the persisted theme is in effect on the very first paint.
    document.documentElement.dataset['theme'] = 'dark';
    window.localStorage.setItem('hearth.theme', 'dark');
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(document.documentElement.dataset['theme']).toBe('dark');
  });
});
