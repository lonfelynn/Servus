-- Revises: V7
-- Creation Date: 2026-07-08
-- Reason: Add profile and personalization fields to users
--   avatar_url   – data-URL / URL of the user's profile picture
--   status_text  – free-text status (max 128 chars, enforced client-side)
--   presence     – online | away | busy | offline
--   accent_color – per-user accent colour for the UI
--   theme_mode   – dark | light
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url   TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS status_text  TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS presence     TEXT DEFAULT 'offline';
ALTER TABLE users ADD COLUMN IF NOT EXISTS accent_color TEXT DEFAULT '#5c6fff';
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme_mode   TEXT DEFAULT 'dark';
