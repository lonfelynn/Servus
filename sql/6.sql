-- Revises: V6
-- Creation Date: 2026-07-06
-- Reason: Soft-delete support for chat messages
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
