-- Revises: V1
-- Creation Date: 2026-06-24
-- Reason: Add notifications table for new-message alerts

CREATE TABLE IF NOT EXISTS notifications (
    id           SERIAL PRIMARY KEY,
    recipient_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    sender_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    message_id   INTEGER NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    is_read      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS notifications_recipient_unread_idx
    ON notifications (recipient_id, is_read);
