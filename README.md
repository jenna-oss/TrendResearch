# ARTIS — Trend Intelligence for Luxury Interiors

> **Deploying this for your firm? → see [DEPLOY.md](./DEPLOY.md).**
> Click **“Use this template”** above to get your own copy, then follow the 7 steps
> (GitHub + Vercel + an Anthropic API key, ~15 min). No servers, no database.

The rest of this file is the technical reference for the app's design and data
contract.

---

## Overview
ARTIS is a monthly trend-intelligence web app for **brand partners** at a marketing team
who serve luxury interior-design firms. It answers two questions from automated research —
**(1) what professional designers are doing** and **(2) what their clients are asking for** —
and lets a brand partner pick the design firm ("client") they're strategizing for and see how
that research applies to that specific client (Lead / Watch / Skip per trend, a fit score, a
"why it fits" line, a likely client opinion, and a written brand brief).

This bundle is the **design reference** + the **data contract** you need to wire the UI onto
your existing research/matching automation.

---

## About the design files
The files in `prototype/` are a **high-fidelity HTML/React prototype** — they show the intended
look, layout, and behavior exactly, but they are a *reference*, not the production app. Recreate
them in your target stack using its established patterns:

- The prototype is **React 18 via in-browser Babel** (no build step) with plain CSS. In production
  you'll likely use a real React/Next/Vite app (or your existing framework). Port the components
  1:1; they're already split sensibly (see **File map**).
- All styling is in one stylesheet (`styles.css`) driven by CSS custom properties. You can lift it
  almost verbatim, or map the tokens into your design system (see **Design tokens**).
- **The most important part for you is the Data Contract below** — the UI is a pure presentation
  layer over a single `window.ARTIS` data object. Replace that object with your automation's output
  and the whole app populates.

**Fidelity: high.** Colors, type, spacing, and interactions are final. Match them.

---

## How to run the prototype
Open `prototype/Artis Trend Report.html` in a browser (or serve the `prototype/` folder with any
static server, e.g. `npx serve prototype`). It loads `data.js` (the inline dataset), then the
component scripts. No install required.

---

## File map (`prototype/`)
| File | Role |
|---|---|
| `Artis Trend Report.html` | Entry point. Loads fonts, React/Babel, `data.js`, then components. |
| `data.js` | **The entire dataset** as `window.ARTIS = {…}`. This is what your backend replaces. |
| `styles.css` | All styling + design tokens (light default + dark variant). |
| `components/ui.jsx` | Primitives: `Icon`, `Plate` (material placeholder), `Verdict`, `CatTag`, `Delta`, `Eyebrow`, `FitMeter`, `Lens`, `Avatar`. |
| `components/charts.jsx` | SVG charts: `Sparkline`, `MomentumChart`, `Donut`. |
| `components/shell.jsx` | `Sidebar` + `Wordmark` (the lowercase `artis` + asterisk logo). |
| `components/dashboard.jsx` | Overview screen (the two questions). |
| `components/explore.jsx` | Explore screen + tabs + `TrendBrowser` (cards) + `ClientPicker`. |
| `components/strategy.jsx` | `ClientStrategy` (the By-Client view) + `PickRow`. |
| `components/detail.jsx` | Trend detail (both lenses) + "Across your clients" panel. |
| `components/app.jsx` | Root: routing + theme/Tweaks wiring. |
| `tweaks-panel.jsx` | Optional in-prototype controls (accent/type/density/chart/dark). Not needed in prod. |
| `build_dataset.js` (in repo root of this handoff) | Reference Node script: raw analysis JSON → `data.js`. |

---

## THE DATA CONTRACT  ← wire your automation here
The UI reads one global object, `window.ARTIS`. In production, serve this as JSON from your API and
hydrate the app with it (see **Integration** at the end). Shape:

```ts
ARTIS = {
  ISSUE: Issue,
  CATEGORIES: Category[],     // 7 fixed taxonomy buckets
  PRO: Trend[],              // "what designers are doing"  (question 1)
  DEM: Trend[],              // "what clients are asking for" (question 2)
  CLIENTS: Client[],         // the design firms a brand partner can pick
  STRATEGY: { [clientId]: ClientStrategy },   // per-client scoring  ← your matching engine
  CONVERGENCE: Convergence[] // themes appearing on BOTH sides (optional, derivable)
}
```

### Issue
```ts
Issue = {
  month: string;            // "May"
  year: number;             // 2026
  label: string;            // "May 2026"  (shown in sidebar/headers)
  updated: string;          // "9 June 2026"
  proPatterns: number;      // total professional patterns analysed (81)
  demTrends: number;        // total demand trends analysed (40)
  signalsAnalysed: number;  // 199
  // proSources/demSources/trendsShown also present; informational
}
```

### Category  (fixed taxonomy — keep these 7 ids/colors)
```ts
Category = { id: string; label: string; color: string /*hex*/ }
// materials #b07d33 · colour #b1543a · form #6f7c41 · craft #8a6188
// space #4f6f7a · nature #5f7b4e · market #9c6b4f
```

### Trend  (one shape for both PRO and DEM; `lens` distinguishes them)
```ts
Trend = {
  id: string;          // "p-…" for professional, "d-…" for demand. MUST be unique & stable.
  lens: "pro" | "dem"; // drives the lens badge + which Explore tab + routing
  rank: number;        // 1-based, by momentum within its lens
  title: string;       // "Bathroom-as-Retreat Design"
  category: string;    // one of the 7 Category ids
  momentum: number;    // 0–100, the headline metric (bars, sort)
  delta: number;       // signed; shown as +N / −N
  signal: "Surging" | "Rising" | "Peaking" | "Steady" | "Cooling"; // colored chip
  tier: string;        // "cross_source" | "single_source" (shows a "Cross-source" tag)
  sources: string[];   // ["Architectural Digest", "Elle Decor"]
  signalCount: number;
  blurb: string;       // 1–2 sentence description (cards, detail lead)
  reps: RepSignal[];   // representative evidence (detail "The signal" section)
  plate: string[4];    // 4 hex colors for the material "plate" placeholder image
  plateLabel: string;  // caption on the plate
  history: number[12]; // 12-pt trailing series for the sparkline / momentum chart

  // DEM-only (client demand):
  momPct?: number;     // avg month-over-month % (search) — shown as a pill + stat
  yoyPct?: number;     // avg year-over-year %
  trajectory?: string; // "breakout" | "rising" | "steady" | "declining"
}

// Professional rep:
RepSignal_pro = { title: string; source: string; url: string; lifecycle: string; strength: string; why: string }
// Demand rep:
RepSignal_dem = { term: string; source: string; type: string; mom: number|null; yoy: number|null; trajectory: string|null }
```
> `plate` / `plateLabel` / `history` are **presentation-only**. If your data lacks a real time series,
> synthesize `history` from the trajectory (the build script shows how) or swap `Plate` for real photography.

### Client  (the design firm; only these fields are rendered)
```ts
Client = {
  id: string;          // "maison-hale"  — key into STRATEGY
  name: string;        // "Maison Hale"
  principal: string;   // "Julian R. Hale" — used in the "what {first} would think" line
  initials: string;    // "JH" — avatar
  region: string;      // "New York · London"
  base: string;        // "UHNW private residences"
  tagline: string;     // "Quiet permanence, material honesty"
  aesthetic: string;   // one-line design language
  palette: string[3];  // 3 hex swatches
}
```
> The sample `data.js` also carries `loves` / `loveKw` / `avoidKw` on each client — those were **only**
> used by the prototype's fake matcher to generate sample STRATEGY. **Your backend does the matching,
> so you can drop those fields.** The UI never reads them.

### ClientStrategy  ← THIS IS YOUR AUTOMATION'S PRIMARY OUTPUT
```ts
ClientStrategy = {
  brief: string;                       // 2–3 sentence written brand strategy for this client/month
  counts?: { Lead: number; Watch: number; Skip: number };  // optional; UI can derive from picks
  picks: { [trendId: string]: Pick }   // one entry per trend you scored for this client
}

Pick = {
  verdict: "Lead" | "Watch" | "Skip";  // recommendation pill
  fit: number;                         // integer 0–100  → the fit meter
  why: string;                         // one line: why it fits (or doesn't) this client
  opinion: string;                     // one line: what the client/principal would likely think
}
```
`picks` keys MUST be valid `Trend.id`s (PRO or DEM). The page joins each pick to its trend to render
title/category/lens/momentum alongside your `verdict / fit / why / opinion`. The same data powers the
**"Across your clients"** panel on each trend detail page (it inverts the lookup: for one trend, show
every client's pick).

### Convergence  (optional — themes on both sides)
```ts
Convergence = {
  label: string;                                  // "Stone"
  pro: { id: string; title: string; signal: string };
  dem: { id: string; title: string; signal: string };
  note: string;
}
```

---

## Screens / views

### 1. Overview  (`dashboard.jsx`, route `dashboard`)
- **Masthead**: eyebrow = `ISSUE.label`; headline "This Month in *Luxury Interior Design*"; one-line
  sub; a stat row (`proPatterns`, `demTrends`, `signalsAnalysed`, `updated`).
- **Hero**: the #1 professional trend (`PRO[0]`) — material plate + lens badge + signal + title + blurb
  + momentum + sparkline + sources. Click → trend detail.
- **Two-question columns**: left "What designers are doing" = top 5 `PRO`; right "What clients are
  asking for" = top 5 `DEM`. Each mini-row: rank, title, category dot, signal, momentum+delta. Footer
  link → Explore (that lens).
- **Where they converge**: cards from `CONVERGENCE` (a professional trend ↔ a demand trend).
- **CTA**: "Build a strategy for your client" → Explore › By Client.

### 2. Explore  (`explore.jsx`, route `explore`, with tabs)
Three tabs: **Professional** (`PRO`), **Client Demand** (`DEM`), **By Client**.
- **Professional / Client Demand**: search + category chips + sort (momentum / rank / biggest move),
  rendered as a responsive card grid. Demand cards additionally show MoM/YoY pills. Card → detail.
- **By Client → ClientPicker**: a grid of `CLIENTS` cards (avatar, name, principal, tagline, palette,
  and the Lead/Watch/Skip counts). Pick one → ClientStrategy.

### 3. By-Client strategy  (`strategy.jsx`)
The core deliverable. For the selected client:
- Header (avatar, name, principal, tagline, region, clientele, palette swatches).
- **Brief** block (`STRATEGY[id].brief`).
- **Counts** tiles (Lead / Watch / Skip) — clickable to filter.
- Filter bar: verdict (via count tiles) + lens segment (All / Professional / Client demand).
- **Pick rows** (sorted by `fit` desc): lens badge, category, signal, trend title, **why** line,
  **opinion** quote, **Verdict** pill, **Fit** meter. Row → trend detail.

### 4. Trend detail  (`detail.jsx`, route `detail`, id = trend id)
- Back link to the originating lens.
- Header: lens badge, `Rank NN`, category, signal, (cross-source tag), title, blurb.
- Material plate hero.
- Stat band — PRO: Momentum, Lifecycle, Signals, Sources · DEM: Momentum, MoM, YoY, Sources.
- Momentum chart (12-pt `history`).
- **The signal**: `reps` rendered as evidence (professional = article titles linking to `url` +
  rationale; demand = search terms + source + MoM).
- **Sources** chips.
- **Across your clients** (rail): every `CLIENT`'s `{verdict, fit}` for this trend → click routes to
  that client's strategy.
- Prev / next within the lens.

---

## Interactions & behavior
- **Routing**: single-page, state object `{ view, id, tab }`. `go(view, id, tab)` is threaded through
  components. `view ∈ {dashboard, explore, detail}`. For `explore`, `tab ∈ {pro, dem, client}` and
  `id` carries a `clientId` when deep-linking to a specific client's strategy. Replace with your
  router (e.g. `/`, `/explore?tab=pro`, `/explore/clients/:clientId`, `/trends/:trendId`).
- **Entrance animations** are transform-only and gated so content is never hidden if the animation
  doesn't run. Keep that property if you port them.
- **Theme**: light (cream) is default; a dark (espresso) variant exists. Driven by `data-theme` on
  `<html>`. Do **not** CSS-`transition` any `var()`-derived `background`/`background-color` across a
  theme change — it sticks in Chromium. (Hover backgrounds use no transition for this reason.)

## State management
The prototype keeps only: current route, the Tweaks object (prototype-only), and local filter/search
state inside Explore and ClientStrategy. In production, fetch `ARTIS` once (monthly snapshot) and cache
it; everything else is derived client-side.

---

## Design tokens (from `styles.css`)
**Light (default)** — `--bg #fbf5e6` · `--bg-1 #f5edd7` · `--bg-2 #fffcf3` · `--ink #2c1a11` ·
`--ink-2 #6a4636` · `--muted #9a8067` · **accent `--accent #9c3a2a`** (brick) · `--pos #6c7a3c` ·
`--neg #b0432d` · lines `rgba(58,36,22,.16)`.
**Dark** — `--bg #211610` · `--bg-1 #291c14` · `--ink #f3e8d2` · `--accent #c2563f`.
**Verdict** — Lead `#4f7a44` · Watch `#9a6b1f` · Skip `#a23c2a` (light); brighter equivalents in dark.
**Signal chips** — Surging=accent · Rising=`--pos` · Peaking=Watch amber · Steady=`--ink-2` · Cooling=`--neg`.
**Type** — display `Cormorant Garamond` (the wordmark + headings); body `Hanken Grotesk`. Both Google Fonts.
The wordmark is locked to Cormorant lowercase `artis` with a brick asterisk over the *i*.
**Radii** `--radius 3px` / `--radius-lg 5px`. **Shadow** `--shadow`. **Sidebar** 260px.
Spacing/density scale via `--pad-x/--pad-y/--gap/--grid-min/--row-py` (compact / comfortable / editorial).

## Assets
No external image assets. "Photos" are CSS **material plates** (`Plate` in `ui.jsx`) — layered gradients
+ grain from each trend's `plate` palette. Swap for real photography by replacing `Plate` with an
`<img>` and adding an image URL to each trend if/when you have art. Fonts load from Google Fonts.

---

## Integration — connecting to your automation
1. **Trends (PRO/DEM)**: your professional + demand analysis files already contain the raw patterns.
   `build_dataset.js` (included) is the exact, documented transform that turns those two JSON files
   into the `PRO`/`DEM`/`CATEGORIES`/`CONVERGENCE`/`ISSUE` shapes above (momentum normalization,
   lifecycle→signal mapping, category classification, history synthesis). Run it monthly.
2. **Clients**: maintain a small config of the firms you serve (the `Client` fields above).
3. **STRATEGY (your matcher)**: for each client × trend, emit `{ verdict, fit, why, opinion }`, plus a
   per-client `brief`. This is the one piece the prototype faked — drop in your real engine's output
   keyed by `clientId` → `trendId`. (Thresholds in the sample: Lead ≥ 72, Watch 50–71, Skip < 50 — yours can differ.)
4. **Serve**: expose the assembled object as JSON (e.g. `GET /api/issues/current`). In the app, fetch
   it on load and pass it where the prototype reads `window.ARTIS`. Nothing else in the UI changes.

> Net: keep the four producers — **Trends**, **Clients**, **Strategy(matcher)**, **Brief** — and the
> screens above light up automatically.
