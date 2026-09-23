// The map: attribution grid -> coloured canvas, machines, landmarks, magnifier.
//
// The attribution grid holds, for every 100 m cell, the first family of rules
// that excludes it (0 = survives, 6 = outside the Region).  At step s the cell
// is drawn in its family's colour if that family is <= s, and green otherwise.

export const GREEN = "#2B8A3E";
// Validated (dataviz validate_palette.js --pairs all): normal-vision ΔE >= 15.0,
// protan/deutan ΔE >= 8.6 between any two, >= 14.5 between green and any family.
// Muted on purpose: the families are the ground, the surviving land the figure.
export const FAMILY = [null, "#C4AC8E", "#E9E196", "#A780AD", "#3A70AD", "#513249"];
const INK = "#1D2428";

const rgb = (h) => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const G = rgb(GREEN);
const F = FAMILY.map((h) => (h ? rgb(h) : G));
const SVGNS = "http://www.w3.org/2000/svg";

export async function loadAttribution(url, grid) {
  const blob = await (await fetch(url)).blob();
  let bmp;
  try {
    bmp = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  } catch {
    bmp = await createImageBitmap(blob);
  }
  const cv = document.createElement("canvas");
  cv.width = grid.cols;
  cv.height = grid.rows;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0);
  const d = ctx.getImageData(0, 0, grid.cols, grid.rows).data;
  const cls = new Uint8Array(grid.cols * grid.rows);
  for (let i = 0; i < cls.length; i++) cls[i] = Math.round(d[i * 4] / grid.scale);
  return cls;
}

export function decodePoints(b64) {
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const u16 = new Uint16Array(u8.buffer);
  const n = u16.length / 3;
  const r = new Float32Array(n), c = new Float32Array(n), p = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    r[i] = u16[3 * i] + 0.5;
    c[i] = u16[3 * i + 1] + 0.5;
    p[i] = u16[3 * i + 2];
  }
  return { n, r, c, p };
}

function el(name, attrs = {}, parent = null) {
  const e = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

// Two stacked canvases, cross-faded by CSS opacity.
class Pair {
  constructor(a, b) {
    this.c = [a, b];
    this.front = 0;
    a.style.opacity = 1;
    b.style.opacity = 0;
  }
  get back() {
    return this.c[1 - this.front];
  }
  size(w, h) {
    for (const c of this.c) {
      c.width = w;
      c.height = h;
    }
  }
  show(animate) {
    const f = this.c[this.front], b = this.back;
    for (const c of this.c) c.style.transition = animate ? "opacity .55s ease" : "none";
    b.style.opacity = 1;
    f.style.opacity = 0;
    this.front = 1 - this.front;
  }
}

export class FunnelMap {
  constructor({ box, maps, pts, svg, meta, landmarks }) {
    this.box = box;
    this.grid = meta.grid;
    this.meta = meta;
    this.lm = landmarks;
    this.maps = new Pair(...maps);
    this.pts = new Pair(...pts);
    this.svg = svg;
    this.cls = null;
    this.counts = null;
    this.W = 0;
    this.H = 0;
    this.buildSvg();
  }

  buildSvg() {
    const { cols, rows } = this.grid;
    const s = this.svg;
    s.setAttribute("viewBox", `0 0 ${cols} ${rows}`);
    s.setAttribute("preserveAspectRatio", "none");
    el("path", { d: this.lm.motorways, class: "mw-casing" }, s);
    el("path", { d: this.lm.motorways, class: "mw" }, s);
    el("path", { d: this.lm.outline, class: "outline" }, s);
    this.fleetG = el("g", { class: "fleet" }, s);
    for (const [x, y] of this.lm.fleet) el("circle", { cx: x, cy: y, r: 4.2 }, this.fleetG);
    const L = this.lm.loupe;
    this.loupeRect = el("rect", { x: L.col0, y: L.row0, width: L.size, height: L.size, class: "loupe-rect" }, s);
    this.leader = el("path", { class: "leader" }, s);
    // Town labels are HTML, so they keep their size at every zoom.
    this.towns = document.createElement("div");
    this.towns.className = "towns";
    for (const t of this.lm.towns) {
      const d = document.createElement("span");
      d.className = `town${t.side === "left" ? " left" : ""}`;
      d.style.left = `${(100 * t.xy[0]) / cols}%`;
      d.style.top = `${(100 * t.xy[1]) / rows}%`;
      d.textContent = t.name;
      this.towns.appendChild(d);
    }
    this.box.appendChild(this.towns);
  }

  setClasses(cls) {
    this.cls = cls;
    this.counts = null;
  }

  // Display resolution: at most the grid's own.
  layout() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(this.box.clientWidth * dpr));
    const k = Math.min(1, this.grid.cols / w);
    const W = Math.round(w * k);
    const H = Math.round((W * this.grid.rows) / this.grid.cols);
    if (W !== this.W || H !== this.H) {
      this.W = W;
      this.H = H;
      this.maps.size(W, H);
      this.pts.size(W, H);
      this.counts = null;
    }
    this.pxScale = W / this.box.clientWidth; // device px per css px
  }

  // Cells of each class under every display pixel.
  computeCounts() {
    const { cols, rows } = this.grid;
    const { W, H } = this;
    const counts = new Uint16Array(W * H * 7);
    const cx = new Int32Array(cols);
    for (let c = 0; c < cols; c++) cx[c] = Math.min(W - 1, Math.floor(((c + 0.5) * W) / cols));
    for (let r = 0; r < rows; r++) {
      const base = Math.min(H - 1, Math.floor(((r + 0.5) * H) / rows)) * W;
      const off = r * cols;
      for (let c = 0; c < cols; c++) {
        counts[(base + cx[c]) * 7 + this.cls[off + c]]++;
      }
    }
    this.counts = counts;
    this.perPx = (cols * rows) / (W * H);
  }

  // Colour every display pixel for step s (0..5).  A pixel that holds any
  // surviving land is at least 62 % green, and its neighbours get a faint
  // green halo, so that 2-ha parcels stay visible at 300 m per pixel.
  paint(ctx, s) {
    if (!this.counts) this.computeCounts();
    const { W, H, counts } = this;
    const n = W * H;
    const img = ctx.createImageData(W, H);
    const d = img.data;
    const frac = new Float32Array(n);
    const dom = new Uint8Array(n);
    const tot = new Uint16Array(n);
    const all = new Uint16Array(n);
    for (let p = 0; p < n; p++) {
      const o = p * 7;
      let t = 0, a = counts[o], best = 0, bk = 0;
      for (let k = 0; k < 6; k++) t += counts[o + k];
      if (!t) continue;
      all[p] = t + counts[o + 6];
      for (let k = 1; k < 6; k++) {
        const v = counts[o + k];
        if (k > s) a += v;
        else if (v > best) {
          best = v;
          bk = k;
        }
      }
      tot[p] = t;
      frac[p] = a / t;
      dom[p] = bk;
    }
    const HALO = 0.34;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const p = y * W + x;
        const t = tot[p];
        if (!t) continue;
        const base = F[dom[p]];
        let mix = 0;
        const f = frac[p];
        if (f > 0) mix = 0.62 + 0.38 * Math.sqrt(f);
        else {
          for (let dy = -1; dy <= 1 && !mix; dy++) {
            const yy = y + dy;
            if (yy < 0 || yy >= H) continue;
            for (let dx = -1; dx <= 1; dx++) {
              const xx = x + dx;
              if (xx >= 0 && xx < W && frac[yy * W + xx] > 0) {
                mix = HALO;
                break;
              }
            }
          }
        }
        const q = p * 4;
        d[q] = base[0] + (G[0] - base[0]) * mix;
        d[q + 1] = base[1] + (G[1] - base[1]) * mix;
        d[q + 2] = base[2] + (G[2] - base[2]) * mix;
        d[q + 3] = (255 * t) / all[p];
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  drawPoints(ctx, pts) {
    ctx.clearRect(0, 0, this.W, this.H);
    if (!pts) return;
    const sx = this.W / this.grid.cols, sy = this.H / this.grid.rows;
    const rad = Math.max(1.5, 1.55 * this.pxScale);
    const ring = rad + Math.max(0.7, 0.75 * this.pxScale);
    ctx.fillStyle = "#FFFFFF";
    ctx.beginPath();
    for (let i = 0; i < pts.n; i++) {
      const x = pts.c[i] * sx, y = pts.r[i] * sy;
      ctx.moveTo(x + ring, y);
      ctx.arc(x, y, ring, 0, 2 * Math.PI);
    }
    ctx.fill();
    ctx.fillStyle = INK;
    ctx.beginPath();
    for (let i = 0; i < pts.n; i++) {
      const x = pts.c[i] * sx, y = pts.r[i] * sy;
      ctx.moveTo(x + rad, y);
      ctx.arc(x, y, rad, 0, 2 * Math.PI);
    }
    ctx.fill();
  }

  draw({ step, pts, ptsKey, fleet }, animate) {
    this.layout();
    const mapKey = `${this.variant}|${step}|${this.W}`;
    if (mapKey !== this.mapKey) {
      this.paint(this.maps.back.getContext("2d"), step);
      this.maps.show(animate);
      this.mapKey = mapKey;
    }
    const pk = `${ptsKey}|${this.W}`;
    if (pk !== this.ptsKey) {
      this.drawPoints(this.pts.back.getContext("2d"), pts);
      this.pts.show(animate);
      this.ptsKey = pk;
    }
    this.fleetG.style.display = fleet ? "" : "none";
  }

  // Leader from the magnifier window to the inset, in grid units.
  placeLeader(inset) {
    if (!inset || !inset.offsetWidth || getComputedStyle(inset).position !== "absolute") {
      this.leader.setAttribute("d", "");
      return;
    }
    const b = this.box.getBoundingClientRect(), i = inset.getBoundingClientRect();
    const k = this.grid.cols / b.width;
    const L = this.lm.loupe;
    const ix = (i.left - b.left) * k, iy = (i.top - b.top) * k;
    const x1 = L.col0 + L.size, y1 = L.row0 + L.size;
    this.leader.setAttribute("d", `M${x1},${y1}L${ix},${iy}`);
  }

  cellAt(evt) {
    const b = this.box.getBoundingClientRect();
    const c = Math.floor(((evt.clientX - b.left) / b.width) * this.grid.cols);
    const r = Math.floor(((evt.clientY - b.top) / b.height) * this.grid.rows);
    if (c < 0 || r < 0 || c >= this.grid.cols || r >= this.grid.rows || !this.cls) return null;
    return this.cls[r * this.grid.cols + c];
  }
}

// ---------------------------------------------------------------------------
// The magnifier: a fixed square at the full 100 m resolution.
// ---------------------------------------------------------------------------
export class Loupe {
  constructor({ canvas, svg, meta, landmarks }) {
    this.canvas = canvas;
    this.svg = svg;
    this.grid = meta.grid;
    this.meta = meta;
    this.L = landmarks.loupe;
    this.lm = landmarks;
    canvas.width = this.L.size;
    canvas.height = this.L.size;
    const { col0, row0, size } = this.L;
    svg.setAttribute("viewBox", `${col0} ${row0} ${size} ${size}`);
    el("path", { d: landmarks.motorways, class: "mw-casing" }, svg);
    el("path", { d: landmarks.motorways, class: "mw" }, svg);
    this.extra = el("g", {}, svg);
    this.turb = el("g", { class: "l-turbines" }, svg);
    this.vill = el("g", { class: "l-villages" }, svg);
    const pad = 5;
    this.villages = landmarks.villages.filter(
      ([x, y]) => x > col0 - 60 && x < col0 + size + 60 && y > row0 - 60 && y < row0 + size + 60);
    for (const [x, y] of this.villages) {
      if (x > col0 && x < col0 + size && y > row0 && y < row0 + size) {
        el("rect", { x: x - 1.3, y: y - 1.3, width: 2.6, height: 2.6 }, this.vill);
      }
    }
    // 1 km scale bar
    const sb = el("g", { class: "scalebar" }, svg);
    const x0 = col0 + pad, y0 = row0 + size - pad;
    el("path", { d: `M${x0},${y0}h10`, class: "sb-bg" }, sb);
    el("path", { d: `M${x0},${y0}h10` }, sb);
    const t = el("text", { x: x0 + 12, y: y0 + 1.2 }, sb);
    t.textContent = "1 km";
  }

  paint(cls, s) {
    const { col0, row0, size } = this.L;
    const ctx = this.canvas.getContext("2d");
    const img = ctx.createImageData(size, size);
    const d = img.data;
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        const v = cls[(row0 + r) * this.grid.cols + col0 + c];
        const q = (r * size + c) * 4;
        if (v >= 6) {
          d[q + 3] = 0;
          continue;
        }
        const col = v === 0 || v > s ? G : F[v];
        d[q] = col[0];
        d[q + 1] = col[1];
        d[q + 2] = col[2];
        d[q + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  inWindow(x, y, m = 0) {
    const { col0, row0, size } = this.L;
    return x > col0 - m && x < col0 + size + m && y > row0 - m && y < row0 + size + m;
  }

  // Largest turbine-free arc of a village, as placement_lib.Horizon measures it.
  freeArc(vx, vy, pts) {
    const R = this.meta.rules.horizon_m / this.grid.res_m;
    const rr = this.meta.turbine.rotor_m / 2 / this.grid.res_m;
    const iv = [];
    for (let i = 0; i < pts.n; i++) {
      const dx = pts.c[i] - vx, dy = pts.r[i] - vy;
      const d = Math.hypot(dx, dy);
      if (d > R) continue;
      const b = (Math.atan2(dy, dx) + 2 * Math.PI) % (2 * Math.PI);
      const h = Math.asin(Math.min(rr / Math.max(d, rr), 1));
      let s = b - h, e = b + h;
      if (s < 0) iv.push([s + 2 * Math.PI, 2 * Math.PI], [0, e]);
      else if (e > 2 * Math.PI) iv.push([s, 2 * Math.PI], [0, e - 2 * Math.PI]);
      else iv.push([s, e]);
    }
    if (!iv.length) return null;
    iv.sort((a, b) => a[0] - b[0]);
    const m = [iv[0].slice()];
    for (const [s, e] of iv.slice(1)) {
      const last = m[m.length - 1];
      if (s <= last[1]) last[1] = Math.max(last[1], e);
      else m.push([s, e]);
    }
    let best = { gap: m[0][0] + 2 * Math.PI - m[m.length - 1][1], from: m[m.length - 1][1] };
    for (let i = 0; i + 1 < m.length; i++) {
      const g = m[i + 1][0] - m[i][1];
      if (g > best.gap) best = { gap: g, from: m[i][1] };
    }
    return best;
  }

  draw({ cls, step, stepId, pts }) {
    this.paint(cls, Math.min(step, 5));
    this.turb.replaceChildren();
    this.extra.replaceChildren();
    if (!pts) return;
    const inside = [];
    for (let i = 0; i < pts.n; i++) if (this.inWindow(pts.c[i], pts.r[i], 4)) inside.push(i);
    const spacing = this.meta.turbine.spacing_m / this.grid.res_m;
    if (stepId === "6") {
      for (const i of inside) el("circle", { cx: pts.c[i], cy: pts.r[i], r: spacing / 2, class: "spacing" }, this.extra);
    }
    if (stepId === "7") {
      const parks = new Map();
      for (const i of inside) {
        if (!parks.has(pts.p[i])) parks.set(pts.p[i], []);
        parks.get(pts.p[i]).push([pts.c[i], pts.r[i]]);
      }
      for (const ps of parks.values()) {
        if (ps.length < 2) {
          el("circle", { cx: ps[0][0], cy: ps[0][1], r: 4, class: "park" }, this.extra);
          continue;
        }
        const h = hull(ps);
        el("path", { d: "M" + h.map((p) => p.join(",")).join("L") + "Z", class: "park" }, this.extra);
      }
    }
    if (["8", "8bis", "9", "bilan"].includes(stepId)) {
      const R = this.meta.rules.horizon_m / this.grid.res_m;
      const arcs = [];
      for (const [vx, vy] of this.villages) {
        if (!this.inWindow(vx, vy, -8)) continue;
        const a = this.freeArc(vx, vy, pts);
        if (a) arcs.push({ vx, vy, ...a });
      }
      arcs.sort((a, b) => a.gap - b.gap);
      for (const a of arcs.slice(0, 2)) {
        const x1 = a.vx + R * Math.cos(a.from), y1 = a.vy + R * Math.sin(a.from);
        const e = a.from + a.gap;
        const x2 = a.vx + R * Math.cos(e), y2 = a.vy + R * Math.sin(e);
        const large = a.gap > Math.PI ? 1 : 0;
        el("path", {
          d: `M${a.vx},${a.vy}L${x1},${y1}A${R},${R} 0 ${large} 1 ${x2},${y2}Z`,
          class: "sector",
        }, this.extra);
        el("circle", { cx: a.vx, cy: a.vy, r: R, class: "radius" }, this.extra);
      }
    }
    for (const i of inside) el("circle", { cx: pts.c[i], cy: pts.r[i], r: 1.5 }, this.turb);
  }
}

function hull(pts) {
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const q of p) {
    while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop();
    lo.push(q);
  }
  for (const q of p.reverse()) {
    while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop();
    up.push(q);
  }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
