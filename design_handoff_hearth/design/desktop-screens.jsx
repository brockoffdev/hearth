// Desktop screens — Editorial calendar, Admin, Setup wizard, Login

const DesktopShell = ({ children, width = 1280, height = 800 }) => (
  <div style={{ width, height, borderRadius: 14, overflow: 'hidden',
    background: 'var(--bg)', boxShadow: '0 30px 70px rgba(0,0,0,.18), 0 0 0 1px rgba(0,0,0,.08)',
    fontFamily: 'var(--fontBody)', color: 'var(--ink)', display: 'flex', flexDirection: 'column' }}>
    {/* faux window chrome */}
    <div style={{ height: 36, background: 'var(--surfaceMuted)', display: 'flex', alignItems: 'center',
      paddingInline: 14, gap: 8, borderBottom: '1px solid var(--rule)' }}>
      <div style={{ display: 'flex', gap: 6 }}>
        {['#FF5F57','#FEBC2E','#28C840'].map(c => <span key={c} style={{ width: 11, height: 11, borderRadius: '50%', background: c }}/>)}
      </div>
      <div style={{ flex: 1, textAlign: 'center', fontSize: 12, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>
        hearth.local
      </div>
    </div>
    <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>
  </div>
);

function Sidebar({ active = 'calendar' }) {
  const items = [
    { id: 'home',     label: 'Home',           icon: 'M3 12l9-9 9 9v9a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1z' },
    { id: 'upload',   label: 'New upload',     icon: 'M12 5v14m-7-7h14' },
    { id: 'queue',    label: 'Review',         icon: 'M4 6h16M4 12h16M4 18h10', badge: 4 },
    { id: 'calendar', label: 'Calendar',       icon: 'M3 8h18M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 2v4m8-4v4' },
    { id: 'tv',       label: 'TV display',     icon: 'M3 5h18v12H3zM8 21h8M12 17v4' },
  ];
  const adminItems = [
    { id: 'family',   label: 'Family',         icon: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM1 21a8 8 0 0 1 16 0M17 8a3 3 0 1 1 0 6M23 21a6 6 0 0 0-9-5.2' },
    { id: 'users',    label: 'Users',          icon: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0' },
    { id: 'google',   label: 'Google',         icon: 'M3 12a9 9 0 1 0 9-9v9h9' },
    { id: 'settings', label: 'Settings',       icon: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.2l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z' },
  ];

  const NavItem = ({ it }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 10,
      background: active === it.id ? 'color-mix(in oklab, var(--accent) 12%, transparent)' : 'transparent',
      color: active === it.id ? 'var(--accent)' : 'var(--fgSoft)', cursor: 'default',
      fontWeight: active === it.id ? 700 : 500 }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path d={it.icon} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      <span style={{ flex: 1, fontSize: 13 }}>{it.label}</span>
      {it.badge && <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 999, background: 'var(--warn)', color: '#fff', fontWeight: 700 }}>{it.badge}</span>}
    </div>
  );

  return (
    <div style={{ width: 220, padding: '18px 14px', borderRight: '1px solid var(--rule)',
      background: 'var(--surfaceMuted)', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ padding: '4px 10px 16px' }}><HearthWordmark size={18}/></div>
      {items.map(it => <NavItem key={it.id} it={it}/>)}
      <div style={{ marginTop: 16, padding: '4px 12px', fontSize: 10, color: 'var(--fgSoft)',
        textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>Admin</div>
      {adminItems.map(it => <NavItem key={it.id} it={it}/>)}
      <div style={{ flex: 1 }}/>
      <div style={{ padding: '10px', borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--rule)',
        display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'var(--accent)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>B</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Bryant</div>
          <div style={{ fontSize: 11, color: 'var(--fgSoft)' }}>Admin</div>
        </div>
      </div>
    </div>
  );
}

// ─── Editorial calendar ───────────────────────────────────────
function DesktopCalendar({ family }) {
  const fams = family || window.HEARTH_FAMILY_DEFAULT;
  // Build month grid for April 2026 (starts Wed)
  const monthDays = Array.from({ length: 35 }, (_, i) => {
    const d = i - 2; // Apr starts on Wed (offset)
    return d >= 1 && d <= 30 ? d : null;
  });
  const events = window.HEARTH_MOCK_EVENTS;
  const today = 27;

  return (
    <DesktopShell>
      <div style={{ display: 'flex', height: '100%' }}>
        <Sidebar active="calendar"/>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* editorial title bar */}
          <div style={{ padding: '24px 36px 14px', borderBottom: '1px solid var(--rule)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 700 }}>
                Vol. IV · Issue 17
              </div>
              <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 56, lineHeight: '60px', letterSpacing: -1.5, color: 'var(--ink)' }}>
                <span style={{ fontStyle: 'italic' }}>April</span> 2026
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 4, padding: 4, borderRadius: 999, background: 'var(--surfaceMuted)', border: '1px solid var(--rule)' }}>
                {['Month','Week','Day','Agenda'].map((v,i) => (
                  <div key={v} style={{ padding: '6px 14px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                    background: i===0 ? 'var(--surface)' : 'transparent', color: i===0 ? 'var(--ink)' : 'var(--fgSoft)',
                    boxShadow: i===0 ? '0 1px 3px rgba(0,0,0,.08)' : 'none' }}>{v}</div>
                ))}
              </div>
              <HBtn>‹</HBtn><HBtn>Today</HBtn><HBtn>›</HBtn>
            </div>
          </div>

          {/* family-color legend */}
          <div style={{ padding: '12px 36px', display: 'flex', gap: 18, borderBottom: '1px solid var(--rule)' }}>
            {fams.map(f => (
              <span key={f.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: f.hex }}/>
                <span style={{ color: 'var(--fgSoft)' }}>{f.name}</span>
              </span>
            ))}
          </div>

          {/* month grid */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
              borderTop: 'none', fontFamily: 'var(--fontBody)' }}>
              {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
                <div key={d} style={{ padding: '10px 12px', fontSize: 11, color: 'var(--fgSoft)',
                  textTransform: 'uppercase', letterSpacing: 0.8, fontWeight: 700,
                  borderRight: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)' }}>{d}</div>
              ))}
              {monthDays.map((d, i) => {
                const dayEvents = d ? events.filter(e => parseInt(e.date.split('-')[2], 10) === d) : [];
                const isToday = d === today;
                return (
                  <div key={i} style={{ minHeight: 110, padding: '8px 10px',
                    borderRight: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)',
                    background: isToday ? 'color-mix(in oklab, var(--accent) 7%, transparent)' : (d ? 'var(--surface)' : 'var(--surfaceMuted)'),
                    position: 'relative' }}>
                    {d && (
                      <>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: isToday ? 22 : 18, fontWeight: isToday ? 700 : 500,
                            color: isToday ? 'var(--accent)' : 'var(--ink)' }}>{d}</span>
                          {isToday && <span style={{ fontSize: 9, fontWeight: 800, color: 'var(--accent)', letterSpacing: 0.8,
                            textTransform: 'uppercase', padding: '2px 6px', borderRadius: 999,
                            background: 'color-mix(in oklab, var(--accent) 18%, transparent)' }}>Today</span>}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          {dayEvents.slice(0, 3).map(e => {
                            const m = fams.find(f => f.id === e.who);
                            return (
                              <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 6,
                                fontSize: 11, padding: '2px 6px', borderRadius: 5,
                                background: `color-mix(in oklab, ${m?.hex} 14%, transparent)`,
                                color: m?.hex, fontWeight: 600 }}>
                                <span style={{ fontFamily: 'var(--fontMono)', fontSize: 9, opacity: 0.7 }}>{e.time}</span>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--ink)' }}>{e.title}</span>
                              </div>
                            );
                          })}
                          {dayEvents.length > 3 && <div style={{ fontSize: 10, color: 'var(--fgSoft)', paddingLeft: 6 }}>+{dayEvents.length - 3} more</div>}
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}

// ─── Setup wizard step 2 (Google) ─────────────────────────────
function SetupGoogle() {
  return (
    <DesktopShell width={1100} height={780}>
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <div style={{ width: 760, padding: 40 }}>
          {/* breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 26 }}>
            <HearthWordmark size={16}/>
            <span style={{ flex: 1 }}/>
            {[{n:1, l:'Account', done:true}, {n:2, l:'Google', active:true}, {n:3, l:'Family', upcoming:true}].map((s, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span style={{ width: 24, height: 1, background: 'var(--rule)' }}/>}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 24, height: 24, borderRadius: '50%',
                    background: s.done ? 'var(--success)' : s.active ? 'var(--accent)' : 'var(--surface)',
                    color: s.upcoming ? 'var(--fgSoft)' : '#fff', fontSize: 12, fontWeight: 700,
                    border: s.upcoming ? '1px solid var(--rule)' : 'none',
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                    {s.done ? '✓' : s.n}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: s.active ? 700 : 500,
                    color: s.active ? 'var(--ink)' : 'var(--fgSoft)' }}>{s.l}</span>
                </div>
              </React.Fragment>
            ))}
          </div>

          <div style={{ fontSize: 12, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 1, fontWeight: 700 }}>
            Step 2 of 3
          </div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 42, lineHeight: '46px', letterSpacing: -0.8, marginTop: 6 }}>
            Connect to <span style={{ fontStyle: 'italic' }}>Google Calendar</span>
          </div>
          <div style={{ color: 'var(--fgSoft)', fontSize: 14, marginTop: 10, maxWidth: 560 }}>
            Hearth pushes confirmed events to one Google account. You'll need OAuth credentials from Google Cloud — about 5 minutes if it's your first time.
            <span style={{ color: 'var(--accent)', textDecoration: 'underline', marginLeft: 6 }}>Read the setup guide ↗</span>
          </div>

          <div style={{ marginTop: 28, padding: 24, borderRadius: 16, background: 'var(--surface)', border: '1px solid var(--rule)' }}>
            <div style={{ fontWeight: 700, marginBottom: 14, fontSize: 14 }}>Paste your OAuth credentials</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Input label="Client ID" value="123456789012-abc8s9d0...apps.googleusercontent.com" mono/>
              <Input label="Client Secret" value="GOCSPX-•••••••••••••••••••••" mono/>
              <div style={{ fontSize: 11, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>
                Authorized redirect URI: http://hearth.local/api/google/oauth/callback
              </div>
            </div>
          </div>

          <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: 1, color: 'var(--fgSoft)', fontSize: 13 }}>Saved locally — only the admin can read these.</span>
            <HBtn>Back</HBtn>
            <HBtn kind="primary" size="lg">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                Continue with Google
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12h14m-6-6l6 6-6 6" stroke="#fff" strokeWidth="2" strokeLinecap="round"/></svg>
              </span>
            </HBtn>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}

function Input({ label, value, mono }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700, marginBottom: 4 }}>{label}</div>
      <div style={{ padding: '10px 12px', borderRadius: 10, background: 'var(--bg)', border: '1px solid var(--rule)',
        fontFamily: mono ? 'var(--fontMono)' : 'var(--fontBody)', fontSize: mono ? 12 : 14, color: 'var(--ink)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</div>
    </div>
  );
}

// ─── Admin: family ────────────────────────────────────────────
function AdminFamily({ family }) {
  const fams = family || window.HEARTH_FAMILY_DEFAULT;
  return (
    <DesktopShell>
      <div style={{ display: 'flex', height: '100%' }}>
        <Sidebar active="family"/>
        <div style={{ flex: 1, padding: 36, overflow: 'auto' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 1, fontWeight: 700 }}>Admin</div>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 38, lineHeight: '42px', letterSpacing: -0.8, marginTop: 4 }}>
              Family<span style={{ fontStyle: 'italic', color: 'var(--accent)' }}> & ink</span>
            </div>
            <div style={{ color: 'var(--fgSoft)', fontSize: 14, marginTop: 6 }}>
              Map each marker color to the right person — and to a Google Calendar.
            </div>
          </div>

          <div style={{ borderRadius: 14, background: 'var(--surface)', border: '1px solid var(--rule)', overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr 1.2fr 1.2fr 1.4fr 60px',
              padding: '12px 18px', fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase',
              letterSpacing: 0.6, fontWeight: 700, borderBottom: '1px solid var(--rule)', background: 'var(--surfaceMuted)' }}>
              <span>Color</span><span>Name</span><span>Hue range</span><span>Calendar</span><span>Last seen</span><span></span>
            </div>
            {fams.map((f, i) => (
              <div key={f.id} style={{ display: 'grid', gridTemplateColumns: '60px 1fr 1.2fr 1.2fr 1.4fr 60px',
                padding: '14px 18px', alignItems: 'center', borderBottom: i < fams.length - 1 ? '1px solid var(--rule)' : 'none' }}>
                <div style={{ width: 26, height: 26, borderRadius: 7, background: f.hex,
                  boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.4)' }}/>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{f.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--fgSoft)' }}>{f.role}</div>
                </div>
                <div style={{ fontFamily: 'var(--fontMono)', fontSize: 12, color: 'var(--fgSoft)' }}>
                  H {f.hex.toLowerCase()} · ±15°
                </div>
                <div style={{ fontSize: 13 }}>
                  <span style={{ padding: '4px 10px', borderRadius: 999, background: 'color-mix(in oklab, var(--success) 14%, transparent)',
                    color: 'var(--success)', fontSize: 11, fontWeight: 700 }}>✓ {f.name.toLowerCase()}@google</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--fgSoft)' }}>2 events · today</div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ color: 'var(--fgSoft)', fontSize: 18, padding: '0 6px' }}>···</span>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <HBtn kind="primary">+ Add family member</HBtn>
            <HBtn>Re-detect colors from a recent photo</HBtn>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}

// ─── Admin: settings (provider) ───────────────────────────────
function AdminSettings({ provider = 'ollama', threshold = 85 }) {
  return (
    <DesktopShell>
      <div style={{ display: 'flex', height: '100%' }}>
        <Sidebar active="settings"/>
        <div style={{ flex: 1, padding: 36, overflow: 'auto' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 1, fontWeight: 700 }}>Admin</div>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 38, lineHeight: '42px', letterSpacing: -0.8, marginTop: 4 }}>
              Settings
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Provider */}
            <Card title="Vision provider" subtitle="How Hearth reads handwriting">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { id: 'ollama',    name: 'Ollama (local)',     model: 'qwen2.5-vl:7b',  cost: 'Free · ~6 GB peak' },
                  { id: 'gemini',    name: 'Google Gemini',      model: 'gemini-2.5-flash', cost: '~$0.001/photo' },
                  { id: 'anthropic', name: 'Anthropic Claude',   model: 'claude-haiku-4-5', cost: '~$0.003/photo' },
                ].map(p => (
                  <label key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 12,
                    padding: '12px 14px', borderRadius: 12, cursor: 'pointer',
                    background: provider === p.id ? 'color-mix(in oklab, var(--accent) 8%, transparent)' : 'var(--surface)',
                    border: `1px solid ${provider === p.id ? 'var(--accent)' : 'var(--rule)'}` }}>
                    <span style={{ width: 16, height: 16, borderRadius: '50%',
                      border: `2px solid ${provider === p.id ? 'var(--accent)' : 'var(--rule)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {provider === p.id && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }}/>}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                      <div style={{ fontSize: 12, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>{p.model}</div>
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--fgSoft)' }}>{p.cost}</span>
                  </label>
                ))}
              </div>
              {provider === 'ollama' && (
                <div style={{ marginTop: 12, padding: 12, borderRadius: 10, background: 'var(--surfaceMuted)',
                  fontFamily: 'var(--fontMono)', fontSize: 12, color: 'var(--fgSoft)' }}>
                  ROCm 6.0 detected · Radeon 780M · keep_alive=0 (lazy unload)
                </div>
              )}
              {provider !== 'ollama' && (
                <div style={{ marginTop: 12 }}>
                  <Input label="API key" value="sk-ant-•••••••••••••••••••••••••••" mono/>
                </div>
              )}
            </Card>

            {/* Confidence */}
            <Card title="Confidence threshold" subtitle="Above this auto-publishes; below queues for review">
              <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 56, lineHeight: '60px', color: 'var(--accent)' }}>{threshold}%</div>
              <div style={{ marginTop: 10, height: 6, borderRadius: 4, background: 'var(--surfaceMuted)', position: 'relative' }}>
                <div style={{ width: `${threshold}%`, height: '100%', borderRadius: 4, background: 'var(--accent)' }}/>
                <div style={{ position: 'absolute', top: -6, left: `calc(${threshold}% - 9px)`, width: 18, height: 18, borderRadius: '50%',
                  background: '#fff', border: '2px solid var(--accent)', boxShadow: '0 2px 6px rgba(0,0,0,.15)' }}/>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--fgSoft)', fontFamily: 'var(--fontMono)' }}>
                <span>50% lenient</span><span>95% strict</span>
              </div>
              <div style={{ marginTop: 16, fontSize: 12, color: 'var(--fgSoft)' }}>
                On the last 50 events: <strong style={{ color: 'var(--ink)' }}>38 auto-published</strong>, 12 queued.
              </div>
            </Card>

            <Card title="Few-shot learning" subtitle="Recent corrections sent with each prompt">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 14 }}>Examples per prompt</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <HBtn size="sm">−</HBtn><span style={{ fontFamily: 'var(--fontMono)', fontWeight: 600, minWidth: 30, textAlign: 'center' }}>10</span><HBtn size="sm">+</HBtn>
                </div>
              </div>
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--fgSoft)' }}>
                Most recent correction: <em>"Pikuapk → Pineapple"</em> (3 days ago)
              </div>
            </Card>

            <Card title="Performance" subtitle="Local inference">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <Stat label="Avg time / photo" value="2m 18s"/>
                <Stat label="Resident RAM" value="0 GB"/>
                <Stat label="Photos this week" value="2"/>
                <Stat label="Accuracy (rolling)" value="84%"/>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <div style={{ padding: 22, borderRadius: 14, background: 'var(--surface)', border: '1px solid var(--rule)' }}>
      <div style={{ fontWeight: 700, fontSize: 14 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 12, color: 'var(--fgSoft)', marginTop: 2, marginBottom: 14 }}>{subtitle}</div>}
      {children}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>{label}</div>
      <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 26, color: 'var(--ink)', marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ─── Login ────────────────────────────────────────────────────
function DesktopLogin() {
  return (
    <DesktopShell width={1100} height={720}>
      <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <div style={{ padding: 50, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          background: 'linear-gradient(135deg, var(--paperDeep), var(--paper))' }}>
          <HearthWordmark size={20}/>
          <div>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 56, lineHeight: '58px', letterSpacing: -1.5, color: 'var(--ink)' }}>
              The wall<br/>
              <span style={{ fontStyle: 'italic', color: 'var(--accent)' }}>calendar,</span><br/>
              everywhere.
            </div>
            <div style={{ marginTop: 18, color: 'var(--fgSoft)', fontSize: 15, maxWidth: 380 }}>
              Snap a photo of your family's whiteboard. Hearth reads the handwriting, sorts events by who wrote them, and pushes everything to Google Calendar.
            </div>
          </div>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 11, color: 'var(--fgSoft)' }}>
            v0.1.0 · self-hosted · LAN-only by default
          </div>
        </div>
        <div style={{ padding: 50, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--fgSoft)', textTransform: 'uppercase', letterSpacing: 1 }}>Sign in</div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 36, marginTop: 6, marginBottom: 24 }}>Welcome back</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 380 }}>
            <Input label="Username" value="bryant"/>
            <Input label="Password" value="•••••••••••" mono/>
            <HBtn kind="primary" size="lg" style={{ marginTop: 10 }}>Sign in</HBtn>
            <div style={{ fontSize: 12, color: 'var(--fgSoft)', textAlign: 'center', marginTop: 6 }}>
              Forgot? Ask your admin to reset.
            </div>
          </div>
        </div>
      </div>
    </DesktopShell>
  );
}

Object.assign(window, { DesktopShell, DesktopCalendar, SetupGoogle, AdminFamily, AdminSettings, DesktopLogin, Sidebar });
