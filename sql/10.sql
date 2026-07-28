-- Revises: V9
-- Creation Date: 2026-07-28
-- Reason: Ende-zu-Ende-Verschlüsselung (E2EE)
--   Der Server speichert nur noch Chiffretext und verpackte Schlüssel — er
--   besitzt zu keinem Zeitpunkt Klartext oder einen entpackbaren Schlüssel.
--
--   users.public_key   – RSA-OAEP-2048 SPKI, base64. Öffentlich, im Klartext.
--   users.private_key  – der zugehörige PKCS#8-Schlüssel, AES-GCM-verpackt mit
--                        einem aus dem Passwort abgeleiteten Schlüssel
--                        (PBKDF2). Ohne das Passwort wertlos.
--   users.key_salt     – PBKDF2-Salt, base64.
--   chat_keys          – der AES-GCM-256-Chatschlüssel, einmal pro Mitglied mit
--                        dessen öffentlichem Schlüssel verpackt.
ALTER TABLE users ADD COLUMN IF NOT EXISTS public_key  TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS private_key TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS key_salt    TEXT;

CREATE TABLE IF NOT EXISTS chat_keys (
    chat_id     INTEGER NOT NULL REFERENCES chats (id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    wrapped_key TEXT    NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_id)
);
