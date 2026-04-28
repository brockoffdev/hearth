import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { HBtn } from '../components/HBtn';
import { getAdminSettings, patchAdminSettings } from '../lib/adminSettings';
import type { AdminSettings, AdminSettingsPatch } from '../lib/adminSettings';
import styles from './AdminSettings.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pct(threshold: number): string {
  return `${Math.round(threshold * 100)}%`;
}

// ---------------------------------------------------------------------------
// 403 view
// ---------------------------------------------------------------------------

function ForbiddenView(): JSX.Element {
  return (
    <div className={styles.forbidden}>
      <div className={styles.forbiddenCard}>
        <h1 className={styles.forbiddenTitle}>403</h1>
        <p className={styles.forbiddenText}>Admin access required.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdminSettings(): JSX.Element {
  const { state } = useAuth();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  // Mutable draft state — tracks user edits vs loaded values
  const [provider, setProvider] = useState<'ollama' | 'gemini' | 'anthropic'>('ollama');
  const [model, setModel] = useState('');
  const [ollamaEndpoint, setOllamaEndpoint] = useState('');
  // API key inputs: undefined = untouched (don't include in PATCH); string = user typed (include)
  const [geminiKeyInput, setGeminiKeyInput] = useState<string | undefined>(undefined);
  const [anthropicKeyInput, setAnthropicKeyInput] = useState<string | undefined>(undefined);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.85);
  const [fewShotWindow, setFewShotWindow] = useState(10);

  const isAdmin = state.status === 'authenticated' && state.user.role === 'admin';

  useEffect(() => {
    if (!isAdmin) return;
    getAdminSettings()
      .then((s) => {
        setSettings(s);
        setProvider(s.vision_provider);
        setModel(s.vision_model);
        setOllamaEndpoint(s.ollama_endpoint);
        setConfidenceThreshold(s.confidence_threshold);
        setFewShotWindow(s.few_shot_correction_window);
      })
      .catch(() => {/* auth redirect handled by RequireAuth */})
      .finally(() => setLoading(false));
  }, [isAdmin]);

  if (state.status === 'authenticated' && state.user.role !== 'admin') {
    return <ForbiddenView />;
  }

  function hasDiffs(): boolean {
    if (!settings) return false;
    return (
      provider !== settings.vision_provider ||
      model !== settings.vision_model ||
      ollamaEndpoint !== settings.ollama_endpoint ||
      confidenceThreshold !== settings.confidence_threshold ||
      fewShotWindow !== settings.few_shot_correction_window ||
      geminiKeyInput !== undefined ||
      anthropicKeyInput !== undefined
    );
  }

  async function handleSave(): Promise<void> {
    if (!settings) return;
    setSaving(true);
    const patch: AdminSettingsPatch = {};
    if (provider !== settings.vision_provider) patch.vision_provider = provider;
    if (model !== settings.vision_model) patch.vision_model = model;
    if (ollamaEndpoint !== settings.ollama_endpoint) patch.ollama_endpoint = ollamaEndpoint;
    if (confidenceThreshold !== settings.confidence_threshold) patch.confidence_threshold = confidenceThreshold;
    if (fewShotWindow !== settings.few_shot_correction_window) patch.few_shot_correction_window = fewShotWindow;
    if (geminiKeyInput !== undefined) patch.gemini_api_key = geminiKeyInput;
    if (anthropicKeyInput !== undefined) patch.anthropic_api_key = anthropicKeyInput;

    try {
      const updated = await patchAdminSettings(patch);
      setSettings(updated);
      setProvider(updated.vision_provider);
      setModel(updated.vision_model);
      setOllamaEndpoint(updated.ollama_endpoint);
      setConfidenceThreshold(updated.confidence_threshold);
      setFewShotWindow(updated.few_shot_correction_window);
      setGeminiKeyInput(undefined);
      setAnthropicKeyInput(undefined);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={styles.content}>
          <div className={styles.heading}>
            <div className={styles.adminLabel}>Admin</div>
            <h1 className={styles.title}>
              <span className={styles.titleAccent}>Settings</span>
            </h1>
          </div>

          {loading ? (
            <p style={{ color: 'var(--fgSoft)', fontSize: 14 }}>Loading…</p>
          ) : (
            <>
              <div className={styles.cardGrid}>
                {/* Vision provider card */}
                <div className={styles.card}>
                  <p className={styles.cardTitle}>Vision provider</p>
                  <div className={styles.providerList}>
                    {(
                      [
                        { id: 'ollama', name: 'Ollama', cost: 'Free · ~6 GB peak' },
                        { id: 'gemini', name: 'Gemini', cost: 'Pay-per-use · BYO key' },
                        { id: 'anthropic', name: 'Anthropic', cost: 'Pay-per-use · BYO key' },
                      ] as const
                    ).map((p) => (
                      <label
                        key={p.id}
                        className={provider === p.id ? styles.providerOptionActive : styles.providerOption}
                      >
                        <input
                          type="radio"
                          className={styles.providerRadio}
                          name="vision_provider"
                          value={p.id}
                          checked={provider === p.id}
                          onChange={() => setProvider(p.id)}
                          aria-label={p.name}
                        />
                        <div className={styles.providerInfo}>
                          <span className={styles.providerName}>{p.name}</span>
                          <span className={styles.providerCost}>{p.cost}</span>
                        </div>
                      </label>
                    ))}
                  </div>

                  <div className={styles.providerFields}>
                    <div className={styles.fieldGroup}>
                      <label className={styles.fieldLabel} htmlFor="vision-model">
                        Model
                      </label>
                      <input
                        id="vision-model"
                        type="text"
                        className={styles.fieldInput}
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        placeholder={
                          provider === 'ollama'
                            ? 'qwen2.5-vl:7b'
                            : provider === 'gemini'
                              ? 'gemini-2.5-flash'
                              : 'claude-haiku-4-5'
                        }
                      />
                    </div>

                    {provider === 'ollama' && (
                      <div className={styles.fieldGroup}>
                        <label className={styles.fieldLabel} htmlFor="ollama-endpoint">
                          Ollama endpoint
                        </label>
                        <input
                          id="ollama-endpoint"
                          type="text"
                          className={styles.fieldInput}
                          value={ollamaEndpoint}
                          onChange={(e) => setOllamaEndpoint(e.target.value)}
                          placeholder="http://localhost:11434"
                        />
                      </div>
                    )}

                    {provider === 'gemini' && (
                      <div className={styles.fieldGroup}>
                        <label className={styles.fieldLabel} htmlFor="gemini-api-key">
                          Gemini API key
                        </label>
                        <div className={styles.apiKeyRow}>
                          <input
                            id="gemini-api-key"
                            type="password"
                            className={styles.apiKeyInput}
                            value={geminiKeyInput ?? ''}
                            onChange={(e) => setGeminiKeyInput(e.target.value)}
                            placeholder={
                              settings?.gemini_api_key_set
                                ? `Currently set: ${settings.gemini_api_key_masked}`
                                : 'Paste API key…'
                            }
                            autoComplete="off"
                          />
                          {(settings?.gemini_api_key_set || geminiKeyInput !== undefined) && (
                            <button
                              type="button"
                              className={styles.clearKeyBtn}
                              onClick={() => setGeminiKeyInput('')}
                              aria-label="Clear Gemini API key"
                            >
                              Clear key
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {provider === 'anthropic' && (
                      <div className={styles.fieldGroup}>
                        <label className={styles.fieldLabel} htmlFor="anthropic-api-key">
                          Anthropic API key
                        </label>
                        <div className={styles.apiKeyRow}>
                          <input
                            id="anthropic-api-key"
                            type="password"
                            className={styles.apiKeyInput}
                            value={anthropicKeyInput ?? ''}
                            onChange={(e) => setAnthropicKeyInput(e.target.value)}
                            placeholder={
                              settings?.anthropic_api_key_set
                                ? `Currently set: ${settings.anthropic_api_key_masked}`
                                : 'Paste API key…'
                            }
                            autoComplete="off"
                          />
                          {(settings?.anthropic_api_key_set || anthropicKeyInput !== undefined) && (
                            <button
                              type="button"
                              className={styles.clearKeyBtn}
                              onClick={() => setAnthropicKeyInput('')}
                              aria-label="Clear Anthropic API key"
                            >
                              Clear key
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Confidence threshold card */}
                <div className={styles.card}>
                  <p className={styles.cardTitle}>Confidence threshold</p>
                  <div className={styles.bigNumber}>{pct(confidenceThreshold)}</div>
                  <input
                    type="range"
                    className={styles.slider}
                    min={50}
                    max={95}
                    step={1}
                    value={Math.round(confidenceThreshold * 100)}
                    onChange={(e) => setConfidenceThreshold(parseInt(e.target.value, 10) / 100)}
                    aria-label="Confidence threshold"
                  />
                  <div className={styles.sliderLabels}>
                    <span>50% lenient</span>
                    <span>95% strict</span>
                  </div>
                </div>

                {/* Few-shot learning card */}
                <div className={styles.card}>
                  <p className={styles.cardTitle}>Few-shot learning</p>
                  <div className={styles.numberInputRow}>
                    <button
                      type="button"
                      className={styles.stepBtn}
                      onClick={() => setFewShotWindow((n) => Math.max(0, n - 1))}
                      disabled={fewShotWindow <= 0}
                      aria-label="Decrease few-shot window"
                    >
                      −
                    </button>
                    <span className={styles.numberDisplay}>{fewShotWindow}</span>
                    <button
                      type="button"
                      className={styles.stepBtn}
                      onClick={() => setFewShotWindow((n) => Math.min(50, n + 1))}
                      disabled={fewShotWindow >= 50}
                      aria-label="Increase few-shot window"
                    >
                      +
                    </button>
                  </div>
                  <p className={styles.rangeHint}>
                    Recent corrections to include as examples (0 = disabled, max 50)
                  </p>
                </div>

                {/* Performance card (read-only placeholder) */}
                <div className={styles.card}>
                  <p className={styles.cardTitle}>Performance</p>
                  <p className={styles.perfPlaceholder}>Not yet measured</p>
                </div>
              </div>

              <div className={styles.saveBar}>
                <HBtn
                  kind="primary"
                  disabled={!hasDiffs() || saving}
                  onClick={() => void handleSave()}
                >
                  {saving ? 'Saving…' : 'Save'}
                </HBtn>
                {savedFlash && <span className={styles.savedMsg}>Saved</span>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
