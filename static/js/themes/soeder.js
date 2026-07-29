// ════════════════════════════════════════════════════════════════════
// soeder.js — Laufzeit für das „Söder"-Theme
// --------------------------------------------------------------------
// Getrennt von der übrigen App-Logik. Stellt window.SoederTheme mit
// activate()/deactivate() bereit; theme.js ruft diese beim Themenwechsel.
// Erzeugt eine Ebene: ein periodisch auftauchendes Söder-Maskottchen.
// MUSS vor theme.js eingebunden werden, damit window.SoederTheme existiert.
// ════════════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // Eingebaute Fallback-Sprüche – bewusst generische Grüße/Redewendungen.
  // Beim Aktivieren werden diese durch den echten Zitat-Snapshot vom Server
  // ersetzt (GET /api/soeder/quotes), sofern verfügbar. Schlägt der Abruf
  // fehl, bleibt diese Liste in Gebrauch, sodass das Theme nie leer ist.
  let QUOTES = [
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

  // Echten Zitat-Snapshot laden und die Fallback-Liste ersetzen. Same-origin,
  // daher CSP-konform. Fehler werden ignoriert (Fallback bleibt bestehen).
  // Läuft nur einmal pro Seitenaufruf.
  let quotesLoaded = false;
  function loadQuotes() {
    if (quotesLoaded) return;
    quotesLoaded = true;
    fetch("/api/soeder/quotes", { credentials: "same-origin" })
      .then((r) => (r.ok ? r.json() : null))
      .then((list) => {
        if (Array.isArray(list)) {
          const clean = list.filter((q) => typeof q === "string" && q.trim());
          if (clean.length) QUOTES = clean;
        }
      })
      .catch(() => { /* Fallback-Sprüche behalten. */ });
  }

  // Söder-Maskottchen: echtes Foto aus static/img. Das Bild wird beim ersten
  // Aktivieren des Themes genau einmal geladen und danach bei jedem Auftauchen
  // nur noch geklont – kein erneuter Netzwerk-/Dekodier-Aufwand. Wer das Theme
  // nie benutzt, lädt das Bild gar nicht erst.
  const MASCOT_SRC = "/static/img/Markus-Soeder.png";
  // Die Bayern-Flagge ist der CSS-Hintergrund des Themes. Wir halten eine
  // Image-Referenz am Leben, damit das dekodierte Bild im Speicher-Cache
  // bleibt: beim Hin- und Herschalten der Themes (und bei jedem Seitenwechsel,
  // dank Cache-Header) wird es nicht erneut geladen oder dekodiert.
  const FLAG_SRC = "/static/img/bavaria-flag.jpeg";
  let mascotTemplate = null;
  let flagCache = null;
  function preloadImages() {
    if (mascotTemplate) return;
    mascotTemplate = new Image();
    mascotTemplate.className = "soeder-photo";
    mascotTemplate.alt = "Markus Söder";
    mascotTemplate.decoding = "async";
    mascotTemplate.src = MASCOT_SRC;

    flagCache = new Image();
    flagCache.decoding = "async";
    flagCache.src = FLAG_SRC;
  }

  // Auftritts-Takt: lange genug stehen bleiben, um das Zitat zu lesen, und
  // danach ausreichend Pause, damit das Maskottchen nicht nervt.
  const STAY_MS = 9000;      // Standzeit pro Auftritt
  const INTERVAL_MS = 14000; // Abstand zwischen zwei Auftritten
  const FIRST_MS = 2500;     // erster Auftritt nach dem Aktivieren

  // Reihum von unten, rechts, oben und links – so kommt Söder nicht immer aus
  // derselben Ecke. Die Reihenfolge ist fest, damit sich Auftritte abwechseln
  // statt zufällig mehrfach hintereinander an derselben Kante zu erscheinen.
  const SIDES = ["bottom", "right", "top", "left"];

  let figureLayer = null;
  let mascotTimer = null;
  let sideToggle = 0;
  let active = false;

  function rand(min, max) { return Math.random() * (max - min) + min; }

  // ── Söder-Maskottchen einblenden ────────────────────────────────────
  function showMascot() {
    if (!figureLayer) return;

    const side = SIDES[sideToggle++ % SIDES.length];
    const wrap = document.createElement("div");
    wrap.className = "soeder-mascot enter from-" + side;

    // Die Kante selbst (und die passende Kippung) setzt das CSS über die
    // from-*-Klasse. Hier kommt nur dazu, wo entlang der Kante er auftaucht,
    // plus der Start-/Endversatz der Ein-/Ausblend-Animation (--fx/--fy):
    // Söder schiebt sich immer aus „seiner" Kante herein und dorthin zurück.
    if (side === "bottom" || side === "top") {
      // Mindestens 6vw von der Ecke weg, sonst ragt die Sprechblase hinaus.
      wrap.style[Math.random() < 0.5 ? "right" : "left"] = rand(6, 14) + "vw";
      wrap.style.setProperty("--fy", (side === "bottom" ? 60 : -60) + "px");
    } else {
      // Fußlinie auf mittlerer Höhe: darüber bleibt Platz für die Sprechblase.
      wrap.style.bottom = rand(30, 50) + "vh";
      wrap.style.setProperty("--fx", (side === "right" ? 70 : -70) + "px");
    }

    const speech = document.createElement("div");
    speech.className = "soeder-speech";
    speech.textContent = QUOTES[Math.floor(Math.random() * QUOTES.length)];

    wrap.appendChild(mascotTemplate.cloneNode(false));
    wrap.appendChild(speech);
    figureLayer.appendChild(wrap);

    // Standzeit lang genug, um das Zitat in Ruhe zu lesen.
    setTimeout(() => {
      wrap.classList.remove("enter");
      wrap.classList.add("leave");
      wrap.addEventListener("animationend", () => wrap.remove(), { once: true });
    }, STAY_MS);
  }

  // ── Aktivieren / Deaktivieren ───────────────────────────────────────
  function activate() {
    if (active) return;
    active = true;

    loadQuotes();     // echten Snapshot holen; Fallback bleibt bis dahin aktiv
    preloadImages();  // Maskottchen + Flaggen-Hintergrund einmalig holen

    figureLayer = document.createElement("div");
    figureLayer.id = "soeder-figure";
    document.body.appendChild(figureLayer);

    setTimeout(showMascot, FIRST_MS);
    mascotTimer = setInterval(showMascot, INTERVAL_MS);
  }

  function deactivate() {
    if (!active) return;
    active = false;

    clearInterval(mascotTimer);
    mascotTimer = null;

    if (figureLayer) { figureLayer.remove(); figureLayer = null; }
  }

  window.SoederTheme = { activate, deactivate };
})();
