-- Revises: V8
-- Creation Date: 2026-07-15
-- Reason: App-Theme + „Söder"-Freischaltung
--   app_theme      – gewähltes App-Theme ('soeder' ist Standard für alle)
--   theme_unlocked – TRUE, sobald der Nutzer sich per Level-Kosten aus dem
--                    Söder-Theme „freigekauft" hat (dann frei umschaltbar)
ALTER TABLE users ADD COLUMN IF NOT EXISTS app_theme      TEXT    DEFAULT 'soeder';
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_unlocked BOOLEAN DEFAULT FALSE;
