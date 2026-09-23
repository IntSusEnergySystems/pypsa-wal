// Pictograms, drawn in-house in one style: 24 x 24 grid, 2 px stroke, round
// ends (the look of Tabler / Lucide, without their licence notices).

function turbine(x, y, s = 1) {
  const L = 5.2 * s;
  const c = (a) => [x + L * Math.cos(a), y + L * Math.sin(a)];
  const [ux, uy] = c(-Math.PI / 2);
  const [rx, ry] = c(Math.PI / 6);
  const [lx, ly] = c((5 * Math.PI) / 6);
  const f = (v) => v.toFixed(2);
  return `<path d="M${f(x)} ${f(y + 1.1 * s)}L${f(x)} ${f(y + 10.5 * s)}"/>` +
    `<path d="M${f(x)} ${f(y)}L${f(ux)} ${f(uy)}M${f(x)} ${f(y)}L${f(rx)} ${f(ry)}M${f(x)} ${f(y)}L${f(lx)} ${f(ly)}"/>` +
    `<circle cx="${f(x)}" cy="${f(y)}" r="${f(0.9 * s)}"/>`;
}

const P = {
  villes:
    '<path d="M2 21h20"/><path d="M4 21v-8l5-4 5 4v8"/><path d="M8 21v-4h2v4"/>' +
    '<circle cx="18" cy="9" r="3.6"/><path d="M18 12.6V21"/>',
  axes:
    '<path d="M7 21 10.5 3"/><path d="M17 21 13.5 3"/>' +
    '<path d="M12 20v-2.5M12 14.5v-2.2M12 9.3V7.6M12 5.3V4.4"/>',
  habitations:
    '<path d="M2 21h20"/><path d="M3 21v-6l4-3.4 4 3.4v6"/>' +
    '<path d="M13.5 13h7.5M19 11l2 2-2 2M15.5 11l-2 2 2 2"/>',
  nature:
    '<path d="M3 21c0-8.5 4.5-13 11-13.5 0 7-4 12.5-11 13.5Z"/><path d="M3 21l6.5-7.5"/>' +
    '<path d="M14.5 21h7M15.5 21v-6M20.5 21v-6M18 21v-6M14.5 15h7M14.5 15l3.5-2.6 3.5 2.6"/>',
  technique:
    '<path d="M2 21l5-8.5 3 4.5 2-2.8 3.2 6.8"/>' +
    '<path d="M16 21 19 4l3 17M16.9 16h4.2M17.8 11h2.4M15.5 7h7"/>',
  espacement:
    `<circle cx="12" cy="12" r="10" stroke-dasharray="2.2 2.6"/>${turbine(12, 8.2, 0.78)}`,
  parcs: [4.2, 9.4, 14.6, 19.8].map((x) => turbine(x, 9, 0.62)).join("") + '<path d="M1.5 21h21"/>',
  horizon:
    '<path d="M2.6 14.6 12 19l9.4-4.4"/><path d="M7.9 17.1A4.5 4.5 0 0 1 16.1 17.1"/>' +
    '<path d="M4.4 10.4A10.5 10.5 0 0 1 19.6 10.4" stroke-dasharray="1.6 2.4"/><circle cx="12" cy="19" r="1.5"/>',
  interdistance:
    `${turbine(4.5, 7, 0.6)}${turbine(19.5, 7, 0.6)}` +
    '<path d="M7.5 19h9M9.5 17l-2 2 2 2M14.5 17l2 2-2 2"/>',
  reserve:
    '<path d="M2 12.5c2.2-2.6 4.8-2.6 6.6 0 1.8-2.6 4.4-2.6 6.6 0"/>' +
    '<path d="M16.8 5.2a2.6 2.6 0 1 1 3.6 2.4c-.8.4-1.3 1-1.3 1.9v.9"/><path d="M19.1 14.2v.1"/>' +
    '<path d="M5 19h6" stroke-dasharray="1.5 2.5"/>',
  bilan: `${turbine(12, 7.5, 0.95)}<path d="M5 21h14"/>`,
  eolienne: turbine(12, 7.5, 0.95),
  fleche_gauche: '<path d="M15 5l-7 7 7 7"/>',
  fleche_droite: '<path d="M9 5l7 7-7 7"/>',
  lecture: '<path d="M8 5v14l11-7Z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  loupe: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/>',
  info: '<circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.8v.1"/>',
  hausse: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  baisse: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  fermer: '<path d="M6 6l12 12M18 6 6 18"/>',
};

export function icon(name, { size = 24, cls = "", stroke = 2, title = "" } = {}) {
  const body = P[name] || "";
  const t = title ? `<title>${title}</title>` : "";
  return `<svg class="ico ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" ` +
    `${title ? 'role="img"' : 'aria-hidden="true"'}>${t}${body}</svg>`;
}

// Wallonia, drawn from the region outline itself.
export function wallonieIcon(outlinePath, grid, { size = 24, cls = "" } = {}) {
  return `<svg class="ico ${cls}" width="${size}" height="${size}" viewBox="-60 -300 ${grid.cols + 120} ${grid.cols + 120}" ` +
    `fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true">` +
    `<path d="${outlinePath}" vector-effect="non-scaling-stroke"/></svg>`;
}
