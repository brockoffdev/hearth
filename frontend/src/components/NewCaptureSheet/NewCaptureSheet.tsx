import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JSX } from 'react';
import { Chevron } from '../Chevron';
import styles from './NewCaptureSheet.module.css';

// ---------------------------------------------------------------------------
// SheetOption
// ---------------------------------------------------------------------------

interface SheetOptionProps {
  icon: string;
  title: string;
  subtitle: string;
  accent?: boolean;
  onClick: () => void;
}

function SheetOption({ icon, title, subtitle, accent = false, onClick }: SheetOptionProps) {
  return (
    <button
      type="button"
      className={styles.option}
      data-accent={String(accent)}
      onClick={onClick}
    >
      <div className={styles.optionIcon}>{icon}</div>
      <div className={styles.optionText}>
        <div className={styles.optionTitle}>{title}</div>
        <div className={styles.optionSubtitle}>{subtitle}</div>
      </div>
      <Chevron size={14} />
    </button>
  );
}

// ---------------------------------------------------------------------------
// NewCaptureSheet
// ---------------------------------------------------------------------------

interface NewCaptureSheetProps {
  onClose: () => void;
}

export function NewCaptureSheet({ onClose }: NewCaptureSheetProps): JSX.Element {
  const navigate = useNavigate();

  const goCamera = useCallback(() => {
    void navigate('/upload?source=camera');
    onClose();
  }, [navigate, onClose]);

  const goLibrary = useCallback(() => {
    void navigate('/upload?source=library');
    onClose();
  }, [navigate, onClose]);

  return (
    <>
      <div
        className={styles.backdrop}
        onClick={onClose}
        role="presentation"
      />
      <div
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-capture-title"
      >
        <div className={styles.grabber} />
        <h2 id="new-capture-title" className={styles.title}>New capture</h2>
        <p className={styles.subtitle}>What does the calendar look like?</p>

        <SheetOption
          icon="📷"
          title="Take a photo"
          subtitle="Best for the wall calendar in front of you"
          accent
          onClick={goCamera}
        />
        <SheetOption
          icon="🖼"
          title="Choose from library"
          subtitle="Use a photo you've already taken"
          onClick={goLibrary}
        />

        <div className={styles.tip}>
          <span className={styles.tipIcon}>💡</span>
          <span className={styles.tipText}>
            Hearth reads even messy handwriting. Good lighting helps; perfect framing doesn&apos;t matter.
          </span>
        </div>

        <button type="button" className={styles.cancelLink} onClick={onClose}>
          Cancel
        </button>
      </div>
    </>
  );
}
