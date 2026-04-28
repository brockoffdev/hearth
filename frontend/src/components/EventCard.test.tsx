import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EventCard } from './EventCard';
import type { Event } from '../lib/events';

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 42,
    upload_id: 7,
    family_member_id: null,
    family_member_name: 'Bryant',
    family_member_color_hex: '#2E5BA8',
    title: 'Soccer practice',
    start_dt: '2026-04-27T15:00:00Z',
    end_dt: '2026-04-27T16:00:00Z',
    all_day: false,
    location: 'Field A',
    notes: null,
    confidence: 0.92,
    status: 'pending_review',
    google_event_id: null,
    cell_crop_path: 'crops/42.jpg',
    has_cell_crop: true,
    raw_vlm_json: null,
    created_at: '2026-04-27T10:00:00Z',
    updated_at: '2026-04-27T10:00:00Z',
    published_at: null,
    ...overrides,
  };
}

describe('EventCard', () => {
  it('renders the event title', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.getByText('Soccer practice')).toBeInTheDocument();
  });

  it('renders the family member name', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.getByText('Bryant')).toBeInTheDocument();
  });

  it('renders the confidence badge', () => {
    render(<EventCard event={makeEvent({ confidence: 0.92 })} />);
    expect(screen.getByText('92%')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<EventCard event={makeEvent()} onClick={handleClick} />);

    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('does not render as button when onClick is not provided', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('hides cell crop when showCellCrop is false', () => {
    render(<EventCard event={makeEvent()} showCellCrop={false} />);
    expect(screen.queryByRole('img', { name: /cell crop/i })).toBeNull();
  });

  it('shows cell crop img when showCellCrop and has_cell_crop are true', () => {
    render(<EventCard event={makeEvent({ has_cell_crop: true })} showCellCrop />);
    const img = screen.getByRole('img', { name: /cell crop/i });
    expect(img.getAttribute('src')).toBe('/api/events/42/cell-crop');
  });

  it('shows placeholder when showCellCrop is true but has_cell_crop is false', () => {
    render(<EventCard event={makeEvent({ has_cell_crop: false })} showCellCrop />);
    expect(screen.queryByRole('img', { name: /cell crop/i })).toBeNull();
  });

  it('renders "all day" in the date subtitle when all_day is true', () => {
    render(<EventCard event={makeEvent({ all_day: true })} />);
    expect(screen.getByText(/all day/i)).toBeInTheDocument();
  });

  it('renders a time string when all_day is false', () => {
    render(<EventCard event={makeEvent({ all_day: false })} />);
    // Not "all day" — should contain a colon from the formatted time
    const subtitle = screen.getByText(/·/);
    expect(subtitle.textContent).not.toMatch(/all day/i);
  });

  it.each([
    ['Izzy', '#7B4FB8', 'isabella'],
    ['Ellie', '#E17AA1', 'eliana'],
  ])(
    'maps backend display name %s to FamilyChip via color hex',
    (name, hex, expectedId) => {
      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      render(
        <EventCard
          event={makeEvent({ family_member_name: name, family_member_color_hex: hex })}
        />,
      );
      // FamilyChip's dot carries data-who attribute matching the resolved id.
      // No console.warn fallback should fire for known members.
      expect(consoleWarn).not.toHaveBeenCalled();
      // The dot is queryable via its data-who attribute.
      const dot = document.querySelector(`[data-who="${expectedId}"]`);
      expect(dot).toBeTruthy();
      consoleWarn.mockRestore();
    },
  );

  it('renders gracefully when family_member_name is null', () => {
    render(
      <EventCard
        event={makeEvent({ family_member_name: null, family_member_color_hex: null })}
      />,
    );
    expect(screen.getByText('Soccer practice')).toBeInTheDocument();
    expect(screen.queryByText('Bryant')).toBeNull();
  });

  it('invokes onClick on Enter keydown', () => {
    const handleClick = vi.fn();
    render(<EventCard event={makeEvent()} onClick={handleClick} />);

    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(handleClick).toHaveBeenCalledOnce();
  });
});
