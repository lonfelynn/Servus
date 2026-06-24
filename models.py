# models.py
import bcrypt
import psycopg2
from database import get_connection

# ── Constants ──────────────────────────────────────────────
XP_PER_MESSAGE = 10
XP_PER_LEVEL   = 100


# ── Password helpers ───────────────────────────────────────
def hash_password(plain_text_password: str) -> str:
    password_bytes = plain_text_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def check_password(plain_text_password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_text_password.encode("utf-8"),
        stored_hash.encode("utf-8")
    )


# ── Users ──────────────────────────────────────────────────
def create_user(username: str, plain_text_password: str) -> bool:
    """Creates a new user. Returns False if the username is already taken."""
    password_hash = hash_password(plain_text_password)
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash)
            )
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except Exception:
        return False


def get_user_by_username(username: str):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()


def get_all_users(exclude_id: "int | None" = None):
    """Returns all users (id, username, level, xp), optionally excluding one id."""
    with get_connection() as connection:
        cursor = connection.cursor()
        if exclude_id is None:
            cursor.execute(
                "SELECT id, username, level, xp FROM users ORDER BY username"
            )
        else:
            cursor.execute(
                "SELECT id, username, level, xp FROM users "
                "WHERE id <> %s ORDER BY username",
                (exclude_id,)
            )
        return cursor.fetchall()


# ── Messages ───────────────────────────────────────────────
def save_message(sender_id: int, receiver_id: int, content: str):
    """Stores a message and returns the created row (incl. id and sent_at)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO messages (sender_id, receiver_id, content) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, sender_id, receiver_id, content, sent_at",
            (sender_id, receiver_id, content)
        )
        return cursor.fetchone()


def get_conversation(user_a: int, user_b: int):
    """Returns all messages exchanged between two users, oldest first."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, sender_id, receiver_id, content, sent_at
            FROM messages
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY sent_at ASC
            """,
            (user_a, user_b, user_b, user_a)
        )
        return cursor.fetchall()


def add_message_xp(user_id: int):
    """Awards XP for sending a message and recalculates the level."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET xp = xp + %s WHERE id = %s RETURNING xp",
            (XP_PER_MESSAGE, user_id)
        )
        new_xp = cursor.fetchone()["xp"]
        new_level = new_xp // XP_PER_LEVEL + 1
        cursor.execute(
            "UPDATE users SET level = %s WHERE id = %s",
            (new_level, user_id)
        )
        return {"xp": new_xp, "level": new_level}

# ── Notifications ──────────────────────────────────────────
def create_notification(recipient_id: int, sender_id: int, message_id: int):
    """Creates a notification for a new incoming message.
    Returns the created row including id and created_at.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO notifications (recipient_id, sender_id, message_id) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, recipient_id, sender_id, message_id, is_read, created_at",
            (recipient_id, sender_id, message_id)
        )
        return cursor.fetchone()


def get_unread_notifications(user_id: int):
    """Returns all unread notifications for a user, newest first.
    Joins with users so the sender's username is included in each row.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT n.id, n.sender_id, n.message_id, n.created_at,
                   u.username AS sender_name
            FROM   notifications n
            JOIN   users u ON u.id = n.sender_id
            WHERE  n.recipient_id = %s AND n.is_read = FALSE
            ORDER  BY n.created_at DESC
            """,
            (user_id,)
        )
        return cursor.fetchall()


def mark_notifications_read_by_sender(recipient_id: int, sender_id: int):
    """Marks all unread notifications from a specific sender as read.
    The recipient_id check ensures users can only mark their own notifications.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE notifications "
            "SET    is_read = TRUE "
            "WHERE  recipient_id = %s AND sender_id = %s AND is_read = FALSE",
            (recipient_id, sender_id)
        )


def mark_all_notifications_read(user_id: int):
    """Marks every unread notification for the given user as read."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = TRUE "
            "WHERE  recipient_id = %s AND is_read = FALSE",
            (user_id,)
        )
