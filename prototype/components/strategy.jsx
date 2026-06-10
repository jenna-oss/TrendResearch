// ARTIS — By-Client strategy view. text/babel → window.
// Renders backend-provided STRATEGY[clientId]: brief + per-trend {verdict, fit, why, opinion}.

function CountTile({ k, n, active, onClick }) {
  const fg = { Lead: "var(--v-lead-fg)", Watch: "var(--v-watch-fg)", Skip: "var(--v-skip-fg)" }[k];
  return (
    <button className="ec-cs-count" onClick={onClick}
      style={active ? { borderColor: fg, background: "color-mix(in srgb, " + fg + " 10%, transparent)" } : null}>
      <span className="ec-cs-count-n" style={{ color: fg }}>{n}</span>
      <span className="ec-cs-count-l" style={{ color: fg }}>{k}</span>
    </button>
  );
}

function PickRow({ trend, pick, cat, go, i }) {
  return (
    <button className="ec-pick" style={{ animationDelay: (i * 30) + "ms" }} onClick={() => go("detail", trend.id)}>
      <div className="ec-pick-main">
        <div className="ec-pick-top">
          <Lens lens={trend.lens} />
          <CatTag cat={cat} />
          <span className="ec-signal ec-signal--sm" data-sig={trend.signal}>{trend.signal}</span>
        </div>
        <h3 className="ec-pick-title">{trend.title}</h3>
        <p className="ec-pick-why">{pick.why}</p>
        <div className="ec-pick-opinion"><span className="ec-op-ic"><Icon name="quote" size={15} /></span>{pick.opinion}</div>
      </div>
      <div className="ec-pick-side">
        <Verdict verdict={pick.verdict} size="lg" />
        <FitMeter value={pick.fit} label="Fit" />
      </div>
    </button>
  );
}

function ClientStrategy({ client, go, t, onBack }) {
  const { PRO, DEM, CATEGORIES, STRATEGY, ISSUE } = window.ARTIS;
  const catOf = (id) => CATEGORIES.find((c) => c.id === id);
  const strat = STRATEGY[client.id];
  const [vf, setVf] = React.useState("all");
  const [lf, setLf] = React.useState("all");

  const all = [...PRO, ...DEM].map((tr) => ({ tr, pick: strat.picks[tr.id] }))
    .filter((x) => x.pick);

  let list = all.filter((x) => {
    if (vf !== "all" && x.pick.verdict !== vf) return false;
    if (lf !== "all" && x.tr.lens !== lf) return false;
    return true;
  }).sort((a, b) => b.pick.fit - a.pick.fit);

  return (
    <div className="ec-cs">
      <button className="ec-back" onClick={onBack}><Icon name="arrow-left" size={16} />All clients</button>

      <header className="ec-cs-head">
        <Avatar initials={client.initials} />
        <div className="ec-cs-id">
          <h1 className="ec-cs-name">{client.name}</h1>
          <div className="ec-cs-prin">{client.principal} · {client.tagline}</div>
          <div className="ec-cs-tags">
            <span><b>Region</b> {client.region}</span>
            <span><b>Clientele</b> {client.base}</span>
          </div>
        </div>
        <div className="ec-swatches" style={{ marginTop: 6 }}>{client.palette.map((p, i) => <span key={i} className="ec-swatch" style={{ background: p }} />)}</div>
      </header>

      <div className="ec-cs-brief">
        <Eyebrow>Brand strategy · {ISSUE.label}</Eyebrow>
        {strat.brief}
      </div>

      <div className="ec-cs-counts">
        <CountTile k="Lead" n={strat.counts.Lead} active={vf === "Lead"} onClick={() => setVf(vf === "Lead" ? "all" : "Lead")} />
        <CountTile k="Watch" n={strat.counts.Watch} active={vf === "Watch"} onClick={() => setVf(vf === "Watch" ? "all" : "Watch")} />
        <CountTile k="Skip" n={strat.counts.Skip} active={vf === "Skip"} onClick={() => setVf(vf === "Skip" ? "all" : "Skip")} />
      </div>

      <div className="ec-cs-bar">
        <div className="ec-seg">
          {[["all", "All research"], ["pro", "Professional"], ["dem", "Client demand"]].map(([k, l]) => (
            <button key={k} className={lf === k ? "is-on" : ""} onClick={() => setLf(k)}>{l}</button>
          ))}
        </div>
        <div className="ec-result-meta" style={{ margin: 0 }}>{list.length} {list.length === 1 ? "trend" : "trends"}{vf !== "all" ? " · " + vf : ""}</div>
      </div>

      {list.length ? (
        <div className="ec-picks">
          {list.map((x, i) => <PickRow key={x.tr.id} trend={x.tr} pick={x.pick} cat={catOf(x.tr.category)} go={go} i={i} />)}
        </div>
      ) : (
        <div className="ec-empty">Nothing matches that filter. <button onClick={() => { setVf("all"); setLf("all"); }}>Reset</button></div>
      )}
    </div>
  );
}

Object.assign(window, { ClientStrategy, PickRow });
