import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { DesignSmoke } from './DesignSmoke';
import { formatETA, formatDuration } from '../lib/eta';


function renderSmoke() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DesignSmoke />
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe('DesignSmoke route', () => {
  it('renders the HearthWordmark — contains "hearth" text', () => {
    renderSmoke();
    // There are multiple "hearth" text instances (header + wordmark section)
    const hearthTexts = screen.getAllByText('hearth');
    expect(hearthTexts.length).toBeGreaterThanOrEqual(1);
  });

  it('renders all 5 family member names', () => {
    renderSmoke();
    expect(screen.getAllByText('Bryant').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Danielle').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Izzy').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Ellie').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Family').length).toBeGreaterThanOrEqual(1);
  });

  it('renders 12 HBtn elements (4 kinds × 3 sizes)', () => {
    renderSmoke();
    // Buttons include: 12 grid buttons + 4 disabled variants + theme toggle
    const buttons = screen.getAllByRole('button');
    // At minimum 12 from the kind×size grid
    expect(buttons.length).toBeGreaterThanOrEqual(12);
  });

  it('renders each button kind', () => {
    renderSmoke();
    // Each kind appears in 3 sizes + disabled = 4 instances each
    const primaryBtns = screen.getAllByText(/^primary/);
    expect(primaryBtns.length).toBeGreaterThanOrEqual(3);

    const ghostBtns = screen.getAllByText(/^ghost/);
    expect(ghostBtns.length).toBeGreaterThanOrEqual(3);

    const defaultBtns = screen.getAllByText(/^default/);
    expect(defaultBtns.length).toBeGreaterThanOrEqual(3);

    const dangerBtns = screen.getAllByText(/^danger/);
    expect(dangerBtns.length).toBeGreaterThanOrEqual(3);
  });

  it('renders ConfidenceBadge glyphs', () => {
    renderSmoke();
    // auto status shows ✓
    expect(screen.getAllByText('✓').length).toBeGreaterThanOrEqual(1);
    // review status shows !
    expect(screen.getAllByText('!').length).toBeGreaterThanOrEqual(1);
    // skipped status shows –
    expect(screen.getAllByText('–').length).toBeGreaterThanOrEqual(1);
  });

  it('renders "PhoneShell" label in the shells section', () => {
    renderSmoke();
    expect(screen.getByText('PhoneShell')).not.toBeNull();
  });

  it('renders "DesktopShell" label in the shells section', () => {
    renderSmoke();
    expect(screen.getByText('DesktopShell')).not.toBeNull();
  });

  it('renders HearthMark svgs (one per size in marks section)', () => {
    const { container } = renderSmoke();
    const svgs = container.querySelectorAll('svg');
    // 5 sizes + 4 wordmarks = at least 9 svgs
    expect(svgs.length).toBeGreaterThanOrEqual(5);
  });

  it('renders section titles', () => {
    renderSmoke();
    expect(screen.getByText('HearthMark')).not.toBeNull();
    expect(screen.getByText('HearthWordmark')).not.toBeNull();
    expect(screen.getByText('HBtn')).not.toBeNull();
    expect(screen.getByText('FamilyChip')).not.toBeNull();
    expect(screen.getByText('ConfidenceBadge')).not.toBeNull();
    expect(screen.getByText('Input')).not.toBeNull();
  });

  it('renders Input section with variant labels', () => {
    renderSmoke();
    expect(screen.getByText('Default (text)')).not.toBeNull();
    expect(screen.getByText('With value')).not.toBeNull();
    expect(screen.getByText('Disabled')).not.toBeNull();
    expect(screen.getByText('With error')).not.toBeNull();
    expect(screen.getByText(/Mono/)).not.toBeNull();
    expect(screen.getByText('Password')).not.toBeNull();
    expect(screen.getByText('Email')).not.toBeNull();
  });

  it('Input section shows error text for the error variant', () => {
    renderSmoke();
    expect(screen.getByText('This field is required')).not.toBeNull();
  });

  it('renders a theme cycle button', () => {
    renderSmoke();
    const toggleBtn = screen.getByText(/— click to cycle/);
    expect(toggleBtn).not.toBeNull();
  });
});

describe('DesignSmoke — Phase 3.5 primitives section', () => {
  it('renders the Phase 3.5 primitives section', () => {
    const { container } = renderSmoke();
    const section = container.querySelector('[data-testid="phase35-section"]');
    expect(section).not.toBeNull();
  });

  it('renders Spinner elements at 3 sizes', () => {
    renderSmoke();
    expect(screen.getByRole('img', { name: 'Spinner 12px' })).not.toBeNull();
    expect(screen.getByRole('img', { name: 'Spinner 18px' })).not.toBeNull();
    expect(screen.getByRole('img', { name: 'Spinner 24px' })).not.toBeNull();
  });

  it('renders ThumbTile variants', () => {
    renderSmoke();
    expect(screen.getByText('default')).not.toBeNull();
    expect(screen.getByText('accent dot')).not.toBeNull();
    expect(screen.getByText('with badge')).not.toBeNull();
  });

  it('renders SectionRule with 3 status labels', () => {
    renderSmoke();
    expect(screen.getByText('In flight')).not.toBeNull();
    expect(screen.getByText('Done')).not.toBeNull();
    expect(screen.getByText("Couldn't read")).not.toBeNull();
  });

  it('renders formatETA examples', () => {
    renderSmoke();
    // null → '—'
    expect(screen.getByText('—')).not.toBeNull();
    // 45 → '~45 sec'
    expect(screen.getByText(formatETA(45))).not.toBeNull();
    // 184 → '~3 min 4 sec'
    expect(screen.getByText(formatETA(184))).not.toBeNull();
  });

  it('renders formatDuration examples', () => {
    renderSmoke();
    expect(screen.getByText(formatDuration(64))).not.toBeNull();
    expect(screen.getByText(formatDuration(120))).not.toBeNull();
  });
});
