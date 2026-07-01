-- Revises: V5
-- Creation Date: 2026-07-01
-- Reason: Friendships + friend requests with a single pending intro message

-- A friendship row is created when someone sends a request. While it is
-- 'pending', the requester's single intro_message (max 2048 chars, enforced in
-- the app) is held here — the addressee can read it but cannot reply until they
-- accept, at which point the message is delivered into the DM chat. Declining a
-- request deletes the row, so only 'pending' and 'accepted' rows ever exist.
CREATE TABLE IF NOT EXISTS friendships (
    id            SERIAL PRIMARY KEY,
    requester_id  INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    addressee_id  INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'pending',   -- 'pending' | 'accepted'
    intro_message TEXT,                              -- single message while pending
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at  TIMESTAMP,
    CONSTRAINT friendships_distinct CHECK (requester_id <> addressee_id),
    UNIQUE (requester_id, addressee_id)
);

CREATE INDEX IF NOT EXISTS friendships_addressee_idx ON friendships (addressee_id, status);
CREATE INDEX IF NOT EXISTS friendships_requester_idx ON friendships (requester_id, status);
