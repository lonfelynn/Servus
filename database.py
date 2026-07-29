# database.py
import os
import glob
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

# Loads the variables from .env into os.environ
load_dotenv()

# ── Connection settings from environment variables ──────────
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Pool size (overridable via .env)
POOL_MIN_CONN = int(os.environ.get("DB_POOL_MIN", "1"))
POOL_MAX_CONN = int(os.environ.get("DB_POOL_MAX", "10"))

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "sql")

# The single, application-wide connection pool.
_pool = None


# ── Pool lifecycle ──────────────────────────────────────────
def init_pool():
    """
    Creates the global connection pool. Idempotent – calling it more
    than once returns the existing pool. ThreadedConnectionPool is used
    because Flask-SocketIO serves requests from multiple threads.
    """
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            POOL_MIN_CONN,
            POOL_MAX_CONN,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            # Every cursor returns dict-like rows (row["username"]).
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


def get_pool():
    """Returns the pool, creating it lazily on first use."""
    if _pool is None:
        init_pool()
    return _pool


def close_pool():
    """Closes every connection in the pool. Call once on shutdown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_connection():
    """
    Borrows a connection from the pool and hands it back automatically.

    Commits on success, rolls back on error, and always returns the
    connection to the pool (it is NOT physically closed).

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
            return cursor.fetchone()
    """
    pool = get_pool()
    connection = pool.getconn()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)


# ── Migrations ──────────────────────────────────────────────
def _migration_order(path):
    """Sort key for migration files: 2.sql must run before 10.sql.

    Files whose name does not start with a number keep working — they sort
    after the numbered ones, by name.
    """
    name = os.path.basename(path)
    number = name.split(".", 1)[0]
    return (0, int(number), name) if number.isdigit() else (1, 0, name)


def run_migrations():
    """
    Applies every *.sql file in the sql/ folder exactly once, ordered by the
    number in the filename. Applied files are recorded in the schema_migrations
    table, so re-running is safe and only new files get executed.
    """
    pool = get_pool()
    connection = pool.getconn()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()

        cursor.execute("SELECT filename FROM schema_migrations")
        applied = {row["filename"] for row in cursor.fetchall()}

        # Numerically by the filename prefix, not alphabetically: plain sorting
        # would put 10.sql before 2.sql and blow up on a fresh database.
        files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")),
                       key=_migration_order)
        for path in files:
            name = os.path.basename(path)
            if name in applied:
                continue

            with open(path, "r", encoding="utf-8") as handle:
                sql = handle.read()

            cursor.execute(sql)
            cursor.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (name,)
            )
            connection.commit()  # one transaction per migration
            print(f"[migrations] applied {name}")
    except Exception:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)
