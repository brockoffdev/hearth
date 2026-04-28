import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { MobileTabBar, TABS } from './MobileTabBar';

function renderBar(active: Parameters<typeof MobileTabBar>[0]['active']) {
  return render(
    <MemoryRouter>
      <MobileTabBar active={active} />
    </MemoryRouter>,
  );
}

describe('MobileTabBar', () => {
  it('renders all 4 tab labels', () => {
    renderBar('home');
    expect(screen.getByText('Home')).not.toBeNull();
    expect(screen.getByText('Uploads')).not.toBeNull();
    expect(screen.getByText('Review')).not.toBeNull();
    expect(screen.getByText('Calendar')).not.toBeNull();
  });

  it('marks the active tab with data-active="true" and aria-current="page"', () => {
    const { container } = renderBar('uploads');
    const uploadsLink = screen.getByText('Uploads').closest('a');
    expect(uploadsLink?.getAttribute('data-active')).toBe('true');
    expect(uploadsLink?.getAttribute('aria-current')).toBe('page');

    // other tabs must NOT have data-active="true"
    const homeLink = screen.getByText('Home').closest('a');
    expect(homeLink?.getAttribute('data-active')).toBe('false');
    expect(homeLink?.getAttribute('aria-current')).toBeNull();

    // suppress unused-var lint for container
    void container;
  });

  it('each tab is a <Link> with the correct href', () => {
    renderBar('home');
    expect(screen.getByText('Home').closest('a')?.getAttribute('href')).toBe('/');
    expect(screen.getByText('Uploads').closest('a')?.getAttribute('href')).toBe('/uploads');
    expect(screen.getByText('Review').closest('a')?.getAttribute('href')).toBe('/review');
    expect(screen.getByText('Calendar').closest('a')?.getAttribute('href')).toBe('/calendar');
  });

  it('active tab SVG path has strokeWidth "2"; inactive has "1.5"', () => {
    const { container } = renderBar('review');

    // Find the nav links in order matching TABS
    const links = container.querySelectorAll('nav a');
    expect(links.length).toBe(4);

    links.forEach((link) => {
      const isActive = link.getAttribute('data-active') === 'true';
      const path = link.querySelector('path');
      const strokeWidth = path?.getAttribute('stroke-width');
      if (isActive) {
        expect(strokeWidth).toBe('2');
      } else {
        expect(strokeWidth).toBe('1.5');
      }
    });
  });

  it('renders a nav with aria-label="Primary"', () => {
    renderBar('calendar');
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    expect(nav).not.toBeNull();
  });

  it('exports TABS with 4 entries covering all tab ids', () => {
    expect(TABS.length).toBe(4);
    const ids = TABS.map((t) => t.id);
    expect(ids).toContain('home');
    expect(ids).toContain('uploads');
    expect(ids).toContain('review');
    expect(ids).toContain('calendar');
  });

  it('accepts an optional className and passes it to the nav', () => {
    const { container } = render(
      <MemoryRouter>
        <MobileTabBar active="home" className="custom-bar" />
      </MemoryRouter>,
    );
    const nav = container.querySelector('nav');
    expect(nav?.classList.contains('custom-bar')).toBe(true);
  });
});
