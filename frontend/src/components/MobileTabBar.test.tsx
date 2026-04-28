import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { MobileTabBar, TABS } from './MobileTabBar';
import type { TabId } from './MobileTabBar';

function renderBar(
  active: TabId,
  badges?: Parameters<typeof MobileTabBar>[0]['badges'],
) {
  return render(
    <MemoryRouter>
      <MobileTabBar active={active} badges={badges} />
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

  it('renders a badge on the review tab when badges.review > 0', () => {
    renderBar('home', { review: 3 });
    const badge = screen.getByLabelText('3 pending');
    expect(badge).not.toBeNull();
    expect(badge.textContent).toBe('3');
  });

  it('does not render a badge when badges.review is 0', () => {
    renderBar('home', { review: 0 });
    expect(screen.queryByLabelText('0 pending')).toBeNull();
  });

  it('does not render a badge when badges prop is omitted', () => {
    renderBar('home');
    const badges = screen.queryAllByLabelText(/pending/);
    expect(badges).toHaveLength(0);
  });

  it('does not render a badge on review tab when badges.review is 0 (suppressed active case)', () => {
    renderBar('review', { review: 0 });
    expect(screen.queryByLabelText('0 pending')).toBeNull();
  });

  it('renders badge on non-active tabs when count > 0', () => {
    renderBar('home', { review: 5 });
    const badge = screen.getByLabelText('5 pending');
    expect(badge).not.toBeNull();
  });

  it('caps badge display at 99+ for counts over 99', () => {
    renderBar('home', { review: 150 });
    const badge = screen.getByLabelText('150 pending');
    expect(badge.textContent).toBe('99+');
  });

  it('can show badges on multiple tabs simultaneously', () => {
    renderBar('home', { review: 2, uploads: 4 });
    expect(screen.getByLabelText('2 pending')).not.toBeNull();
    expect(screen.getByLabelText('4 pending')).not.toBeNull();
  });
});
