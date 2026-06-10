// ARTIS — App root, routing, Tweaks. text/babel → window.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "dark": false,
  "accent": "#9c3a2a",
  "typeset": "editorial",
  "density": "comfortable",
  "chartStyle": "area"
}/*EDITMODE-END*/;

const TYPESETS = {
  editorial: { display: '"Cormorant Garamond", Georgia, serif', body: '"Hanken Grotesk", system-ui, sans-serif', dw: 600 },
  fashion:   { display: '"Bodoni Moda", Georgia, serif', body: '"Archivo", system-ui, sans-serif', dw: 600 },
  classic:   { display: '"Playfair Display", Georgia, serif', body: '"Hanken Grotesk", system-ui, sans-serif', dw: 600 },
};

const ACCENTS = ["#9c3a2a", "#b5603f", "#b0883e", "#6e7a3e", "#5a3a28"];

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [route, setRoute] = React.useState({ view: "dashboard", id: null, tab: null });
  const go = (view, id, tab) => setRoute({ view, id: id || null, tab: tab || null });

  React.useEffect(() => {
    const r = document.documentElement;
    r.dataset.theme = t.dark ? "dark" : "light";
    r.dataset.density = t.density;
    r.style.setProperty("--accent", t.accent);
    const ts = TYPESETS[t.typeset] || TYPESETS.editorial;
    r.style.setProperty("--font-display", ts.display);
    r.style.setProperty("--font-body", ts.body);
    r.style.setProperty("--display-weight", ts.dw);
  }, [t.dark, t.density, t.accent, t.typeset]);

  React.useEffect(() => {
    const el = document.querySelector(".ec-main");
    if (el) el.scrollTop = 0;
  }, [route.view, route.id]);

  const { view, id, tab } = route;

  return (
    <div className="ec-app">
      <Sidebar view={view} go={go} />
      <main className="ec-main">
        <div className="ec-main-inner" key={view + (id || "") + (tab || "")}>
          {view === "dashboard" && <Dashboard go={go} t={t} />}
          {view === "explore" && <Explore go={go} t={t} initialTab={tab} initialClient={tab === "client" ? id : null} />}
          {view === "detail" && <Detail go={go} id={id} t={t} />}
        </div>
        <footer className="ec-footer">
          <span>ARTIS — Trend Intelligence for Luxury Interiors</span>
          <span>{window.ARTIS.ISSUE.label} · {window.ARTIS.ISSUE.signalsAnalysed} signals analysed</span>
        </footer>
      </main>

      <TweaksPanel>
        <TweakSection label="Theme" />
        <TweakRadio label="Mode" value={t.dark ? "dark" : "light"} options={["dark", "light"]}
          onChange={(v) => setTweak("dark", v === "dark")} />
        <TweakColor label="Accent" value={t.accent} options={ACCENTS}
          onChange={(v) => setTweak("accent", v)} />

        <TweakSection label="Typography" />
        <TweakSelect label="Typeset" value={t.typeset}
          options={[
            { value: "editorial", label: "Editorial — Cormorant" },
            { value: "fashion", label: "Fashion — Bodoni" },
            { value: "classic", label: "Classic — Playfair" },
          ]}
          onChange={(v) => setTweak("typeset", v)} />

        <TweakSection label="Layout" />
        <TweakRadio label="Density" value={t.density} options={["compact", "comfortable", "editorial"]}
          onChange={(v) => setTweak("density", v)} />

        <TweakSection label="Charts" />
        <TweakRadio label="Style" value={t.chartStyle} options={["line", "area", "bars"]}
          onChange={(v) => setTweak("chartStyle", v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
