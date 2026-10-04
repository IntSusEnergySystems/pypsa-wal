// The map: class grid -> coloured canvas, landmarks, magnifier.
//
// map.png holds, for every 100 m pixel, a class in its red channel (x 8):
// 1..5 the family of rules that removes the pixel, 6 too small or too narrow
// for a park, 10 + g the gisement g of the land that survives; and in its
// green channel the share of the pixel that survives (0..250).  At step s a
// removed pixel takes its family's colour once that family's step is reached,
// green before; surviving land is green until the park rule, then the colour
// of its gisement group, dimmed from step 7 if the choices keep it closed.

export const GREEN = "#2B8A3E";
export const PARK_RULE = "#CFC8BA";
export const CLOSED = "#E4DFD5";
export const FADED_MIX = 0.62;   // share of the background mixed into a family colour from step 6
const BG = [241, 236, 226];
const SVGNS = "http://www.w3.org/2000/svg";

const rgb = (h) => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

export async function loadClasses(url, cols, rows, scale) {
  const blob = await (await fetch(url)).blob();
  let bmp;
  try {
    bmp = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  } catch {
    bmp = await createImageBitmap(blob);
  }
  const cv = document.createElement("canvas");
  cv.width = cols;
  cv.height = rows;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0);
  const d = ctx.getImageData(0, 0, cols, rows).data;
  const cls = new Uint8Array(cols * rows), share = new Uint8Array(cols * rows);
  for (let i = 0; i < cls.length; i++) {
    cls[i] = Math.round(d[i * 4] / scale);
    share[i] = d[i * 4 + 1];
  }
  return { cls, share, cols, rows };
}

function el(name, attrs = {}, parent = null) {
  const e = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

const mix = (c, t) => c.map((v, k) => Math.round(v * (1 - t) + BG[k] * t));

// Palette for one state: class -> [r, g, b] (null = transparent), and the
// classes to draw enlarged.  Up to step 5 the map explains *why* land goes;
// from step 6 it shows *what* the land left is, so the families fade; from
// step 7 everything excluded or closed is one light neutral and only the land
// the rules open keeps its colour.
export function palette(meta, step, isOpen) {
  const fam = meta.families.map((f) => rgb(f.colour));
  const grp = meta.groups.map((g) => rgb(g.colour));
  const G = rgb(GREEN), PR = rgb(PARK_RULE), CL = rgb(CLOSED);
  const pal = new Array(256).fill(null);
  const emph = [];
  for (let d = 1; d <= fam.length; d++) {
    pal[d] = step >= 7 ? CL : step >= 6 ? mix(fam[d - 1], FADED_MIX) : step >= d ? fam[d - 1] : G;
  }
  pal[6] = step >= 7 ? CL : step >= 6 ? PR : G;
  meta.gisements.forEach((g, i) => {
    let c = G;
    if (step >= 6) c = grp[g.group];
    if (step >= 7) {
      const o = isOpen(g.key);          // 0 closed, 1 open, 2 admissible but rationed by a quota
      if (o === 1) emph.push(10 + i + 1);
      else if (o === 2) c = mix(c, 0.55);
      else c = CL;
    }
    pal[10 + i + 1] = c;
  });
  return { pal, emph };
}

// Draw the class grid; the `emph` classes are also drawn as squares of
// `r` canvas pixels around each cell, so that a few thousand hectares stay
// visible on a map of the whole Region (the calculation is not affected).
export function paint(canvas, data, { pal, emph }, r = 0) {
  canvas.width = data.cols;
  canvas.height = data.rows;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(data.cols, data.rows);
  const px = img.data;
  for (let i = 0; i < data.cls.length; i++) {
    const c = pal[data.cls[i]];
    if (!c) continue;
    px[i * 4] = c[0];
    px[i * 4 + 1] = c[1];
    px[i * 4 + 2] = c[2];
    px[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  if (!r || !emph.length) return;
  const E = new Set(emph);
  let n = 0;
  for (let i = 0; i < data.cls.length; i++) if (E.has(data.cls[i])) n++;
  if (n > 60000) return;   // enough land to be seen as it is
  for (let i = 0; i < data.cls.length; i++) {
    const k = data.cls[i];
    if (!E.has(k)) continue;
    const c = pal[k];
    ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
    const x = i % data.cols, y = (i / data.cols) | 0;
    ctx.fillRect(x - r, y - r, 2 * r + 1, 2 * r + 1);
  }
}

// Two stacked canvases, cross-faded by CSS opacity.
export class Pair {
  constructor(a, b) {
    this.c = [a, b];
    this.front = 0;
    a.style.opacity = 1;
    b.style.opacity = 0;
  }
  get back() {
    return this.c[1 - this.front];
  }
  show(animate) {
    const f = this.c[this.front], b = this.back;
    for (const c of this.c) c.style.transition = animate ? "opacity .5s ease" : "none";
    b.style.opacity = 1;
    f.style.opacity = 0;
    this.front = 1 - this.front;
  }
}

export function buildSvg(svg, box, meta, lm) {
  const { cols, rows } = meta.grid;
  svg.setAttribute("viewBox", `0 0 ${cols} ${rows}`);
  svg.setAttribute("preserveAspectRatio", "none");
  el("path", { d: lm.motorways, class: "mw-casing" }, svg);
  el("path", { d: lm.motorways, class: "mw" }, svg);
  el("path", { d: lm.outline, class: "outline" }, svg);
  const parks = el("g", { class: "fleet" }, svg);
  for (const [x, y, ha] of lm.parks) el("circle", { cx: x, cy: y, r: 3 + Math.min(6, Math.sqrt(ha)) }, parks);
  const L = lm.loupe;
  el("rect", { x: L.col0, y: L.row0, width: L.size, height: L.size, class: "loupe-rect" }, svg);
  const towns = document.createElement("div");
  towns.className = "towns";
  for (const t of lm.towns) {
    const d = document.createElement("span");
    d.className = `town${t.side === "left" ? " town-left" : ""}`;
    d.style.left = `${(100 * t.xy[0]) / cols}%`;
    d.style.top = `${(100 * t.xy[1]) / rows}%`;
    d.textContent = t.name;
    towns.appendChild(d);
  }
  box.appendChild(towns);
  return { parks };
}
