// TV mode — three layouts (editorial / minimal / info-dense), landscape + portrait

function TVShell({ children, width = 1280, height = 720, dark = true, portrait = false }) {
  if (portrait) { width = 540; height = 960; }
  return (
    <div style={{ width, height, position: 'relative', overflow: 'hidden',
      background: dark ? '#0F0D0B' : 'var(--paper)', color: dark ? '#F4EEE3' : 'var(--ink)',
      fontFamily: 'var(--fontBody)',
      borderRadius: 6, boxShadow: '0 30px 60px rgba(0,0,0,.3), 0 0 0 8px #1a1815, 0 0 0 9px #2a2724' }}>
      {children}
      <div style={{ position: 'absolute', top: 14, right: 14, width: 8, height: 8, borderRadius: '50%',
        background: 'var(--success)', boxShadow: '0 0 8px var(--success)', opacity: 0.6 }}/>
    </div>
  );
}

const TODAYS_EVENTS_BY_PERSON = {
  bryant:   [{t:'08:30', title:'1:1 with Maya'}, {t:'14:00', title:'Dentist'}, {t:'18:00', title:'Pickup Izzy'}],
  danielle: [{t:'09:00', title:'Yoga'},          {t:'13:30', title:'Studio time'}, {t:'19:00', title:'Book club'}],
  isabella: [{t:'08:30', title:'Preschool'},     {t:'15:00', title:'Park w/ Lila'}, {t:'17:30', title:'Family dinner'}],
  eliana:   [{t:'10:15', title:'Pediatrician'},  {t:'12:30', title:'Nap'},        {t:'17:30', title:'Family dinner'}],
  family:   [{t:'17:30', title:'Dinner — Nana'}, {t:'19:30', title:'Movie night'}, {t:'—',     title:'Sat: brunch'}, {t:'—', title:'May 10: Mother\u2019s Day'}, {t:'Jul 15', title:'Izzy turns 4'}],
};

function ClockDate() {
  return { time: '7:42', period: 'AM', day: 'Monday', date: 'April 27' };
}

// ─── Layout A — Editorial / magazine ───────────────────────────
function TVEditorial({ family, portrait = false }) {
  const fams = family || window.HEARTH_FAMILY_DEFAULT;
  const now = ClockDate();
  return (
    <TVShell dark portrait={portrait}>
      <div style={{ height: '100%', padding: portrait ? '32px 32px 24px' : '40px 56px 32px',
        display: 'flex', flexDirection: 'column' }}>
        {/* masthead */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          paddingBottom: 16, borderBottom: '1.5px solid rgba(244,238,227,.18)' }}>
          <div>
            <div style={{ fontFamily: 'var(--fontMono)', fontSize: 11, letterSpacing: 2, opacity: 0.55, textTransform: 'uppercase' }}>
              The Brock Family · Vol. IV · No. 117
            </div>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: portrait ? 64 : 88, lineHeight: '0.95', letterSpacing: -2, marginTop: 8 }}>
              <span style={{ fontStyle: 'italic' }}>Monday,</span><br/>April 27.
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: portrait ? 70 : 96, lineHeight: 1, letterSpacing: -3 }}>
              {now.time}<span style={{ fontSize: portrait ? 28 : 36, opacity: 0.5, marginLeft: 6 }}>{now.period}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 16, marginTop: 8, fontSize: 14, opacity: 0.7 }}>
              <span>☀ 64°F · sunny</span><span>·</span><span>Hi 72° · Lo 51°</span>
            </div>
          </div>
        </div>

        {/* lede */}
        <div style={{ padding: '20px 0 24px', borderBottom: '1px solid rgba(244,238,227,.12)', display: 'flex', gap: 24, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'var(--fontMono)', fontSize: 11, letterSpacing: 1.5, opacity: 0.5, textTransform: 'uppercase' }}>Today's headline</div>
            <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: portrait ? 28 : 36, lineHeight: 1.1, marginTop: 6, maxWidth: 720 }}>
              <span style={{ fontStyle: 'italic', color: '#D97A2C' }}>Family dinner</span> at 5:30 — <br/>Nana visits, <span style={{ opacity: 0.65 }}>everyone home by 5.</span>
            </div>
          </div>
          {!portrait && (
            <div style={{ minWidth: 160, textAlign: 'right' }}>
              <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 56, lineHeight: 1, letterSpacing: -1 }}>14</div>
              <div style={{ fontSize: 12, opacity: 0.6, marginTop: 4 }}>events this week</div>
            </div>
          )}
        </div>

        {/* per-person columns */}
        <div style={{ flex: 1, display: 'grid',
          gridTemplateColumns: portrait ? '1fr 1fr' : `repeat(${fams.length}, 1fr)`,
          gridTemplateRows: portrait ? 'repeat(3, auto)' : 'auto', gap: portrait ? 16 : 20, paddingTop: 24, overflow: 'hidden' }}>
          {fams.map(f => {
            const events = TODAYS_EVENTS_BY_PERSON[f.id] || [];
            return (
              <div key={f.id} style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 10,
                  borderBottom: `2px solid ${f.hex}` }}>
                  <span style={{ width: 14, height: 14, borderRadius: '50%', background: f.hex }}/>
                  <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: portrait ? 22 : 26, lineHeight: 1 }}>{f.name}</span>
                </div>
                <div style={{ paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {events.slice(0, f.id === 'family' ? 5 : 3).map((e, i) => (
                    <div key={i}>
                      <div style={{ fontFamily: 'var(--fontMono)', fontSize: 12, letterSpacing: 1, opacity: 0.55 }}>{e.t}</div>
                      <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: portrait ? 18 : 21, lineHeight: 1.15, marginTop: 2 }}>{e.title}</div>
                    </div>
                  ))}
                  {events.length === 0 && <div style={{ opacity: 0.35, fontStyle: 'italic', fontSize: 14 }}>Nothing on the wall.</div>}
                </div>
              </div>
            );
          })}
        </div>

        {/* page indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 18, borderTop: '1px solid rgba(244,238,227,.12)', marginTop: 12 }}>
          <span style={{ fontFamily: 'var(--fontMono)', fontSize: 10, letterSpacing: 1.5, opacity: 0.45, textTransform: 'uppercase' }}>Now showing</span>
          {['Day','Week','Month','Coming up'].map((p, i) => (
            <span key={p} style={{ padding: '3px 10px', borderRadius: 999,
              background: i === 0 ? 'rgba(244,238,227,.18)' : 'transparent',
              fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
              color: i === 0 ? '#fff' : 'rgba(244,238,227,.4)' }}>{p}</span>
          ))}
          <span style={{ flex: 1 }}/>
          <span style={{ fontFamily: 'var(--fontMono)', fontSize: 10, opacity: 0.4 }}>refreshes every 5 min · cycles every 20s</span>
        </div>
      </div>
    </TVShell>
  );
}

// ─── Layout B — Minimal / poster ───────────────────────────────
function TVMinimal({ family }) {
  const fams = family || window.HEARTH_FAMILY_DEFAULT;
  const now = ClockDate();
  return (
    <TVShell dark>
      <div style={{ height: '100%', padding: '60px 80px', display: 'grid',
        gridTemplateColumns: '1.4fr 1fr', gap: 60, alignItems: 'center' }}>
        <div>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 12, letterSpacing: 3, opacity: 0.4, textTransform: 'uppercase' }}>
            {now.day}
          </div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 220, lineHeight: '0.9', letterSpacing: -10, marginTop: 12 }}>
            27.
          </div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 38, marginTop: 18, fontStyle: 'italic', opacity: 0.75 }}>
            April · Two thousand twenty-six
          </div>
          <div style={{ display: 'flex', gap: 28, marginTop: 36, paddingTop: 20, borderTop: '1px solid rgba(244,238,227,.14)' }}>
            <Stat2 label="Now" value={`${now.time} ${now.period}`}/>
            <Stat2 label="Outside" value="64° sunny"/>
            <Stat2 label="On the wall" value="14 events"/>
          </div>
        </div>
        <div>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 12, letterSpacing: 3, opacity: 0.4, textTransform: 'uppercase', marginBottom: 16 }}>
            Up next today
          </div>
          {[
            { who: 'isabella', t: '8:30', title: 'Preschool drop-off' },
            { who: 'eliana',   t: '10:15', title: 'Pediatrician' },
            { who: 'bryant',   t: '14:00', title: 'Dentist' },
            { who: 'family',   t: '17:30', title: 'Dinner — Nana' },
          ].map((e, i) => {
            const m = fams.find(f => f.id === e.who);
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16,
                padding: '14px 0', borderBottom: '1px solid rgba(244,238,227,.1)' }}>
                <div style={{ fontFamily: 'var(--fontMono)', fontSize: 13, opacity: 0.55, minWidth: 56, letterSpacing: 0.5 }}>{e.t}</div>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: m?.hex }}/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, lineHeight: 1.1 }}>{e.title}</div>
                  <div style={{ fontSize: 12, opacity: 0.5, marginTop: 1 }}>{m?.name}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </TVShell>
  );
}

function Stat2({ label, value }) {
  return (
    <div>
      <div style={{ fontFamily: 'var(--fontMono)', fontSize: 10, letterSpacing: 1.5, opacity: 0.45, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 22, marginTop: 4 }}>{value}</div>
    </div>
  );
}

// ─── Layout C — Info-dense / dashboard ─────────────────────────
function TVDense({ family }) {
  const fams = family || window.HEARTH_FAMILY_DEFAULT;
  const now = ClockDate();
  // 7-day strip
  const days = [
    { d: 27, lbl: 'Mon', today: true,  events: 4 },
    { d: 28, lbl: 'Tue', events: 3 },
    { d: 29, lbl: 'Wed', events: 2 },
    { d: 30, lbl: 'Thu', events: 4 },
    { d:  1, lbl: 'Fri', events: 3 },
    { d:  2, lbl: 'Sat', events: 5 },
    { d:  3, lbl: 'Sun', events: 1 },
  ];
  return (
    <TVShell dark>
      <div style={{ height: '100%', padding: 32, display: 'grid',
        gridTemplateColumns: '1.6fr 1fr', gridTemplateRows: 'auto 1fr', gap: 18 }}>
        {/* header strip */}
        <div style={{ gridColumn: '1 / 3', display: 'flex', alignItems: 'center', gap: 24, paddingBottom: 14, borderBottom: '1px solid rgba(244,238,227,.12)' }}>
          <HearthMark size={28} color="#D97A2C"/>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 30, lineHeight: 1 }}>
            <span style={{ fontStyle: 'italic' }}>Mon</span> Apr 27
          </div>
          <span style={{ flex: 1 }}/>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 13, opacity: 0.6 }}>☀ 64° · Hi 72° · Lo 51° · Sunset 7:51 PM</div>
          <div style={{ fontFamily: 'var(--fontDisplay)', fontSize: 36, lineHeight: 1, letterSpacing: -1 }}>
            {now.time}<span style={{ fontSize: 14, opacity: 0.5, marginLeft: 4 }}>{now.period}</span>
          </div>
        </div>

        {/* 7-day strip */}
        <div style={{ gridColumn: '1 / 3', display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6 }}>
          {days.map(d => (
            <div key={d.d} style={{ padding: '10px 12px', borderRadius: 10,
              background: d.today ? 'rgba(217,122,44,.18)' : 'rgba(244,238,227,.04)',
              border: `1px solid ${d.today ? 'rgba(217,122,44,.5)' : 'rgba(244,238,227,.06)'}` }}>
              <div style={{ fontFamily: 'var(--fontMono)', fontSize: 10, letterSpacing: 1, opacity: 0.6, textTransform: 'uppercase' }}>{d.lbl}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 4 }}>
                <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: 26, lineHeight: 1, color: d.today ? '#D97A2C' : '#fff' }}>{d.d}</span>
                <span style={{ fontSize: 11, opacity: 0.55 }}>{d.events} events</span>
              </div>
              <div style={{ display: 'flex', gap: 3, marginTop: 8 }}>
                {Array.from({length: d.events}).map((_, i) => (
                  <span key={i} style={{ width: 6, height: 6, borderRadius: '50%',
                    background: fams[i % fams.length].hex, opacity: 0.85 }}/>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* main today list */}
        <div style={{ background: 'rgba(244,238,227,.04)', borderRadius: 12, padding: 20, overflow: 'hidden',
          border: '1px solid rgba(244,238,227,.06)' }}>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 11, letterSpacing: 2, opacity: 0.5, textTransform: 'uppercase', marginBottom: 14 }}>Today's lineup</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { t: '8:30',  who: 'isabella', title: 'Preschool drop-off' },
              { t: '9:00',  who: 'danielle', title: 'Yoga' },
              { t: '10:15', who: 'eliana',   title: 'Pediatrician' },
              { t: '11:00', who: 'bryant',   title: '1:1 with Maya' },
              { t: '14:00', who: 'bryant',   title: 'Dentist' },
              { t: '15:00', who: 'isabella', title: 'Park w/ Lila' },
              { t: '17:30', who: 'family',   title: 'Dinner — Nana' },
              { t: '19:00', who: 'danielle', title: 'Book club' },
            ].map((e, i) => {
              const m = fams.find(f => f.id === e.who);
              const past = i < 1;
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14,
                  padding: '8px 12px', borderRadius: 8, opacity: past ? 0.4 : 1,
                  background: m && i === 1 ? `color-mix(in oklab, ${m.hex} 12%, transparent)` : 'transparent' }}>
                  <div style={{ fontFamily: 'var(--fontMono)', fontSize: 13, opacity: 0.7, minWidth: 50 }}>{e.t}</div>
                  <div style={{ width: 4, height: 22, borderRadius: 2, background: m?.hex }}/>
                  <div style={{ flex: 1, fontFamily: 'var(--fontDisplay)', fontSize: 18 }}>{e.title}</div>
                  <div style={{ fontSize: 11, opacity: 0.5 }}>{m?.name}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* who's doing what */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontFamily: 'var(--fontMono)', fontSize: 11, letterSpacing: 2, opacity: 0.5, textTransform: 'uppercase' }}>Who's where, now</div>
          {fams.map(f => {
            const status = {
              bryant:   { now: 'At work · Q2 review', next: 'Dentist 2 PM' },
              danielle: { now: 'Yoga · 9 AM',        next: 'Studio 1:30 PM' },
              isabella: { now: 'Preschool · until 2:30', next: 'Park w/ Lila 3 PM' },
              eliana:   { now: 'Home · with Nana',  next: 'Pediatrician 10:15' },
              family:   { now: '—',                  next: 'Dinner 5:30' },
            }[f.id] || {};
            return (
              <div key={f.id} style={{ padding: 12, borderRadius: 10, background: 'rgba(244,238,227,.04)',
                borderLeft: `3px solid ${f.hex}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: 16 }}>{f.name}</span>
                  <span style={{ flex: 1 }}/>
                  <span style={{ fontFamily: 'var(--fontMono)', fontSize: 10, opacity: 0.5 }}>{status.now}</span>
                </div>
                <div style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>↳ {status.next}</div>
              </div>
            );
          })}
        </div>
      </div>
    </TVShell>
  );
}

Object.assign(window, { TVShell, TVEditorial, TVMinimal, TVDense });
