import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { ReviewPlaceholder } from './ReviewPlaceholder';

function renderReview() {
  return render(
    <MemoryRouter>
      <ReviewPlaceholder />
    </MemoryRouter>,
  );
}

describe('ReviewPlaceholder', () => {
  it('renders the Review heading', () => {
    renderReview();
    expect(screen.getByRole('heading', { name: 'Review' })).not.toBeNull();
  });

  it('renders the coming-soon subtitle', () => {
    renderReview();
    expect(screen.getByText(/coming in phase 6/i)).not.toBeNull();
  });

  it('renders the tab bar with "review" tab active', () => {
    const { container } = renderReview();
    const nav = container.querySelector('nav[aria-label="Primary"]');
    expect(nav).not.toBeNull();
    // There are two "Review" texts: the h1 and the tab label — query the anchor
    const reviewLink = container.querySelector('a[href="/review"]');
    expect(reviewLink?.getAttribute('data-active')).toBe('true');
  });

  it('tab bar Home link navigates to /', () => {
    renderReview();
    const homeLink = screen.getByText('Home').closest('a');
    expect(homeLink?.getAttribute('href')).toBe('/');
  });
});
