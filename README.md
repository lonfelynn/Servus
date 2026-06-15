# Servus

A bavarian school project. Finally a messenger made by students for students.

## Features (base layer)

- Registration / login / logout (passwords hashed with bcrypt)
- Contact list of all registered users
- 1-on-1 chat with real-time messages via Socket.IO
- Message history stored in PostgreSQL
- Simple XP / level system (you gain XP for every message you send)

The whole interface is in German.

## Setup

Dependencies are managed with [Poetry](https://python-poetry.org/).

1. **Install the dependencies**

   ```bash
   poetry install
   ```

2. **Set up PostgreSQL**

   Make sure a PostgreSQL server is running and create an empty database, e.g.:

   ```sql
   CREATE ROLE servus WITH LOGIN PASSWORD 'your_password';
   CREATE DATABASE servus OWNER servus;
   ```

3. **Configure environment variables**

   Copy `.env.example` to `.env` and fill in your database credentials:

   ```bash
   cp .env.example .env
   ```

4. **Run the app**

   ```bash
   poetry run python app.py
   ```

   On start the app opens a connection pool and runs the database
   migrations (`sql/*.sql`) automatically, so the tables are created on
   first launch. Open <http://localhost:5000> in your browser.

## Database

- **Connection pool** – the whole app shares one `ThreadedConnectionPool`
  (see `database.py`). Use it via the context manager, which borrows a
  connection and returns it to the pool automatically:

  ```python
  from database import get_connection

  with get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute("SELECT ...")
      rows = cursor.fetchall()
  ```

- **Migrations** – every `*.sql` file in the `sql/` folder is applied once,
  in filename order, and recorded in the `schema_migrations` table. To add a
  schema change, drop a new file next to the existing one (e.g. `sql/1.sql`)
  and restart the app — only new files are executed.

## Testing the chat

Register two accounts (open a second browser or a private window for the
second user), then select the other user from the contact list and send
messages back and forth — they appear in real time.

## Project structure

| File / folder        | Purpose                                             |
| -------------------- | --------------------------------------------------- |
| `app.py`             | Flask app, routes, JSON API and Socket.IO handlers  |
| `auth.py`            | Registration / login / logout blueprint             |
| `models.py`          | Database access (users, messages, XP)               |
| `database.py`        | PostgreSQL connection + table creation              |
| `templates/`         | `login.html`, `register.html`, `chat.html`          |
| `static/css/`        | Stylesheets (`style.css` for auth, `chat.css`)      |
| `static/js/`         | Page scripts (`login.js`, `register.js`, `chat.js`) |
