// « Où peut-on installer des éoliennes en Wallonie ? » — the dashboard.
//
// State lives in the URL (#etape=7&derogation=0&isolees=1&interdistance=0&foret=codt)
// and every view is a pure function of it, so the export script drives the
// page through window.renderState() and the GIF is literally the dashboard.

import { int, dec, pct, approx, gw, times, typo, tpl, signed } from "./fmt.js";
import { icon, wallonieIcon } from "./icons.js";
import { FunnelMap, Loupe, loadAttribution, decodePoints, GREEN, FAMILY } from "./map.js";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const EXPORT = params.get("export"); // "portrait" | "landscape" | null
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const T = await (await fetch("textes.json")).json();
const DATA = await (await fetch("data/states.json")).json();
const LM = await (await fetch("data/landmarks.json")).json();
const PTS_RAW = await (await fetch("data/points.json")).json();
const META = DATA.meta;
const STEP_TEXT = Object.fromEntries(T.etapes.map((e) => [e.id, e]));
const FAMKEYS = META.families;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
// isolees=1 is the reference: the Cadre §3.1 exception for machines above
// 3.2 MW, applied only on land no park of four can use. The dashboard shows
// the other position as a switch that bans single turbines.
const DEFAULT = { etape: "0", derogation: 0, isolees: 1, interdistance: 0, foret: 0, parc: 0 };
// The three readings of the forest zone, in the URL by name.
const FORET = ["codt", "resineux", "tout"];
const state = { ...DEFAULT, view: "etape", choix: null };

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const s = { ...DEFAULT };
  // Links made before steps 6 and 7 were merged (23 Sep 2026).
  if (h.has("etape")) s.etape = { "8bis": "7bis", 9: "8" }[h.get("etape")] ?? h.get("etape");
  for (const k of ["derogation", "isolees", "parc"]) if (h.has(k)) s[k] = h.get(k) === "1" ? 1 : 0;
  if (h.has("interdistance")) s.interdistance = [0, 4, 6].includes(+h.get("interdistance")) ? +h.get("interdistance") : 0;
  if (h.has("foret")) s.foret = Math.max(0, FORET.indexOf(h.get("foret")));
  return s;
}

function writeHash() {
  if (EXPORT) return;
  const h = new URLSearchParams();
  h.set("etape", state.etape);
  for (const k of ["derogation", "isolees", "interdistance"]) h.set(k, state[k]);
  h.set("foret", FORET[state.foret]);
  if (state.parc) h.set("parc", 1);
  history.replaceState(null, "", `#${h}`);
}

const comboKey = (s = state) => `d${s.derogation}-i${s.isolees}-x${s.interdistance}-f${s.foret}`;
const combo = (s = state) => DATA.states[comboKey(s)];

// The sequence of stops for the current choices: 0..7, [7bis], 8, bilan.
function sequence(s = state) {
  const seq = ["0", "1", "2", "3", "4", "5", "6", "7"];
  if (s.interdistance) seq.push("7bis");
  return seq.concat(["8", "bilan"]);
}

// Index of a stop in the states' step array: 0-5 land, 6 the free packing
// (not a stop: its count is already the one of step 5), 7 parks, 8 horizon,
// [9 inter-distance], last the residual allowance.
function stepIndex(id, s = state) {
  const n = combo(s).steps.length;
  if (id === "8" || id === "bilan") return n - 1;
  if (id === "7bis") return 9;
  if (id === "6" || id === "7") return +id + 1;
  return +id;
}

const stepData = (id, s = state) => combo(s).steps[stepIndex(id, s)];
const landStep = (id) => (/^\d$/.test(id) ? Math.min(+id, 5) : 5);
const grossMW = (s) => combo(s).steps[combo(s).steps.length - 2].mw;
const nChoices = (s = state) => ["derogation", "isolees", "interdistance", "foret"]
  .reduce((n, k) => n + (s[k] !== DEFAULT[k] ? 1 : 0), 0);

function stepNumberLabel(id) {
  if (id === "bilan") return T.commandes.bilan;
  if (id === "7bis") return "7 bis";
  return id;
}

// Values the text templates can use.
function values(s = state) {
  const R = META.rules;
  const last = stepData("8", s);
  const res = 1 - META.survival.central;
  return {
    region_km2: int(META.region_km2),
    corridor_km: dec(R.corridor_m / 1000, 1),
    habitat_m: R.habitat_m,
    conifer_m: R.conifer_m,
    dwelling_m: R.dwelling_m,
    tip_m: META.turbine.tip_m,
    p_nom: dec(META.turbine.p_nom_mw, 0),
    spacing_m: META.turbine.spacing_m,
    park_link_km: dec(R.park_link_m / 1000, 1),
    km: s.interdistance,
    reserve_pct: Math.round(100 * res),
    orni_pct: Math.round(100 * META.residual.ornithology.central),
    partiel_pct: Math.round(100 * META.residual.partial_constraints.central),
    reserve_max_pct: Math.round(100 * (1 - META.survival.high)),
    gw: gwRound(last.mw),
    lo_gw: gw(last.mw_low),
    hi_gw: gw(last.mw_high),
    fois: times(last.mw / META.installed_mw),
    installe_gw: gw(META.installed_mw),
    date: META.calc_date,
    ref: int(grossMW(DEFAULT)),
    cap: int(META.model_cap_mw),
  };
}

function gwRound(mw) {
  const s = dec(mw / 1000, 1);
  return s.endsWith(",0") ? s.slice(0, -2) : s;
}

// ---------------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------------
const map = new FunnelMap({
  box: $("map-box"),
  maps: [$("map-a"), $("map-b")],
  pts: [$("pts-a"), $("pts-b")],
  svg: $("map-svg"),
  meta: META,
  landmarks: LM,
});
const loupe = new Loupe({ canvas: $("loupe-canvas"), svg: $("loupe-svg"), meta: META, landmarks: LM });
const classes = {};
const points = {};

async function classesFor(land) {
  if (!classes[land]) classes[land] = loadAttribution(`data/attribution_${land}.png`, META.grid);
  return classes[land];
}
function pointsFor(key) {
  if (!key) return null;
  if (!points[key]) points[key] = decodePoints(PTS_RAW[key]);
  return points[key];
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
let rendering = Promise.resolve();

async function render({ animate = !REDUCED && !EXPORT } = {}) {
  const land = combo().land;
  const cls = await classesFor(land);
  if (map.variant !== land) {
    map.setClasses(cls);
    map.variant = land;
  }
  const id = state.etape;
  const sd = stepData(id);
  const pts = pointsFor(sd.pts);
  map.draw({ step: landStep(id), pts, ptsKey: sd.pts, fleet: !!state.parc }, animate);
  loupe.draw({ cls, step: landStep(id), stepId: id, pts });
  $("loading").hidden = true;
  renderIndicator(animate);
  renderCard();
  renderTimeline();
  renderLegend();
  renderEtsi();
  renderExport();
  requestAnimationFrame(() => map.placeLeader($("loupe")));
  writeHash();
}

function update(patch, opts) {
  Object.assign(state, patch);
  const seq = sequence();
  if (!seq.includes(state.etape)) state.etape = state.etape === "7bis" ? "8" : "0";
  rendering = rendering.then(() => render(opts));
  return rendering;
}

// --- key figure -------------------------------------------------------------
const tweens = {};
function tweenNumber(elId, to, fmtFn, animate) {
  const e = $(elId);
  if (!e) return;
  const from = tweens[elId] ?? to;
  tweens[elId] = to;
  if (!animate || from === to || document.hidden) {
    e.textContent = fmtFn(to);
    return;
  }
  // Start from the old value at once, and land on the new one even if the
  // tab never gets an animation frame (background tabs, throttled panes).
  e.textContent = fmtFn(from);
  const t0 = performance.now(), dur = 650;
  const tick = (t) => {
    if (tweens[elId] !== to) return;
    const k = Math.min(1, (t - t0) / dur);
    e.textContent = fmtFn(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  setTimeout(() => {
    if (tweens[elId] === to) e.textContent = fmtFn(to);
  }, dur + 120);
}

function renderIndicator(animate) {
  const id = state.etape;
  const sd = stepData(id);
  const I = T.indicateur;
  const final = id === "8" || id === "bilan";
  const early = /^[0-5]$/.test(id);
  const label = early ? I.place_pour : final ? I.possibles : I.autorisees;
  const approxMark = final ? "≈ " : "";
  let area = "";
  if (!final) {
    area = tpl(I.terrain, { km2: int(sd.area_km2), pct: dec((100 * sd.area_km2) / META.region_km2, 1) });
  }
  let sub = "";
  if (id === "0") sub = I.si_chaque_hectare;
  else if (final) sub = tpl(I.fourchette, { lo: approx(sd.mw_low), hi: approx(sd.mw_high) });
  const n = nChoices();
  const tag = n ? `<div class="ind-tag">${tpl(n > 1 ? I.scenario_modifies : I.scenario_modifie, { n })}</div>` : "";
  const box = $("indicator");
  box.className = `indicator${final ? " final" : ""}${early ? " early" : ""}`;
  box.innerHTML =
    `<div class="ind-label">${typo(label)}</div>` +
    `<div class="ind-n"><span class="ind-approx">${approxMark}</span><span id="ind-n"></span> <span class="ind-unit">${early || final ? T.indicateur.eoliennes : ""}</span></div>` +
    `<div class="ind-mw"><span class="ind-approx">${approxMark}</span><span id="ind-mw"></span> MW</div>` +
    (sub ? `<div class="ind-sub">${typo(sub)}</div>` : "") +
    (area ? `<div class="ind-area">${area}</div>` : "") +
    tag;
  const f = final ? (v) => approx(v) : (v) => int(v);
  tweenNumber("ind-n", sd.n, f, animate);
  tweenNumber("ind-mw", sd.mw, f, animate);
}

// --- step card ---------------------------------------------------------------
function effectLines(id) {
  const E = T.effet;
  const seq = sequence();
  const i = seq.indexOf(id);
  const cur = stepData(id);
  if (id === "0") return [`<p class="effect">${tpl(E.depart, { mw: int(cur.mw) })}</p>`];
  if (id === "bilan") return [bilanBars()];
  const prev = stepData(seq[i - 1]);
  if (/^[1-5]$/.test(id)) {
    const km2 = prev.area_km2 - cur.area_km2;
    if (km2 < 0.05) return [`<p class="effect">${typo(E.terrain_zero)}</p>`];
    return [
      `<p class="effect big">${tpl(E.terrain, { km2: int(km2), pct: dec((-100 * km2) / prev.area_km2, 0) })}</p>`,
      `<p class="effect">${tpl(E.eoliennes_moins, { n: int(prev.n - cur.n) })}</p>`,
    ];
  }
  if (id === "8") {
    return [`<p class="effect big">${tpl(E.reserve, { pct: Math.round(100 * (1 - META.survival.central)) })}</p>`];
  }
  const dn = prev.n - cur.n;
  if (id === "6") {
    return [
      `<p class="effect big">${tpl(E.places, { n: int(cur.n) })}</p>`,
      `<p class="effect">${tpl(E.regroupement, { n: int(dn), pct: dec((-100 * dn) / prev.n, 0) })}</p>`,
    ];
  }
  return [`<p class="effect big">${tpl(E.moins, { n: int(dn), pct: dec((-100 * dn) / prev.n, 0) })}</p>`];
}

function bilanBars() {
  const last = stepData("8");
  const max = Math.max(last.mw_high, META.installed_mw) * 1.08;
  const w = (v) => `${(100 * v) / max}%`;
  const E = T.effet;
  return `<div class="bilan-bars" role="img" aria-label="${typo(`${E.bilan_parc} ${gw(META.installed_mw)} GW, ${E.bilan_possible} ${gwRound(last.mw)} GW`)}">
    <div class="bb-row"><span class="bb-label">${typo(E.bilan_parc)}</span>
      <div class="bb-track"><div class="bb-bar now" style="width:${w(META.installed_mw)}"></div></div>
      <span class="bb-val">${typo(`${gw(META.installed_mw)} GW`)}</span></div>
    <div class="bb-row"><span class="bb-label">${typo(E.bilan_possible)}</span>
      <div class="bb-track"><div class="bb-range" style="left:${w(last.mw_low)};width:${w(last.mw_high - last.mw_low)}"></div>
      <div class="bb-bar" style="width:${w(last.mw)}"></div></div>
      <span class="bb-val">${typo(`≈ ${gwRound(last.mw)} GW`)}</span></div>
  </div>`;
}

function cardTitle(id) {
  const st = STEP_TEXT[id];
  const v = values();
  if (id === "6" && !state.isolees) return tpl(st.titre_strict, v);
  return tpl(st.titre, v);
}

function ruleLine(id) {
  const st = STEP_TEXT[id];
  const v = values();
  if (id === "6" && !state.isolees) return tpl(st.regle_strict, v);
  if (id === "1" && state.foret) return tpl(st[`regle_foret${state.foret}`], v);
  if (id === "2" && state.derogation) return tpl("Dérogation : toute la zone agricole est admise", v);
  return tpl(st.regle, v);
}

function etsiNotes(id) {
  const st = STEP_TEXT[id];
  if (!st.et_si) return "";
  const v = values();
  const notes = [];
  if (st.et_si.derogation && state.derogation) notes.push(["hausse", st.et_si.derogation]);
  if (st.et_si.foret && state.foret) notes.push(["hausse", st.et_si.foret[state.foret - 1]]);
  if (st.et_si.strict && !state.isolees) notes.push(["baisse", st.et_si.strict]);
  if (st.et_si.interdistance && state.interdistance) notes.push(["baisse", st.et_si.interdistance]);
  return notes.map(([k, s]) => `<p class="card-note ${k}">${icon(k, { size: 16 })}<span>${tpl(s, v)}</span></p>`).join("");
}

function pictoFor(id) {
  const st = STEP_TEXT[id];
  if (st.picto === "wallonie") return wallonieIcon(LM.outline, META.grid, { size: 30 });
  return icon(st.picto, { size: 30 });
}

function imageFor(id) {
  const st = STEP_TEXT[id];
  const key = st.image;
  return `<img src="img/${key}.jpg" alt="${typo(st.alt)}" onerror="this.closest('.card-media').classList.add('noimg');this.remove()">`;
}

function renderCard() {
  const id = state.etape;
  const st = STEP_TEXT[id];
  const seq = sequence();
  const fam = st.famille ? FAMKEYS.indexOf(st.famille) + 1 : 0;
  const eyebrow = id === "bilan"
    ? T.commandes.bilan
    : `${T.commandes.etape} ${stepNumberLabel(id)} ${T.commandes.sur} 8`;
  const chip = fam
    ? `<span class="fam-chip" style="--c:${FAMILY[fam]}"></span><span class="fam-name">${typo(T.familles[st.famille])}</span>`
    : "";
  $("card").innerHTML = `
    <div class="card-media${fam ? "" : " neutral"}" style="--c:${fam ? FAMILY[fam] : GREEN}">
      ${imageFor(id)}
      <div class="card-placeholder">${pictoFor(id)}</div>
      <div class="card-picto" style="--c:${fam ? FAMILY[fam] : GREEN}">${pictoFor(id)}</div>
    </div>
    <div class="card-body">
      <div class="eyebrow"><span>${eyebrow}</span>${chip ? `<span class="sep">·</span>${chip}` : ""}</div>
      <h2 class="card-title">${cardTitle(id)}</h2>
      <p class="card-rule">${ruleLine(id)}</p>
      <div class="card-effect">${effectLines(id).join("")}</div>
      ${etsiNotes(id)}
      <p class="card-why"><span class="why-label">Pourquoi ?</span> ${tpl(st.pourquoi, values())}</p>
      ${id === "bilan" && !EXPORT ? `<a class="card-cta" href="#et-si">${typo(T.et_si.titre)} ↓</a>` : ""}
    </div>`;
  if (!EXPORT) {
    const seqIdx = seq.indexOf(id);
    $("card").dataset.pos = `${seqIdx + 1}/${seq.length}`;
  }
}

// --- timeline ------------------------------------------------------------------
function renderTimeline() {
  const seq = sequence();
  const cur = seq.indexOf(state.etape);
  const max = stepData("0").mw;
  const items = seq.map((id, i) => {
    const st = STEP_TEXT[id];
    const sd = stepData(id);
    const fam = st.famille ? FAMKEYS.indexOf(st.famille) + 1 : 0;
    const h = id === "bilan" ? 0 : Math.max(1.5, (100 * sd.mw) / max);
    const cls = i < cur ? "past" : i === cur ? "current" : "future";
    const val = id === "bilan" ? "" : `${id === "8" ? "≈ " : ""}${id === "8" ? approx(sd.mw) : int(sd.mw)} MW`;
    const whisker = id === "8"
      ? `<span class="tl-whisker" style="bottom:${(100 * sd.mw_low) / max}%;height:${(100 * (sd.mw_high - sd.mw_low)) / max}%"></span>`
      : "";
    const node = id === "bilan"
      ? `<span class="tl-node star">${icon("eolienne", { size: 14, stroke: 2.2 })}</span>`
      : `<span class="tl-node"${fam ? ` style="--c:${FAMILY[fam]}"` : ""}>${fam ? '<span class="tl-fam"></span>' : ""}<span class="tl-num">${stepNumberLabel(id).replace(" bis", "b")}</span></span>`;
    return `<button type="button" class="tl-stop ${cls}" data-id="${id}" aria-current="${i === cur ? "step" : "false"}"
        aria-label="${typo(`${stepNumberLabel(id)} : ${cardTitle(id)}${val ? `, ${val}` : ""}`)}">
      <span class="tl-bar-area"><span class="tl-val">${typo(val)}</span>${whisker}<span class="tl-bar" style="height:${h}%"></span></span>
      ${node}
      <span class="tl-label">${cardTitle(id)}</span>
    </button>`;
  });
  const playing = !!player;
  $("timeline").innerHTML = `
    <div class="tl-controls">
      <button type="button" class="tl-btn" id="tl-prev" aria-label="${T.commandes.precedent}" ${cur === 0 ? "disabled" : ""}>${icon("fleche_gauche", { size: 18 })}</button>
      <button type="button" class="tl-btn play" id="tl-play" aria-label="${playing ? T.commandes.pause : T.commandes.lecture}">${icon(playing ? "pause" : "lecture", { size: 16 })}<span>${playing ? T.commandes.pause : T.commandes.lecture}</span></button>
      <button type="button" class="tl-btn" id="tl-next" aria-label="${T.commandes.suivant}" ${cur === seq.length - 1 ? "disabled" : ""}>${icon("fleche_droite", { size: 18 })}</button>
    </div>
    <div class="tl-track" style="--n:${seq.length};--p:${cur}">
      <div class="tl-line"><span class="tl-line-fill" style="width:${(100 * cur) / (seq.length - 1)}%"></span></div>
      ${items.join("")}
    </div>`;
  $("tl-prev").onclick = () => go(-1);
  $("tl-next").onclick = () => go(1);
  $("tl-play").onclick = togglePlay;
  for (const b of $("timeline").querySelectorAll(".tl-stop")) {
    b.onclick = () => {
      stopPlay();
      update({ etape: b.dataset.id });
    };
  }
  const curEl = $("timeline").querySelector(".tl-stop.current");
  if (curEl && !EXPORT) {
    const track = $("timeline").querySelector(".tl-track");
    if (track.scrollWidth > track.clientWidth) {
      track.scrollLeft = curEl.offsetLeft - track.clientWidth / 2 + curEl.offsetWidth / 2;
    }
  }
}

function go(d) {
  stopPlay();
  const seq = sequence();
  const i = Math.max(0, Math.min(seq.length - 1, seq.indexOf(state.etape) + d));
  update({ etape: seq[i] });
}

let player = null;
function togglePlay() {
  if (player) return stopPlay(true);
  const seq = sequence();
  if (state.etape === "bilan") update({ etape: "0" });
  player = setInterval(() => {
    const s = sequence();
    const i = s.indexOf(state.etape);
    if (i >= s.length - 1) return stopPlay(true);
    update({ etape: s[i + 1] });
    if (i + 1 >= s.length - 1) stopPlay(true);
  }, 3200);
  renderTimeline();
  return seq;
}
function stopPlay(rerender = false) {
  if (!player) return;
  clearInterval(player);
  player = null;
  if (rerender) renderTimeline();
}

// --- legend --------------------------------------------------------------------
function renderLegend() {
  const s = landStep(state.etape);
  const land = combo().land;
  const counts = famAreas(land);
  const items = FAMKEYS.map((k, i) => {
    const f = i + 1;
    const on = f <= s;
    const km2 = counts[f];
    return `<li class="${on ? "on" : "off"}"><span class="sw" style="--c:${FAMILY[f]}"></span>
      <span class="lg-name">${typo(T.familles[k])}</span>
      <span class="lg-km">${on ? (km2 < 0.5 ? typo("aucun") : typo(`−${int(km2)} km²`)) : ""}</span></li>`;
  });
  const showPts = !!stepData(state.etape).pts;
  $("legend").innerHTML = `
    <ul class="lg-list">
      <li class="on avail"><span class="sw" style="--c:${GREEN}"></span><span class="lg-name">${typo(T.legende.disponible)}</span>
        <span class="lg-km">${typo(`${int(stepData(state.etape).area_km2 ?? stepData("7").area_km2)} km²`)}</span></li>
      <li class="lg-head">${typo(T.legende.titre)} :</li>
      ${items.join("")}
    </ul>
    <div class="lg-extra">
      ${showPts ? `<span class="lg-pt"><span class="dot"></span>${typo(T.legende.eoliennes_modele)}</span>` : ""}
      <label class="lg-toggle"><input type="checkbox" id="chk-parc" ${state.parc ? "checked" : ""}>
        <span class="ring"></span>${typo(tpl(T.legende.parc_actuel, { n: META.fleet_n }))}</label>
    </div>`;
  $("chk-parc").onchange = (e) => update({ parc: e.target.checked ? 1 : 0 }, { animate: false });
}

const famAreaCache = {};
function famAreas(land) {
  if (famAreaCache[land]) return famAreaCache[land];
  // Areas by family, from the funnel itself (first family that excludes).
  const key = Object.keys(DATA.states).find((k) => DATA.states[k].land === land);
  const st = DATA.states[key].steps;
  const out = [0];
  for (let f = 1; f <= FAMKEYS.length; f++) out.push(st[f - 1].area_km2 - st[f].area_km2);
  famAreaCache[land] = out;
  return out;
}

// --- et si -------------------------------------------------------------------
function effectOf(patch) {
  const base = grossMW(state);
  const alt = grossMW({ ...state, ...patch });
  return { base, alt, rel: alt / base - 1 };
}

function badge(rel) {
  if (Math.abs(rel) < 0.0005) return `<span class="badge zero">±0 %</span>`;
  const k = rel > 0 ? "hausse" : "baisse";
  return `<span class="badge ${k}">${icon(k, { size: 12, stroke: 2.4 })}${typo(`${signed(Math.round(100 * rel), int)} %`)}</span>`;
}

function renderEtsi() {
  if (EXPORT) return;
  const C = T.et_si.choix;
  const v = values();
  const row = (key, control, effect, on) => {
    const c = C[key];
    return `<div class="choice ${on ? "active" : ""} ${effect}" data-key="${key}">
      ${control}
      <p class="ch-rule">${tpl(c.en_vigueur, v)}
        <button type="button" class="ch-goto" data-etape="${c.etape}">${typo(tpl(T.et_si.agit_etape, { n: stepNumberLabel(c.etape) }))} →</button></p>
    </div>`;
  };
  // A switch whose checked position applies patchOn. For "isolees" the switch
  // reads as a ban: checked means isolees=0.
  const patches = {};
  const toggle = (key, on, patchOn, patchOff) => {
    patches[key] = [patchOn, patchOff];
    const e = on ? effectOf(patchOff) : effectOf(patchOn);
    const rel = on ? e.base / e.alt - 1 : e.rel;
    const kind = rel >= 0 ? "warm" : "cool";
    return row(key, `<label class="ch-head"><input type="checkbox" class="switch" data-key="${key}" ${on ? "checked" : ""}>
      <span class="ch-label">${typo(C[key].libelle)}</span>${badge(rel)}</label>`, kind, state[key] !== DEFAULT[key]);
  };
  // One radio row per option; the first option is the rule in force and
  // carries a tag instead of an effect.
  const radios = (key, opts, kind) => {
    const base = grossMW({ ...state, [key]: opts[0] });
    const items = opts.map((o, i) => {
      const on = state[key] === o;
      const rel = grossMW({ ...state, [key]: o }) / base - 1;
      return `<label class="opt ${on ? "on" : ""}"><input type="radio" name="opt-${key}" data-k="${key}" value="${o}" ${on ? "checked" : ""}>
        <span class="opt-label">${typo(C[key].options[i])}</span>${i ? badge(rel) : `<span class="opt-ref">${typo(T.et_si.en_vigueur_tag)}</span>`}</label>`;
    }).join("");
    return row(key, `<div class="ch-head"><span class="ch-label">${typo(C[key].libelle)}</span></div>
      <div class="options" role="radiogroup" aria-label="${typo(C[key].libelle)}">${items}</div>`, kind, state[key] !== DEFAULT[key]);
  };
  $("etsi-titre").textContent = typo(T.et_si.titre);
  $("etsi-intro").textContent = typo(T.et_si.intro);
  $("etsi-reset").textContent = typo(T.et_si.reinitialiser);
  $("etsi-reset").disabled = nChoices() === 0;
  $("etsi-choix").innerHTML =
    toggle("derogation", !!state.derogation, { derogation: 1 }, { derogation: 0 }) +
    toggle("isolees", !state.isolees, { isolees: 0 }, { isolees: 1 }) +
    radios("interdistance", [0, 4, 6], "cool") +
    radios("foret", [0, 1, 2], "warm");
  // The list is rebuilt on every update: give focus back to the control used.
  const refocus = (sel) => $("etsi-choix").querySelector(sel)?.focus();
  for (const inp of $("etsi-choix").querySelectorAll("input.switch")) {
    const [on, off] = patches[inp.dataset.key];
    inp.onchange = async () => {
      await update(inp.checked ? on : off);
      refocus(`input.switch[data-key="${inp.dataset.key}"]`);
    };
  }
  for (const inp of $("etsi-choix").querySelectorAll("input[type=radio]")) {
    inp.onchange = async () => {
      await update({ [inp.dataset.k]: +inp.value });
      refocus(`input[name="${inp.name}"]:checked`);
    };
  }
  for (const b of $("etsi-choix").querySelectorAll(".ch-goto")) {
    b.onclick = () => {
      const e = b.dataset.etape;
      const patch = { etape: e };
      if (e === "7bis" && !state.interdistance) patch.interdistance = 4;
      update(patch);
      $("map-box").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
      closeDrawer();
    };
  }
  const n = nChoices();
  $("fab-etsi").innerHTML = `${typo(T.commandes.et_si_bouton)}${n ? `<span class="fab-n">${n}</span>` : ""}`;
  $("lien-etsi").innerHTML = `${typo(T.commandes.et_si_bouton)}${n ? `<span class="fab-n">${n}</span>` : ""}`;
}

function closeDrawer() {
  $("et-si").classList.remove("open");
  document.body.classList.remove("drawer-open");
}

// --- expert ------------------------------------------------------------------
function renderExpert() {
  const X = T.expert;
  const ref = grossMW(DEFAULT);
  const rows = [];
  for (const [k, v] of Object.entries(META.judgement)) rows.push([X.lignes[k], v.p_nom_max_mw, k === "pic_plan_de_secteur"]);
  for (const k of ["T136_V112", "T208_NREL55"]) rows.push([X.lignes[k], META.by_turbine[k].p_nom_max_mw]);
  for (const k of ["observed", "isotropic"]) rows.push([X.lignes[k], META.by_spacing[k].p_nom_max_mw]);
  const span = Math.max(...rows.map((r) => Math.abs(r[1] / ref - 1)));
  const body = rows.map(([label, mw, dim]) => {
    const rel = mw / ref - 1;
    const w = (50 * Math.abs(rel)) / span;
    return `<tr class="${dim ? "dim" : ""}"><td>${typo(label)}</td><td class="num">${int(mw)}</td>
      <td class="num">${typo(`${signed(Math.round(100 * rel), int)} %`)}</td>
      <td class="xbar"><span class="xb ${rel >= 0 ? "pos" : "neg"}" style="${rel >= 0 ? `left:50%;width:${w}%` : `right:50%;width:${w}%`}"></span></td></tr>`;
  }).join("");
  $("expert-titre").textContent = typo(X.titre);
  $("expert-body").innerHTML = `<p>${tpl(X.intro, { ref: int(ref) })}</p>
    <table class="xtable"><thead><tr><th>${typo(X.colonnes[0])}</th><th class="num">${X.colonnes[1]}</th><th class="num">${typo(X.colonnes[2])}</th><th></th></tr></thead>
    <tbody>${body}</tbody></table>
    <p class="x-cap">${tpl(X.plafond, { cap: int(META.model_cap_mw) })}</p>`;
}

// --- static parts ------------------------------------------------------------
function renderStatic() {
  document.title = typo(T.titre);
  $("titre").textContent = typo(T.titre);
  $("sous-titre").textContent = typo(T.sous_titre);
  $("lien-rapport").textContent = typo(T.lien_rapport);
  $("btn-methode").innerHTML = `${icon("info", { size: 16 })}<span>${typo(T.lien_methode)}</span>`;
  $("map-note").textContent = typo(T.legende.note);
  $("loupe-caption").innerHTML = `${icon("loupe", { size: 13 })}<span>${typo(T.loupe.titre)}</span>`;
  $("etsi-close").innerHTML = icon("fermer", { size: 18 });
  $("etsi-close").setAttribute("aria-label", T.commandes.fermer);
  const C = T.credits;
  $("credits").innerHTML = `<div class="cr-text"><p>${typo(C.source)} · ${typo(tpl(C.calcul, { date: META.calc_date }))}</p>
    <p>${typo(C.donnees)}</p></div>
    <div class="cr-logo"><img src="img/cc_by_logo.png" alt="${typo(C.licence)}"></div>`;
  $("methode-titre").textContent = typo(T.methode.titre);
  $("methode-body").innerHTML = T.methode.paragraphes.map((p) => `<p>${tpl(p, values())}</p>`).join("");
  $("methode-fermer").textContent = T.commandes.fermer;
  $("btn-methode").onclick = () => $("methode").showModal();
  $("fab-etsi").onclick = () => {
    $("et-si").classList.add("open");
    document.body.classList.add("drawer-open");
  };
  $("etsi-close").onclick = closeDrawer;
  $("loupe").onclick = () => {
    $("loupe").classList.toggle("big");
    setTimeout(() => map.placeLeader($("loupe")), 320);
  };
  $("etsi-reset").onclick = () => update({
    derogation: DEFAULT.derogation, isolees: DEFAULT.isolees,
    interdistance: DEFAULT.interdistance, foret: DEFAULT.foret,
  });
  $("lien-etsi").onclick = (e) => {
    if (matchMedia("(max-width: 899px)").matches) {
      e.preventDefault();
      $("fab-etsi").click();
    }
  };
  renderExpert();
}

// --- hover ----------------------------------------------------------------
function setupHover() {
  const tip = $("tooltip");
  const S = T.survol;
  $("map-box").addEventListener("mousemove", (e) => {
    if (e.target.closest(".indicator, .loupe")) {
      tip.classList.remove("show");
      return;
    }
    const v = map.cellAt(e);
    if (v == null || v >= 6) {
      tip.classList.remove("show");
      return;
    }
    const s = landStep(state.etape);
    const famName = (f) => typo(T.familles[FAMKEYS[f - 1]]);
    let html;
    if (v !== 0 && v <= s) {
      html = `<span class="sw" style="--c:${FAMILY[v]}"></span>${tpl(S.retire, { n: v, famille: famName(v) })}`;
    } else {
      html = `<span class="sw" style="--c:${GREEN}"></span>${typo(S.disponible)}`;
      html += `<br><span class="tt-sub">${v === 0 ? typo(S.reste) : tpl(S.sera_retire, { n: v, famille: famName(v) })}</span>`;
    }
    tip.innerHTML = html;
    const b = $("map-box").getBoundingClientRect();
    const x = e.clientX - b.left, y = e.clientY - b.top;
    tip.style.left = `${Math.min(x + 14, b.width - 240)}px`;
    tip.style.top = `${y + 14}px`;
    tip.classList.add("show");
  });
  $("map-box").addEventListener("mouseleave", () => tip.classList.remove("show"));
}

// ---------------------------------------------------------------------------
// Export layouts (driven by scripts/infographic_export.py)
// ---------------------------------------------------------------------------
function renderExport() {
  if (!EXPORT) return;
  const seq = sequence().filter((id) => id !== "bilan");
  const cur = seq.indexOf(state.etape);
  $("export-progress").innerHTML = `<div class="xp-track">${seq.map((id, i) =>
    `<span class="xp-seg ${i < cur ? "past" : i === cur ? "current" : ""}"></span>`).join("")}</div>`;
  const view = state.view;
  document.body.dataset.view = view;
  const X = T.export;
  const v = values();
  let html = "";
  if (view === "titre") {
    const final = stepData("5");
    html = `<h1>${typo(T.titre)}</h1><p class="xt-lead">${tpl(X.titre_accroche, { pct: dec((100 * final.area_km2) / META.region_km2, 1) })}</p>
      <p class="xt-sub">${typo(T.sous_titre)}</p>`;
  } else if (view === "choix") {
    html = choiceSlide(state.choix);
  } else if (view === "etsi") {
    html = etsiSummary();
  } else if (view === "enveloppe") {
    const [lo, hi] = envelope();
    html = `<h2 class="xt-h">${tpl(X.enveloppe_titre, { lo_gw: gw(lo.mw), hi_gw: gw(hi.mw) })}</h2>
      ${rangeBar(lo.mw, hi.mw, grossMW(DEFAULT))}
      <p class="xt-text">${tpl(X.enveloppe_texte, { lo: describe(lo.key), hi: describe(hi.key) })}</p>`;
  }
  $("export-title").innerHTML = html;
  void v;
}

const CHOICE_PATCH = {
  derogation: { derogation: 1 },
  isolees: { isolees: 0 },
  inter4: { interdistance: 4 },
  inter6: { interdistance: 6 },
  resineux: { foret: 1 },
  foret: { foret: 2 },
};

function choiceSlide(key) {
  const C = T.et_si.choix;
  const ck = key.startsWith("inter") ? "interdistance" : key === "resineux" ? "foret" : key;
  const ref = grossMW(DEFAULT);
  const alt = grossMW({ ...DEFAULT, ...CHOICE_PATCH[key] });
  const rel = alt / ref - 1;
  const label = ck === "interdistance" ? `${C.interdistance.libelle} : ${key.slice(5)} km`
    : ck === "foret" ? `${C.foret.libelle} : ${C.foret.options[CHOICE_PATCH[key].foret]}` : C[ck].libelle;
  return `<div class="xc ${rel >= 0 ? "warm" : "cool"}"><div class="eyebrow">${typo(T.et_si.titre)}</div>
    <h2 class="xt-h">${typo(label)}</h2>
    <p class="xc-effect">${badge(rel)} <span>${typo(`${int(alt)} MW au lieu de ${int(ref)} MW`)}</span></p>
    <p class="xt-text">${tpl(C[ck].en_vigueur, values())}</p></div>`;
}

function etsiSummary() {
  const X = T.export;
  const C = T.et_si.choix;
  const ref = grossMW(DEFAULT);
  const rows = [
    [C.derogation.court, { derogation: 1 }],
    [C.isolees.court, { isolees: 0 }],
    [`${C.interdistance.court} : 4 km`, { interdistance: 4 }],
    [`${C.interdistance.court} : 6 km`, { interdistance: 6 }],
    [`${C.foret.court} : ${C.foret.options[1]}`, { foret: 1 }],
    [`${C.foret.court} : ${C.foret.options[2]}`, { foret: 2 }],
  ].map(([l, p]) => [l, grossMW({ ...DEFAULT, ...p }) / ref - 1]);
  const span = 1.2;
  return `<h2 class="xt-h">${typo(X.etsi_titre)}</h2><p class="xt-sub">${tpl(X.etsi_sous_titre, { ref: int(ref) })}</p>
    <div class="xs">${rows.map(([l, r]) => `<div class="xs-row"><span class="xs-l">${typo(l)}</span>
      <span class="xs-track"><span class="xs-bar ${r >= 0 ? "warm" : "cool"}" style="${r >= 0 ? "left:50%" : "right:50%"};width:${(50 * Math.abs(r)) / span}%"></span></span>
      <span class="xs-v">${typo(`${signed(Math.round(100 * r), int)} %`)}</span></div>`).join("")}</div>`;
}

// The strictest and the most open combination of the choices, gross (before
// the residual allowance), from the precomputed states.
function envelope() {
  const all = Object.entries(DATA.states).map(([key, st]) => ({ key, mw: st.steps[st.steps.length - 2].mw }));
  all.sort((a, b) => a.mw - b.mw);
  return [all[0], all[all.length - 1]];
}

function describe(key) {
  const C = T.et_si.choix;
  const [d, i, x, f] = key.split("-").map((p) => +p.slice(1));
  const parts = [];
  if (d) parts.push(C.derogation.court.toLowerCase());
  if (!i) parts.push(C.isolees.court.toLowerCase());
  if (x) parts.push(`${x} km ${C.interdistance.court.toLowerCase()}`);
  if (f) parts.push(C.foret.options[f]);
  return parts.length ? parts.join(", ") : T.et_si.aucun_choix;
}

function rangeBar(lo, hi, ref) {
  const max = Math.max(12000, hi * 1.08);
  const p = (v) => `${(100 * v) / max}%`;
  return `<div class="xr"><div class="xr-track"><span class="xr-range" style="left:${p(lo)};width:${p(hi - lo)}"></span>
    <span class="xr-ref" style="left:${p(ref)}"></span><span class="xr-now" style="left:0;width:${p(META.installed_mw)}"></span></div>
    <div class="xr-labels"><span style="left:${p(lo)}">${typo(`${gw(lo)} GW`)}</span><span style="left:${p(ref)}">${typo(`réf. ${gw(ref)} GW`)}</span>
    <span style="left:${p(hi)}">${typo(`${gw(hi)} GW`)}</span></div>
    <div class="xr-legend"><span class="xr-sw now"></span>${typo(`parc actuel ${gw(META.installed_mw)} GW`)}</div></div>`;
}

async function settle() {
  await document.fonts.ready;
  const imgs = [...document.querySelectorAll("#card img")];
  await Promise.all(imgs.map((im) => (im.complete ? null : new Promise((r) => {
    im.addEventListener("load", r, { once: true });
    im.addEventListener("error", r, { once: true });
  }))));
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
}

window.renderState = async (opts = {}) => {
  const patch = { ...DEFAULT, view: "etape", choix: null, ...opts };
  if (patch.view === "titre") patch.etape = "0";
  if (patch.view === "choix") {
    Object.assign(patch, { etape: "7" }, CHOICE_PATCH[patch.choix]);
    const step = { derogation: "2", isolees: "6", resineux: "1", foret: "1", inter4: "7bis", inter6: "7bis" };
    if (step[patch.choix]) patch.etape = step[patch.choix];
  }
  if (patch.view === "etsi" || patch.view === "enveloppe") patch.etape = "7";
  Object.assign(state, patch);
  await render({ animate: false });
  await settle();
  return true;
};
window.infographic = { T, META, sequence, values };

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
if (EXPORT) document.body.classList.add("export", EXPORT);
Object.assign(state, readHash());
renderStatic();
setupHover();
await update({}, { animate: false });
window.addEventListener("hashchange", () => {
  const h = readHash();
  if (comboKey(h) !== comboKey() || h.etape !== state.etape || h.parc !== state.parc) update(h);
});
let rz;
window.addEventListener("resize", () => {
  clearTimeout(rz);
  rz = setTimeout(() => update({}, { animate: false }), 120);
});
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select, dialog")) return;
  if (e.key === "ArrowRight") go(1);
  if (e.key === "ArrowLeft") go(-1);
});
// Warm the other land variants once the first view is up.
setTimeout(() => ["derog", "conif", "derog_conif", "forest", "derog_forest"].forEach((l) => classesFor(l)), 800);
document.body.classList.add("ready");
