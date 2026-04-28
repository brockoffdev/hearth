// Hearth shared UI primitives — chips, buttons, badges, calendar grid placeholder

// Family-color chip
function FamilyChip({ who, family, size = 'md', label = true }) {
  const m = (family || window.HEARTH_FAMILY_DEFAULT).find(f => f.id === who) || {};
  const sz = size === 'sm' ? 18 : size === 'lg' ? 28 : 22;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        width: sz, height: sz, borderRadius: 999, background: m.hex,
        boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,.4), 0 1px 2px rgba(0,0,0,.15)',
        flexShrink: 0,
      }} />
      {label && <span style={{ fontSize: size === 'sm' ? 12 : 13, color: 'var(--fgSoft)', fontWeight: 500 }}>{m.name}</span>}
    </span>
  );
}

function ConfidenceBadge({ value, status }) {
  const pct = Math.round(value * 100);
  const color = status === 'auto' ? 'var(--success)' : status === 'review' ? 'var(--warn)' : 'var(--inkSoft)';
  const bg    = status === 'auto' ? 'color-mix(in oklab, var(--success) 14%, transparent)'
              : status === 'review' ? 'color-mix(in oklab, var(--warn) 14%, transparent)'
              : 'color-mix(in oklab, var(--inkSoft) 12%, transparent)';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 9px', borderRadius: 999, background: bg, color,
      fontSize: 11, fontWeight: 600, letterSpacing: 0.4,
      fontFamily: 'var(--fontMono)',
    }}>
      {status === 'auto' ? '✓' : status === 'review' ? '!' : '–'} {pct}%
    </span>
  );
}

function HBtn({ children, kind = 'default', size = 'md', onClick, style }) {
  const pad = size === 'lg' ? '14px 22px' : size === 'sm' ? '6px 12px' : '10px 16px';
  const fs  = size === 'lg' ? 16 : size === 'sm' ? 13 : 14;
  const map = {
    primary: { bg: 'var(--accent)', fg: '#fff', bd: 'var(--accent)' },
    ghost:   { bg: 'transparent', fg: 'var(--ink)', bd: 'var(--rule)' },
    default: { bg: 'var(--surface)', fg: 'var(--ink)', bd: 'var(--rule)' },
    danger:  { bg: 'transparent', fg: 'var(--danger)', bd: 'color-mix(in oklab, var(--danger) 30%, transparent)' },
  };
  const k = map[kind];
  return (
    <button onClick={onClick} style={{
      padding: pad, fontSize: fs, fontFamily: 'var(--fontBody)', fontWeight: 600,
      background: k.bg, color: k.fg, border: `1px solid ${k.bd}`,
      borderRadius: 999, cursor: 'pointer', letterSpacing: -0.1,
      transition: 'transform .08s, filter .12s', ...style,
    }}>{children}</button>
  );
}

// Wordmark — flame-arch glyph + "hearth"
function HearthMark({ size = 22, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      {/* Hearth arch */}
      <path d="M3 21V11a9 9 0 0 1 18 0v10" stroke={color} strokeWidth="1.6" strokeLinecap="round"/>
      <path d="M3 21h18" stroke={color} strokeWidth="1.6" strokeLinecap="round"/>
      {/* Flame inside */}
      <path d="M12 18c2.2 0 4-1.7 4-3.8 0-1.6-1-2.4-1.8-3.4-.7-.9-.7-2-.7-2.8 0 0-1 .6-1.6 1.7-.6 1-.4 2-.4 2-1.2-.5-1.5-1.7-1.5-1.7s-2 1.6-2 4.1c0 2.1 1.8 3.9 4 3.9z"
        fill={color}/>
    </svg>
  );
}

function HearthWordmark({ size = 18, color = 'var(--ink)' }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color }}>
      <HearthMark size={size + 4} color={color}/>
      <span style={{ fontFamily: 'var(--fontDisplay)', fontSize: size + 4, fontWeight: 500, letterSpacing: -0.3 }}>hearth</span>
    </span>
  );
}

// Subtle striped placeholder for "imagine a photo of the wall calendar here"
function PhotoPlaceholder({ width = '100%', height = 240, label = 'Wall calendar photo' }) {
  return (
    <div style={{
      width, height, position: 'relative', overflow: 'hidden',
      borderRadius: 12, border: '1px solid var(--rule)',
      background: `repeating-linear-gradient(135deg,
        var(--paperDeep) 0 12px,
        color-mix(in oklab, var(--paperDeep) 70%, transparent) 12px 24px)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <span style={{
        fontFamily: 'var(--fontMono)', fontSize: 11, color: 'var(--fgSoft)',
        background: 'var(--bg)', padding: '4px 10px', borderRadius: 999,
        border: '1px solid var(--rule)', letterSpacing: 0.4,
      }}>{label}</span>
    </div>
  );
}

// A "calendar cell" mock that looks like marker handwriting
function HandwrittenCell({ entries = [], date, isToday, accent }) {
  return (
    <div style={{
      position: 'relative', minHeight: 84, padding: '6px 8px',
      borderRight: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)',
      background: isToday ? 'color-mix(in oklab, var(--accent) 7%, transparent)' : 'transparent',
    }}>
      <div style={{
        fontFamily: 'var(--fontDisplay)', fontSize: 13, color: isToday ? 'var(--accent)' : 'var(--fgSoft)',
        fontWeight: isToday ? 700 : 400,
      }}>{date}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
        {entries.map((e, i) => (
          <div key={i} style={{
            fontFamily: '"Caveat", "Patrick Hand", cursive', fontSize: 14, lineHeight: '16px',
            color: e.color, fontWeight: 600,
          }}>
            {e.time && <span style={{ fontSize: 11, marginRight: 4, opacity: 0.85 }}>{e.time}</span>}
            {e.text}
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { FamilyChip, ConfidenceBadge, HBtn, HearthMark, HearthWordmark, PhotoPlaceholder, HandwrittenCell });
