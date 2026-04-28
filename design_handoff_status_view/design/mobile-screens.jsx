// Mobile screens — Home, Upload, Processing, Results, Queue, Review, Login

const { useState, useEffect } = React;

function PhoneShell({ children, dark = false, statusTime = '9:41' }) {
  return (
    <div style={{ width: 390, height: 844, borderRadius: 48, overflow: 'hidden',
      position: 'relative', background: dark ? '#0F0D0B' : 'var(--paper)',
      boxShadow: '0 30px 60px rgba(0,0,0,.18), 0 0 0 1px rgba(0,0,0,.12)',
      fontFamily: 'var(--fontBody)' }}>
      <div style={{ position: 'absolute', top: 11, left: '50%', transform: 'translateX(-50%)',
        width: 126, height: 37, borderRadius: 24, background: '#000', zIndex: 50 }}/>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10 }}>
        <IOSStatusBar dark={dark} time={statusTime}/>
      </div>
      <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>{children}</div>
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 60,
        height: 34, display: 'flex', justifyContent: 'center', alignItems: 'flex-end',
        paddingBottom: 8, pointerEvents: 'none' }}>
        <div style={{ width: 139, height: 5, borderRadius: 100,
          background: dark ? 'rgba(255,255,255,.7)' : 'rgba(0,0,0,.25)' }}/>
      </div>
    </div>
  );
}

function MobileTabBar({ active = 'home' }) {
  const tabs = [
    { id: 'home', label: 'Home', icon: 'M3 12l9-9 9 9v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z' },
    { id: 'upload', label: 'Upload', icon: 'M12 3v14m0-14l-5 5m5-5l5 5M4 19h16' },
    { id: 'queue', label: 'Review', icon: 'M4 6h16M4 12h16M4 18h10' },
    { id: 'cal', label: 'Calendar', icon: 'M3 8h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 2v4m8-4v4' },
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
          color: active === t.id ? 'var(--accent)' : 'var(--fgSoft)', flex: 1,
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

// ─── Home ──────────────────────────────────────────────────────
function MobileHome({ family, queueCount = 4, lastUpload = '8 min ago' }) {
  const upcoming = window.HEARTH_MOCK_EVENTS.slice(0, 5);
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
        <div style={{ padding: '8px 22px 20px' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 38, lineHeight: '42px', letterSpacing: -1, color: 'var(--ink)' }}>
            Good morning,<br/><span style={{ fontStyle: 'italic', color: 'var(--accent)' }}>Bryant.</span>
          </div>
          <div style={{ marginTop: 10, color: 'var(--fgSoft)', fontSize: 14 }}>
            Monday · April 27 · 3 events today
          </div>
        </div>

        {/* Upload CTA card */}
        <div style={{ margin: '0 18px 18px', borderRadius: 22,
          background: 'linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent) 65%, var(--ink)))',
          color: '#fff', padding: 20, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', right: -22, top: -22, width: 130, height: 130, borderRadius: '50%',
            background: 'rgba(255,255,255,.1)' }}/>
          <div style={{ fontSize: 13, opacity: 0.85, fontWeight: 600, letterSpacing: 0.3, textTransform: 'uppercase' }}>Capture</div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 26, lineHeight: '30px', marginTop: 6, fontWeight: 500 }}>
            Take a photo of the wall calendar
          </div>
          <div style={{ fontSize: 13, opacity: 0.9, marginTop: 8 }}>
            Last upload {lastUpload} · 12 events found
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <div style={{ padding: '11px 16px', borderRadius: 999, background: '#fff', color: 'var(--accent)', fontSize: 14, fontWeight: 700 }}>
              📷 New photo
            </div>
            <div style={{ padding: '11px 14px', borderRadius: 999, background: 'rgba(255,255,255,.15)', color: '#fff', fontSize: 14, fontWeight: 600 }}>
              From library
            </div>
          </div>
        </div>

        {/* Review chip */}
        {queueCount > 0 && (
          <div style={{ margin: '0 18px 22px', padding: '12px 14px', borderRadius: 14,
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

        {/* Today's events */}
        <div style={{ padding: '0 22px 8px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, color: 'var(--ink)' }}>Next up</div>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>This week</span>
        </div>
        <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {upcoming.map(e => {
            const m = (family || window.HEARTH_FAMILY_DEFAULT).find(f => f.id === e.who);
            return (
              <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 14px', borderRadius: 16, background: 'var(--surface)',
                border: '1px solid var(--rule)' }}>
                <div style={{ width: 4, alignSelf: 'stretch', borderRadius: 2, background: m?.hex }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 2 }}>
                    {new Date(e.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} · {e.time} · {m?.name}
                  </div>
                </div>
                <FamilyChip who={e.who} family={family} size="sm" label={false}/>
              </div>
            );
          })}
        </div>
      </div>
      <MobileTabBar active="home"/>
    </PhoneShell>
  );
}

// ─── Upload (camera) — landscape-default ──────────────────────
function MobileUpload({ orientation = 'landscape' }) {
  if (orientation === 'landscape') return <MobileUploadLandscape/>;
  return (
    <PhoneShell dark>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden',
        background: 'radial-gradient(circle at 30% 20%, #2a2520 0%, #0a0807 70%)' }}>
        <div style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center', color: '#fff', fontSize: 13 }}>
          Rotate your phone — landscape works better
        </div>
        <div style={{ position: 'absolute', inset: '160px 80px 240px', borderRadius: 14,
          border: '2px dashed rgba(255,255,255,.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(255,255,255,.55)', fontSize: 13, textAlign: 'center', padding: 20 }}>
          Tap to use portrait anyway
        </div>
        <div style={{ position: 'absolute', bottom: 70, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 36 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, background: 'rgba(255,255,255,.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="#fff" strokeWidth="1.6"/></svg>
          </div>
          <div style={{ width: 78, height: 78, borderRadius: '50%', background: '#fff',
            border: '4px solid rgba(255,255,255,.4)', boxShadow: '0 0 0 4px rgba(255,255,255,.18)' }}/>
          <div style={{ width: 44, height: 44, borderRadius: 10, background: 'rgba(255,255,255,.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 4l16 16M20 4L4 20" stroke="#fff" strokeWidth="1.6" strokeLinecap="round"/></svg>
          </div>
        </div>
        <div style={{ position: 'absolute', bottom: 36, left: 0, right: 0, textAlign: 'center', color: 'rgba(255,255,255,.6)', fontSize: 11 }}>
          Tip: brighter light = sharper handwriting
        </div>
      </div>
    </PhoneShell>
  );
}

// ─── Processing (SSE) ─────────────────────────────────────────
function MobileProcessing({ activeStage = 4, cellProgress = 7, totalCells = 15 }) {
  const stages = window.HEARTH_STAGES.slice(0, 9);
  return (
    <PhoneShell>
      <div style={{ padding: '54px 22px 18px' }}>
        <div style={{ fontSize: 12, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>Upload #42</div>
        <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 28, lineHeight: '32px', marginTop: 6, color: 'var(--ink)' }}>
          Reading your<br/>wall calendar…
        </div>
      </div>
      <div style={{ padding: '0 22px 18px' }}>
        <PhotoPlaceholder height={120} label="📷 your photo, 2048px"/>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 22px 24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {stages.map((s, i) => {
            const done = i < activeStage;
            const active = i === activeStage;
            return (
              <div key={s.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 0' }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  background: done ? 'var(--success)' : active ? 'transparent' : 'transparent',
                  border: done ? 'none' : `1.5px solid ${active ? 'var(--accent)' : 'var(--rule)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 1,
                  position: 'relative' }}>
                  {done && <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M4 12l5 5L20 6" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                  {active && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)',
                    animation: 'hpulse 1.2s ease-in-out infinite' }}/>}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: active ? 700 : 500,
                    color: active ? 'var(--ink)' : done ? 'var(--fgSoft)' : 'var(--fgSoft)',
                    textDecoration: done ? 'none' : 'none' }}>
                    {s.label}{active && s.key === 'cell_progress' ? ` · ${cellProgress} of ${totalCells}` : ''}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 1 }}>{s.hint}</div>
                  {active && (
                    <div style={{ marginTop: 8, height: 4, borderRadius: 4, background: 'var(--paperDeep)', overflow: 'hidden' }}>
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
      <style>{`@keyframes hpulse { 0%,100% { transform: scale(1); opacity: 1 } 50% { transform: scale(1.4); opacity: .55 } }`}</style>
    </PhoneShell>
  );
}

// ─── Results ──────────────────────────────────────────────────
function MobileResults({ family }) {
  const auto    = window.HEARTH_MOCK_EVENTS.filter(e => e.status === 'auto').slice(0, 6);
  const review  = window.HEARTH_MOCK_EVENTS.filter(e => e.status === 'review').slice(0, 4);
  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ padding: '54px 22px 12px' }}>
          <div style={{ fontSize: 12, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>Done</div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 30, lineHeight: '34px', marginTop: 6, color: 'var(--ink)' }}>
            Found <span style={{ color: 'var(--accent)' }}>{auto.length + review.length}</span> events.
          </div>
          <div style={{ color: 'var(--fgSoft)', marginTop: 8, fontSize: 14 }}>
            <strong style={{ color: 'var(--success)' }}>{auto.length} auto-published</strong> · <strong style={{ color: 'var(--warn)' }}>{review.length} need review</strong>
          </div>
        </div>

        <div style={{ padding: '8px 22px 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--success)' }}/>
          <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: 18, color: 'var(--ink)' }}>Auto-published</span>
          <span style={{ flex: 1, height: 1, background: 'var(--rule)' }}/>
        </div>
        <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {auto.map(e => <ResultCard key={e.id} e={e} family={family}/>)}
        </div>

        <div style={{ padding: '20px 22px 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--warn)' }}/>
          <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: 18, color: 'var(--ink)' }}>Awaiting review</span>
          <span style={{ flex: 1, height: 1, background: 'var(--rule)' }}/>
        </div>
        <div style={{ padding: '0 18px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {review.map(e => <ResultCard key={e.id} e={e} family={family} reviewable/>)}
        </div>
      </div>
      <MobileTabBar active="upload"/>
    </PhoneShell>
  );
}

function ResultCard({ e, family, reviewable }) {
  const m = (family || window.HEARTH_FAMILY_DEFAULT).find(f => f.id === e.who);
  return (
    <div style={{ padding: '12px 14px', borderRadius: 16, background: 'var(--surface)',
      border: '1px solid var(--rule)', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      {reviewable && (
        <div style={{ width: 56, height: 56, borderRadius: 10, flexShrink: 0,
          background: `repeating-linear-gradient(45deg, var(--paperDeep) 0 6px, color-mix(in oklab, var(--paperDeep) 60%, transparent) 6px 12px)`,
          border: '1px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: '"Caveat", cursive', color: m?.hex, fontSize: 16, fontWeight: 600 }}>
          {e.title.split(' ').slice(0,2).join(' ')}
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <FamilyChip who={e.who} family={family} size="sm" label={false}/>
          <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>{m?.name}</span>
          <span style={{ flex: 1 }}/>
          <ConfidenceBadge value={e.conf} status={e.status}/>
        </div>
        <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 15 }}>{e.title}</div>
        <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 2 }}>
          {new Date(e.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} · {e.time}
        </div>
        {e.note && <div style={{ marginTop: 6, padding: '6px 8px', borderRadius: 8, fontSize: 12,
          background: 'color-mix(in oklab, var(--warn) 8%, transparent)', color: 'var(--ink)',
          fontFamily: 'var(--fontMono)' }}>{e.note}</div>}
      </div>
    </div>
  );
}

// ─── Queue list ───────────────────────────────────────────────
function MobileQueue({ family }) {
  const items = window.HEARTH_MOCK_EVENTS.filter(e => e.status === 'review');
  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ padding: '54px 22px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 32, color: 'var(--ink)' }}>Review</div>
            <span style={{ fontSize: 13, color: 'var(--fgSoft)' }}>{items.length} items</span>
          </div>
          <div style={{ color: 'var(--fgSoft)', fontSize: 13, marginTop: 4 }}>
            Below 85% confidence. Tap to confirm or fix.
          </div>
        </div>
        <div style={{ padding: '0 18px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(e => <ResultCard key={e.id} e={e} family={family} reviewable/>)}
        </div>
      </div>
      <MobileTabBar active="queue"/>
    </PhoneShell>
  );
}

// ─── Review one item ──────────────────────────────────────────
function MobileReview({ family }) {
  const e = window.HEARTH_MOCK_EVENTS.find(x => x.id === 'e6');
  const m = (family || window.HEARTH_FAMILY_DEFAULT).find(f => f.id === e.who);
  return (
    <PhoneShell>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ padding: '54px 22px 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--surface)', border: '1px solid var(--rule)',
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M15 6l-6 6 6 6" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round"/></svg>
          </div>
          <span style={{ fontSize: 13, color: 'var(--fgSoft)' }}>Review · 1 of 4</span>
          <span style={{ flex: 1 }}/>
          <ConfidenceBadge value={e.conf} status="review"/>
        </div>
        <div style={{ padding: '12px 22px 18px' }}>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, color: 'var(--ink)' }}>What did the calendar say?</div>
        </div>
        {/* The actual cell crop from the photo */}
        <div style={{ margin: '0 22px 16px', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--rule)',
          background: '#FBF5E8', padding: 18, position: 'relative' }}>
          <div style={{ position: 'absolute', top: 8, left: 12, fontSize: 11, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>cell · Apr 30</div>
          <div style={{ fontFamily: '"Caveat", cursive', fontSize: 36, color: m?.hex, transform: 'rotate(-2deg)', marginTop: 14 }}>
            Pikuapk Place
          </div>
          <div style={{ fontFamily: '"Caveat", cursive', fontSize: 24, color: m?.hex, opacity: 0.85, marginLeft: 28 }}>3 pm</div>
        </div>
        <div style={{ padding: '0 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Title" value="Pikuapk Place" hint='VLM read it as "Pikuapk." Likely "Pineapple Place"?'/>
          <Field label="Who" value={m?.name} chip={<FamilyChip who={e.who} family={family} size="sm" label={false}/>}/>
          <div style={{ display: 'flex', gap: 10 }}>
            <Field label="Date" value="Thu, Apr 30" flex/>
            <Field label="Time" value="3:00 PM" flex/>
          </div>
          <Field label="Location" value="" placeholder="Add location (optional)"/>
        </div>
        <div style={{ padding: '20px 22px 30px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <HBtn kind="primary" size="lg" style={{ width: '100%' }}>Looks good — publish to Calendar</HBtn>
          <div style={{ display: 'flex', gap: 8 }}>
            <HBtn kind="ghost" style={{ flex: 1 }}>Skip</HBtn>
            <HBtn kind="danger" style={{ flex: 1 }}>Reject</HBtn>
          </div>
        </div>
      </div>
    </PhoneShell>
  );
}

function Field({ label, value, placeholder, hint, chip, flex }) {
  return (
    <div style={{ flex: flex ? 1 : undefined }}>
      <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700, marginBottom: 4 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
        borderRadius: 12, background: 'var(--surface)', border: '1px solid var(--rule)', minHeight: 44 }}>
        {chip}
        <span style={{ flex: 1, color: value ? 'var(--ink)' : 'var(--fgSoft)', fontSize: 15 }}>{value || placeholder}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8" stroke="var(--fgSoft)" strokeWidth="1.6" strokeLinecap="round"/></svg>
      </div>
      {hint && <div style={{ marginTop: 4, fontSize: 11, color: 'var(--warn)', fontFamily: 'var(--fontMono)' }}>↳ {hint}</div>}
    </div>
  );
}

Object.assign(window, { PhoneShell, MobileHome, MobileUpload, MobileUploadLandscape, MobileProcessing, MobileResults, MobileQueue, MobileReview, ResultCard, MobileTabBar });

// ─── Landscape camera (default) ──────────────────────────────
function MobileUploadLandscape() {
  // Phone rotated 90° — we render at 844×390 then rotate the wrapper.
  const W = 844, H = 390;
  return (
    <div style={{ width: H, height: W, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: W, height: H, transform: 'rotate(90deg)', transformOrigin: 'center', borderRadius: 48,
        overflow: 'hidden', position: 'relative',
        background: 'radial-gradient(circle at 50% 30%, #2a2520 0%, #0a0807 70%)',
        boxShadow: '0 30px 60px rgba(0,0,0,.18), 0 0 0 1px rgba(0,0,0,.12)',
        fontFamily: 'var(--fontBody)' }}>
        {/* dynamic island sits on the left when rotated → physical top */}
        <div style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
          width: 37, height: 126, borderRadius: 24, background: '#000', zIndex: 50 }}/>

        {/* fake calendar viewfinder — wide */}
        <div style={{ position: 'absolute', top: 38, left: 80, right: 80, bottom: 90,
          borderRadius: 12, background: '#FBF5E8',
          backgroundImage: `repeating-linear-gradient(0deg, transparent 0 38px, #d8c8a8 38px 39px),
                            repeating-linear-gradient(90deg, transparent 0 90px, #d8c8a8 90px 91px)`,
          boxShadow: 'inset 0 0 30px rgba(0,0,0,.1)',
          fontFamily: '"Caveat", cursive', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 4, left: 10, fontSize: 14, color: '#444', fontWeight: 600 }}>April 2026</div>
          <div style={{ position: 'absolute', top: 50, left: 22, color: '#2E5BA8', fontSize: 13 }}>1:1 11a</div>
          <div style={{ position: 'absolute', top: 92, left: 110, color: '#C0392B', fontSize: 13 }}>book club</div>
          <div style={{ position: 'absolute', top: 50, left: 200, color: '#7B4FB8', fontSize: 13 }}>swim 9a</div>
          <div style={{ position: 'absolute', top: 130, left: 250, color: '#D97A2C', fontSize: 13 }}>Nana →</div>
          <div style={{ position: 'absolute', top: 92, left: 380, color: '#E17AA1', fontSize: 13 }}>checkup</div>
          <div style={{ position: 'absolute', top: 130, left: 480, color: '#2E5BA8', fontSize: 13 }}>dentist 2p</div>
          <div style={{ position: 'absolute', top: 50, left: 560, color: '#D97A2C', fontSize: 13 }}>brunch 11</div>
          <div style={{ position: 'absolute', top: 170, left: 60, color: '#7B4FB8', fontSize: 13 }}>Pineapple Pl.</div>
        </div>

        {/* corner brackets */}
        {[[72,30],[760,30],[72,266],[760,266]].map(([x,y], i) => {
          const tl = i === 0, tr = i === 1, bl = i === 2;
          return <div key={i} style={{ position: 'absolute', left: x, top: y, width: 20, height: 20,
            borderTop: (tl||tr) ? '3px solid #fff' : 'none',
            borderBottom: (!tl && !tr) ? '3px solid #fff' : 'none',
            borderLeft: (tl||bl) ? '3px solid #fff' : 'none',
            borderRight: (!tl && !bl) ? '3px solid #fff' : 'none', borderRadius: 3 }}/>;
        })}

        {/* top hint bar */}
        <div style={{ position: 'absolute', top: 12, left: 0, right: 0, textAlign: 'center', color: '#fff',
          fontSize: 12, opacity: 0.85 }}>
          Align all 5 weeks inside the brackets · brighter light = sharper handwriting
        </div>

        {/* right edge: shutter + thumb + close (the rotated "bottom" of the phone) */}
        <div style={{ position: 'absolute', right: 12, top: 0, bottom: 0, width: 90,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18 }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: 'rgba(255,255,255,.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M4 4l16 16M20 4L4 20" stroke="#fff" strokeWidth="1.6" strokeLinecap="round"/></svg>
          </div>
          <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#fff',
            border: '4px solid rgba(255,255,255,.4)', boxShadow: '0 0 0 4px rgba(255,255,255,.18)' }}/>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: 'rgba(255,255,255,.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="#fff" strokeWidth="1.6"/></svg>
          </div>
        </div>

        {/* left edge: orientation toggle */}
        <div style={{ position: 'absolute', left: 60, top: 0, bottom: 0, width: 60,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
          <div style={{ width: 38, height: 38, borderRadius: 999, background: 'rgba(255,255,255,.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', border: '1.5px solid #fff' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><rect x="2" y="7" width="20" height="10" rx="2" stroke="#fff" strokeWidth="1.6"/></svg>
          </div>
          <div style={{ fontSize: 9, color: '#fff', letterSpacing: 1, textTransform: 'uppercase' }}>Landscape</div>
          <div style={{ width: 38, height: 38, borderRadius: 999,
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,.5)' }}>
            <svg width="14" height="18" viewBox="0 0 24 24" fill="none"><rect x="7" y="2" width="10" height="20" rx="2" stroke="currentColor" strokeWidth="1.6"/></svg>
          </div>
          <div style={{ fontSize: 9, color: 'rgba(255,255,255,.5)', letterSpacing: 1, textTransform: 'uppercase' }}>Portrait</div>
        </div>

        {/* home indicator (rotated, so it's a vertical line on the right) */}
        <div style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
          width: 5, height: 139, borderRadius: 100, background: 'rgba(255,255,255,.7)' }}/>
      </div>
    </div>
  );
}
