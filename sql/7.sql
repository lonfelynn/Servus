-- Revises: V7
-- Creation Date: 2026-07-08
-- Reason: Add support for file attachments in chat messages
ALTER TABLE chat_messages ADD COLUMN file_url TEXT;
ALTER TABLE chat_messages ADD COLUMN file_type TEXT;
ALTER TABLE chat_messages ADD COLUMN file_name TEXT;
