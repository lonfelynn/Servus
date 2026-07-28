// icons.js – zentrale SVG-Icon-Bibliothek
// Ersetzt die früher genutzten Emoji-/Unicode-Zeichen durch ein einheitliches
// Line-Icon-Set (siehe static/img/icons/). Alle Icons zeichnen mit
// `currentColor`, damit sie die Textfarbe des Buttons erben und dem Theme
// sowie der Akzentfarbe folgen. Wird VOR chat.js eingebunden, damit
// `window.ICONS` global verfügbar ist.

(function () {
  // Baut ein <svg>-Markup aus den inneren Pfaden. `filled` nutzt fill statt stroke.
  function icon(inner, opts) {
    opts = opts || {};
    const sw = opts.strokeWidth || 1.75;
    if (opts.filled) {
      return `<svg class="icon" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">${inner}</svg>`;
    }
    return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
  }

  // Die "Knöpfe" des Einstellungen-Icons werden mit der Panel-Farbe gefüllt,
  // damit die Linie optisch hinter ihnen durchläuft.
  const KNOB = 'fill="var(--panel)"';

  window.ICONS = {
    settings: icon(
      `<line x1="4" y1="6" x2="20" y2="6"/><circle cx="15" cy="6" r="2" ${KNOB}/>` +
      `<line x1="4" y1="12" x2="20" y2="12"/><circle cx="9" cy="12" r="2" ${KNOB}/>` +
      `<line x1="4" y1="18" x2="20" y2="18"/><circle cx="16" cy="18" r="2" ${KNOB}/>`
    ),
    logout: icon(
      `<path d="M13 4H6a1 1 0 00-1 1v14a1 1 0 001 1h7"/>` +
      `<line x1="21" y1="12" x2="9" y2="12"/><polyline points="16 7 21 12 16 17"/>`
    ),
    profile: icon(`<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>`),
    lock: icon(`<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>`),
    eye: icon(`<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>`),
    eyeOff: icon(
      `<path d="M3 3l18 18"/><path d="M10.6 10.6a3 3 0 004.2 4.2"/>` +
      `<path d="M6.7 6.7C4 8.2 2 12 2 12s4 7 10 7c1.6 0 3-.4 4.2-1.1M17.9 17.9C19.9 16.4 22 12 22 12s-1.8-3.2-4.9-5.2"/>`
    ),
    send: icon(`<polygon points="22 2 15 22 11 13 2 9 22 2"/>`),
    messenger: icon(`<path d="M4 4h16a1 1 0 011 1v11a1 1 0 01-1 1H9l-5 4V5a1 1 0 011-1z"/>`),
    mail: icon(`<rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="2 6 12 13 22 6"/>`),
    userPlus: icon(
      `<circle cx="9" cy="8" r="3.5"/><path d="M2.5 21a6.5 6.5 0 0113 0"/>` +
      `<line x1="18.5" y1="8" x2="18.5" y2="14"/><line x1="15.5" y1="11" x2="21.5" y2="11"/>`
    ),
    members: icon(
      `<circle cx="9" cy="8" r="3.5"/><path d="M2.5 21a6.5 6.5 0 0113 0"/>` +
      `<circle cx="18" cy="9" r="2.6"/><path d="M15.7 13.8a5 5 0 016.3 4.8"/>`
    ),
    bell: icon(`<path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>`),
    plus: icon(`<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>`),
    close: icon(`<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>`),
    edit: icon(`<path d="M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>`),
    reply: icon(`<polyline points="9 14 4 9 9 4"/><path d="M4 9h9a7 7 0 017 7v3"/>`),
    forward: icon(`<polyline points="15 14 20 9 15 4"/><path d="M20 9h-9a7 7 0 00-7 7v3"/>`),
    copy: icon(
      `<rect x="9" y="9" width="12" height="12" rx="2"/>` +
      `<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>`
    ),
    trash: icon(
      `<line x1="3" y1="6" x2="21" y2="6"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>` +
      `<path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>` +
      `<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>`
    ),
    back: icon(`<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>`),
    chevronDown: icon(`<polyline points="6 9 12 15 18 9"/>`),
    search: icon(`<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>`),
    more: icon(`<circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/>`, { filled: true }),
    attach: icon(`<path d="M8 13l6.5-6.5a3 3 0 114.24 4.24L11 18.5a5 5 0 01-7.07-7.07L12 3.36"/>`),
    image: icon(`<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>`),
    camera: icon(`<path d="M4 7h3l1.5-2h7L17 7h3a1 1 0 011 1v11a1 1 0 01-1 1H4a1 1 0 01-1-1V8a1 1 0 011-1z"/><circle cx="12" cy="14" r="4"/>`),
    download: icon(`<line x1="12" y1="3" x2="12" y2="15"/><polyline points="7 11 12 16 17 11"/><line x1="4" y1="21" x2="20" y2="21"/>`),
    check: icon(`<polyline points="5 13 9 17 19 7"/>`, { strokeWidth: 1.9 }),
    checkDouble: icon(`<polyline points="1 13 5 17 12 9"/><polyline points="7 13 11 17 22 6"/>`, { strokeWidth: 1.9 }),
    alert: icon(`<path d="M12 2L2 21h20L12 2z"/><line x1="12" y1="9" x2="12" y2="13.5"/><circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none"/>`),
    info: icon(`<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="11.5"/><circle cx="12" cy="8" r="0.9" fill="currentColor" stroke="none"/>`),
    sun: icon(
      `<circle cx="12" cy="12" r="4.5"/>` +
      `<line x1="12" y1="2" x2="12" y2="4.5"/><line x1="12" y1="19.5" x2="12" y2="22"/>` +
      `<line x1="2" y1="12" x2="4.5" y2="12"/><line x1="19.5" y1="12" x2="22" y2="12"/>` +
      `<line x1="4.9" y1="4.9" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.1" y2="19.1"/>` +
      `<line x1="4.9" y1="19.1" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.1" y2="4.9"/>`
    ),
    moon: icon(`<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>`),
    // Palette – Inhalt um 0.5px zentriert, damit das Glyph exakt in der Box sitzt
    // (die Miniatur-Vorlage saß leicht links/tief).
    palette: icon(
      `<g transform="translate(0.4 0.2)">` +
      `<path d="M12 3a9 9 0 100 18c1 0 1.6-.6 1.6-1.4 0-.4-.15-.7-.4-1a1.4 1.4 0 011.1-2.3H16a4 4 0 004-4 8 8 0 00-8-8.3z"/>` +
      `<circle cx="7.5" cy="10.5" r="1.1" fill="currentColor" stroke="none"/>` +
      `<circle cx="9.5" cy="15.5" r="1.1" fill="currentColor" stroke="none"/>` +
      `<circle cx="15" cy="8.5" r="1.1" fill="currentColor" stroke="none"/>` +
      `</g>`,
      { strokeWidth: 1.6 }
    ),
  };
})();
