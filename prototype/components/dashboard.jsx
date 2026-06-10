// ARTIS — Overview dashboard (the two questions). text/babel → window.

function StatTile({ value, label, sub }) {
  return (
    <div className="ec-stat">
      <div className="ec-stat-val">{value}</div>
      <div className="ec-stat-lab">{label}</div>
      {sub && <div className="ec-stat-sub">{sub}</div>}
    </div>
  );
}

function MiniRow({ t, cat, go }) {
  return (
    <button className="ec-mini-row" onClick={() => go("detail", t.id)}>
      <span className="ec-mini-rank">{String(t.rank).padStart(2, "0")}</span>
      <span className="ec-mini-body">
        <span className="ec-mini-title">{t.title}</span>
        <span className="ec-mini-meta"><CatTag cat={cat} /><span className="ec-signal ec-signal--sm" data-sig={t.signal}>{t.signal}</span></span>
      </span>
      <span className="ec-mini-mom">{t.momentum}<Delta value={t.delta} /></span>
    </button>
  );
}

function QCard({ num, title, sub, trends, cat, go, chartStyle, linkLabel, onLink }) {
  return (
    <div className="ec-qcard">
      <div className="ec-qcard-head">
        <span className="ec-qcard-num">{num}</span>
        <h3 className="ec-qcard-title">{title}</h3>
        <span className="ec-qcard-sub">{sub}</span>
      </div>
      <div className="ec-mini">
        {trends.map((t) => <MiniRow key={t.id} t={t} cat={cat(t.category)} go={go} chartStyle={chartStyle} />)}
      </div>
      <div className="ec-qcard-foot">
        <button className="ec-textlink" onClick={onLink}>{linkLabel} <Icon name="arrow-right" size={14} /></button>
      </div>
    </div>
  );
}

function Dashboard({ go, t }) {
  const { PRO, DEM, CATEGORIES, ISSUE, CONVERGENCE, CLIENTS } = window.ARTIS;
  const catOf = (id) => CATEGORIES.find((c) => c.id === id);
  const hero = PRO[0];
  const heroCat = catOf(hero.category);
  const cs = t.chartStyle;

  return (
    <div className="ec-screen ec-dash">
      <header className="ec-masthead">
        <div className="ec-mast-rule" />
        <Eyebrow>{ISSUE.label}</Eyebrow>
        <h1 className="ec-mast-title">This Month in<br /><em>Luxury Interior Design</em></h1>
        <p className="ec-mast-sub">Two questions, one automated read: what luxury <em>designers</em> are doing, and what their <em>clients</em> are asking for — so brand partners can build strategy on evidence.</p>
        <div className="ec-stat-row">
          <StatTile value={ISSUE.proPatterns} label="Professional patterns" sub="editorial & trade" />
          <StatTile value={ISSUE.demTrends} label="Client-demand trends" sub="search · realty · platforms" />
          <StatTile value={ISSUE.signalsAnalysed.toLocaleString()} label="Signals analysed" />
          <StatTile value={ISSUE.updated} label="Last updated" sub="auto-refreshed monthly" />
        </div>
      </header>

      {/* Hero — #1 professional trend */}
      <button className="ec-hero" onClick={() => go("detail", hero.id)}>
        <div className="ec-hero-media">
          <Plate palette={hero.plate} label={hero.plateLabel} variant={0} ratio="16 / 11" radius={3} />
          <span className="ec-hero-badge">Top Professional Signal</span>
        </div>
        <div className="ec-hero-body">
          <div className="ec-hero-top"><Lens lens="pro" /><span className="ec-signal" data-sig={hero.signal}>{hero.signal}</span></div>
          <h2 className="ec-hero-title">{hero.title}</h2>
          <p className="ec-hero-blurb">{hero.blurb}</p>
          <div className="ec-hero-metrics">
            <div className="ec-hero-mom"><span className="ec-hero-mom-num">{hero.momentum}</span><span className="ec-hero-mom-lab">Momentum</span><Delta value={hero.delta} /></div>
            <Sparkline series={hero.history} color={heroCat.color} style={cs} w={120} h={40} />
          </div>
          <div className="ec-hero-take">
            <div className="ec-hero-sources"><CatTag cat={heroCat} /> · {hero.sources.join(" · ")}</div>
            <span className="ec-hero-cta">Open the full report <Icon name="arrow-right" size={16} /></span>
          </div>
        </div>
      </button>

      {/* Two questions */}
      <div className="ec-q-grid">
        <QCard num="Question 01" title="What designers are doing" sub="Professional signals"
          trends={PRO.slice(0, 5)} cat={catOf} go={go} chartStyle={cs}
          linkLabel={`Explore all ${PRO.length} professional`} onLink={() => go("explore", null, "pro")} />
        <QCard num="Question 02" title="What clients are asking for" sub="Client-demand signals"
          trends={DEM.slice(0, 5)} cat={catOf} go={go} chartStyle={cs}
          linkLabel={`Explore all ${DEM.length} demand`} onLink={() => go("explore", null, "dem")} />
      </div>

      {/* Convergence */}
      {CONVERGENCE.length > 0 && (
        <section className="ec-converge">
          <div className="ec-section-head"><Eyebrow>Two-sided momentum</Eyebrow><h3 className="ec-section-title">Where they converge</h3><span className="ec-section-meta">Trends moving on both sides at once</span></div>
          <div className="ec-conv-list">
            {CONVERGENCE.map((c, i) => (
              <div key={i} className="ec-conv">
                <div className="ec-conv-label">{c.label}</div>
                <div className="ec-conv-pair">
                  <button className="ec-conv-side" onClick={() => go("detail", c.pro.id)}><Lens lens="pro" /><span className="ec-conv-t">{c.pro.title}</span></button>
                  <button className="ec-conv-side" onClick={() => go("detail", c.dem.id)}><Lens lens="dem" /><span className="ec-conv-t">{c.dem.title}</span></button>
                </div>
                <p className="ec-conv-note">{c.note}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* By-client CTA */}
      <div className="ec-cta">
        <div className="ec-cta-l">
          <Eyebrow>For brand partners</Eyebrow>
          <h3 className="ec-cta-title">Build a strategy for your client</h3>
          <p className="ec-cta-sub">Pick the design firm you're working with and see exactly how this month's research applies — which trends to lead with, which to watch, and where each one fits the brand.</p>
        </div>
        <div className="ec-cta-clients">
          <div className="ec-cta-avatars">
            {CLIENTS.slice(0, 5).map((c) => <Avatar key={c.id} initials={c.initials} />)}
          </div>
          <button className="ec-btn" onClick={() => go("explore", null, "client")} style={{ marginLeft: 18 }}>Open By Client <Icon name="arrow-right" size={16} /></button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard });
