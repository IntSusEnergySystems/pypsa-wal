// « Où peut-on installer du photovoltaïque au sol en Wallonie ? » — the dashboard.
//
// State lives in the URL (#etape=7&agri=ferme&friches=1&zae=25&eau=0&sols=0)
// and every view is a pure function of it.  The capacity arithmetic below is
// pv_lib.policy_total of the workflow, line for line; infographic_data.py
// checks the two against each other before it writes the data.

import { int, dec, pct, gw, typo, tpl, signed } from "./fmt.js";
import { icon } from "./icons.js";
import { loadClasses, palette, paint, Pair, buildSvg, GREEN, PARK_RULE, CLOSED } from "./map.js";

const $ = (id) => document.getElementById(id);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

// The build stamps the module URL (?v=…) so a republished page is never read
// from a stale cache; the data files take the same stamp.
const Q = new URL(import.meta.url).search;
const T = await (await fetch(`textes.json${Q}`)).json();
const DATA = await (await fetch(`data/states.json${Q}`)).json();
const LM = await (await fetch(`data/landmarks.json${Q}`)).json();
const META = DATA.meta;
const STEPS = T.etapes.map((e) => e.id);
const GIS = META.gisements;
const SYS = Object.fromEntries(GIS.map((g) => [g.key, g.system]));

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const CHOICES = {
  agri: ["ferme", "q06", "q2", "prairies", "toutes"],
  friches: [1, 0],
  zae: [0, 25, 100],
  eau: [0, 1],
  sols: [0, 1, 2],   // aucun, part réaliste (référence), tous
};
const DEFAULT = { etape: "0", agri: "q06", friches: 1, zae: Math.round(100 * META.policy_reference.zae), eau: 0, sols: 1 };
const POOR_SHARE = [0, META.soil_evidence.share, 1];
const state = { ...DEFAULT };

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const s = { ...DEFAULT };
  if (h.has("etape") && STEPS.includes(h.get("etape"))) s.etape = h.get("etape");
  if (CHOICES.agri.includes(h.get("agri"))) s.agri = h.get("agri");
  for (const k of ["friches", "zae", "eau", "sols"]) {
    if (h.has(k) && CHOICES[k].includes(+h.get(k))) s[k] = +h.get(k);
  }
  return s;
}

function writeHash() {
  const h = new URLSearchParams();
  for (const k of ["etape", "agri", "friches", "zae", "eau", "sols"]) h.set(k, state[k]);
  history.replaceState(null, "", `#${h}`);
}

const nChanged = (s = state) => ["agri", "friches", "zae", "eau", "sols"].reduce((n, k) => n + (s[k] !== DEFAULT[k] ? 1 : 0), 0);

// ---------------------------------------------------------------------------
// The arithmetic (pv_lib.policy_total)
// ---------------------------------------------------------------------------
const QUOTA = { q06: META.agri.quotas[0], q1: META.agri.quotas[1], q2: META.agri.quotas[2] };
const agriSet = (a) => (a === "ferme" ? "none" : a === "toutes" ? "toutes" : "prairies");

function mwcPerHa(key) {
  const sys = SYS[key];
  return sys === "floating" ? META.densities_mwc_ha.floating * META.floating_coverage : META.densities_mwc_ha[sys];
}

function shares(s) {
  const sh = { ...META.policy_reference };
  sh.sar = s.friches ? 1 : 0;
  sh.zae = sh.zspec = s.zae / 100;
  sh.water_other = s.eau ? 1 : 0;
  sh.agri_zone_poor = POOR_SHARE[s.sols];
  const admitted = META.agri.sets[agriSet(s.agri)] || [];
  for (const g of GIS) if (SYS[g.key].startsWith("agrivoltaic")) sh[g.key] = admitted.includes(g.key) ? 1 : 0;
  return sh;
}

function compute(s = state) {
  const key = `a${agriSet(s.agri)}-s${s.friches}-z${s.zae > 0 ? 1 : 0}-u${s.sols > 0 ? 1 : 0}`;
  const openable = DATA.combos[key];
  const sh = shares(s);
  const open = {};
  for (const g of GIS) open[g.key] = openable[g.key] * (sh[g.key] || 0);
  const agri = GIS.filter((g) => SYS[g.key].startsWith("agrivoltaic")).map((g) => g.key);
  const agriHa = agri.reduce((a, k) => a + open[k], 0);
  const quota = QUOTA[s.agri];
  const capHa = quota != null ? quota * META.agri.sau_ha : null;
  let f = 1;
  if (capHa != null && agriHa > capHa) f = capHa / agriHa;
  for (const k of agri) open[k] *= f;
  const mwc = {};
  let total = 0, ha = 0;
  for (const g of GIS) {
    mwc[g.key] = open[g.key] * mwcPerHa(g.key);
    total += mwc[g.key];
    ha += open[g.key];
  }
  const groups = META.groups.map(() => 0);
  for (const g of GIS) groups[g.group] += mwc[g.key];
  return { mwc, open, total, ha, groups, agriHa: agriHa * f, agriPossibleHa: agriHa, capHa, capBinding: f < 1, sh };
}

const technicalMwc = GIS.reduce((a, g) => a + META.technical_ha[g.key] * mwcPerHa(g.key), 0);
const REF = compute(DEFAULT);

// Capacity carried by each stop of the timeline.
function stepValue(id, s = state) {
  if (id === "bilan" || id === "7") return compute(s).total;
  if (id === "6") return technicalMwc;
  const i = +id;
  return META.funnel[i].left_ha * META.densities_mwc_ha.ground;
}
const stepLand = (id) => (id === "bilan" || id === "7" ? null : META.funnel[Math.min(+id, 6)].left_ha);
const stepNum = (id) => (id === "bilan" ? 8 : +id);

function values(s = state) {
  const c = compute(s);
  const B = META.benchmarks;
  return {
    region_km2: int(META.region_ha / 100),
    gwc: gwStr(c.total),
    ref_gwc: gwStr(REF.total),
    tech_gwc: gwStr(technicalMwc),
    model_gwc: gwStr(B.model_p_nom_max_mw),
    pace_gwc: dec(B.pace_2030_gwc, 0),
    installe_gwc: dec(B.installed_total_2025_mwc / 1000, 1),
    park_ha: dec(META.park.min_area_ha, 0),
    park_m: int(META.park.min_width_m),
    dens_sol: dec(META.densities_mwc_ha.ground, 1),
    dens_agri: dec(META.densities_mwc_ha.agrivoltaic_grazing, 1),
    zae_pct: int(Math.round(100 * META.policy_reference.zae)),
    sau_kha: int(META.agri.sau_ha / 1000),
    date: META.calc_date,
    flh: int(META.energy.ground.flh_h),
    twh: dec((c.total * META.energy.ground.flh_h) / 1e6, 1),
    sols_pct: dec(100 * META.soil_evidence.share, 0),
    sols_ha: int(META.soil_evidence.steps_ha.mapped_poor_ha),
    sols_farmed_pct: dec(100 * META.soil_evidence.farmed_share_by_awac_class["2"], 0),
    quota_ha: int(META.agri.sau_ha * META.agri.quotas[0]),
    strict_gwc: gwStr(compute({ ...DEFAULT, agri: "ferme", sols: 0 }).total),
  };
}

function gwDelta(mw) {
  const a = Math.abs(mw);
  const txt = a >= 10000 ? int(a / 1000) : a >= 1000 ? dec(a / 1000, 1) : dec(a / 1000, 2);
  return `${mw >= 0 ? "+" : "−"}${txt}\u202fGWc`;
}

function gwStr(mw) {
  if (mw >= 100000) return int(mw / 1000);
  if (mw >= 10000) return dec(mw / 1000, 0);
  return dec(mw / 1000, 1);
}

// ---------------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------------
const pair = new Pair($("map-a"), $("map-b"));
const { parks } = buildSvg($("map-svg"), $("map-box"), META, LM);
const MAP = await loadClasses(`data/map.png${Q}`, META.grid.cols, META.grid.rows, META.grid.scale);
const LOUPE = await loadClasses(`data/loupe.png${Q}`, META.loupe_grid.cols, META.loupe_grid.rows, META.loupe_grid.scale);
$("loading").hidden = true;
$("map-box").style.aspectRatio = `${META.grid.cols} / ${META.grid.rows}`;
let lastKey = null;

function renderMap(animate) {
  const step = stepNum(state.etape) >= 7 ? 7 : stepNum(state.etape);
  const sh = shares(state);
  const rationed = compute().capBinding;
  const key = `${step}|${JSON.stringify(sh)}|${rationed}`;
  if (key === lastKey) return;
  lastKey = key;
  const pal = palette(META, step, (g) => ((sh[g] || 0) > 0 ? (rationed && SYS[g].startsWith("agrivoltaic") ? 2 : 1) : 0));
  const cssW = $("map-box").getBoundingClientRect().width || 800;
  paint(pair.back, MAP, pal, Math.max(1, Math.round((1.1 * MAP.cols) / cssW)));
  pair.show(animate);
  paint($("loupe-canvas"), LOUPE, pal, 1);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
const STEP = Object.fromEntries(T.etapes.map((e) => [e.id, e]));

function renderIndicator() {
  const id = state.etape;
  const v = stepValue(id);
  const land = stepLand(id);
  const n = stepNum(id);
  const label = n <= 5 ? T.indicateur.place_pour : n === 6 ? T.indicateur.technique : T.indicateur.possible;
  let html = `<div class="ind-label">${typo(label)}</div>` +
    `<div class="ind-n">${gwStr(v)}<span class="ind-unit"> GWc</span></div>`;
  if (n === 0) html += `<div class="ind-sub">${typo(T.indicateur.si_tout)}</div>`;
  if (land != null) {
    html += `<div class="ind-area">${tpl(T.indicateur.terrain, {
      km2: int(land / 100), pct: dec((100 * land) / META.region_ha, land / META.region_ha < 0.1 ? 1 : 0) })}</div>`;
  } else {
    const c = compute();
    html += `<div class="ind-area">${tpl(T.indicateur.ouverts, { ha: int(c.ha) })}</div>`;
    if (c.capBinding) html += `<div class="ind-area">${tpl(T.indicateur.quota, { ha: int(c.capHa), possible: int(c.agriPossibleHa) })}</div>`;
  }
  const k = nChanged();
  if (k) html += `<span class="ind-tag">${tpl(k > 1 ? T.indicateur.choix_n : T.indicateur.choix_1, { n: k })}</span>`;
  $("indicator").innerHTML = html;
}

function effectLine(id) {
  const i = STEPS.indexOf(id);
  if (i <= 0) return "";
  const prev = STEPS[i - 1];
  const a = stepLand(prev), b = stepLand(id);
  if (a != null && b != null) {
    const d = b - a;
    return `<p class="effect big">${typo(`${signed(d / 100)} km²`)} <span class="effect-rel">(${signed((100 * d) / a, (x) => dec(x, 0))} %)</span></p>`;
  }
  if (id === "7") {
    const d = compute().total - technicalMwc;
    return `<p class="effect big">${typo(`${signed(d / 1000, (x) => gwStr(x * 1000))} GWc`)}</p>` +
      `<p class="effect">${tpl(T.effet.fermes, { gwc: gwStr(technicalMwc - compute().total) })}</p>`;
  }
  return "";
}

function renderCard() {
  const e = STEP[state.etape];
  const V = values();
  const fam = e.famille != null ? META.families[e.famille - 1].colour : e.id === "6" ? PARK_RULE : GREEN;
  let body = `<div class="card-band" style="--c:${fam}"><span class="card-picto">${icon(e.picto, 30)}</span></div>` +
    `<div class="card-body"><div class="eyebrow">${typo(state.etape === "bilan" ? T.commandes.bilan : tpl(T.commandes.etape_n, { n: state.etape, total: 7 }))}</div>` +
    `<h2 class="card-title">${tpl(e.titre, V)}</h2>` +
    `<p class="card-rule">${tpl(e.regle, V)}</p>` +
    `<div class="card-effect">${effectLine(state.etape)}</div>`;
  if (state.etape === "7" || state.etape === "bilan") body += breakdown();
  if (state.etape === "bilan") body += bilanBars();
  body += `<p class="card-why"><span class="why-label">${typo(T.pourquoi)}</span> ${tpl(e.pourquoi, V)}</p>`;
  if (e.source) body += `<p class="card-source">${typo(e.source)}</p>`;
  if (state.etape === "7") body += `<a class="card-cta" href="#et-si">${typo(T.commandes.voir_etsi)}</a>`;
  body += "</div>";
  $("card").innerHTML = body;
}

function breakdown() {
  const c = compute();
  const max = Math.max(...META.groups.map((_, i) => META.groups.length && c.groups[i]), 1);
  let h = `<div class="gis-bars"><div class="gb-head">${typo(T.bilan.par_gisement)}</div>`;
  META.groups.forEach((g, i) => {
    h += `<div class="gb-row"><span class="gb-sw" style="--c:${g.colour}"></span>` +
      `<span class="gb-label">${typo(T.groupes[i])}</span>` +
      `<span class="gb-track"><span class="gb-bar" style="width:${(100 * c.groups[i]) / max}%;--c:${g.colour}"></span></span>` +
      `<span class="gb-val">${gwStr(c.groups[i])} GWc</span></div>`;
  });
  return h + "</div>";
}

function bilanBars() {
  const c = compute();
  const B = META.benchmarks;
  const rows = [
    [T.bilan.ce_choix, c.total, ""],
    [T.bilan.reference, REF.total, "ref"],
    [T.bilan.strict, compute({ ...DEFAULT, agri: "ferme", sols: 0 }).total, "ref"],
    [T.bilan.modele, B.model_p_nom_max_mw, "ext"],
    [T.bilan.pace, B.pace_2030_gwc * 1000, "ext"],
  ];
  const max = Math.max(...rows.map((r) => r[1]));
  let h = `<div class="bilan-bars">`;
  for (const [label, v, cls] of rows) {
    h += `<div class="bb-row"><span class="bb-label">${typo(label)}</span>` +
      `<span class="bb-track"><span class="bb-bar ${cls}" style="width:${(100 * v) / max}%"></span></span>` +
      `<span class="bb-val">${gwStr(v)} GWc</span></div>`;
  }
  h += `<p class="bb-note">${tpl(T.bilan.note, values())}</p>`;
  return h + "</div>";
}

function renderTimeline() {
  const tl = $("timeline");
  const vals = STEPS.map((id) => stepValue(id));
  const max = Math.max(...vals.slice(1));
  const cur = STEPS.indexOf(state.etape);
  let h = `<div class="tl-controls">` +
    `<button class="tl-btn" id="tl-prev" aria-label="${T.commandes.precedent}" ${cur === 0 ? "disabled" : ""}>${icon("prev", 18)}</button>` +
    `<button class="tl-btn play" id="tl-play">${icon(playing ? "pause" : "play", 16)} ${typo(playing ? T.commandes.pause : T.commandes.lecture)}</button>` +
    `<button class="tl-btn" id="tl-next" aria-label="${T.commandes.suivant}" ${cur === STEPS.length - 1 ? "disabled" : ""}>${icon("next", 18)}</button></div>`;
  h += `<div class="tl-track" style="--n:${STEPS.length}"><div class="tl-line"><div class="tl-line-fill" style="width:${(100 * cur) / (STEPS.length - 1)}%"></div></div>`;
  STEPS.forEach((id, i) => {
    const e = STEP[id];
    const cls = i < cur ? "past" : i === cur ? "current" : "";
    const hgt = i === 0 ? 58 : Math.max(2, (58 * Math.min(vals[i], max)) / max);
    const fam = e.famille != null ? `<span class="tl-fam" style="--c:${META.families[e.famille - 1].colour}"></span>` : "";
    h += `<button class="tl-stop ${cls}" data-id="${id}" aria-label="${typo(e.titre)}">` +
      `<span class="tl-bar-area"><span class="tl-val">${gwStr(vals[i])} GWc</span><span class="tl-bar${i === 0 ? " tl-bar-cut" : ""}" style="height:${hgt}px"></span></span>` +
      `<span class="tl-node">${id === "bilan" ? "★" : id}${fam}</span>` +
      `<span class="tl-label">${typo(e.court || e.titre)}</span></button>`;
  });
  tl.innerHTML = h + "</div>";
  tl.querySelectorAll(".tl-stop").forEach((b) => b.addEventListener("click", () => { stopPlay(); update({ etape: b.dataset.id }); }));
  $("tl-prev").addEventListener("click", () => { stopPlay(); go(-1); });
  $("tl-next").addEventListener("click", () => { stopPlay(); go(1); });
  $("tl-play").addEventListener("click", togglePlay);
}

function renderLegend() {
  const n = stepNum(state.etape);
  let h = n >= 6 ? `<ul class="lg-list">` : `<ul class="lg-list"><li class="avail"><span class="sw" style="--c:${GREEN}"></span>${typo(T.legende.disponible)}</li>`;
  if (n >= 1 && n < 7) {
    h += `<li class="lg-head">${typo(T.legende.retire)}</li>`;
    META.families.forEach((f, i) => {
      h += `<li class="${i + 1 > n ? "off" : ""}"><span class="sw" style="--c:${f.colour}"></span>${typo(T.familles[i])}</li>`;
    });
  }
  if (n === 6) h += `<li><span class="sw" style="--c:${PARK_RULE}"></span>${typo(T.legende.trop_petit)}</li>`;
  h += "</ul>";
  if (n >= 6) {
    h += `<ul class="lg-list lg-gis"><li class="lg-head">${typo(T.legende.gisements)}</li>`;
    META.groups.forEach((g, i) => { h += `<li><span class="sw" style="--c:${g.colour}"></span>${typo(T.groupes[i])}</li>`; });
    if (n >= 7 && compute().capBinding) h += `<li><span class="sw sw-rationed"></span>${tpl(T.legende.quota, { pct: dec((100 * compute().capHa) / compute().agriPossibleHa, 0) })}</li>`;
    if (n >= 7) h += `<li><span class="sw" style="--c:${CLOSED}"></span>${typo(T.legende.ferme)}</li>`;
    h += "</ul>";
  }
  h += `<div class="lg-extra"><label class="lg-toggle"><input type="checkbox" id="lg-parcs" ${showParks ? "checked" : ""}><span class="ring"></span>${tpl(T.legende.parcs, { n: LM.parks.length })}</label></div>`;
  $("legend").innerHTML = h;
  $("lg-parcs").addEventListener("change", (ev) => { showParks = ev.target.checked; parks.style.display = showParks ? "" : "none"; });
  parks.style.display = showParks ? "" : "none";
}
let showParks = true;

// ---------------------------------------------------------------------------
// Et si… ?
// ---------------------------------------------------------------------------
function renderEtsi() {
  const E = T.et_si;
  $("etsi-titre").innerHTML = typo(E.titre);
  $("etsi-intro").innerHTML = typo(E.intro);
  let h = "";
  for (const [k, spec] of Object.entries(E.choix)) {
    const active = state[k] !== DEFAULT[k];
    h += `<fieldset class="choice ${active ? "active" : ""}"><legend class="ch-head">${icon(spec.picto, 20)}<span class="ch-label">${typo(spec.titre)}</span></legend>`;
    h += `<p class="ch-rule">${tpl(spec.regle, values())}</p>`;
    // Each option shows what it changes against this choice's reference
    // option, the other choices staying as they are.
    const base = compute({ ...state, [k]: DEFAULT[k] }).total;
    for (const opt of spec.options) {
      const val = typeof DEFAULT[k] === "number" ? +opt.v : opt.v;
      const d = compute({ ...state, [k]: val }).total - base;
      const isRef = val === DEFAULT[k];
      const dir = isRef || Math.abs(d) < 0.5 ? "" : d > 0 ? "warm" : "cool";
      const checked = state[k] === val;
      h += `<label class="opt ${checked ? "on" : ""} ${dir}"><input type="radio" name="${k}" value="${opt.v}" ${checked ? "checked" : ""}>` +
        `<span class="opt-label">${tpl(opt.label, values())}${isRef ? ` <span class="ref-tag">${typo(E.reference)}</span>` : ""}` +
        `${opt.note ? `<span class="opt-note">${tpl(opt.note, values())}</span>` : ""}</span>` +
        `<span class="opt-val">${isRef ? "" : gwDelta(d)}</span></label>`;
    }
    h += `<p class="ch-why">${tpl(spec.pourquoi, values())}</p></fieldset>`;
  }
  $("etsi-choix").innerHTML = h;
  $("etsi-choix").querySelectorAll("input[type=radio]").forEach((inp) => inp.addEventListener("change", () => {
    const k = inp.name;
    update({ [k]: typeof DEFAULT[k] === "number" ? +inp.value : inp.value, etape: stepNum(state.etape) < 7 ? "7" : state.etape });
  }));
  $("etsi-reset").innerHTML = typo(E.reinitialiser);
  $("etsi-reset").disabled = nChanged() === 0;
}
$("etsi-reset").addEventListener("click", () => update({ agri: DEFAULT.agri, friches: DEFAULT.friches, zae: DEFAULT.zae, eau: DEFAULT.eau, sols: DEFAULT.sols }));

// ---------------------------------------------------------------------------
// Static parts
// ---------------------------------------------------------------------------
function renderStatic() {
  const V = values(DEFAULT);
  $("titre").innerHTML = typo(T.titre);
  $("sous-titre").innerHTML = typo(T.sous_titre);
  $("btn-methode").innerHTML = `${icon("info", 16)} ${typo(T.lien_methode)}`;
  $("lien-rapport").innerHTML = typo(T.lien_rapport);
  $("lien-etsi").innerHTML = typo(T.et_si.titre);
  $("fab-etsi").innerHTML = typo(T.et_si.titre);
  $("map-note").innerHTML = typo(T.legende.note);
  $("loupe-caption").innerHTML = `${icon("loupe", 13)} <span>${typo(T.loupe)}</span>`;
  $("methode-titre").innerHTML = typo(T.methode.titre);
  $("methode-body").innerHTML = T.methode.paragraphes.map((p) => `<p>${tpl(p, V)}</p>`).join("");
  $("methode-fermer").innerHTML = typo(T.methode.fermer);
  $("btn-methode").addEventListener("click", () => $("methode").showModal());
  $("expert-titre").innerHTML = typo(T.expert.titre);
  $("expert-body").innerHTML = expertTable();
  $("credits").innerHTML = `<p>${tpl(T.credits, V)}</p><img src="img/cc_by_logo.png" alt="CC BY 4.0" height="30">`;
  $("fab-etsi").addEventListener("click", () => $("et-si").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth" }));
  $("loupe").addEventListener("click", () => $("loupe").classList.toggle("big"));
}

function expertTable() {
  const S = META.sensitivity || [];
  let h = `<p>${typo(T.expert.intro)}</p><table class="expert-table"><thead><tr><th>${typo(T.expert.cas)}</th><th>GWc</th><th>${typo(T.expert.ecart)}</th></tr></thead><tbody>`;
  for (const r of S) {
    const lab = T.expert.cases[r.case] || r.label;
    h += `<tr class="g-${r.group}"><td>${typo(lab)}</td><td>${gwStr(r.policy_mwc)}</td><td>${signed(r.delta_pct, (x) => dec(x, 0))}${" "}%</td></tr>`;
  }
  return h + "</tbody></table>";
}

// ---------------------------------------------------------------------------
// Hover
// ---------------------------------------------------------------------------
function describe(cls) {
  const n = stepNum(state.etape);
  if (cls === 0) return null;
  if (cls <= 5) return cls <= n ? [META.families[cls - 1].colour, tpl(T.survol.retire, { famille: T.familles[cls - 1] })] : [GREEN, T.survol.disponible];
  if (cls === 6) return n >= 6 ? [PARK_RULE, T.legende.trop_petit] : [GREEN, T.survol.disponible];
  const g = GIS[cls - 11];
  if (!g) return null;
  if (n < 6) return [GREEN, T.survol.disponible];
  const open = (shares(state)[g.key] || 0) > 0;
  const lab = T.gisements[g.key] || g.key;
  return [open || n < 7 ? META.groups[g.group].colour : CLOSED, n >= 7 ? `${lab} · ${open ? T.survol.ouvert : T.survol.ferme}` : lab];
}

function setupHover() {
  const box = $("map-box"), tip = $("tooltip");
  box.addEventListener("mousemove", (ev) => {
    const r = box.getBoundingClientRect();
    const x = Math.floor(((ev.clientX - r.left) / r.width) * MAP.cols);
    const y = Math.floor(((ev.clientY - r.top) / r.height) * MAP.rows);
    const d = x >= 0 && y >= 0 && x < MAP.cols && y < MAP.rows ? describe(MAP.cls[y * MAP.cols + x]) : null;
    if (!d || ev.target.closest(".loupe, .indicator")) { tip.classList.remove("show"); return; }
    tip.innerHTML = `<span class="sw" style="--c:${d[0]}"></span>${typo(d[1])}`;
    const tx = Math.min(ev.clientX - r.left + 14, r.width - 250);
    tip.style.left = `${tx}px`;
    tip.style.top = `${ev.clientY - r.top + 14}px`;
    tip.classList.add("show");
  });
  box.addEventListener("mouseleave", () => tip.classList.remove("show"));
}

// ---------------------------------------------------------------------------
// Driving
// ---------------------------------------------------------------------------
let playing = false, timer = null;
function go(d) {
  const i = STEPS.indexOf(state.etape);
  const j = Math.max(0, Math.min(STEPS.length - 1, i + d));
  if (j !== i) update({ etape: STEPS[j] });
}
function togglePlay() {
  if (playing) return stopPlay(true);
  playing = true;
  if (state.etape === "bilan") state.etape = "0";
  render();
  timer = setInterval(() => {
    if (state.etape === "bilan") return stopPlay(true);
    go(1);
  }, 2600);
}
function stopPlay(rerender = false) {
  if (!playing) return;
  playing = false;
  clearInterval(timer);
  if (rerender) renderTimeline();
}

function render(animate = !REDUCED) {
  renderMap(animate);
  renderTimeline();
  renderIndicator();
  renderCard();
  renderLegend();
  renderEtsi();
  $("fab-etsi").classList.toggle("changed", nChanged() > 0);
}

function update(patch) {
  Object.assign(state, patch);
  writeHash();
  render();
}

window.addEventListener("hashchange", () => { Object.assign(state, readHash()); render(); });
document.addEventListener("keydown", (ev) => {
  if (ev.target.closest("input, textarea, dialog")) return;
  if (ev.key === "ArrowRight") { stopPlay(); go(1); }
  if (ev.key === "ArrowLeft") { stopPlay(); go(-1); }
});

// Export hook: the capture script sets a state and waits for the frame.
window.renderState = async (hash) => {
  location.hash = hash;
  Object.assign(state, readHash());
  render(false);
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return true;
};

Object.assign(state, readHash());
renderStatic();
setupHover();
render(false);
document.body.classList.add("ready");
