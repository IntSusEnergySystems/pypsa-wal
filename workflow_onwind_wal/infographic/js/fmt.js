// French number formatting and typography, applied to every label.

const NNBSP = " "; // espace fine insécable
const NBSP = " ";

export function int(n) {
  const s = String(Math.round(Math.abs(n))).replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
  return (n < 0 ? "−" : "") + s;
}

export function dec(x, d = 1) {
  const s = Math.abs(x).toFixed(d).replace(".", ",");
  const [a, b] = s.split(",");
  const head = a.replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
  return (x < 0 ? "−" : "") + (b ? `${head},${b}` : head);
}

export function signed(n, formatter = int) {
  return (n > 0 ? "+" : n < 0 ? "−" : "±") + formatter(Math.abs(n));
}

export function pct(x, d = 0) {
  return `${dec(x, d)}${NNBSP}%`;
}

// Round to a readable precision for "≈" figures.
export function approx(n, step = 10) {
  return int(Math.round(n / step) * step);
}

export function gw(mw, d = 1) {
  return dec(mw / 1000, d);
}

const WORDS = ["zéro", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"];

// "environ trois fois", "environ 2,4 fois"
export function times(ratio) {
  const r = Math.round(ratio);
  if (Math.abs(ratio - r) < 0.25 && r >= 2 && r <= 10) return `environ ${WORDS[r]} fois`;
  return `environ ${dec(ratio, 1)} fois`;
}

// Espaces fines avant : ; ! ? %, dans les guillemets ; espace insécable avant les unités.
export function typo(s) {
  if (s == null) return "";
  return String(s)
    .replace(/ ([:;!?%])/g, `${NNBSP}$1`)
    .replace(/« /g, `«${NNBSP}`)
    .replace(/ »/g, `${NNBSP}»`)
    .replace(/(\d) (km²|km|m|MW|GW|ha|°)(?![\p{L}])/gu, `$1${NBSP}$2`)
    .replace(/(\d)\.\.\.(\d)/g, "$1–$2");
}

// Fill {placeholders} then apply the typography.
export function tpl(s, values = {}) {
  return typo(String(s).replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m)));
}
