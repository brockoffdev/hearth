import { useState } from 'react';
import { useTheme } from '../design/ThemeProvider';
import { THEME_LABELS } from '../design/themeLabels';
import { cn } from '../lib/cn';
import { HearthMark } from '../components/HearthMark';
import { HearthWordmark } from '../components/HearthWordmark';
import { HBtn } from '../components/HBtn';
import { FamilyChip } from '../components/FamilyChip';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { PhoneShell } from '../components/PhoneShell';
import { DesktopShell } from '../components/DesktopShell';
import { Input } from '../components/Input';
import { WizardSteps } from '../components/WizardSteps';
import type { WizardStep } from '../components/WizardSteps';
import type { FamilyMemberId } from '../lib/family';
import { Spinner } from '../components/Spinner';
import { ThumbTile } from '../components/ThumbTile';
import { SectionRule } from '../components/SectionRule';
import { Chevron } from '../components/Chevron';
import { BackChevron } from '../components/BackChevron';
import { formatETA, formatDuration } from '../lib/eta';
import { useNewCaptureSheet } from '../components/NewCaptureSheet';
import styles from './DesignSmoke.module.css';

const FAMILY_MEMBERS: FamilyMemberId[] = ['bryant', 'danielle', 'isabella', 'eliana', 'family'];

export function DesignSmoke() {
  const { theme, cycleTheme } = useTheme();
  const [inputValue, setInputValue] = useState('');
  const [pwValue, setPwValue] = useState('');
  const captureSheet = useNewCaptureSheet();

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <HearthWordmark size={28} />
        <button className={styles.themeToggle} onClick={cycleTheme}>
          {THEME_LABELS[theme]} — click to cycle
        </button>
      </header>

      <p className={styles.subtitle}>
        Design system smoke test — Phase 1 primitives in all three themes.
      </p>

      {/* HearthMark section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>HearthMark</h2>
        <div className={styles.row}>
          {([16, 22, 36, 56, 100] as const).map((size) => (
            <div key={size} className={styles.swatch}>
              <HearthMark size={size} />
              <span className={styles.swatchLabel}>{size}px</span>
            </div>
          ))}
        </div>
      </section>

      {/* HearthWordmark section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>HearthWordmark</h2>
        <div className={styles.row}>
          {([14, 18, 24, 36] as const).map((size) => (
            <div key={size} className={styles.swatch}>
              <HearthWordmark size={size} />
              <span className={styles.swatchLabel}>{size}px</span>
            </div>
          ))}
        </div>
      </section>

      {/* HBtn section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>HBtn</h2>
        <div className={styles.btnGrid}>
          {(['primary', 'ghost', 'default', 'danger'] as const).map((kind) =>
            (['sm', 'md', 'lg'] as const).map((size) => (
              <HBtn key={`${kind}-${size}`} kind={kind} size={size}>
                {kind} {size}
              </HBtn>
            ))
          )}
        </div>
        <div className={cn(styles.row, styles.rowSpacedTop)}>
          {(['primary', 'ghost', 'default', 'danger'] as const).map((kind) => (
            <HBtn key={`${kind}-disabled`} kind={kind} disabled>
              {kind} disabled
            </HBtn>
          ))}
        </div>
      </section>

      {/* FamilyChip section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>FamilyChip</h2>
        <div className={styles.chipGrid}>
          {FAMILY_MEMBERS.map((id) =>
            (['sm', 'md', 'lg'] as const).map((size) => (
              <FamilyChip key={`${id}-${size}`} who={id} size={size} />
            ))
          )}
        </div>
        <div className={cn(styles.row, styles.rowSpacedTop)}>
          <span className={styles.swatchLabel}>No label:</span>
          {FAMILY_MEMBERS.map((id) => (
            <FamilyChip key={`${id}-nolabel`} who={id} showLabel={false} />
          ))}
        </div>
      </section>

      {/* ConfidenceBadge section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>ConfidenceBadge</h2>
        <div className={styles.row}>
          <ConfidenceBadge value={0.61} status="review" />
          <ConfidenceBadge value={0.85} status="review" />
          <ConfidenceBadge value={0.95} status="auto" />
          <ConfidenceBadge value={1.0} status="auto" />
          <ConfidenceBadge value={0.45} status="skipped" />
        </div>
      </section>

      {/* Input section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Input</h2>
        <div className={styles.inputGrid}>
          {/* Default text */}
          <Input
            label="Default (text)"
            value={inputValue}
            onChange={setInputValue}
            placeholder="Type something…"
          />
          {/* With value */}
          <Input
            label="With value"
            value="bryant"
            onChange={() => {}}
          />
          {/* Placeholder, no value */}
          <Input
            label="Placeholder only"
            value=""
            onChange={() => {}}
            placeholder="e.g. admin"
          />
          {/* Disabled */}
          <Input
            label="Disabled"
            value="locked"
            onChange={() => {}}
            disabled
          />
          {/* With error */}
          <Input
            label="With error"
            value="bad"
            onChange={() => {}}
            error="This field is required"
          />
          {/* Mono variant */}
          <Input
            label="Mono (OAuth token)"
            value="ya29.a0AfH6SMB…"
            onChange={() => {}}
            mono
          />
          {/* Password type */}
          <Input
            label="Password"
            value={pwValue}
            onChange={setPwValue}
            type="password"
            placeholder="••••••••"
          />
          {/* Email type */}
          <Input
            label="Email"
            value=""
            onChange={() => {}}
            type="email"
            placeholder="user@example.com"
          />
        </div>
      </section>

      {/* WizardSteps section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>WizardSteps</h2>

        {/* State 1: All upcoming (not yet started) */}
        {(() => {
          const steps: readonly WizardStep[] = [
            { key: 'account', label: 'Account', status: 'upcoming' },
            { key: 'google',  label: 'Google',  status: 'upcoming' },
            { key: 'family',  label: 'Family',  status: 'upcoming' },
          ];
          return (
            <div className={styles.wizardStepsRow}>
              <span className={styles.swatchLabel}>All upcoming:</span>
              <WizardSteps steps={steps} />
            </div>
          );
        })()}

        {/* State 2: Step 1 active (Account in progress) */}
        {(() => {
          const steps: readonly WizardStep[] = [
            { key: 'account', label: 'Account', status: 'active' },
            { key: 'google',  label: 'Google',  status: 'upcoming' },
            { key: 'family',  label: 'Family',  status: 'upcoming' },
          ];
          return (
            <div className={styles.wizardStepsRow}>
              <span className={styles.swatchLabel}>Step 1 active:</span>
              <WizardSteps steps={steps} />
            </div>
          );
        })()}

        {/* State 3: Step 2 active (Account done, Google in progress) */}
        {(() => {
          const steps: readonly WizardStep[] = [
            { key: 'account', label: 'Account', status: 'done' },
            { key: 'google',  label: 'Google',  status: 'active' },
            { key: 'family',  label: 'Family',  status: 'upcoming' },
          ];
          return (
            <div className={styles.wizardStepsRow}>
              <span className={styles.swatchLabel}>Step 2 active:</span>
              <WizardSteps steps={steps} />
            </div>
          );
        })()}

        {/* State 4: Step 3 active (Account + Google done, Family in progress) */}
        {(() => {
          const steps: readonly WizardStep[] = [
            { key: 'account', label: 'Account', status: 'done' },
            { key: 'google',  label: 'Google',  status: 'done' },
            { key: 'family',  label: 'Family',  status: 'active' },
          ];
          return (
            <div className={styles.wizardStepsRow}>
              <span className={styles.swatchLabel}>Step 3 active:</span>
              <WizardSteps steps={steps} />
            </div>
          );
        })()}

        {/* State 5: All done */}
        {(() => {
          const steps: readonly WizardStep[] = [
            { key: 'account', label: 'Account', status: 'done' },
            { key: 'google',  label: 'Google',  status: 'done' },
            { key: 'family',  label: 'Family',  status: 'done' },
          ];
          return (
            <div className={styles.wizardStepsRow}>
              <span className={styles.swatchLabel}>All done:</span>
              <WizardSteps steps={steps} />
            </div>
          );
        })()}
      </section>

      {/* Shell section */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>PhoneShell + DesktopShell</h2>
        <div className={styles.shellRow}>
          <div>
            <p className={styles.swatchLabel}>PhoneShell (390×844)</p>
            <div className={styles.shellThumb}>
              <PhoneShell>
                <div className={styles.shellInner}>PhoneShell</div>
              </PhoneShell>
            </div>
          </div>
          <div>
            <p className={styles.swatchLabel}>DesktopShell (1280×800)</p>
            <div className={styles.shellThumb}>
              <DesktopShell>
                <div className={styles.shellInner}>DesktopShell</div>
              </DesktopShell>
            </div>
          </div>
        </div>
      </section>

      {/* NewCaptureSheet trigger */}
      <section className={styles.section} data-testid="new-capture-sheet-section">
        <h2 className={styles.sectionTitle}>NewCaptureSheet</h2>
        <div className={styles.row}>
          <HBtn kind="primary" onClick={captureSheet.open} data-testid="trigger-new-capture-sheet">
            Trigger New Capture sheet
          </HBtn>
          <span className={styles.swatchLabel}>
            {captureSheet.isOpen ? 'open' : 'closed'}
          </span>
        </div>
      </section>

      {/* Phase 3.5 primitives section */}
      <section className={styles.section} data-testid="phase35-section">
        <h2 className={styles.sectionTitle}>Phase 3.5 Primitives</h2>

        {/* Spinner */}
        <div className={styles.row} style={{ marginBottom: '1.5rem' }}>
          {([12, 18, 24] as const).map((size) => (
            <div key={size} className={styles.swatch}>
              <Spinner size={size} ariaLabel={`Spinner ${size}px`} />
              <span className={styles.swatchLabel}>{size}px</span>
            </div>
          ))}
        </div>

        {/* ThumbTile */}
        <div className={styles.row} style={{ marginBottom: '1.5rem' }}>
          <div className={styles.swatch}>
            <ThumbTile />
            <span className={styles.swatchLabel}>default</span>
          </div>
          <div className={styles.swatch}>
            <ThumbTile accent="var(--accent)">📷</ThumbTile>
            <span className={styles.swatchLabel}>accent dot</span>
          </div>
          <div className={styles.swatch}>
            <ThumbTile
              accent="var(--danger)"
              badge={
                <span style={{
                  width: 20, height: 20, borderRadius: 999,
                  background: 'var(--accent)', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 800, border: '2px solid var(--paper)',
                  fontFamily: 'var(--fontMono)',
                }}>1</span>
              }
            >
              📷
            </ThumbTile>
            <span className={styles.swatchLabel}>with badge</span>
          </div>
        </div>

        {/* SectionRule */}
        <div style={{ marginBottom: '1.5rem' }}>
          <SectionRule label="In flight" dotColor="var(--accent)" count={2} />
          <SectionRule label="Done" dotColor="var(--success)" count={5} />
          <SectionRule label="Couldn't read" dotColor="var(--danger)" count={1} />
        </div>

        {/* Chevron + BackChevron */}
        <div className={styles.row} style={{ marginBottom: '1.5rem' }}>
          <div className={styles.swatch}>
            <Chevron />
            <span className={styles.swatchLabel}>Chevron (14px)</span>
          </div>
          <div className={styles.swatch}>
            <Chevron size={20} color="var(--accent)" />
            <span className={styles.swatchLabel}>Chevron (20px accent)</span>
          </div>
          <div className={styles.swatch}>
            <BackChevron />
            <span className={styles.swatchLabel}>BackChevron (32px)</span>
          </div>
        </div>

        {/* formatETA examples */}
        <div className={styles.row}>
          {([null, 0, 45, 184, 3600] as const).map((sec) => (
            <div key={String(sec)} className={styles.swatch}>
              <span style={{ fontFamily: 'var(--fontMono)', fontSize: 14, color: 'var(--ink)' }}>
                {formatETA(sec)}
              </span>
              <span className={styles.swatchLabel}>{sec === null ? 'null' : `${sec}s`}</span>
            </div>
          ))}
          {([45, 64, 120, 3661] as const).map((sec) => (
            <div key={`dur-${sec}`} className={styles.swatch}>
              <span style={{ fontFamily: 'var(--fontMono)', fontSize: 14, color: 'var(--fgSoft)' }}>
                {formatDuration(sec)}
              </span>
              <span className={styles.swatchLabel}>dur {sec}s</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
