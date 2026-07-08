// theme.js – Theme- und Akzentfarben-Verwaltung
// Selbstständig: liest die gespeicherten Werte aus localStorage und wendet sie
// beim Laden an. Wird vor chat.js/profile.js eingebunden, damit applyTheme /
// applyAccent global verfügbar sind.

// Theme aus localStorage laden und anwenden
function loadTheme() {
  const savedTheme  = localStorage.getItem('servus-theme')  || 'dark';
  const savedAccent = localStorage.getItem('servus-accent') || '#5c6fff';

  applyTheme(savedTheme);
  applyAccent(savedAccent);
}

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
