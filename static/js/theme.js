// theme.js – Theme-, Modus- und Akzentfarben-Verwaltung
// Selbstständig: liest die gespeicherten Werte aus localStorage und wendet sie
// beim Laden an. Wird vor chat.js/profile.js eingebunden, damit applyTheme /
// applyAccent / applyAppTheme global verfügbar sind.
//
// Drei getrennte Einstellungen:
//   • App-Theme  ('normal' | 'soeder')  – ganzes Erscheinungsbild, data-app-theme
//   • Modus      ('dark'   | 'light')   – nur innerhalb von 'normal' relevant
//   • Akzent     (Hex-Farbe)            – nur innerhalb von 'normal' relevant
// Die Söder-Laufzeit (schwebende Zitate + Maskottchen) lebt in soeder.js und
// wird hier nur an-/abgeschaltet.

const APP_THEMES = ['normal', 'soeder'];

function loadTheme() {
  // Söder ist der Standard für alle. localStorage dient nur als schneller Cache,
  // die verbindliche Wahrheit (auch die Freischaltung) liefert der Server über
  // /api/me → syncThemeState() (siehe profile.js).
  const savedApp    = localStorage.getItem('servus-app-theme') || 'soeder';
  const savedMode   = localStorage.getItem('servus-theme')     || 'dark';
  const savedAccent = localStorage.getItem('servus-accent')    || '#5c6fff';

  // Modus + Akzent zuerst setzen, damit beim Wechsel auf 'normal' alles stimmt.
  applyTheme(savedMode);
  applyAccent(savedAccent);
  applyAppTheme(savedApp);
}

// Server-Status übernehmen (App-Theme + Freischaltung). Wird nach /api/me
// aufgerufen und ist die verbindliche Quelle.
function syncThemeState(state) {
  if (!state) return;
  if (typeof state.theme_unlocked === 'boolean') {
    localStorage.setItem('servus-theme-unlocked', state.theme_unlocked ? '1' : '0');
  }
  if (typeof state.theme_unlock_cost === 'number') {
    localStorage.setItem('servus-theme-unlock-cost', String(state.theme_unlock_cost));
  }
  applyAppTheme(state.app_theme || 'soeder');
}

function isThemeUnlocked() {
  return localStorage.getItem('servus-theme-unlocked') === '1';
}

function getThemeUnlockCost() {
  return Number(localStorage.getItem('servus-theme-unlock-cost')) || 15;
}

// ── App-Theme (normal / soeder) ─────────────────────────────────────
function applyAppTheme(name) {
  if (!APP_THEMES.includes(name)) name = 'normal';
  const root = document.documentElement;

  if (name === 'normal') {
    root.removeAttribute('data-app-theme');
    if (window.SoederTheme) window.SoederTheme.deactivate();
  } else {
    root.setAttribute('data-app-theme', name);
    if (name === 'soeder' && window.SoederTheme) window.SoederTheme.activate();
  }
  localStorage.setItem('servus-app-theme', name);
}

function getAppTheme() {
  return localStorage.getItem('servus-app-theme') || 'soeder';
}

// ── Hell/Dunkel-Modus ───────────────────────────────────────────────
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === 'light') {
    root.classList.add('light-mode');
  } else {
    root.classList.remove('light-mode');
  }
  localStorage.setItem('servus-theme', theme);
}

function applyAccent(color) {
  const root = document.documentElement;
  root.style.setProperty('--user-accent', color);
  // Das CSS greift die Akzentfarbe über :root[data-accent] ab – deshalb muss
  // das Attribut gesetzt sein, damit --user-accent überhaupt wirksam wird.
  root.setAttribute('data-accent', '');
  localStorage.setItem('servus-accent', color);
}

function toggleTheme() {
  const isLight = document.documentElement.classList.contains('light-mode');
  applyTheme(isLight ? 'dark' : 'light');
}

function getTheme() {
  return document.documentElement.classList.contains('light-mode') ? 'light' : 'dark';
}

function getAccent() {
  return getComputedStyle(document.documentElement).getPropertyValue('--user-accent').trim();
}

// Theme beim Laden anwenden
loadTheme();
