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
  function loadQuotes() {
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

  // Söder-Maskottchen: echtes Foto aus static/img. Das Bild wird genau einmal
  // vorgeladen und danach bei jedem Auftauchen nur noch geklont – so löst kein
  // erneuter Netzwerk-/Dekodier-Aufwand aus.
  const MASCOT_SRC = "/static/img/Markus-Soeder.png";
  const mascotTemplate = new Image();
  mascotTemplate.className = "soeder-photo";
  mascotTemplate.alt = "Markus Söder";
  mascotTemplate.src = MASCOT_SRC;   // startet den Download sofort (Cache füllen)

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

    wrap.appendChild(mascotTemplate.cloneNode(false));
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

    loadQuotes();  // echten Snapshot holen; Fallback bleibt bis dahin aktiv

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
