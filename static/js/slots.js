// slots.js – „Servus Slots": das Casino-Modal, in dem man XP verspielt.
//
// Die Walzen hier sind reine Deko: Ausgang, Auszahlung und der neue XP-Stand
// kommen ausschließlich vom Server (POST /api/slots/spin). Der Browser dreht
// erst los, wartet auf die Antwort und lässt die Walzen dann auf das
// serverseitige Ergebnis fallen — gewinnen kann man mit der Konsole also nicht.

// Mindestdauer einer Drehung, damit das Spiel auch bei schnellem Server
// nach etwas aussieht, plus der Versatz zwischen den drei Walzen.
const SLOT_MIN_SPIN_MS = 900;
const SLOT_REEL_STAGGER_MS = 260;
// Anzahl der Symbole auf einer laufenden Walze (nur fürs Auge).
const SLOT_STRIP_LENGTH = 8;

// ── Walzensymbole ──────────────────────────────────────────
// Bewusst SVG statt Emoji: Emoji sehen auf jedem Betriebssystem anders aus,
// lassen sich nicht einfärben und skalieren nicht sauber mit der Zelle. Jedes
// Symbol zeichnet in `currentColor`; die Farbe pro Symbol kommt vom Server
// (slots.py SYMBOLS) und wird auf der Zelle gesetzt. Nur die Kirschstiele und
// die Facetten des Diamanten haben eine eigene Farbe — sonst wäre die Form
// nicht lesbar.
const SLOT_SYMBOL_SVG = {
  cherry:
    `<path d="M13.5 3.2c-3.2 2.6-5.2 5.4-6.1 8.6" fill="none" stroke="#4d7c0f" stroke-width="1.7" stroke-linecap="round"/>` +
    `<path d="M13.5 3.2c2.4 2.2 3.8 4.7 4.2 7.4" fill="none" stroke="#4d7c0f" stroke-width="1.7" stroke-linecap="round"/>` +
    `<circle cx="7" cy="16.6" r="4.4" fill="currentColor"/>` +
    `<circle cx="17.2" cy="15.4" r="3.9" fill="currentColor"/>`,
  lemon:
    `<ellipse cx="12" cy="12" rx="8.6" ry="6.1" transform="rotate(-24 12 12)" fill="currentColor"/>` +
    `<path d="M18.6 7.1l2.1-1.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  bell:
    `<path d="M12 2.6a1.7 1.7 0 011.7 1.7v.6A6.2 6.2 0 0118 10.7v4.1l1.7 2.3a.85.85 0 01-.68 1.36H5a.85.85 0 01-.68-1.36L6 14.8v-4.1a6.2 6.2 0 014.3-5.8v-.6A1.7 1.7 0 0112 2.6z" fill="currentColor"/>` +
    `<circle cx="12" cy="20" r="1.9" fill="currentColor"/>`,
  star:
    `<path d="M12 2.4l2.95 5.98 6.6.96-4.78 4.66 1.13 6.57L12 17.47l-5.9 3.1 1.13-6.57L2.45 9.34l6.6-.96z" fill="currentColor"/>`,
  diamond:
    `<path d="M7.2 3h9.6l4.2 6.1L12 21.2 3 9.1z" fill="currentColor"/>` +
    `<path d="M3 9.1h18M7.2 3L5.8 9.1 12 21.2M16.8 3l1.4 6.1L12 21.2" fill="none" stroke="rgba(255,255,255,.45)" stroke-width="1"/>`,
  seven:
    `<path d="M5.8 3.6h12.4v3.5L11.4 20.4H6.9l6.9-13.3H5.8z" fill="currentColor"/>`,
};

const SLOT_UNKNOWN_SVG = `<circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2"/>`;

const slotsModal      = document.getElementById("slots-modal");
const slotsBtn        = document.getElementById("slots-btn");
const slotsCloseBtn   = document.getElementById("slots-close-btn");
const slotsMachine    = document.getElementById("slots-machine");
const slotsResultEl   = document.getElementById("slots-result");
const slotsXpEl       = document.getElementById("slots-xp");
const slotsDeltaEl    = document.getElementById("slots-delta");
const slotsLevelEl    = document.getElementById("slots-level");
const slotsProgressEl = document.getElementById("slots-progress-fill");
const slotsBetsEl     = document.getElementById("slots-bets");
const slotsBetInput   = document.getElementById("slots-bet-input");
const slotsMaxBtn     = document.getElementById("slots-max-btn");
const slotsSpinBtn    = document.getElementById("slots-spin-btn");
const slotsSpinLabel  = document.getElementById("slots-spin-label");
const slotsPaytableEl = document.getElementById("slots-paytable");
const slotsStatsEl    = document.getElementById("slots-stats");
const slotsHistoryEl  = document.getElementById("slots-history");
const slotsOddsEl     = document.getElementById("slots-odds");
const slotsHintEl     = document.getElementById("slots-hint");
const slotsReels      = [0, 1, 2].map(i => document.getElementById("slots-reel-" + i));
const slotsStrips     = [0, 1, 2].map(i => document.getElementById("slots-strip-" + i));

// Zustand: die Server-Konfiguration (Symbole, Gewinntabelle, Grenzen), eine
// id → Symbol-Tabelle fürs schnelle Nachschlagen und der letzte XP-Stand.
let slotsConfig = null;
let slotsSymbolsById = {};
let slotsBalance = { xp: 0, level: 1, level_xp: 0, level_span: 1 };
let slotsBet = 50;
let slotsSpinning = false;

const slotEscape = (text) =>
  (typeof escapeHtml === "function" ? escapeHtml(String(text)) : String(text));

const slotNumber = (value) => Number(value).toLocaleString("de-DE");

// Eine fertige Walzenfläche: SVG in der Farbe des Symbols.
function slotFace(symbolId, extraClass = "") {
  const symbol = slotsSymbolsById[symbolId];
  const svg = SLOT_SYMBOL_SVG[symbolId] || SLOT_UNKNOWN_SVG;
  const color = symbol ? symbol.color : "currentColor";
  return `<div class="slots-face ${extraClass}" style="color: ${slotEscape(color)}">` +
         `<svg viewBox="0 0 24 24" aria-hidden="true">${svg}</svg></div>`;
}

// ── Laden ──────────────────────────────────────────────────
async function loadSlots() {
  const res = await fetch("/api/slots");
  if (!res.ok) throw new Error("Slots konnten nicht geladen werden.");
  const data = await res.json();

  slotsConfig = data;
  slotsSymbolsById = Object.fromEntries(data.symbols.map(s => [s.id, s]));

  applyBalance(data);
  renderPaytable(data.paytable);
  renderStats(data.stats);
  renderHistory(data.history);

  slotsBetInput.min = data.min_bet;
  slotsBetInput.max = data.max_bet;
  slotsOddsEl.textContent =
    `${data.rtp} % Auszahlungsquote · rund ${data.hit_rate} % der Spins gewinnen`;
  slotsHintEl.textContent =
    `Einsatz zwischen ${data.min_bet} und ${data.max_bet} XP. Auf Dauer gewinnt ` +
    `der Automat — verlorene XP kosten dich auch Level.`;

  renderBetChips();
  setBet(Math.min(slotsBet, data.max_bet, Math.max(data.min_bet, data.xp)));

  // Ruhezustand der Walzen: das Ergebnis des letzten Spins, sonst drei Kirschen.
  const last = data.history[0];
  slotsStrips.forEach((strip, i) => {
    setReelSymbol(strip, last ? last.symbols[i] : "cherry");
  });
}

// ── Kontostand ─────────────────────────────────────────────
function applyBalance(data) {
  slotsBalance = {
    xp: data.xp,
    level: data.level,
    level_xp: data.level_xp,
    level_span: data.level_span,
  };
  slotsXpEl.textContent = slotNumber(data.xp);
  slotsLevelEl.textContent = `Level ${data.level}`;
  const fill = Math.max(0, Math.min(1, data.level_xp / data.level_span));
  slotsProgressEl.style.setProperty("--fill", fill);
  refreshBetAvailability();
}

// Zählt die Anzeige vom alten auf den neuen Stand hoch/runter, damit der
// Gewinn (oder Verlust) sichtbar wird statt einfach umzuspringen.
function animateXp(from, to) {
  const start = performance.now();
  const duration = 600;

  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    // ease-out, damit es am Ende ausläuft
    const value = Math.round(from + (to - from) * (1 - Math.pow(1 - t, 3)));
    slotsXpEl.textContent = slotNumber(value);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function showDelta(net) {
  slotsDeltaEl.textContent = (net > 0 ? "+" : "") + slotNumber(net) + " XP";
  slotsDeltaEl.classList.remove("hidden", "negative", "positive", "pop");
  slotsDeltaEl.classList.add(net >= 0 ? "positive" : "negative");
  // Reflow erzwingen, damit die Animation bei jedem Spin neu startet.
  void slotsDeltaEl.offsetWidth;
  slotsDeltaEl.classList.add("pop");
}

// ── Einsatz ────────────────────────────────────────────────
function renderBetChips() {
  slotsBetsEl.innerHTML = slotsConfig.bet_steps.map(step => `
    <button type="button" class="slots-chip" data-bet="${step}">${step}</button>
  `).join("");

  slotsBetsEl.querySelectorAll(".slots-chip").forEach(chip => {
    chip.addEventListener("click", () => setBet(Number(chip.dataset.bet)));
  });
}

function setBet(value) {
  if (!slotsConfig) return;
  let bet = Math.round(Number(value) || 0);
  bet = Math.max(slotsConfig.min_bet, Math.min(slotsConfig.max_bet, bet));
  slotsBet = bet;
  slotsBetInput.value = bet;

  slotsBetsEl.querySelectorAll(".slots-chip").forEach(chip => {
    chip.classList.toggle("selected", Number(chip.dataset.bet) === bet);
  });
  refreshBetAvailability();
}

// Sperrt Chips über dem Kontostand und den Drehen-Knopf, wenn die XP nicht
// reichen — die endgültige Prüfung macht trotzdem der Server.
function refreshBetAvailability() {
  if (!slotsConfig) return;
  const xp = slotsBalance.xp;

  slotsBetsEl.querySelectorAll(".slots-chip").forEach(chip => {
    chip.disabled = Number(chip.dataset.bet) > xp;
  });

  const affordable = xp >= slotsBet && xp >= slotsConfig.min_bet;
  slotsSpinBtn.disabled = slotsSpinning || !affordable;
  slotsSpinLabel.textContent = slotsSpinning
    ? "Dreht…"
    : (xp < slotsConfig.min_bet
        ? `Mindestens ${slotsConfig.min_bet} XP nötig`
        : `Drehen · ${slotsBet} XP`);
}

// ── Walzen ─────────────────────────────────────────────────
function setReelSymbol(strip, symbolId) {
  strip.innerHTML = `<div class="slots-cell">${slotFace(symbolId)}</div>`;
}

function startReels() {
  const ids = slotsConfig.symbols.map(s => s.id);
  slotsReels.forEach(reel => reel.classList.remove("won"));
  slotsStrips.forEach(strip => {
    strip.innerHTML = Array.from({ length: SLOT_STRIP_LENGTH }, () =>
      `<div class="slots-cell">${slotFace(ids[Math.floor(Math.random() * ids.length)])}</div>`
    ).join("");
    strip.classList.remove("landed");
    strip.classList.add("spinning");
  });
}

// Lässt die Walzen nacheinander auf das Server-Ergebnis fallen.
function stopReels(symbols) {
  return new Promise(resolve => {
    slotsStrips.forEach((strip, i) => {
      setTimeout(() => {
        strip.classList.remove("spinning");
        setReelSymbol(strip, symbols[i]);
        strip.classList.add("landed");
        if (i === slotsStrips.length - 1) setTimeout(resolve, 220);
      }, i * SLOT_REEL_STAGGER_MS);
    });
  });
}

// Hebt die Walzen hervor, die zur Gewinnkombination gehören.
function markWinningReels(symbols, winSymbol) {
  if (!winSymbol) return;
  symbols.forEach((id, i) => {
    if (id === winSymbol) slotsReels[i].classList.add("won");
  });
}

// ── Spin ───────────────────────────────────────────────────
async function spin() {
  if (slotsSpinning || !slotsConfig) return;

  slotsSpinning = true;
  slotsMachine.classList.remove("win");
  slotsDeltaEl.classList.add("hidden");
  setResult("Die Walzen drehen…", "");
  refreshBetAvailability();

  const xpBefore = slotsBalance.xp;
  startReels();
  const spinStarted = performance.now();

  let data;
  try {
    const res = await fetch("/api/slots/spin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bet: slotsBet }),
    });
    // Das Ratelimit (Flask-Limiter) antwortet mit HTML, nicht mit JSON.
    data = res.status === 429
      ? { ok: false, error: "Zu viele Spins hintereinander — kurz durchatmen." }
      : await res.json();
  } catch (e) {
    data = { ok: false, error: "Keine Verbindung zum Automaten." };
  }

  // Walzen mindestens SLOT_MIN_SPIN_MS laufen lassen.
  const elapsed = performance.now() - spinStarted;
  if (elapsed < SLOT_MIN_SPIN_MS) {
    await new Promise(r => setTimeout(r, SLOT_MIN_SPIN_MS - elapsed));
  }

  if (!data.ok) {
    // Der Einsatz wurde in keinem dieser Fälle abgebucht — der Kontostand von
    // vor der Drehung gilt weiter.
    slotsStrips.forEach(strip => {
      strip.classList.remove("spinning");
      setReelSymbol(strip, "cherry");
    });
    setResult(data.error || "Spin fehlgeschlagen.", "lose");
    slotsSpinning = false;
    refreshBetAvailability();
    return;
  }

  await stopReels(data.symbols);
  markWinningReels(data.symbols, data.win_symbol);

  applyBalance(data);
  animateXp(xpBefore, data.xp);
  showDelta(data.net);

  let message = data.message;
  if (data.level_delta > 0) message += ` Level ${data.level} erreicht!`;
  else if (data.level_delta < 0) message += ` Zurück auf Level ${data.level}.`;

  setResult(message, data.net > 0 ? "win" : data.net === 0 ? "even" : "lose");
  if (data.net > 0) {
    slotsMachine.classList.add("win");
    setTimeout(() => slotsMachine.classList.remove("win"), 1200);
  }

  // Bilanz und Historie kommen mit der Spin-Antwort — kein Nachladen nötig.
  renderStats(data.stats);
  renderHistory(data.history);

  slotsSpinning = false;
  refreshBetAvailability();

  // Level/XP in der Seitenleiste nachziehen (loadMe stammt aus chat.js).
  if (typeof loadMe === "function") loadMe();
}

function setResult(text, tone) {
  slotsResultEl.textContent = text;
  slotsResultEl.className = "slots-result" + (tone ? " " + tone : "");
}

// ── Gewinntabelle, Bilanz, Historie ────────────────────────
function renderPaytable(rows) {
  slotsPaytableEl.innerHTML = `
    <div class="slots-paytable-head">
      <span>Symbol</span><span>3 gleiche</span><span>2 gleiche</span>
    </div>
    ${rows.map(row => `
      <div class="slots-paytable-row">
        <span class="slots-paytable-symbol">
          ${slotFace(row.symbol, "small")}
          <span class="slots-paytable-label">${slotEscape(row.label)}</span>
        </span>
        <span>${slotEscape(row.triple)}× Einsatz</span>
        <span>${slotEscape(row.double)}× Einsatz</span>
      </div>
    `).join("")}
  `;
}

function renderStats(stats) {
  const sign = stats.net > 0 ? "+" : "";
  const tone = stats.net > 0 ? "win" : stats.net < 0 ? "lose" : "even";
  slotsStatsEl.innerHTML = `
    <div class="slots-stat"><span>Spins</span><strong>${stats.spins}</strong></div>
    <div class="slots-stat"><span>Eingesetzt</span><strong>${slotNumber(stats.wagered)} XP</strong></div>
    <div class="slots-stat"><span>Ausgezahlt</span><strong>${slotNumber(stats.won)} XP</strong></div>
    <div class="slots-stat"><span>Bilanz</span><strong class="${tone}">${sign}${slotNumber(stats.net)} XP</strong></div>
  `;
}

function renderHistory(history) {
  if (!history || history.length === 0) {
    slotsHistoryEl.innerHTML = `<div class="slots-history-empty">Noch kein Spin gedreht.</div>`;
    return;
  }

  slotsHistoryEl.innerHTML = history.map(spin => {
    const sign = spin.net > 0 ? "+" : "";
    const tone = spin.net > 0 ? "win" : spin.net < 0 ? "lose" : "even";
    const time = new Date(spin.created_at).toLocaleTimeString("de-DE",
      { hour: "2-digit", minute: "2-digit" });
    return `
      <div class="slots-history-row">
        <span class="slots-history-symbols">${spin.symbols.map(id => slotFace(id, "tiny")).join("")}</span>
        <span class="slots-history-bet">${spin.bet} XP</span>
        <span class="slots-history-net ${tone}">${sign}${slotNumber(spin.net)}</span>
        <span class="slots-history-time">${time}</span>
      </div>
    `;
  }).join("");
}

// ── Modal öffnen / schließen ───────────────────────────────
async function openSlotsModal() {
  slotsModal.classList.remove("hidden");
  setResult("Viel Glück!", "");
  slotsDeltaEl.classList.add("hidden");
  try {
    await loadSlots();
  } catch (e) {
    setResult("Der Automat ist gerade nicht erreichbar.", "lose");
  }
}

function closeSlotsModal() {
  // Während einer laufenden Drehung nicht schließen — der Spin ist serverseitig
  // ohnehin schon gebucht, aber die Anzeige soll ihn zu Ende zeigen.
  if (slotsSpinning) return;
  slotsModal.classList.add("hidden");
}

if (slotsBtn) {
  slotsBtn.addEventListener("click", openSlotsModal);
  slotsCloseBtn.addEventListener("click", closeSlotsModal);
  slotsSpinBtn.addEventListener("click", spin);
  slotsMaxBtn.addEventListener("click", () => setBet(Math.min(slotsConfig.max_bet, slotsBalance.xp)));
  slotsBetInput.addEventListener("change", (e) => setBet(e.target.value));
  slotsModal.addEventListener("click", (e) => {
    if (e.target === slotsModal) closeSlotsModal();
  });
}
