/**
 * build_dataset.js — reference pipeline: raw analysis JSON  ->  prototype/data.js
 *
 *   node build_dataset.js \
 *        professional_trends_analysis.json \
 *        demand_trends_analysis.json \
 *        clients.json \
 *        > prototype/data.js
 *
 * Produces `window.ARTIS = {…}` matching the Data Contract in README.md.
 *
 * WHAT THIS FILE OWNS (deterministic, safe to keep):
 *   - PRO / DEM trend objects from your two analysis files
 *   - category classification, momentum normalization, signal mapping, 12-pt history synthesis
 *   - CONVERGENCE + ISSUE
 *
 * WHAT YOU REPLACE:
 *   - computeStrategy()  ← the per-client matcher. This is a NAIVE keyword stand-in.
 *     Swap it for your real matching/LLM engine's output: { verdict, fit, why, opinion } per
 *     (client, trend) + a per-client `brief`.  Everything else stays.
 */
const fs = require('fs');
const path = require('path');

const [, , proPath, demPath, clientsPath, strategyPath] = process.argv;
if (!proPath || !demPath) {
  console.error('usage: node build_dataset.js <professional.json> <demand.json> [clients.json] [strategy.json|strategyDir]');
  process.exit(1);
}
const proRaw = JSON.parse(fs.readFileSync(proPath, 'utf8'));
const demRaw = JSON.parse(fs.readFileSync(demPath, 'utf8'));
const CLIENTS = clientsPath
  ? JSON.parse(fs.readFileSync(clientsPath, 'utf8'))
  : require('./clients.sample.json');

// ---------- real strategy output (from generate_editorial_briefs.py) ----------
// Optional 4th arg: either a single strategy JSON ({ clientId: {brief,counts,picks} })
// or a directory of them. Merged into LOADED_STRATEGY; any client without a real
// entry falls back to the keyword stub computeStrategy() below.
const LOADED_STRATEGY = {};
if (strategyPath) {
  const stat = fs.statSync(strategyPath);
  const files = stat.isDirectory()
    ? fs.readdirSync(strategyPath).filter((f) => f.endsWith('.json')).map((f) => path.join(strategyPath, f))
    : [strategyPath];
  for (const f of files) {
    try { Object.assign(LOADED_STRATEGY, JSON.parse(fs.readFileSync(f, 'utf8'))); }
    catch (e) { console.error(`warning: could not read strategy file ${f}: ${e.message}`); }
  }
  console.error(`Loaded real strategy for: ${Object.keys(LOADED_STRATEGY).join(', ') || '(none)'}`);
}

// ---------- helpers ----------
const uniq = (a) => [...new Set(a)];
const SMALL = new Set(['and','or','for','of','the','to','with','in','on','a','an','as','by','at']);
const tcWord = (w, first) => w.split('-').map((p, i) => {
  const lp = p.toLowerCase();
  if (SMALL.has(lp) && !(first && i === 0)) return lp;
  return p.charAt(0).toUpperCase() + p.slice(1);
}).join('-');
const titleCase = (s) => s.split(' ').map((w, i) => tcWord(w, i === 0)).join(' ');
const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
const trimSentence = (s, n) => {
  if (!s) return ''; if (s.length <= n) return s;
  const cut = s.slice(0, n); const p = cut.lastIndexOf('. ');
  return p > 40 ? cut.slice(0, p + 1) : cut.slice(0, cut.lastIndexOf(' ')) + '…';
};
const dedupe = (reps, k) => { const seen = new Set(), out = []; for (const r of reps) { const key = k(r); if (!seen.has(key)) { seen.add(key); out.push(r); } } return out; };

// ---------- taxonomy ----------
const CATEGORIES = [
  { id:'materials', label:'Materials', color:'#b07d33', palette:['#241a10','#5c4326','#b07d33','#e6cd97'] },
  { id:'colour',    label:'Colour',    color:'#b1543a', palette:['#2a0f0f','#6e2526','#b1543a','#d98a6a'] },
  { id:'form',      label:'Form',      color:'#6f7c41', palette:['#23291c','#44502f','#6f7c41','#aebb86'] },
  { id:'craft',     label:'Craft',     color:'#8a6188', palette:['#241a26','#4a3450','#8a6188','#c39ec0'] },
  { id:'space',     label:'Space',     color:'#4f6f7a', palette:['#16242a','#2f4c54','#4f6f7a','#9bb6bf'] },
  { id:'nature',    label:'Nature',    color:'#5f7b4e', palette:['#1c2a1a','#36492f','#5f7b4e','#a7bd8c'] },
  { id:'market',    label:'Market',    color:'#9c6b4f', palette:['#241810','#4a3120','#9c6b4f','#d3a87f'] },
];
const catKW = {
  colour:['oxblood','colour','color','verdigris','palette','lacquer'],
  nature:['garden','plant','botanical','companion','floricult','flower','biophilic','floral','outdoor','wallpaper'],
  market:['marketplace','shopping','retail','platform','members','business','marketing','commission','appointment','event space','immersive'],
  craft:['craft','artisan','handmade','weaving','marquetry','bespoke','ceramic','stoneware','murano','burlwood','glass','diaspora','indonesian','african','chinese','postcolonial','tile','mosaic','millwork'],
  space:['bath','kitchen','retreat','room','oasis','wellness','spa','studio','bunk','closet','pantry','aging-in-place','shower'],
  materials:['brass','steel','metal','stone','marble','travertine','onyx','plaster','tadelakt','oak','wood','linen','matelass','quilt','muslin','cabinetry','burl','concrete','reeded','fluted','coffered'],
  form:['modular','seating','furniture','monogram','sofa','couch','sculptural','curved','chair','table','revival','casual','modernism','1990','midcentury','animalia','architectural'],
};
const classify = (label) => {
  const l = label.toLowerCase();
  for (const c of ['colour','nature','market','craft','space','materials','form']) if (catKW[c].some((k) => l.includes(k))) return c;
  return 'form';
};
const catPal = (id) => CATEGORIES.find((c) => c.id === id).palette;

// 12-pt illustrative series shaped by the trend's signal
const SIG_SHAPE = { Surging:'surge', Rising:'rise', Peaking:'peak', Steady:'steady', Cooling:'cool' };
function hist(now, shape, seed) {
  const out = [];
  for (let i = 0; i < 12; i++) {
    const t = i / 11; let base;
    if (shape === 'surge') base = now * (0.45 + 0.55 * Math.pow(t, 2.4));
    else if (shape === 'rise') base = now * (0.6 + 0.4 * t);
    else if (shape === 'peak') base = now * (0.55 + 0.5 * Math.sin(t * 1.4));
    else if (shape === 'cool') base = now * (0.95 - 0.2 * t);
    else base = now * (0.86 + 0.1 * Math.sin(t * 3 + seed));
    out.push(Math.max(6, Math.min(99, Math.round(base + Math.sin(i * 1.7 + seed) * 2.2))));
  }
  out[11] = Math.round(now);
  return out;
}

// ---------- PRO ----------
const proPats = proRaw.patterns.slice().sort((a, b) => a.rank - b.rank).slice(0, 16);
const pS = proPats.map((p) => p.weighted_score), pMin = Math.min(...pS), pMax = Math.max(...pS);
const PRO = proPats.map((p, i) => {
  const cat = classify(p.theme_label);
  const signal = ({ rising:'Rising', stable:'Steady', peaking:'Peaking', declining:'Cooling' }[p.lifecycle_dominant]) || 'Steady';
  const m = Math.min(97, Math.round(56 + 40 * ((p.weighted_score - pMin) / Math.max(1, pMax - pMin)) + (p.tier === 'cross_source' ? 4 : 0)));
  const delta = signal === 'Rising' ? 4 + (i % 4) + (p.tier === 'cross_source' ? 4 : 0)
    : signal === 'Peaking' ? (i % 2 ? 2 : -2) : signal === 'Cooling' ? -(3 + (i % 4)) : (i % 3) - 1;
  const reps = dedupe(p.representative_signals, (r) => r.source_url || r.title).slice(0, 3)
    .map((r) => ({ title:r.title, source:r.source_name, url:r.source_url, lifecycle:r.lifecycle, strength:r.signal_strength, why:r.tag_rationale }));
  return { id:'p-' + slug(p.theme_label), lens:'pro', rank:i + 1, title:titleCase(p.theme_label), category:cat,
    momentum:m, delta, signal, tier:p.tier, sources:uniq(p.sources), signalCount:p.signal_count, score:p.weighted_score,
    blurb:trimSentence(reps[0] && reps[0].why || '', 180), reps, plate:catPal(cat), plateLabel:titleCase(p.theme_label).slice(0, 28), history:hist(m, SIG_SHAPE[signal], i) };
});

// ---------- DEM ----------
const demPats = demRaw.patterns.slice().sort((a, b) => a.rank - b.rank).slice(0, 14);
const dS = demPats.map((p) => p.weighted_score), dMin = Math.min(...dS), dMax = Math.max(...dS);
const trajWord = { breakout:'breaking out', rising:'climbing', steady:'holding steady', declining:'cooling' };
const DEM = demPats.map((p, i) => {
  const cat = classify(p.theme_label);
  const signal = ({ breakout:'Surging', rising:'Rising', steady:'Steady', declining:'Cooling' }[p.quant_trajectory]) || (p.direction === 'rising' ? 'Rising' : 'Steady');
  const m = Math.min(96, Math.round(52 + 40 * ((p.weighted_score - dMin) / Math.max(1, dMax - dMin)) + (p.tier_label === 'cross_source' ? 4 : 0)));
  let delta = p.avg_mom_pct != null ? Math.max(-9, Math.min(18, Math.round(p.avg_mom_pct / 22))) : (signal === 'Surging' ? 12 : signal === 'Rising' ? 7 : (i % 3) - 1);
  if (signal === 'Surging' && delta < 8) delta = 8 + (i % 6);
  const reps = dedupe(p.representative_signals, (r) => r.term_raw).slice(0, 4)
    .map((r) => ({ term:r.term_raw, source:r.source_name, type:r.signal_type, mom:r.mom_pct, yoy:r.yoy_pct, trajectory:r.trajectory }));
  const terms = reps.filter((r) => r.type === 'quantitative').map((r) => r.term).slice(0, 3);
  const momText = p.avg_mom_pct != null ? ` (${p.avg_mom_pct > 0 ? '+' : ''}${Math.round(p.avg_mom_pct)}% MoM` + (p.avg_yoy_pct != null ? `, ${p.avg_yoy_pct > 0 ? '+' : ''}${Math.round(p.avg_yoy_pct)}% YoY)` : ')') : '';
  const blurb = `Client interest is ${trajWord[p.quant_trajectory] || 'present'}${momText}. ${terms.length ? ('Demand signals: ' + terms.join(', ') + '.') : 'Surfacing across realty, search and platform data.'}`;
  return { id:'d-' + slug(p.theme_label), lens:'dem', rank:i + 1, title:titleCase(p.theme_label), category:cat,
    momentum:m, delta, signal, tier:p.tier_label, sources:uniq(p.sources), signalCount:p.signal_count, score:p.weighted_score,
    momPct:p.avg_mom_pct, yoyPct:p.avg_yoy_pct, trajectory:p.quant_trajectory, blurb:trimSentence(blurb, 200), reps,
    plate:catPal(cat), plateLabel:titleCase(p.theme_label).slice(0, 28), history:hist(m, SIG_SHAPE[signal], i + 5) };
});

const ALL = [...PRO, ...DEM];

// ============================================================================
//  computeStrategy()  ←←←  REPLACE THIS ENTIRE FUNCTION with your matcher output
//  Stand-in only: scores by keyword overlap so the prototype has data to show.
// ============================================================================
function hashIdx(s, n) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 131 + s.charCodeAt(i)) >>> 0; return h % n; }
const catLabel = (id) => CATEGORIES.find((c) => c.id === id).label.toLowerCase();
const WHY = {
  Lead:["Squarely on-brand for {name} — {aesthetic}. Make {title} a headline this cycle.","{title} is {name} territory; the {sig} momentum makes it timely to own.","A natural extension of {name}'s {cat} language — lead with it.","This reinforces {name}'s positioning directly. Build the brand story around it.","Few firms are better placed than {name} to own {title} right now.","On-message for {name} — move first while the {cat} signal is {sig}."],
  Watch:["Adjacent to {name}'s world — usable as a {cat} accent, not the headline.","Some real overlap, but {sig} signal means watch {title} before leaning in.","Borrow the idea for {name} without committing the whole room.","{title} could work for {name} in a restrained form — keep it on the radar.","Worth a measured nod; let demand mature before {name} commits.","Partial fit for {name} — test it on one project, don't make it the brand."],
  Skip:["Off-register for {name} — {title} pulls against the house line.","Little here for {name}; note it, but don't build strategy on it.","{title} sits outside {name}'s {cat} sensibility this cycle.","Not a fit for {name} right now — the positioning works against it.","Thin audience overlap for {name}; let competitors chase this one.","{name} gains little from {title} — skip it and stay on message."],
};
const OPINION = {
  Lead:["{first} would champion this — it reinforces everything {name} already stands for.","Expect an enthusiastic yes; it reads as the house language, finally named.","{first} has been doing a version of this for years — they'll embrace it.","A confident yes from {first}; it's squarely their taste.","{first} would want {name}'s name attached to this first."],
  Watch:["{first} would take it under advisement — intriguing, but on their terms.","A cautious maybe — {first} would want it restrained before committing.","{first} would explore it quietly before saying yes in public.","Measured interest from {first}; usable, not a priority."],
  Skip:["{first} would pass — it reads against the {name} sensibility.","Likely a polite no; it sits outside the register they've built.","{first} wouldn't chase this — wrong audience for {name}.","Expect a pass from {first}; it isn't the {name} story."],
};
const fill = (t, c, tr) => t.replace(/{name}/g, c.name).replace(/{aesthetic}/g, c.aesthetic || '')
  .replace(/{first}/g, (c.principal || '').split(' ')[0]).replace(/{sig}/g, tr.signal.toLowerCase())
  .replace(/{title}/g, tr.title).replace(/{cat}/g, catLabel(tr.category));

function computeStrategy(client, trends) {
  const picks = {};
  for (const tr of trends) {
    const text = (tr.title + ' ' + tr.blurb + ' ' + tr.reps.map((r) => r.title || r.term).join(' ')).toLowerCase();
    let fit = 42;
    if ((client.loves || []).includes(tr.category)) fit += 24;
    fit += Math.min(27, (client.loveKw || []).filter((k) => text.includes(k)).length * 9);
    fit -= Math.min(32, (client.avoidKw || []).filter((k) => text.includes(k)).length * 16);
    fit += ({ Surging:10, Rising:7, Peaking:2, Steady:0, Cooling:-7 }[tr.signal] || 0);
    fit = Math.max(14, Math.min(96, fit));
    const verdict = fit >= 72 ? 'Lead' : fit >= 50 ? 'Watch' : 'Skip';
    picks[tr.id] = {
      verdict, fit,
      why: fill(WHY[verdict][hashIdx(client.id + '~' + tr.id, WHY[verdict].length)], client, tr),
      opinion: fill(OPINION[verdict][hashIdx(tr.id + '#' + client.id, OPINION[verdict].length)], client, tr),
    };
  }
  const v = Object.values(picks);
  const counts = { Lead:v.filter((p) => p.verdict === 'Lead').length, Watch:v.filter((p) => p.verdict === 'Watch').length, Skip:v.filter((p) => p.verdict === 'Skip').length };
  return { brief: client.brief || `Strategy for ${client.name}, ${ISSUE.label}.`, counts, picks };
}
// ============================================================================

const ISSUE = (() => {
  const g = new Date(proRaw.generated_at || Date.now());
  const month = g.toLocaleString('en-US', { month: 'long' });
  return { month, year: g.getFullYear(), label: `${month} ${g.getFullYear()}`,
    updated: g.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }),
    proPatterns: proRaw.patterns_total, demTrends: demRaw.trends_total,
    signalsAnalysed: (proRaw.input_signal_count || 0) + (demRaw.input_signal_count || 0),
    trendsShown: ALL.length, proSources: uniq(PRO.flatMap((t) => t.sources)).length, demSources: uniq(DEM.flatMap((t) => t.sources)).length };
})();

// Adopt a real per-client strategy (from the editorial reasoning engine) when one
// exists; otherwise fall back to the keyword stub. Counts are recomputed from the
// trends actually shown (ALL) so the UI's count tiles match the visible pick rows.
function adoptStrategy(loaded, clientName) {
  const picks = loaded.picks || {};
  const shown = {};
  for (const tr of ALL) if (picks[tr.id]) shown[tr.id] = picks[tr.id];
  const v = Object.values(shown);
  const counts = {
    Lead: v.filter((p) => p.verdict === 'Lead').length,
    Watch: v.filter((p) => p.verdict === 'Watch').length,
    Skip: v.filter((p) => p.verdict === 'Skip').length,
  };
  return { brief: loaded.brief || `Strategy for ${clientName}, ${ISSUE.label}.`, counts, picks };
}

const STRATEGY = {};
for (const c of CLIENTS) {
  STRATEGY[c.id] = LOADED_STRATEGY[c.id]
    ? adoptStrategy(LOADED_STRATEGY[c.id], c.name)
    : computeStrategy(c, ALL);
}

// CONVERGENCE — themes that appear on both sides
const tokens = ['stone','wood','glass','botanical','curved','bath','vintage','ceramic','steel','millwork','craft','oak'];
const CONVERGENCE = []; const used = new Set();
for (const tok of tokens) {
  if (CONVERGENCE.length >= 3) break;
  const pro = PRO.find((t) => (t.title + ' ' + t.blurb).toLowerCase().includes(tok));
  const dem = DEM.find((t) => (t.title + ' ' + t.blurb).toLowerCase().includes(tok));
  if (pro && dem && !used.has(pro.id) && !used.has(dem.id)) {
    used.add(pro.id); used.add(dem.id);
    CONVERGENCE.push({ label: tok[0].toUpperCase() + tok.slice(1), pro:{ id:pro.id, title:pro.title, signal:pro.signal }, dem:{ id:dem.id, title:dem.title, signal:dem.signal }, note:'Designers are exploring it while clients are actively searching for it — two-sided momentum worth acting on.' });
  }
}

// strip matcher-only fields from clients before emitting (UI never reads them)
const CLIENTS_OUT = CLIENTS.map(({ loves, loveKw, avoidKw, brief, ...rest }) => rest);

const out = { ISSUE, CATEGORIES: CATEGORIES.map(({ id, label, color }) => ({ id, label, color })), PRO, DEM, CLIENTS: CLIENTS_OUT, STRATEGY, CONVERGENCE };
process.stdout.write('// ARTIS — generated dataset. Do not edit by hand; re-run build_dataset.js.\nwindow.ARTIS = ' + JSON.stringify(out) + ';\n');
