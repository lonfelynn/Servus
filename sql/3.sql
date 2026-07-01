-- Revises: V3
-- Creation Date: 2026-07-01
-- Reason: Per-chat unread notifications for the unified chat model

-- One row per unread message per recipient. Unread counts are aggregated per
-- chat so the sidebar can show a badge on each chat.
CREATE TABLE IF NOT EXISTS chat_notifications (
    id           SERIAL PRIMARY KEY,
    recipient_id INTEGER NOT NULL REFERENCES users (id)          ON DELETE CASCADE,
    chat_id      INTEGER NOT NULL REFERENCES chats (id)          ON DELETE CASCADE,
    message_id   INTEGER NOT NULL REFERENCES chat_messages (id)  ON DELETE CASCADE,
    is_read      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS chat_notifications_recipient_unread_idx
    ON chat_notifications (recipient_id, is_read);
