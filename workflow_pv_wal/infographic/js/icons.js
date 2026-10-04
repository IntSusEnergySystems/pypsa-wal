// Pictograms, drawn in-house in one style: 24 x 24 grid, 2 px stroke, round
// ends (the look of Tabler / Lucide, without their licence notices).  Same
// grammar as the wind dashboard's set.

const P = {
  wallonie:
    '<path d="M3 13.5 6 9l3 1 2.5-3 3 1.5 3-2 3.5 2-1 4 1.5 3-3 3.5-3-1-2.5 2-3-1.5-2.5.5-2-2.5Z"/>',
  nature:
    '<path d="M3 21c0-8.5 4.5-13 11-13.5 0 7-4 12.5-11 13.5Z"/><path d="M3 21l6.5-7.5"/>' +
    '<path d="M16 21v-5M16 16l-2.5-2.5M16 17.5l2.5-2.5"/>',
  foret:
    '<path d="M7 21v-4M17 21v-3"/><path d="M7 3 3 13h8Z"/><path d="M17 6l-4 9h8Z"/><path d="M2 21h20"/>',
  paysage:
    '<path d="M2 20l6-9 4 5 3-3 7 7Z"/><circle cx="17" cy="6" r="2.5"/>' +
    '<path d="M9 5.5h2M10 4.5v2"/>',
  risques:
    '<path d="M2 20l5-8.5 3 4.5 2-2.8 3.2 6.8"/>' +
    '<path d="M15 9c1.2-1 2.4-1 3.5 0s2.3 1 3.5 0M15 13c1.2-1 2.4-1 3.5 0s2.3 1 3.5 0"/>',
  bati:
    '<path d="M2 21h20"/><path d="M4 21V10l5-3.5L14 10v11"/><path d="M8 21v-4h2v4"/>' +
    '<path d="M17 21V4M14.5 7h5M15 12h4"/>',
  parc:
    '<rect x="3" y="5" width="18" height="14" rx="1.5" stroke-dasharray="3 2.2"/>' +
    '<path d="M7 15l2-5h6l2 5Z"/><path d="M12 15v2"/>',
  circulaire:
    '<path d="M6 3h9l4 4v14H6Z"/><path d="M15 3v4h4"/><path d="M9 12h7M9 15.5h7M9 8.5h3"/>',
  solaire:
    '<path d="M3 17h18l-3-9H6Z"/><path d="M4.5 12.5h15M9.5 8l-1 9M14.5 8l1 9"/><path d="M12 17v4M8 21h8"/>',
  friche:
    '<path d="M3 21V11l4-2v12M7 21V9l5-3v15M12 21V9h9v12"/><path d="M15 12v2M18 12v2M15 17v2M18 17v2"/>',
  zae:
    '<path d="M2 21h20"/><path d="M3 21V11l5 3V11l5 3V11l5 3V7h3v14"/>',
  eau:
    '<path d="M2 16c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0"/><path d="M2 20c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0"/>' +
    '<path d="M6 12l1.5-5h9L18 12Z"/>',
  agri:
    '<path d="M2 21h20"/><path d="M4 11h10l2 4"/><path d="M9 11V5M5 5h8"/>' +
    '<path d="M18 21c0-5 1-8 3.5-10M18 21c0-4-1.5-6.5-4-8"/>',
  sol:
    '<path d="M2 9h20"/><path d="M5 13h1M10 14h1M15 12.5h1M19 15h1M7 18h1M13 19h1M18 19.5h1"/>' +
    '<path d="M8 9c0-3 1.5-5 4-6 2.5 1 4 3 4 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  hausse: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  baisse: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  play: '<path d="M7 4l13 8-13 8Z"/>',
  pause: '<path d="M8 4v16M16 4v16"/>',
  prev: '<path d="M15 5l-7 7 7 7"/>',
  next: '<path d="M9 5l7 7-7 7"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  loupe: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/>',
};

export function icon(name, size = 24) {
  const body = P[name] || P.info;
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" ` +
    `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}
