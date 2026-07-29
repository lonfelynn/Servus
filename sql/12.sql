-- Revises: V11
-- Creation Date: 2026-07-29
-- Reason: XP-Slotmaschine („Servus Slots")
--   Jeder Spin wird protokolliert, damit die Historie und die Statistik im
--   Casino-Modal nicht aus der Sitzung, sondern aus der Datenbank kommen —
--   und damit nachvollziehbar bleibt, wohin die XP eines Nutzers geflossen
--   sind. Die XP selbst stehen weiterhin ausschließlich in users.xp.
--     bet      – Einsatz in XP
--     payout   – Bruttoauszahlung in XP (0 = verloren, = bet → Einsatz zurück)
--     symbols  – die drei Walzensymbole als 'bell,star,seven'
--     xp_after – XP-Stand direkt nach dem Spin (für die Historie)
CREATE TABLE IF NOT EXISTS slot_spins (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    bet        INTEGER NOT NULL,
    payout     INTEGER NOT NULL,
    symbols    TEXT    NOT NULL,
    xp_after   INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS slot_spins_user_idx ON slot_spins (user_id, created_at DESC);
