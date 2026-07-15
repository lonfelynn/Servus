// ════════════════════════════════════════════════════════════════════
// soeder.js — Laufzeit für das „Söder"-Theme
// --------------------------------------------------------------------
// Getrennt von der übrigen App-Logik. Stellt window.SoederTheme mit
// activate()/deactivate() bereit; theme.js ruft diese beim Themenwechsel.
// Erzeugt zwei feste Ebenen: schwebende Zitate (Hintergrund) und ein
// periodisch auftauchendes Söder-Maskottchen (Vordergrund).
// MUSS vor theme.js eingebunden werden, damit window.SoederTheme existiert.
// ════════════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // Locker-bayerische Sprüche – bewusst generische Grüße/Redewendungen,
  // keine erfundenen Zitate, die einer realen Person untergeschoben werden.
  const QUOTES = [
    "Mia san mia!",
    "Servus beinand!",
    "Passt scho.",
    "A gmahde Wiesn.",
    "Grüß Gott!",
    "Des basd!",
    "Bavaria one!",
    "Weißwurscht & Breze",
    "Oans, zwoa, gsuffa!",
    "Immer schee locker bleim.",
    "Freibier für olle!",
    "Host mi?",
  ];

  // Kleines Cartoon-Maskottchen (kein echtes Foto) – Anzug, Krawatte, Brille.
  const MASCOT_SVG = `
    <svg class="soeder-svg" viewBox="0 0 120 150" width="100%" height="100%"
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <!-- Anzug -->
      <path d="M18 150 V118 a42 42 0 0 1 84 0 V150 Z" fill="#1f2a3a"/>
      <path d="M60 108 L44 150 H52 L60 122 L68 150 H76 Z" fill="#f4f6fa"/>
      <path d="M60 110 L54 128 L60 140 L66 128 Z" fill="#0098d8"/>
      <!-- Hals -->
      <rect x="50" y="92" width="20" height="20" rx="6" fill="#e9b58f"/>
      <!-- Kopf -->
      <ellipse cx="60" cy="64" rx="30" ry="33" fill="#f0c19a"/>
      <!-- Ohren -->
      <circle cx="31" cy="66" r="6" fill="#e9b58f"/>
      <circle cx="89" cy="66" r="6" fill="#e9b58f"/>
      <!-- Haare -->
      <path d="M30 56 q0 -34 30 -34 q30 0 30 34 q-8 -16 -30 -16 q-22 0 -30 16 Z" fill="#6b5842"/>
      <!-- Brille -->
      <g stroke="#2a2a2a" stroke-width="2.5" fill="none">
        <rect x="38" y="58" width="18" height="14" rx="5"/>
        <rect x="64" y="58" width="18" height="14" rx="5"/>
        <line x1="56" y1="64" x2="64" y2="64"/>
      </g>
      <!-- Augen -->
      <circle cx="47" cy="65" r="2.4" fill="#26313f"/>
      <circle cx="73" cy="65" r="2.4" fill="#26313f"/>
      <!-- Lächeln -->
      <path d="M48 80 q12 10 24 0" stroke="#a15c3d" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    </svg>`;

  let bgLayer = null;
  let figureLayer = null;
  let quoteTimer = null;
  let mascotTimer = null;
  let cornerToggle = 0;
  let active = false;

  function rand(min, max) { return Math.random() * (max - min) + min; }

  // ── Schwebendes Zitat erzeugen ──────────────────────────────────────
  function spawnQuote() {
    if (!bgLayer) return;
    const el = document.createElement("div");
    el.className = "soeder-quote";
    el.textContent = QUOTES[Math.floor(Math.random() * QUOTES.length)];

    const startX = rand(-5, 80);           // vw
    const startY = rand(10, 90);           // vh
    const drift  = rand(-14, 14);          // horizontale Abweichung (vw)
    el.style.setProperty("--x", startX + "vw");
    el.style.setProperty("--y", startY + "vh");
    el.style.setProperty("--dx", drift + "vw");
    el.style.setProperty("--dy", rand(-30, -14) + "vh");   // langsam nach oben
    el.style.setProperty("--rot", rand(-8, 8) + "deg");
    el.style.setProperty("--dur", rand(16, 26) + "s");

    el.addEventListener("animationend", () => el.remove());
    bgLayer.appendChild(el);
  }

  // ── Söder-Maskottchen einblenden ────────────────────────────────────
  function showMascot() {
    if (!figureLayer) return;

    const wrap = document.createElement("div");
    wrap.className = "soeder-mascot enter";

    // Abwechselnd rechte/linke untere Ecke.
    const onRight = (cornerToggle++ % 2) === 0;
    wrap.style.bottom = "0";
    wrap.style[onRight ? "right" : "left"] = rand(2, 8) + "vw";

    const speech = document.createElement("div");
    speech.className = "soeder-speech";
    speech.textContent = QUOTES[Math.floor(Math.random() * QUOTES.length)];

    wrap.innerHTML = MASCOT_SVG;
    wrap.appendChild(speech);
    figureLayer.appendChild(wrap);

    // Nach kurzer Standzeit wieder ausblenden und entfernen.
    setTimeout(() => {
      wrap.classList.remove("enter");
      wrap.classList.add("leave");
      wrap.addEventListener("animationend", () => wrap.remove(), { once: true });
    }, 2600);
  }

  // ── Aktivieren / Deaktivieren ───────────────────────────────────────
  function activate() {
    if (active) return;
    active = true;

    bgLayer = document.createElement("div");
    bgLayer.id = "soeder-bg";
    figureLayer = document.createElement("div");
    figureLayer.id = "soeder-figure";
    document.body.appendChild(bgLayer);
    document.body.appendChild(figureLayer);

    // Ein paar Zitate direkt zum Start, danach regelmäßig nachlegen.
    for (let i = 0; i < 4; i++) setTimeout(spawnQuote, i * 900);
    quoteTimer = setInterval(spawnQuote, 2600);

    setTimeout(showMascot, 1500);
    mascotTimer = setInterval(showMascot, 7000);
  }

  function deactivate() {
    if (!active) return;
    active = false;

    clearInterval(quoteTimer);
    clearInterval(mascotTimer);
    quoteTimer = mascotTimer = null;

    if (bgLayer) { bgLayer.remove(); bgLayer = null; }
    if (figureLayer) { figureLayer.remove(); figureLayer = null; }
  }

  window.SoederTheme = { activate, deactivate };
})();
