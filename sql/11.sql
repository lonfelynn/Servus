-- Revises: V10
-- Creation Date: 2026-07-28
-- Reason: Systemhinweise im Chat (Mitglied hinzugefügt/entfernt, umbenannt)
--   chat_messages.kind = NULL  → normale Nachricht (Chiffretext)
--   chat_messages.kind = 'system' → vom Server erzeugter Hinweis. Diese Zeilen
--   sind bewusst Klartext: der Server besitzt keinen Chatschlüssel und könnte
--   sie gar nicht verschlüsseln. Sie enthalten nur Nutzernamen und den
--   Chatnamen — beides kennt der Server ohnehin.
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS kind TEXT;
