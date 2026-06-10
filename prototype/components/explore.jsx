// ARTIS — Explore: Professional / Client Demand / By Client. text/babel → window.

function TrendCard({ t, cat, go, chartStyle, i }) {
  const isDem = t.lens === "dem";
  return (
    <button className="ec-card" style={{ animationDelay: (i * 35) + "ms" }} onClick={() => go("detail", t.id)}>
      <div className="ec-card-media">
        <Plate palette={t.plate} label={t.plateLabel} variant={t.rank % 4} ratio="5 / 4" radius={2} />
        <span className="ec-card-rank">{String(t.rank).padStart(2, "0")}</span>
      </div>
      <div className="ec-card-body">
        <div className="ec-card-top"><CatTag cat={cat} /><span className="ec-signal ec-signal--sm" data-sig={t.signal}>{t.signal}</span></div>
        <h3 className="ec-card-title">{t.title}</h3>
        <p className="ec-card-blurb">{t.blurb}</p>
        {isDem && (t.momPct != null || t.yoyPct != null) && (
          <div className="ec-mom-row">
            {t.momPct != null && <span className={"ec-mom-pill" + (t.momPct < 0 ? " neg" : "")}>MoM <b>{t.momPct > 0 ? "+" : ""}{Math.round(t.momPct)}%</b></span>}
            {t.yoyPct != null && <span className={"ec-mom-pill" + (t.yoyPct < 0 ? " neg" : "")}>YoY <b>{t.yoyPct > 0 ? "+" : ""}{Math.round(t.yoyPct)}%</b></span>}
          </div>
        )}
        <div className="ec-card-foot">
          <div className="ec-card-mom"><span className="ec-card-mom-num">{t.momentum}</span><span className="ec-card-mom-lab">momentum</span><Delta value={t.delta} /></div>
          <Sparkline series={t.history} color={cat.color} style={chartStyle} w={84} h={30} />
        </div>
      </div>
    </button>
  );
}

function TrendBrowser({ trends, go, t }) {
  const { CATEGORIES } = window.ARTIS;
  const catOf = (id) => CATEGORIES.find((c) => c.id === id);
  const [q, setQ] = React.useState("");
  const [cat, setCat] = React.useState("all");
  const [sort, setSort] = React.useState("momentum");
  const cats = CATEGORIES.filter((c) => trends.some((tr) => tr.category === c.id));

  let list = trends.filter((tr) => {
    if (cat !== "all" && tr.category !== cat) return false;
    if (q.trim()) {
      const s = (tr.title + " " + tr.blurb).toLowerCase();
      if (!s.includes(q.trim().toLowerCase())) return false;
    }
    return true;
  });
  const sorters = {
    momentum: (a, b) => b.momentum - a.momentum,
    rank: (a, b) => a.rank - b.rank,
    move: (a, b) => b.delta - a.delta,
  };
  list = [...list].sort(sorters[sort]);
  const sortLabels = { momentum: "Momentum", rank: "Rank", move: "Biggest move" };

  return (
    <div>
      <div className="ec-toolbar">
        <label className="ec-search">
          <Icon name="search" size={17} style={{ opacity: .55 }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search trends, materials, terms…" />
          {q && <button className="ec-search-clear" onClick={() => setQ("")}>×</button>}
        </label>
        <div className="ec-sort">
          <span className="ec-sort-lab">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(sortLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>
      <div className="ec-filters">
        <div className="ec-chips">
          <button className={"ec-chip" + (cat === "all" ? " is-on" : "")} onClick={() => setCat("all")}>All categories</button>
          {cats.map((c) => (
            <button key={c.id} className={"ec-chip" + (cat === c.id ? " is-on" : "")} onClick={() => setCat(c.id)} style={cat === c.id ? { borderColor: c.color, color: c.color } : null}>
              <span className="ec-chip-dot" style={{ background: c.color }} />{c.label}
            </button>
          ))}
        </div>
      </div>
      <div className="ec-result-meta">{list.length} {list.length === 1 ? "trend" : "trends"} · sorted by {sortLabels[sort].toLowerCase()}</div>
      {list.length ? (
        <div className="ec-grid">
          {list.map((tr, i) => <TrendCard key={tr.id} t={tr} cat={catOf(tr.category)} go={go} chartStyle={t.chartStyle} i={i} />)}
        </div>
      ) : (
        <div className="ec-empty">No trends match. <button onClick={() => { setQ(""); setCat("all"); }}>Reset filters</button></div>
      )}
    </div>
  );
}

function Explore({ go, t, initialTab, initialClient }) {
  const { PRO, DEM, CLIENTS, ISSUE } = window.ARTIS;
  const [tab, setTab] = React.useState(initialTab || "pro");
  const [client, setClient] = React.useState(() => initialClient ? (CLIENTS.find((c) => c.id === initialClient) || null) : null);

  const tabs = [
    { id: "pro", label: "Professional", count: PRO.length },
    { id: "dem", label: "Client Demand", count: DEM.length },
    { id: "client", label: "By Client", count: CLIENTS.length },
    { id: "intake", label: "Add Client", count: null },
  ];

  return (
    <div className="ec-screen ec-explore">
      <header className="ec-exp-head">
        <Eyebrow>{ISSUE.label}</Eyebrow>
        <h1 className="ec-exp-title">Explore the Research</h1>
        <p className="ec-exp-sub">Two streams of evidence — what designers are doing, and what clients are asking for — plus tailored strategy for the firm you're working with.</p>
      </header>

      <div className="ec-tabs">
        {tabs.map((tb) => (
          <button key={tb.id} className={"ec-tab" + (tab === tb.id ? " is-on" : "")} onClick={() => { setTab(tb.id); if (tb.id !== "client") setClient(null); }}>
            {tb.label}{tb.count != null && <span className="ec-tab-count">{tb.count}</span>}
          </button>
        ))}
      </div>

      {tab === "pro" && <TrendBrowser trends={PRO} go={go} t={t} />}
      {tab === "dem" && <TrendBrowser trends={DEM} go={go} t={t} />}
      {tab === "client" && (
        client
          ? <ClientStrategy client={client} go={go} t={t} onBack={() => setClient(null)} />
          : <ClientPicker onPick={setClient} />
      )}
      {tab === "intake" && <IntakeClient />}
    </div>
  );
}

function ClientPicker({ onPick }) {
  const { CLIENTS, STRATEGY } = window.ARTIS;
  return (
    <div>
      <div className="ec-pickclient-head">
        <h2>Choose a client</h2>
        <p>Select the design firm you're building a brand strategy for. The research is scored against each firm's positioning by the Artis engine.</p>
      </div>
      <div className="ec-client-grid">
        {CLIENTS.map((c) => {
          const counts = STRATEGY[c.id].counts;
          return (
            <button key={c.id} className="ec-clientcard" onClick={() => onPick(c)}>
              <div className="ec-clientcard-top">
                <Avatar initials={c.initials} />
                <div>
                  <div className="ec-clientcard-name">{c.name}</div>
                  <div className="ec-clientcard-prin">{c.principal}</div>
                </div>
              </div>
              <div className="ec-clientcard-tag">{c.tagline}</div>
              <div className="ec-swatches">{c.palette.map((p, i) => <span key={i} className="ec-swatch" style={{ background: p }} />)}</div>
              <div className="ec-clientcard-meta">
                <span><b>{c.region}</b></span>
                <span>{c.base}</span>
                <span style={{ marginTop: 4 }}><b style={{ color: "var(--v-lead-fg)" }}>{counts.Lead} lead</b> · {counts.Watch} watch · {counts.Skip} skip</span>
              </div>
              <span className="ec-clientcard-go">Open strategy <Icon name="arrow-right" size={13} /></span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { Explore, TrendCard, TrendBrowser, ClientPicker });
