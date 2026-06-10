// ARTIS — Trend detail (professional & demand). text/babel → window.

function DStat({ value, label, accent, children }) {
  return (
    <div className="ec-dstat">
      <div className="ec-dstat-val" style={accent ? { color: "var(--accent)" } : null}>{value}{children}</div>
      <div className="ec-dstat-lab">{label}</div>
    </div>
  );
}

function Detail({ go, id, t }) {
  const { PRO, DEM, CATEGORIES, CLIENTS, STRATEGY } = window.ARTIS;
  const lensList = id && id.startsWith("d-") ? DEM : PRO;
  const idx = Math.max(0, lensList.findIndex((x) => x.id === id));
  const tr = lensList[idx];
  const cat = CATEGORIES.find((c) => c.id === tr.category);
  const prev = lensList[(idx - 1 + lensList.length) % lensList.length];
  const next = lensList[(idx + 1) % lensList.length];
  const isDem = tr.lens === "dem";
  const fmtPct = (v) => v == null ? "—" : (v > 0 ? "+" : "") + Math.round(v) + "%";

  const across = CLIENTS.map((c) => ({ c, pick: STRATEGY[c.id].picks[tr.id] }))
    .filter((x) => x.pick).sort((a, b) => b.pick.fit - a.pick.fit);

  return (
    <div className="ec-screen ec-detail" key={id}>
      <button className="ec-back" onClick={() => go("explore", null, tr.lens)}><Icon name="arrow-left" size={16} />{isDem ? "Client Demand" : "Professional"}</button>

      <header className="ec-det-head">
        <div className="ec-det-meta">
          <Lens lens={tr.lens} />
          <span className="ec-det-rank">Rank {String(tr.rank).padStart(2, "0")}</span>
          <CatTag cat={cat} />
          <span className="ec-signal" data-sig={tr.signal}>{tr.signal}</span>
          {tr.tier && (tr.tier.includes("cross") ? <span className="ec-signal" style={{ color: "var(--ink-2)" }}>Cross-source</span> : null)}
        </div>
        <h1 className="ec-det-title">{tr.title}</h1>
        <p className="ec-det-lead">{tr.blurb}</p>
      </header>

      <div className="ec-det-hero">
        <Plate palette={tr.plate} label={tr.plateLabel} variant={tr.rank % 4} ratio="21 / 9" radius={3} />
      </div>

      <div className="ec-det-band">
        <DStat value={tr.momentum} label="Momentum" accent><span className="ec-dstat-delta"><Delta value={tr.delta} /></span></DStat>
        {isDem ? <DStat value={fmtPct(tr.momPct)} label="MoM search" /> : <DStat value={tr.signal} label="Lifecycle" />}
        {isDem ? <DStat value={fmtPct(tr.yoyPct)} label="YoY search" /> : <DStat value={tr.signalCount} label="Signals" />}
        <DStat value={tr.sources.length} label="Sources" />
      </div>

      <div className="ec-det-grid">
        <main className="ec-det-main">
          <section className="ec-block">
            <div className="ec-block-head"><Eyebrow>Momentum · illustrative trajectory</Eyebrow></div>
            <div className="ec-chart-wrap">
              <MomentumChart series={tr.history} color={cat.color} style={t.chartStyle === "bars" ? "bars" : (t.chartStyle === "area" ? "area" : "line")} />
            </div>
          </section>

          <section className="ec-block">
            <div className="ec-block-head"><Eyebrow>The signal</Eyebrow><h2 className="ec-block-title">{isDem ? "What clients are searching" : "What the field is saying"}</h2></div>
            <ul className="ec-evidence">
              {tr.reps.map((r, i) => (
                <li key={i} className="ec-ev">
                  <div className="ec-ev-main">
                    {isDem
                      ? <span className="ec-ev-title">{r.term}</span>
                      : (r.url ? <a className="ec-ev-title ec-ev-link" href={r.url} target="_blank" rel="noopener noreferrer">{r.title}<Icon name="arrow-right" size={13} style={{ transform: "rotate(-45deg)" }} /></a> : <span className="ec-ev-title">{r.title}</span>)}
                    {!isDem && r.why && <p className="ec-ev-why">{r.why}</p>}
                  </div>
                  <div className="ec-ev-side">
                    <span className="ec-ev-source">{r.source}</span>
                    {isDem && r.mom != null && <span className={"ec-mom-pill" + (r.mom < 0 ? " neg" : "")}>MoM <b>{fmtPct(r.mom)}</b></span>}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="ec-block">
            <div className="ec-block-head"><Eyebrow>Provenance</Eyebrow><h2 className="ec-block-title">Sources</h2></div>
            <div className="ec-source-chips">
              {tr.sources.map((s) => <span key={s} className="ec-source-chip">{s}</span>)}
            </div>
          </section>
        </main>

        <aside className="ec-det-rail">
          <div className="ec-take">
            <div className="ec-take-head">
              <Eyebrow>Across your clients</Eyebrow>
            </div>
            <p className="ec-across-intro">How the Artis engine reads this trend for each firm.</p>
            <div className="ec-across">
              {across.map((x) => (
                <button key={x.c.id} className="ec-across-row" onClick={() => go("explore", x.c.id, "client")}>
                  <Avatar initials={x.c.initials} />
                  <span className="ec-across-id">
                    <span className="ec-across-name">{x.c.name}</span>
                    <span className="ec-across-tag">{x.c.tagline}</span>
                  </span>
                  <span className="ec-across-fit">{x.pick.fit}</span>
                  <Verdict verdict={x.pick.verdict} />
                </button>
              ))}
            </div>
          </div>
        </aside>
      </div>

      <nav className="ec-det-nav">
        <button className="ec-det-nav-btn" onClick={() => go("detail", prev.id)}>
          <span className="ec-det-nav-dir"><Icon name="arrow-left" size={15} />Previous</span>
          <span className="ec-det-nav-title">{String(prev.rank).padStart(2, "0")} · {prev.title}</span>
        </button>
        <button className="ec-det-nav-btn ec-det-nav-btn--next" onClick={() => go("detail", next.id)}>
          <span className="ec-det-nav-dir">Next<Icon name="arrow-right" size={15} /></span>
          <span className="ec-det-nav-title">{String(next.rank).padStart(2, "0")} · {next.title}</span>
        </button>
      </nav>
    </div>
  );
}

Object.assign(window, { Detail });
