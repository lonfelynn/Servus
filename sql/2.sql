-- Revises: V2
-- Creation Date: 2026-07-01
-- Reason: Unified chat model — every chat (incl. 1-on-1 DMs) is a chat with members

-- A chat is a conversation between 2..n users. A 1-on-1 DM is simply a chat
-- with exactly two members. `name` is NULL by default; the display name is then
-- derived from the members. Once someone renames the chat, `name` is set.
CREATE TABLE IF NOT EXISTS chats (
    id         SERIAL PRIMARY KEY,
    name       TEXT,                                       -- NULL = aus Mitgliedern ableiten
    created_by INTEGER REFERENCES users (id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Which users belong to which chat. The composite PK guarantees a user can be
-- in a chat only once.
CREATE TABLE IF NOT EXISTS chat_members (
    chat_id   INTEGER NOT NULL REFERENCES chats (id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS chat_members_user_idx ON chat_members (user_id);

-- Messages now reference a chat instead of a single receiver.
CREATE TABLE IF NOT EXISTS chat_messages (
    id        SERIAL PRIMARY KEY,
    chat_id   INTEGER NOT NULL REFERENCES chats (id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    content   TEXT NOT NULL,
    sent_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS chat_messages_chat_idx ON chat_messages (chat_id, sent_at);
