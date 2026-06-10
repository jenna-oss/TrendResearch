// ÉCLAT — UI primitives, icons, and material "plate" placeholders
// Loaded as text/babel. Exports to window.

const { useState: _uiUseState } = React;

// --- Line icons (UI affordances) --------------------------------------
function Icon({ name, size = 16, stroke = 1.6, style }) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: stroke,
    strokeLinecap: "round", strokeLinejoin: "round", style,
  };
  switch (name) {
    case "arrow-right": return (<svg {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="13 6 19 12 13 18"/></svg>);
    case "arrow-left": return (<svg {...p}><line x1="19" y1="12" x2="5" y2="12"/><polyline points="11 6 5 12 11 18"/></svg>);
    case "up": return (<svg {...p}><polyline points="6 14 12 8 18 14"/></svg>);
    case "down": return (<svg {...p}><polyline points="6 10 12 16 18 10"/></svg>);
    case "search": return (<svg {...p}><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>);
    case "grid": return (<svg {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>);
    case "list": return (<svg {...p}><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3.5" cy="6" r="0.6" fill="currentColor"/><circle cx="3.5" cy="12" r="0.6" fill="currentColor"/><circle cx="3.5" cy="18" r="0.6" fill="currentColor"/></svg>);
    case "layers": return (<svg {...p}><polygon points="12 3 21 8 12 13 3 8 12 3"/><polyline points="3 13 12 18 21 13"/></svg>);
    case "compass": return (<svg {...p}><circle cx="12" cy="12" r="9"/><polygon points="15.5 8.5 11 11 8.5 15.5 13 13 15.5 8.5"/></svg>);
    case "archive": return (<svg {...p}><rect x="3" y="4" width="18" height="4"/><path d="M5 8v11h14V8"/><line x1="10" y1="12" x2="14" y2="12"/></svg>);
    case "dot": return (<svg {...p}><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/></svg>);
    case "quote": return (<svg {...p}><path d="M7 7h4v4c0 2.5-1.5 4-4 4.5"/><path d="M14 7h4v4c0 2.5-1.5 4-4 4.5"/></svg>);
    case "sparkle": return (<svg {...p}><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/></svg>);
    default: return null;
  }
}

// --- Material plate (moodboard-style placeholder) ----------------------
// Layered gradient fields from a palette, with grain + thin frame + caption.
// Looks like an art-directed material study rather than a fake photo.
function Plate({ palette, label, variant = 0, ratio = "4 / 3", radius = 2, caption = true, children, style }) {
  const [a, b, c, d] = palette;
  const comps = [
    `radial-gradient(120% 90% at 18% 12%, ${c}cc 0%, transparent 55%), linear-gradient(135deg, ${b} 0%, ${a} 70%), radial-gradient(60% 60% at 82% 88%, ${d}88 0%, transparent 60%)`,
    `radial-gradient(90% 120% at 85% 20%, ${d}aa 0%, transparent 55%), linear-gradient(20deg, ${a} 0%, ${b} 60%, ${c}55 100%)`,
    `linear-gradient(115deg, ${a} 0%, ${a} 40%, ${b} 40%, ${b} 62%, ${c} 62%, ${c} 80%, ${d} 80%)`,
    `radial-gradient(140% 100% at 50% 120%, ${c}aa 0%, transparent 50%), radial-gradient(100% 80% at 20% -10%, ${d}66 0%, transparent 45%), linear-gradient(160deg, ${b}, ${a})`,
  ];
  const bg = comps[variant % comps.length];
  return (
    <div className="ec-plate" style={{ aspectRatio: ratio, borderRadius: radius, background: a, ...style }}>
      <div className="ec-plate-field" style={{ background: bg, borderRadius: radius }} />
      <div className="ec-grain" />
      <div className="ec-plate-frame" style={{ borderRadius: radius }} />
      {caption && label && (
        <div className="ec-plate-cap">
          <span className="ec-plate-cap-rule" />
          {label}
        </div>
      )}
      {children}
    </div>
  );
}

// --- Verdict pill (client's take) --------------------------------------
function Verdict({ verdict, size = "sm" }) {
  const pad = size === "lg" ? "6px 14px" : "3px 10px";
  const fs = size === "lg" ? 13 : 11;
  return (
    <span className="ec-verdict" data-v={verdict} style={{ padding: pad, fontSize: fs }}>
      <span className="ec-verdict-dot" />
      {verdict}
    </span>
  );
}

// --- Category tag ------------------------------------------------------
function CatTag({ cat, dim }) {
  if (!cat) return null;
  return (
    <span className="ec-cat" style={{ color: dim ? "var(--muted)" : cat.color }}>
      <span className="ec-cat-dot" style={{ background: cat.color }} />
      {cat.label}
    </span>
  );
}

// --- Signal / delta chip ----------------------------------------------
function Delta({ value, signal }) {
  const up = value >= 0;
  return (
    <span className="ec-delta" style={{ color: up ? "var(--pos)" : "var(--neg)" }}>
      <Icon name={up ? "up" : "down"} size={13} stroke={2} />
      {up ? "+" : ""}{value}
    </span>
  );
}

// --- Eyebrow label -----------------------------------------------------
function Eyebrow({ children, style }) {
  return <div className="ec-eyebrow" style={style}>{children}</div>;
}

// --- Brand-fit meter ---------------------------------------------------
function FitMeter({ value, label = "Brand fit", big }) {
  return (
    <div className="ec-fit" style={{ minWidth: big ? 180 : 130 }}>
      <div className="ec-fit-top">
        <span className="ec-fit-label">{label}</span>
        <span className="ec-fit-val" style={{ fontSize: big ? 20 : 14 }}>{value}<span className="ec-fit-pct">%</span></span>
      </div>
      <div className="ec-fit-track">
        <div className="ec-fit-fill" style={{ width: value + "%" }} />
      </div>
    </div>
  );
}

// --- Lens badge (Professional / Client demand) ------------------------
function Lens({ lens, label }) {
  const txt = label || (lens === "pro" ? "Professional" : "Client demand");
  return <span className="ec-lens" data-lens={lens}>{txt}</span>;
}

// --- Avatar ------------------------------------------------------------
function Avatar({ initials, className = "" }) {
  return <span className={"ec-avatar " + className} aria-hidden="true">{initials}</span>;
}

Object.assign(window, { Icon, Plate, Verdict, CatTag, Delta, Eyebrow, FitMeter, Lens, Avatar });
