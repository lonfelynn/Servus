# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Servus is a school-project real-time messenger (Flask + Flask-SocketIO + PostgreSQL).
**The entire user-facing UI is in German** — keep all user-visible strings (templates,
JS messages, error texts) in German. Code, comments, and identifiers are English.

## Commands

Dependencies are managed with **Poetry** (there is no `requirements.txt`).

```bash
poetry install                 # install dependencies
cp .env.example .env           # then fill in DB credentials + SECRET_KEY
poetry run python app.py       # runs migrations, then serves on http://localhost:5000
```

Running `app.py` calls `init_pool()` and `run_migrations()` before `socketio.run`, so the
DB pool is opened and all `sql/*.sql` files are applied automatically on start.

Prerequisites: a running PostgreSQL server and an existing database (e.g. `CREATE DATABASE servus;`).

There is **no test suite, linter, or build step** configured. On Windows the `python`
command may be the Microsoft Store stub; use the `py` launcher (e.g. `py -m py_compile app.py`)
to syntax-check.

## Architecture

Server-rendered Jinja templates + vanilla JS on the frontend; Flask blueprint for auth,
Socket.IO for live messaging, and a pooled psycopg2 layer for PostgreSQL.

- **`app.py`** — app factory-less entrypoint. Holds page routes (`/`, `/chat`), the JSON
  API (`/api/me`, `/api/users`, `/api/messages/<id>`), and the Socket.IO handlers. Registers
  the auth blueprint and the `close_pool` atexit hook.
- **`auth.py`** — `auth_bp` blueprint: `/register`, `/login`, `/logout`. POST bodies are JSON;
  responses are `{ok, error}` / `{ok, redirect}`. On login it sets `session["user_id"]` and
  `session["username"]` — these two session keys are the contract the rest of the app relies on.
- **`models.py`** — all SQL lives here. Password hashing (bcrypt), users, messages, and the
  XP/level system.
- **`database.py`** — the connection pool and the migration runner (see below).
- **`templates/`** + **`static/css/`** + **`static/js/`** — one CSS and one JS file per page.

### Database access — the connection pool

The whole app shares **one** `ThreadedConnectionPool` (threaded because Socket.IO serves from
multiple threads). **Never** call `psycopg2.connect` directly and **never** `.close()` a borrowed
connection. Always go through the `get_connection()` context manager, which borrows from the pool,
**commits on success / rolls back on exception**, and returns the connection to the pool:

```python
from database import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT ... WHERE id = %s", (user_id,))
    return cursor.fetchone()
```

- `cursor_factory=RealDictCursor` is set at the pool level, so **rows are dict-like**
  (`row["username"]`, not `row[0]`).
- Use `%s` placeholders (psycopg2), never `?` (that is SQLite and was the original bug).

### Migrations

`run_migrations()` applies every `sql/*.sql` file **once, in filename order**, each in its own
transaction, and records applied files in the `schema_migrations` table. To change the schema,
add a new file (`sql/1.sql`, `sql/2.sql`, …) — do not edit already-applied files. SQL must be
**PostgreSQL dialect** (use `SERIAL` for auto-increment PKs; `INTEGER PRIMARY KEY` does *not*
auto-increment in Postgres).

### Real-time messaging flow

1. On Socket.IO `connect`, the user joins a private room `user_<user_id>` (read from the Flask session).
2. The client emits `send_message` `{to, content}`. The server saves it, awards XP via
   `add_message_xp`, and emits `new_message` to **both** the receiver's room and the sender's
   room (so the sender's own tabs render it too — there is a single render path).
3. The client computes the conversation partner of an incoming `new_message`
   (`sender_id === ME ? receiver_id : sender_id`) and only appends it if that chat is open.

**Serialization gotcha:** psycopg2 returns `sent_at` as a Python `datetime`, which neither
`emit` nor `jsonify` can serialize cleanly. Always convert message rows through
`message_to_dict()` in `app.py` (which calls `.isoformat()`) before sending over Socket.IO or the API.

### Frontend conventions

- Auth pages (`login.html`, `register.html`) POST JSON via fetch and redirect on `{ok:true}`.
- `chat.html` injects server values with a single inline `<script>` (`window.SERVUS = {me, myName}`)
  because those need Jinja; `chat.js` then reads them. Load order matters: data block →
  Socket.IO CDN → `chat.js`.
- All dynamic text rendered into the DOM goes through `escapeHtml()` in `chat.js`.

## Notes

- Pyright/IDE warnings about unresolved `flask`/`psycopg2`/`dotenv`, the `room=` kwarg on `emit`,
  and dict subscripting of cursor rows are **false positives** (missing stubs / analysis env), not bugs.
- Secrets live in `.env` (git-ignored); `.env.example` is the template. `SECRET_KEY` signs Flask sessions.
