import { useNavigate, useSearchParams } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import type { JSX } from 'react';
import { ApiError } from '../lib/api';
import { uploadPhoto } from '../lib/uploads';
import { HearthWordmark } from '../components/HearthWordmark';
import { HBtn } from '../components/HBtn';
import styles from './Upload.module.css';

// ---------------------------------------------------------------------------
// UI state machine
// ---------------------------------------------------------------------------

type UIState =
  | { kind: 'idle' }
  | { kind: 'preview'; file: File; previewUrl: string }
  | { kind: 'uploading' }
  | { kind: 'error'; message: string };

// ---------------------------------------------------------------------------
// Camera SVG icon
// ---------------------------------------------------------------------------

function CameraIcon() {
  return (
    <svg
      className={styles.cameraIcon}
      width="64"
      height="64"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Sub-views (kept inline as render functions)
// ---------------------------------------------------------------------------

interface IdleViewProps {
  onShutter: () => void;
  onGallery: () => void;
}

function IdleView({ onShutter, onGallery }: IdleViewProps) {
  return (
    <div className={styles.idleView}>
      <div className={styles.viewfinderFrame}>
        <CameraIcon />
        <p className={styles.viewfinderLabel}>Align the wall calendar in frame</p>
      </div>
      <button
        type="button"
        className={styles.shutterBtn}
        onClick={onShutter}
        aria-label="Take a photo"
      >
        <div className={styles.shutterInner} />
      </button>
      <button type="button" className={styles.galleryLink} onClick={onGallery}>
        or Pick from gallery
      </button>
    </div>
  );
}

interface PreviewViewProps {
  previewUrl: string;
  onConfirm: () => void;
  onRetake: () => void;
}

function PreviewView({ previewUrl, onConfirm, onRetake }: PreviewViewProps) {
  return (
    <div className={styles.previewView}>
      <img
        src={previewUrl}
        alt="Photo preview"
        className={styles.previewImg}
      />
      <div className={styles.actionBar}>
        <HBtn kind="ghost" onClick={onRetake}>
          Retake
        </HBtn>
        <HBtn kind="primary" onClick={onConfirm}>
          Use this
        </HBtn>
      </div>
    </div>
  );
}

function UploadingView() {
  return (
    <div className={styles.uploadingView}>
      <div className={styles.spinner} role="status" aria-label="Uploading" />
      <span>Uploading…</span>
    </div>
  );
}

interface ErrorViewProps {
  message: string;
  onRetake: () => void;
}

function ErrorView({ message, onRetake }: ErrorViewProps) {
  return (
    <div className={styles.idleView}>
      <div className={styles.errorBanner} role="alert">
        {message}
      </div>
      <HBtn kind="ghost" onClick={onRetake}>
        Try again
      </HBtn>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload route
// ---------------------------------------------------------------------------

export function Upload(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const source = searchParams.get('source');
  const [state, setState] = useState<UIState>({ kind: 'idle' });
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  // Auto-trigger the matching input on mount based on ?source= query param.
  // The empty dep array is intentional: we read `source` only once on mount
  // to open the OS file picker. Re-running on source changes would be wrong.
  useEffect(() => {
    if (source === 'camera') cameraInputRef.current?.click();
    else if (source === 'library') galleryInputRef.current?.click();
    // No cleanup needed — we just trigger the file picker once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Revoke blob URL when the preview URL changes or the component unmounts.
  // Keying on the URL itself guarantees the closure captures the right value
  // even if the user transitions idle → preview → unmount.
  const previewUrl = state.kind === 'preview' ? state.previewUrl : null;
  useEffect(() => {
    if (previewUrl === null) return;
    return () => {
      URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const openCamera = () => {
    cameraInputRef.current?.click();
  };

  const openGallery = () => {
    galleryInputRef.current?.click();
  };

  const resetInputs = () => {
    if (cameraInputRef.current) cameraInputRef.current.value = '';
    if (galleryInputRef.current) galleryInputRef.current.value = '';
  };

  const onFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side validation: file type
    if (!file.type.startsWith('image/')) {
      setState({ kind: 'error', message: 'Please pick an image' });
      resetInputs();
      return;
    }

    // Client-side validation: file size (25 MB cap matching backend)
    if (file.size > 25 * 1024 * 1024) {
      setState({ kind: 'error', message: 'Photo must be ≤25MB' });
      resetInputs();
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setState({ kind: 'preview', file, previewUrl });
  };

  const onConfirm = async () => {
    if (state.kind !== 'preview') return;
    const { file, previewUrl } = state;

    // Revoke before moving to uploading state
    URL.revokeObjectURL(previewUrl);
    setState({ kind: 'uploading' });

    try {
      const upload = await uploadPhoto(file);
      void navigate(`/uploads/${upload.id}`);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Upload failed';
      setState({ kind: 'error', message });
    }
  };

  const onRetake = () => {
    if (state.kind === 'preview') {
      URL.revokeObjectURL(state.previewUrl);
    }
    setState({ kind: 'idle' });
    resetInputs();
  };

  const onClose = () => {
    if (state.kind === 'preview') {
      URL.revokeObjectURL(state.previewUrl);
    }
    void navigate('/');
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className={styles.page}>
      {/* Hidden file inputs */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic"
        capture="environment"
        onChange={onFilePicked}
        hidden
      />
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic"
        onChange={onFilePicked}
        hidden
      />

      {/* Header */}
      <header className={styles.header}>
        <HearthWordmark size={20} />
        <button
          type="button"
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
      </header>

      {/* Orientation hint — shown only in idle, hidden in landscape via CSS */}
      {state.kind === 'idle' && (
        <div className={styles.orientationHint}>
          📱 Rotate to landscape for the best framing
        </div>
      )}

      {/* Main stage */}
      <main className={styles.stage}>
        {state.kind === 'idle' && (
          <IdleView onShutter={openCamera} onGallery={openGallery} />
        )}
        {state.kind === 'preview' && (
          <PreviewView
            previewUrl={state.previewUrl}
            onConfirm={() => void onConfirm()}
            onRetake={onRetake}
          />
        )}
        {state.kind === 'uploading' && <UploadingView />}
        {state.kind === 'error' && (
          <ErrorView message={state.message} onRetake={onRetake} />
        )}
      </main>
    </div>
  );
}
