-- Revises: V0
-- Creation Date: 2026-05-20 08:44
-- Reason: Initial migrations

-- Account table that stores all users with unique usernames, also stores leveling levels and xp
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS account_username_idx ON account (username);

-- Table for all messages including sender and receiver ids
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    sender_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
    receiver_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)

