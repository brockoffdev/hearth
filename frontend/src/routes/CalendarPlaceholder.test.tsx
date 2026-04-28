import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { CalendarPlaceholder } from './CalendarPlaceholder';

function renderCalendar() {
  return render(
    <MemoryRouter>
      <CalendarPlaceholder />
    </MemoryRouter>,
  );
}

describe('CalendarPlaceholder', () => {
  it('renders the Calendar heading', () => {
    renderCalendar();
    expect(screen.getByRole('heading', { name: 'Calendar' })).not.toBeNull();
  });

  it('renders the coming-soon subtitle', () => {
    renderCalendar();
    expect(screen.getByText(/coming in phase 8/i)).not.toBeNull();
  });

  it('renders the tab bar with "calendar" tab active', () => {
    const { container } = renderCalendar();
    const nav = container.querySelector('nav[aria-label="Primary"]');
    expect(nav).not.toBeNull();
    // There are two "Calendar" texts: the h1 and the tab label — query the anchor
    const calendarLink = container.querySelector('a[href="/calendar"]');
    expect(calendarLink?.getAttribute('data-active')).toBe('true');
  });

  it('tab bar Home link navigates to /', () => {
    renderCalendar();
    const homeLink = screen.getByText('Home').closest('a');
    expect(homeLink?.getAttribute('href')).toBe('/');
  });
});
