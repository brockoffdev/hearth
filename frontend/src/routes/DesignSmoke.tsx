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
import type { FamilyMemberId } from '../lib/family';
import styles from './DesignSmoke.module.css';

const FAMILY_MEMBERS: FamilyMemberId[] = ['bryant', 'danielle', 'isabella', 'eliana', 'family'];

export function DesignSmoke() {
  const { theme, cycleTheme } = useTheme();
  const [inputValue, setInputValue] = useState('');
  const [pwValue, setPwValue] = useState('');

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
    </div>
  );
}
