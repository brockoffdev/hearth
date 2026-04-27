import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { ThemeProvider } from '../design/ThemeProvider';
import { DesignSmoke } from './DesignSmoke';


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
