// Hearth v2 — Status view & background-processing enhancement
// Adds: MobileStatus, MobileProcessingV2 (with Continue), MobileHomeV2 (with Status entry)
// Lifts everything from existing primitives + tokens. No new colors.

const { useState: useStateV2 } = React;

// ─── Mock in-flight + completed + failed uploads ─────────────────
window.HEARTH_UPLOADS_MOCK = [
  // in-flight
  { id: 'u-43', status: 'processing', startedAt: 'Just now',  thumbLabel: 'Apr 27, 8:38 AM',
    current_stage: 'cell_progress',     completed_stages: ['received','preprocessing','grid_detected','model_loading'],
    cellProgress: 12, totalCells: 35,    remaining_seconds: 184 },
  { id: 'u-42', status: 'processing', startedAt: '38 sec ago', thumbLabel: 'Apr 27, 8:37 AM',
    current_stage: 'preprocessing',      completed_stages: ['received'],
    remaining_seconds: 235,              queuedBehind: 1 },
  // completed
  { id: 'u-41', status: 'completed',  finishedAt: '2 hr ago',  thumbLabel: 'Apr 27, 6:14 AM',
    found: 14, review: 3, durationSec: 118 },
  { id: 'u-40', status: 'completed',  finishedAt: 'Yesterday', thumbLabel: 'Apr 26, 9:02 PM',
    found: 6,  review: 0, durationSec: 64 },
  { id: 'u-39', status: 'completed',  finishedAt: '2 days ago',thumbLabel: 'Apr 25, 11:47 AM',
    found: 11, review: 1, durationSec: 97 },
  // failed
  { id: 'u-38', status: 'failed',     finishedAt: '3 days ago',thumbLabel: 'Apr 24, 4:20 PM',
    error: 'Image too blurry — could not detect grid' },
];

function fmtETA(sec) {
  if (sec == null) return '—';
  if (sec < 60) return `~${sec} sec`;
  const m = Math.floor(sec / 60), s = sec % 60;
  return s ? `~${m} min ${s} sec` : `~${m} min`;
}
function fmtDur(sec) {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}
function stageLabel(key) {
  const s = window.HEARTH_STAGES.find(x => x.key === key);
  return s ? s.label : key;
}

// ─── A · MobileStatus — the inbox ──────────────────────────────
function MobileStatus({ uploads }) {
  const items = uploads || window.HEARTH_UPLOADS_MOCK;
  const inflight  = items.filter(u => u.status === 'processing');
  const completed = items.filter(u => u.status === 'completed');
  const failed    = items.filter(u => u.status === 'failed');
  const totalETA  = inflight.reduce((m, u) => Math.max(m, u.remaining_seconds || 0), 0);

  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* header */}
        <div style={{ padding: '54px 22px 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <BackChevron/>
          <span style={{ flex: 1 }}/>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>Pull to refresh</span>
        </div>
        <div style={{ padding: '4px 22px 14px' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 32, color: 'var(--ink)', letterSpacing: -0.5 }}>
            Uploads
          </div>
          <div style={{ color: 'var(--fgSoft)', fontSize: 13, marginTop: 4 }}>
            {inflight.length > 0
              ? <span><strong style={{ color: 'var(--accent)' }}>{inflight.length} processing</strong> · longest {fmtETA(totalETA)} remaining</span>
              : <span>All caught up · {completed.length} recent</span>}
          </div>
        </div>

        {/* in-flight */}
        {inflight.length > 0 && (
          <>
            <SectionRule label="In flight" dot="var(--accent)" count={inflight.length}/>
            <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {inflight.map(u => <InflightRow key={u.id} u={u}/>)}
            </div>
          </>
        )}

        {/* completed */}
        {completed.length > 0 && (
          <>
            <SectionRule label="Done" dot="var(--success)" count={completed.length} mt={inflight.length ? 18 : 6}/>
            <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {completed.map(u => <CompletedRow key={u.id} u={u}/>)}
            </div>
          </>
        )}

        {/* failed */}
        {failed.length > 0 && (
          <>
            <SectionRule label="Couldn't read" dot="var(--danger)" count={failed.length} mt={18}/>
            <div style={{ padding: '0 18px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {failed.map(u => <FailedRow key={u.id} u={u}/>)}
            </div>
          </>
        )}
      </div>
      <MobileTabBarV2 active="upload"/>
    </PhoneShell>
  );
}

function SectionRule({ label, dot, count, mt = 6 }) {
  return (
    <div style={{ padding: `${mt}px 22px 8px`, display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: dot }}/>
      <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: 17, color: 'var(--ink)' }}>{label}</span>
      <span style={{ fontSize: 11, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>{count}</span>
      <span style={{ flex: 1, height: 1, background: 'var(--rule)' }}/>
    </div>
  );
}

function ThumbTile({ children, accent }) {
  return (
    <div style={{ width: 56, height: 56, borderRadius: 12, flexShrink: 0,
      background: `repeating-linear-gradient(135deg, var(--paperDeep) 0 8px, color-mix(in oklab, var(--paperDeep) 60%, transparent) 8px 16px)`,
      border: '1px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--fontMono)', fontSize: 10, color: 'var(--fgSoft)',
      position: 'relative', overflow: 'hidden' }}>
      {accent && <span style={{ position: 'absolute', top: 6, right: 6, width: 8, height: 8, borderRadius: '50%', background: accent }}/>}
      {children}
    </div>
  );
}

function InflightRow({ u }) {
  const total = window.HEARTH_STAGES.length - 1; // exclude 'done'
  const completed = u.completed_stages.length;
  const pct = Math.min(100, Math.round((completed / total) * 100));
  const isCellStage = u.current_stage === 'cell_progress' && u.cellProgress;
  const stageText = isCellStage
    ? `${stageLabel(u.current_stage)} · ${u.cellProgress} of ${u.totalCells}`
    : stageLabel(u.current_stage);

  return (
    <div style={{ padding: '12px 14px', borderRadius: 16,
      background: 'color-mix(in oklab, var(--accent) 5%, var(--surface))',
      border: '1px solid color-mix(in oklab, var(--accent) 25%, var(--rule))',
      display: 'flex', gap: 12, alignItems: 'flex-start', position: 'relative' }}>
      <ThumbTile accent="var(--accent)">📷</ThumbTile>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Spinner size={12}/>
          <span style={{ fontWeight: 700, color: 'var(--ink)', fontSize: 14, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stageText}</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fgSoft)', marginTop: 3, fontFamily: 'var(--fontMono)' }}>
          {u.thumbLabel} · started {u.startedAt}
          {u.queuedBehind ? ` · waiting on ${u.queuedBehind} ahead` : ''}
        </div>
        <div style={{ marginTop: 8, height: 4, borderRadius: 4, background: 'var(--paperDeep)', overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)',
            transition: 'width .4s', boxShadow: '0 0 8px color-mix(in oklab, var(--accent) 50%, transparent)' }}/>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--fgSoft)' }}>
            <strong style={{ color: 'var(--ink)', fontFamily: 'var(--fontMono)' }}>{fmtETA(u.remaining_seconds)}</strong> remaining
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>Open ↗</span>
        </div>
      </div>
    </div>
  );
}

function CompletedRow({ u }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 16, background: 'var(--surface)',
      border: '1px solid var(--rule)', display: 'flex', gap: 12, alignItems: 'center' }}>
      <ThumbTile>✓</ThumbTile>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 14 }}>
          {u.found} events found{u.review > 0 ? `, ${u.review} need review` : ''}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fgSoft)', marginTop: 2, fontFamily: 'var(--fontMono)' }}>
          {u.thumbLabel} · {u.finishedAt} · took {fmtDur(u.durationSec)}
        </div>
      </div>
      {u.review > 0 && <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
        background: 'color-mix(in oklab, var(--warn) 14%, transparent)', color: 'var(--warn)',
        fontFamily: 'var(--fontMono)' }}>{u.review} ✏</span>}
      <Chevron/>
    </div>
  );
}

function FailedRow({ u }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 16, background: 'var(--surface)',
      border: '1px solid color-mix(in oklab, var(--danger) 25%, var(--rule))',
      display: 'flex', gap: 12, alignItems: 'center' }}>
      <ThumbTile accent="var(--danger)">!</ThumbTile>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 14 }}>Couldn't read this one</div>
        <div style={{ fontSize: 11, color: 'var(--fgSoft)', marginTop: 2, fontFamily: 'var(--fontMono)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {u.thumbLabel} · {u.error}
        </div>
      </div>
      <HBtn kind="default" size="sm">Retry</HBtn>
    </div>
  );
}

function Spinner({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      style={{ animation: 'hspin 0.9s linear infinite', flexShrink: 0 }}>
      <circle cx="12" cy="12" r="9" stroke="var(--rule)" strokeWidth="2.5"/>
      <path d="M12 3a9 9 0 0 1 9 9" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}
function Chevron() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path d="M9 6l6 6-6 6" stroke="var(--fgSoft)" strokeWidth="1.8" strokeLinecap="round"/></svg>;
}
function BackChevron() {
  return <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--surface)',
    border: '1px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M15 6l-6 6 6 6" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round"/></svg></div>;
}

// ─── B · Updated MobileProcessing — adds Continue-in-background ──
function MobileProcessingV2({ activeStage = 4, cellProgress = 12, totalCells = 35, etaSec = 184 }) {
  const stages = window.HEARTH_STAGES.slice(0, 9);
  return (
    <PhoneShell>
      <div style={{ padding: '54px 22px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <BackChevron/>
        <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>Upload #43 · started just now</span>
      </div>
      <div style={{ padding: '4px 22px 14px' }}>
        <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 28, lineHeight: '32px', color: 'var(--ink)' }}>
          Reading your<br/>wall calendar…
        </div>
        <div style={{ marginTop: 8, fontSize: 13, color: 'var(--fgSoft)' }}>
          <strong style={{ color: 'var(--ink)', fontFamily: 'var(--fontMono)' }}>{fmtETA(etaSec)}</strong> remaining ·
          we'll let you know when it's done.
        </div>
      </div>

      <div style={{ padding: '0 22px 14px' }}>
        <PhotoPlaceholder height={96} label="📷 your photo, 2048px"/>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 22px 12px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {stages.map((s, i) => {
            const done = i < activeStage;
            const active = i === activeStage;
            return (
              <div key={s.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '8px 0' }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                  background: done ? 'var(--success)' : 'transparent',
                  border: done ? 'none' : `1.5px solid ${active ? 'var(--accent)' : 'var(--rule)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 1 }}>
                  {done && <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M4 12l5 5L20 6" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                  {active && <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--accent)',
                    animation: 'hpulse 1.2s ease-in-out infinite' }}/>}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: active ? 700 : 500,
                    color: active ? 'var(--ink)' : 'var(--fgSoft)' }}>
                    {s.label}{active && s.key === 'cell_progress' ? ` · ${cellProgress} of ${totalCells}` : ''}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--fgSoft)', marginTop: 1 }}>{s.hint}</div>
                  {active && (
                    <div style={{ marginTop: 6, height: 4, borderRadius: 4, background: 'var(--paperDeep)', overflow: 'hidden' }}>
                      <div style={{ width: `${(cellProgress/totalCells)*100}%`, height: '100%', background: 'var(--accent)',
                        transition: 'width .3s' }}/>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* New: Continue-in-background CTA */}
      <div style={{ padding: '12px 18px 22px', borderTop: '1px solid var(--rule)',
        background: 'var(--bg)', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <HBtn kind="primary" size="lg" style={{ width: '100%' }}>
          Continue in background
        </HBtn>
        <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--fgSoft)' }}>
          Keeps running on the server. Check back from Uploads.
        </div>
      </div>
      <style>{`
        @keyframes hpulse { 0%,100% { transform: scale(1); opacity: 1 } 50% { transform: scale(1.4); opacity: .55 } }
        @keyframes hspin  { to { transform: rotate(360deg) } }
      `}</style>
    </PhoneShell>
  );
}

// ─── C · Updated MobileHome — adds status entry-point ────────────
function MobileHomeV2({ family, queueCount = 4, lastUpload = '8 min ago', inflightCount = 1, inflightETA = 184 }) {
  const upcoming = window.HEARTH_MOCK_EVENTS.slice(0, 4);
  const m = (id) => (family || window.HEARTH_FAMILY_DEFAULT).find(f => f.id === id);
  const hasInflight = inflightCount > 0;
  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto', paddingBottom: 12 }}>
        <div style={{ padding: '54px 22px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <HearthWordmark size={20}/>
          <div style={{ width: 36, height: 36, borderRadius: 999, background: 'var(--surface)',
            border: '1px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="4" stroke="var(--ink)" strokeWidth="1.6"/>
              <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
          </div>
        </div>
        <div style={{ padding: '8px 22px 16px' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 38, lineHeight: '42px', letterSpacing: -1, color: 'var(--ink)' }}>
            Good morning,<br/><span style={{ fontStyle: 'italic', color: 'var(--accent)' }}>Bryant.</span>
          </div>
          <div style={{ marginTop: 10, color: 'var(--fgSoft)', fontSize: 14 }}>
            Monday · April 27 · 3 events today
          </div>
        </div>

        {/* New: Live in-flight banner — only when uploads are processing */}
        {hasInflight && (
          <div style={{ margin: '0 18px 14px', padding: '12px 14px', borderRadius: 16,
            background: 'color-mix(in oklab, var(--accent) 8%, var(--surface))',
            border: '1px solid color-mix(in oklab, var(--accent) 30%, var(--rule))',
            display: 'flex', alignItems: 'center', gap: 12 }}>
            <Spinner size={18}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, color: 'var(--ink)', fontSize: 14 }}>
                {inflightCount === 1 ? '1 photo processing…' : `${inflightCount} photos processing…`}
              </div>
              <div style={{ fontSize: 11, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>
                {fmtETA(inflightETA)} remaining · we'll notify when done
              </div>
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>View →</span>
          </div>
        )}

        {/* Upload CTA card */}
        <div style={{ margin: '0 18px 14px', borderRadius: 22,
          background: 'linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent) 65%, var(--ink)))',
          color: '#fff', padding: 20, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', right: -22, top: -22, width: 130, height: 130, borderRadius: '50%',
            background: 'rgba(255,255,255,.1)' }}/>
          <div style={{ fontSize: 13, opacity: 0.85, fontWeight: 600, letterSpacing: 0.3, textTransform: 'uppercase' }}>Capture</div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 26, lineHeight: '30px', marginTop: 6, fontWeight: 500 }}>
            Take a photo of the wall calendar
          </div>
          <div style={{ fontSize: 13, opacity: 0.9, marginTop: 8 }}>Last upload {lastUpload} · 12 events found</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <div style={{ padding: '11px 16px', borderRadius: 999, background: '#fff', color: 'var(--accent)', fontSize: 14, fontWeight: 700 }}>📷 New photo</div>
            <div style={{ padding: '11px 14px', borderRadius: 999, background: 'rgba(255,255,255,.15)', color: '#fff', fontSize: 14, fontWeight: 600 }}>From library</div>
          </div>
        </div>

        {queueCount > 0 && (
          <div style={{ margin: '0 18px 18px', padding: '12px 14px', borderRadius: 14,
            border: '1px solid color-mix(in oklab, var(--warn) 30%, transparent)',
            background: 'color-mix(in oklab, var(--warn) 8%, transparent)',
            display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--warn)', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>{queueCount}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Awaiting your review</div>
              <div style={{ fontSize: 12, color: 'var(--fgSoft)' }}>From this morning's upload</div>
            </div>
            <span style={{ color: 'var(--accent)', fontSize: 13, fontWeight: 700 }}>Review →</span>
          </div>
        )}

        <div style={{ padding: '0 22px 8px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, color: 'var(--ink)' }}>Next up</div>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>This week</span>
        </div>
        <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {upcoming.map(e => {
            const who = m(e.who);
            return (
              <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 14px', borderRadius: 16, background: 'var(--surface)',
                border: '1px solid var(--rule)' }}>
                <div style={{ width: 4, alignSelf: 'stretch', borderRadius: 2, background: who?.hex }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 2 }}>
                    {new Date(e.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} · {e.time} · {who?.name}
                  </div>
                </div>
                <FamilyChip who={e.who} family={family} size="sm" label={false}/>
              </div>
            );
          })}
        </div>

        {/* New: Muted "View all uploads" link — always visible, but quiet when nothing's processing */}
        <div style={{ padding: '14px 22px 22px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: hasInflight ? 'var(--accent)' : 'var(--fgSoft)',
            fontWeight: hasInflight ? 700 : 500 }}>
            View all uploads
          </span>
          <Chevron/>
        </div>
      </div>
      <MobileTabBarV2 active="home"/>
    </PhoneShell>
  );
}

// ─── D · Tab bar v2 — "Upload" tab renamed to "Uploads" (stack/inbox icon) ────
// Same 4-tab structure; the tab now opens Status (the inbox), and "+ New capture"
// from inside Status presents the camera/library sheet.
function MobileTabBarV2({ active = 'home' }) {
  const tabs = [
    { id: 'home',   label: 'Home',     icon: 'M3 12l9-9 9 9v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z' },
    // Stacked-rectangles glyph = "list of uploads" — replaces the old upload-arrow
    { id: 'upload', label: 'Uploads',  icon: 'M5 7h14M5 12h14M5 17h14' },
    { id: 'queue',  label: 'Review',   icon: 'M4 6h12M4 12h16M4 18h10' },
    { id: 'cal',    label: 'Calendar', icon: 'M3 8h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 2v4m8-4v4' },
  ];
  return (
    <div style={{
      paddingTop: 8, paddingBottom: 28, paddingInline: 12,
      borderTop: '1px solid var(--rule)', background: 'var(--bg)',
      display: 'flex', justifyContent: 'space-around',
    }}>
      {tabs.map(t => (
        <div key={t.id} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          color: active === t.id ? 'var(--accent)' : 'var(--fgSoft)', flex: 1, position: 'relative',
        }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d={t.icon} stroke="currentColor" strokeWidth={active === t.id ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span style={{ fontSize: 10, fontWeight: active === t.id ? 700 : 500 }}>{t.label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── E · Status with "+ New capture" CTA + queue-aware mock data ─────
// Shows three uploads: photo 1 running, photos 2+3 waiting with queuedBehind chips.
window.HEARTH_UPLOADS_QUEUED_MOCK = [
  // in-flight, actively running
  { id: 'u-50', status: 'processing', startedAt: '12 sec ago', thumbLabel: 'Apr 27, 9:14 AM',
    current_stage: 'preprocessing', completed_stages: ['received'],
    remaining_seconds: 198 },
  // queued — submitted but waiting on photo 1
  { id: 'u-51', status: 'processing', startedAt: '8 sec ago', thumbLabel: 'Apr 27, 9:14 AM',
    current_stage: 'queued', completed_stages: [],
    remaining_seconds: 393, queuedBehind: 1 },
  // queued — waiting on photos 1 + 2
  { id: 'u-52', status: 'processing', startedAt: '4 sec ago', thumbLabel: 'Apr 27, 9:14 AM',
    current_stage: 'queued', completed_stages: [],
    remaining_seconds: 588, queuedBehind: 2 },
  // recent completed below for context
  { id: 'u-49', status: 'completed', finishedAt: '1 hr ago', thumbLabel: 'Apr 27, 8:11 AM',
    found: 9, review: 2, durationSec: 102 },
];

function MobileStatusQueued({ uploads, sheetOpen = false }) {
  const items = uploads || window.HEARTH_UPLOADS_QUEUED_MOCK;
  const inflight  = items.filter(u => u.status === 'processing');
  const completed = items.filter(u => u.status === 'completed');
  const failed    = items.filter(u => u.status === 'failed');
  // Total wall-time = sum of remaining for the longest-tail (last in queue), since they run serially
  const totalETA  = inflight.reduce((m, u) => Math.max(m, u.remaining_seconds || 0), 0);

  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* header */}
        <div style={{ padding: '54px 22px 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <BackChevron/>
          <span style={{ flex: 1 }}/>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>Pull to refresh</span>
        </div>
        <div style={{ padding: '4px 22px 14px' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 32, color: 'var(--ink)', letterSpacing: -0.5 }}>
            Uploads
          </div>
          <div style={{ color: 'var(--fgSoft)', fontSize: 13, marginTop: 4 }}>
            <strong style={{ color: 'var(--accent)' }}>{inflight.length} processing</strong> · {fmtETA(totalETA)} til all done
          </div>
        </div>

        {/* + New capture primary CTA — replaces the old "Upload" tab as the entry to capture */}
        <div style={{ padding: '0 18px 18px' }}>
          <div style={{ padding: '14px 16px', borderRadius: 16,
            background: 'linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent) 65%, var(--ink)))',
            color: '#fff', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer',
            boxShadow: '0 6px 18px color-mix(in oklab, var(--accent) 35%, transparent)' }}>
            <div style={{ width: 36, height: 36, borderRadius: 999, background: 'rgba(255,255,255,.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>＋</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>New capture</div>
              <div style={{ fontSize: 12, opacity: 0.9 }}>Camera or photo library</div>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M9 6l6 6-6 6" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
        </div>

        {/* in-flight */}
        <SectionRule label="In flight" dot="var(--accent)" count={inflight.length}/>
        <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {inflight.map((u, idx) => (
            <InflightRowQueued key={u.id} u={u} position={idx + 1} total={inflight.length}/>
          ))}
        </div>

        {/* completed */}
        {completed.length > 0 && (
          <>
            <SectionRule label="Done" dot="var(--success)" count={completed.length} mt={18}/>
            <div style={{ padding: '0 18px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {completed.map(u => <CompletedRow key={u.id} u={u}/>)}
            </div>
          </>
        )}
      </div>
      <MobileTabBarV2 active="upload"/>

      {/* + New capture bottom sheet — when sheetOpen */}
      {sheetOpen && <NewCaptureSheet/>}
    </PhoneShell>
  );
}

// Variant of InflightRow that handles the "queued" stage explicitly (waiting on N ahead)
function InflightRowQueued({ u, position, total }) {
  const isQueued = u.current_stage === 'queued';
  const stages = window.HEARTH_STAGES.length - 1;
  const completed = u.completed_stages.length;
  const pct = isQueued ? 0 : Math.min(100, Math.round((completed / stages) * 100));
  const headline = isQueued
    ? `Waiting · ${u.queuedBehind} ${u.queuedBehind === 1 ? 'photo' : 'photos'} ahead`
    : (u.current_stage === 'cell_progress' && u.cellProgress
        ? `${stageLabel(u.current_stage)} · ${u.cellProgress} of ${u.totalCells}`
        : stageLabel(u.current_stage));

  return (
    <div style={{ padding: '12px 14px', borderRadius: 16,
      background: isQueued ? 'var(--surface)' : 'color-mix(in oklab, var(--accent) 5%, var(--surface))',
      border: `1px solid ${isQueued ? 'var(--rule)' : 'color-mix(in oklab, var(--accent) 25%, var(--rule))'}`,
      display: 'flex', gap: 12, alignItems: 'flex-start', position: 'relative', opacity: isQueued ? 0.85 : 1 }}>
      {/* Position indicator: small numbered badge for serial queue */}
      <div style={{ position: 'relative' }}>
        <ThumbTile accent={isQueued ? null : 'var(--accent)'}>📷</ThumbTile>
        <div style={{ position: 'absolute', top: -6, left: -6, width: 20, height: 20, borderRadius: 999,
          background: isQueued ? 'var(--paperDeep)' : 'var(--accent)',
          color: isQueued ? 'var(--fgSoft)' : '#fff',
          border: '2px solid var(--paper)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 800, fontFamily: 'var(--fontMono)' }}>
          {position}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {isQueued
            ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                <circle cx="12" cy="12" r="9" stroke="var(--fgSoft)" strokeWidth="1.8"/>
                <path d="M12 7v5l3 2" stroke="var(--fgSoft)" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
            : <Spinner size={12}/>}
          <span style={{ fontWeight: 700, color: 'var(--ink)', fontSize: 14, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{headline}</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fgSoft)', marginTop: 3, fontFamily: 'var(--fontMono)' }}>
          {u.thumbLabel} · started {u.startedAt}
        </div>
        {!isQueued && (
          <div style={{ marginTop: 8, height: 4, borderRadius: 4, background: 'var(--paperDeep)', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)',
              transition: 'width .4s', boxShadow: '0 0 8px color-mix(in oklab, var(--accent) 50%, transparent)' }}/>
          </div>
        )}
        {isQueued && (
          <div style={{ marginTop: 8, height: 4, borderRadius: 4, background: 'var(--paperDeep)', overflow: 'hidden',
            position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 0,
              background: `repeating-linear-gradient(45deg, var(--rule) 0 4px, transparent 4px 8px)` }}/>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--fgSoft)' }}>
            <strong style={{ color: 'var(--ink)', fontFamily: 'var(--fontMono)' }}>{fmtETA(u.remaining_seconds)}</strong>
            {isQueued ? ' total' : ' remaining'}
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color: isQueued ? 'var(--fgSoft)' : 'var(--accent)' }}>
            {isQueued ? 'Cancel ×' : 'Open ↗'}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── F · "+ New capture" bottom sheet — Camera or Library ────────
function NewCaptureSheet() {
  return (
    <>
      {/* dim backdrop */}
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 80,
        animation: 'hfade .15s ease-out' }}/>
      {/* sheet */}
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 90,
        background: 'var(--paper)', borderRadius: '24px 24px 0 0',
        padding: '12px 18px 36px',
        boxShadow: '0 -10px 40px rgba(0,0,0,.18)',
        animation: 'hsheet .22s cubic-bezier(.2,.8,.2,1)' }}>
        {/* grabber */}
        <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--rule)',
          margin: '6px auto 14px' }}/>
        <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, color: 'var(--ink)', textAlign: 'center', marginBottom: 4 }}>
          New capture
        </div>
        <div style={{ fontSize: 13, color: 'var(--fgSoft)', textAlign: 'center', marginBottom: 18 }}>
          What does the calendar look like?
        </div>

        <SheetOption
          icon="📷"
          title="Take a photo"
          subtitle="Best for the wall calendar in front of you"
          accent
        />
        <SheetOption
          icon="🖼"
          title="Choose from library"
          subtitle="Use a photo you've already taken"
        />

        <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 12,
          background: 'var(--paperDeep)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 14 }}>💡</span>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)', flex: 1 }}>
            Hearth reads even messy handwriting. Good lighting helps; perfect framing doesn't matter.
          </span>
        </div>

        <div style={{ marginTop: 14, textAlign: 'center' }}>
          <span style={{ fontSize: 13, color: 'var(--fgSoft)', fontWeight: 600 }}>Cancel</span>
        </div>
      </div>
      <style>{`
        @keyframes hfade  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes hsheet { from { transform: translateY(100%) } to { transform: translateY(0) } }
      `}</style>
    </>
  );
}

function SheetOption({ icon, title, subtitle, accent }) {
  return (
    <div style={{ padding: '14px 16px', borderRadius: 14, marginBottom: 8,
      background: accent ? 'color-mix(in oklab, var(--accent) 8%, var(--surface))' : 'var(--surface)',
      border: `1px solid ${accent ? 'color-mix(in oklab, var(--accent) 25%, var(--rule))' : 'var(--rule)'}`,
      display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer' }}>
      <div style={{ width: 44, height: 44, borderRadius: 12,
        background: accent ? 'var(--accent)' : 'var(--paperDeep)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 22, filter: accent ? 'none' : 'grayscale(.2)' }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, color: 'var(--ink)', fontSize: 15 }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 2 }}>{subtitle}</div>
      </div>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path d="M9 6l6 6-6 6" stroke="var(--fgSoft)" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    </div>
  );
}

Object.assign(window, {
  MobileStatus, MobileProcessingV2, MobileHomeV2, MobileTabBarV2,
  MobileStatusQueued, NewCaptureSheet, fmtETA,
});
