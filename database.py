# database.py
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Loads the variables from .env into os.environ
load_dotenv()

# ── Connection settings from environment variables ──────────
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")


def get_connection():
    """
    Opens and returns a connection to the PostgreSQL database.
    RealDictCursor allows accessing columns by name (row["username"])
    instead of by index (row[0]) – same behaviour as before.
    """
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    connection.cursor_factory = psycopg2.extras.RealDictCursor
    return connection


def init_db():
    """
    Creates all tables if they do not exist yet.
    Safe to call every time the app starts.
    Note: PostgreSQL uses SERIAL instead of AUTOINCREMENT,
    and TIMESTAMP instead of DATETIME.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            level         INTEGER NOT NULL DEFAULT 1,
            xp            INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          SERIAL PRIMARY KEY,
            sender_id   INTEGER NOT NULL REFERENCES users(id),
            receiver_id INTEGER NOT NULL REFERENCES users(id),
            content     TEXT    NOT NULL,
            sent_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    cursor.close()
    connection.close()
