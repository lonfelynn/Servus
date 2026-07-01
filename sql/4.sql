-- Revises: V4
-- Creation Date: 2026-07-01
-- Reason: Track edits on chat messages

-- NULL means the message was never edited. Set to the current timestamp by
-- the UPDATE in update_chat_message() whenever a message is changed.
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
