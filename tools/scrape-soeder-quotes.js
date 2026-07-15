// ════════════════════════════════════════════════════════════════════
// scrape-soeder-quotes.js — EINMALIGES Snapshot-Werkzeug (Browser-Konsole)
// --------------------------------------------------------------------
// Die Quelle (zitatsuchmaschine.informatik.hu-berlin.de) steckt hinter der
// Anubis-Bot-Sperre, die ein Server-Fetch nicht überwindet. DEIN Browser hat
// die Sperre aber bereits passiert. Darum wird der Snapshot hier, direkt in
// der geöffneten Seite, gezogen — kein Scraping vom Server aus.
//
// So geht's:
//   1. Öffne im Browser:
//      https://zitatsuchmaschine.informatik.hu-berlin.de/quotee/Markus%20Söder?order=relevance
//   2. Warte, bis die Zitate sichtbar sind (Anubis-Check durch).
//   3. DevTools öffnen (F12) → Reiter „Console" → dieses ganze Skript einfügen,
//      Enter drücken. Es sammelt die Zitate der aktuellen Seite.
//   4. Für mehr Zitate: zur nächsten Seite blättern und Schritt 3 wiederholen —
//      es sammelt über Seiten hinweg an (Speicherung in localStorage).
//   5. Wenn genug beisammen: in der Konsole  saveSoederQuotes()  ausführen.
//      Es lädt „soeder_quotes.json" herunter → diese Datei nach data/ legen,
//      die vorhandene ersetzen.
//
// Passt der CSS-Selektor nicht (0 gefunden)? SELECTOR unten anpassen — ein
// Rechtsklick auf ein Zitat → „Untersuchen" verrät die richtige Klasse.
// ════════════════════════════════════════════════════════════════════
(function () {
  "use strict";

  // Kandidaten-Selektoren für ein einzelnes Zitat. Der erste, der etwas findet,
  // gewinnt. Bei Bedarf oben einen passenden Selektor ergänzen.
  const SELECTORS = [
    "[class*='quote'] [class*='text']",
    "[class*='quote']",
    "blockquote",
    "q",
    ".zitat",
  ];

  const STORE_KEY = "soeder_quotes_snapshot";
  const MIN_LEN = 6;    // zu kurze Fragmente ignorieren
  const MAX_LEN = 400;  // offensichtlich keine Zitate mehr

  function collect() {
    let nodes = [];
    for (const sel of SELECTORS) {
      nodes = Array.from(document.querySelectorAll(sel));
      if (nodes.length) {
        console.log(`[Söder] Selektor "${sel}" → ${nodes.length} Treffer.`);
        break;
      }
    }
    if (!nodes.length) {
      console.warn("[Söder] Nichts gefunden. Passe SELECTORS oben im Skript an.");
      return [];
    }

    const found = [];
    for (const n of nodes) {
      let t = (n.textContent || "").replace(/\s+/g, " ").trim();
      t = t.replace(/^[„"»]+/, "").replace(/["«"]+$/, "").trim();
      if (t.length >= MIN_LEN && t.length <= MAX_LEN) found.push(t);
    }
    return found;
  }

  // Über Seiten hinweg ansammeln + deduplizieren.
  const prev = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
  const merged = Array.from(new Set([...prev, ...collect()]));
  localStorage.setItem(STORE_KEY, JSON.stringify(merged));
  console.log(`[Söder] Insgesamt gesammelt: ${merged.length} Zitate.`);

  // Download-Helfer global bereitstellen.
  window.saveSoederQuotes = function () {
    const data = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "soeder_quotes.json";
    a.click();
    URL.revokeObjectURL(a.href);
    console.log(`[Söder] ${data.length} Zitate heruntergeladen → data/soeder_quotes.json ersetzen.`);
  };

  // Zum Zurücksetzen der Sammlung:  localStorage.removeItem("soeder_quotes_snapshot")
  console.log('[Söder] Fertig. Zum Speichern:  saveSoederQuotes()');
})();
