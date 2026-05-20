# database.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "messenger.db")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            level         INTEGER NOT NULL DEFAULT 1,
            xp            INTEGER NOT NULL DEFAULT 0,
            created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id   INTEGER NOT NULL REFERENCES users(id),
            receiver_id INTEGER NOT NULL REFERENCES users(id),
            content     TEXT    NOT NULL,
            sent_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()
