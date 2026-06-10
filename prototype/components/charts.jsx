// ÉCLAT — SVG charts. Loaded as text/babel. Exports to window.

// shared: map a series to points within a box
function _scale(series, w, h, pad) {
  const min = Math.min(...series), max = Math.max(...series);
  const span = Math.max(1, max - min);
  const innerW = w - pad * 2, innerH = h - pad * 2;
  return series.map((v, i) => [
    pad + (i / (series.length - 1)) * innerW,
    pad + innerH - ((v - min) / span) * innerH,
  ]);
}
function _path(pts) { return pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" "); }

// --- Sparkline (inline, in list rows) ---------------------------------
function Sparkline({ series, w = 88, h = 30, color = "var(--accent)", style = "line" }) {
  const pts = _scale(series, w, h, 3);
  const up = series[series.length - 1] >= series[0];
  const stroke = color;
  const area = "M" + pts[0][0] + " " + (h - 2) + " " + _path(pts).slice(1) + " L" + pts[pts.length - 1][0] + " " + (h - 2) + " Z";
  const last = pts[pts.length - 1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="ec-spark">
      {style === "area" && <path d={area} fill={stroke} opacity="0.13" />}
      {style === "bars" ? (
        pts.map((p, i) => <rect key={i} x={p[0] - 1.4} y={p[1]} width="2.8" height={h - 2 - p[1]} fill={stroke} opacity={0.25 + 0.6 * (i / pts.length)} />)
      ) : (
        <path d={_path(pts)} fill="none" stroke={stroke} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      )}
      <circle cx={last[0]} cy={last[1]} r="2.4" fill={stroke} />
    </svg>
  );
}

// --- Momentum chart (detail page) -------------------------------------
const MONTHS = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"];
function MomentumChart({ series, color = "var(--accent)", height = 240, style = "area" }) {
  const w = 720, h = height, padX = 44, padTop = 18, padBot = 34;
  const min = Math.min(...series), max = Math.max(...series);
  const lo = Math.max(0, Math.floor((min - 6) / 10) * 10);
  const hi = Math.min(100, Math.ceil((max + 6) / 10) * 10);
  const span = Math.max(1, hi - lo);
  const innerW = w - padX - 14, innerH = h - padTop - padBot;
  const pts = series.map((v, i) => [
    padX + (i / (series.length - 1)) * innerW,
    padTop + innerH - ((v - lo) / span) * innerH,
  ]);
  const grid = [];
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const val = lo + (span * i) / steps;
    const y = padTop + innerH - (i / steps) * innerH;
    grid.push({ y, val: Math.round(val) });
  }
  const area = "M" + pts[0][0] + " " + (padTop + innerH) + " " + _path(pts).slice(1) + " L" + pts[pts.length - 1][0] + " " + (padTop + innerH) + " Z";
  const last = pts[pts.length - 1];
  const gid = "mg" + Math.round(series[0] + series[11]);
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="ec-momentum" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {grid.map((g, i) => (
        <g key={i}>
          <line x1={padX} y1={g.y} x2={w - 14} y2={g.y} stroke="var(--line)" strokeWidth="1" strokeDasharray={i === 0 ? "0" : "2 4"} opacity={i === 0 ? 0.8 : 0.5} />
          <text x={padX - 10} y={g.y + 3.5} textAnchor="end" className="ec-axis">{g.val}</text>
        </g>
      ))}
      {MONTHS.map((m, i) => (
        <text key={m} x={pts[i][0]} y={h - 12} textAnchor="middle" className="ec-axis" opacity={i % 2 || i === 11 ? 0.9 : 0.45}>{m}</text>
      ))}
      {style !== "bars" && <path d={area} fill={`url(#${gid})`} />}
      {style === "bars" ? (
        pts.map((p, i) => <rect key={i} x={p[0] - 6} y={p[1]} width="12" height={padTop + innerH - p[1]} rx="1.5" fill={color} opacity={0.35 + 0.5 * (i / pts.length)} />)
      ) : (
        <path d={_path(pts)} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
      )}
      {style !== "bars" && pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={i === pts.length - 1 ? 4.5 : 2.2} fill={i === pts.length - 1 ? color : "var(--bg-1)"} stroke={color} strokeWidth="1.6" />
      ))}
      <text x={last[0]} y={last[1] - 12} textAnchor="middle" className="ec-momentum-now" fill={color}>{series[11]}</text>
    </svg>
  );
}

// --- Category donut ----------------------------------------------------
function Donut({ data, size = 160, thickness = 22 }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  let off = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="ec-donut">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--line)" strokeWidth={thickness} opacity="0.4" />
      {data.map((d, i) => {
        const frac = d.value / total;
        const len = frac * circ;
        const seg = (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={d.color} strokeWidth={thickness}
            strokeDasharray={`${len - 2} ${circ - len + 2}`} strokeDashoffset={-off}
            transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt" />
        );
        off += len;
        return seg;
      })}
      <text x={cx} y={cy - 3} textAnchor="middle" className="ec-donut-num">{total}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" className="ec-donut-lab">trends</text>
    </svg>
  );
}

Object.assign(window, { Sparkline, MomentumChart, Donut });
