# models.py
import bcrypt
from database import get_connection

# ── Constants ──────────────────────────────────────────────
XP_PER_MESSAGE      = 10
XP_FAST_REPLY_BONUS = 5
XP_PER_LEVEL        = 100


def hash_password(plain_text_password: str) -> str:
    password_bytes = plain_text_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def check_password(plain_text_password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_text_password.encode("utf-8"),
        stored_hash.encode("utf-8")
    )


def create_user(username: str, plain_text_password: str) -> bool:
    password_hash = hash_password(plain_text_password)
    try:
        connection = get_connection()
        connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        connection.commit()
        return True
    except Exception:
        return False
    finally:
        connection.close()


def get_user_by_username(username: str):
    connection = get_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    connection.close()
    return user


def get_user_by_id(user_id: int):
    connection = get_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    connection.close()
    return user
