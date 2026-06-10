// ARTIS — App shell: sidebar nav. text/babel → window.

function Wordmark() {
  return (
    <div className="ec-wordmark" aria-label="artis">
      <span className="ec-wm-word">art<span className="ec-wm-i">ı<span className="ec-wm-star" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
          <line x1="12" y1="3.5" x2="12" y2="20.5" /><line x1="4.6" y1="7.75" x2="19.4" y2="16.25" /><line x1="19.4" y1="7.75" x2="4.6" y2="16.25" />
        </svg>
      </span></span>s</span>
    </div>
  );
}

function Sidebar({ view, go }) {
  const { ISSUE } = window.ARTIS;
  const nav = [
    { id: "dashboard", label: "Overview", icon: "layers", sub: "The two questions" },
    { id: "explore", label: "Explore", icon: "compass", sub: "Research & strategy" },
    { id: "archive", label: "Archive", icon: "archive", sub: "Past months", soon: true },
  ];
  return (
    <aside className="ec-sidebar">
      <div className="ec-sidebar-top">
        <Wordmark />
        <div className="ec-sidebar-tag">Luxury Interiors · Trend Intelligence</div>
      </div>

      <nav className="ec-nav">
        {nav.map((n) => {
          const active = view === n.id || (view === "detail" && n.id === "explore");
          return (
            <button key={n.id} className={"ec-nav-item" + (active ? " is-active" : "") + (n.soon ? " is-soon" : "")}
              onClick={() => !n.soon && go(n.id)}>
              <span className="ec-nav-ico"><Icon name={n.icon} size={17} /></span>
              <span className="ec-nav-text">
                <span className="ec-nav-label">{n.label}{n.soon && <em className="ec-soon">soon</em>}</span>
                <span className="ec-nav-sub">{n.sub}</span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="ec-sidebar-issue">
        <Eyebrow>This month</Eyebrow>
        <div className="ec-issue-row">
          <span className="ec-issue-no" style={{ fontSize: 22 }}>{ISSUE.label}</span>
        </div>
        <div className="ec-issue-meta">{ISSUE.proPatterns} professional · {ISSUE.demTrends} demand</div>
      </div>

      <button className="ec-client-card" onClick={() => go("explore", null, "client")} style={{ textAlign: "left", cursor: "pointer" }}>
        <div className="ec-client-ey">Brand partner</div>
        <div className="ec-client-name">Build a strategy</div>
        <div className="ec-clientcard-go">Choose a client <Icon name="arrow-right" size={13} /></div>
      </button>
    </aside>
  );
}

Object.assign(window, { Wordmark, Sidebar });
