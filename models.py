# models.py
import bcrypt
import psycopg2
import slots
from database import get_connection

# ── Constants ──────────────────────────────────────────────
XP_PER_MESSAGE = 10
BASE_XP = 100
XP_GROWTH = 1.5


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


# Profile/settings columns a user is allowed to update (added in sql/7.sql).
_PROFILE_COLUMNS = ("status_text", "presence", "avatar_url", "accent_color", "theme_mode")


def update_user_profile(user_id: int, **fields):
    """Updates the given profile/settings columns for a user.

    Only whitelisted columns in `_PROFILE_COLUMNS` are written, and only those
    passed with a non-None value — so callers can send just the fields that
    changed. Returns the updated row (or the current row if nothing changed).
    """
    updates = [(col, val) for col, val in fields.items()
               if col in _PROFILE_COLUMNS and val is not None]
    if not updates:
        return get_user_by_id(user_id)

    set_clause = ", ".join(f"{col} = %s" for col, _ in updates)
    params = [val for _, val in updates]
    params.append(user_id)
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s RETURNING *", params
        )
        return cursor.fetchone()


def get_all_users(exclude_id: "int | None" = None):
    """Returns all users (id, username, level, xp, avatar_url, status_text, presence), optionally excluding one id."""
    with get_connection() as connection:
        cursor = connection.cursor()
        if exclude_id is None:
            cursor.execute(
                "SELECT id, username, level, xp, avatar_url, status_text, presence FROM users ORDER BY username"
            )
        else:
            cursor.execute(
                "SELECT id, username, level, xp, avatar_url, status_text, presence FROM users "
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
            "RETURNING id, chat_id, sender_id, content, sent_at, edited_at, is_deleted",
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
def calculate_level(total_xp: int) -> int:
    
    level = 1
    xp_required = BASE_XP
    remaining_xp = total_xp

    while remaining_xp >= xp_required:
        remaining_xp -= xp_required
        level += 1
        xp_required = int(xp_required * XP_GROWTH)

    return level

def xp_for_level(level: int) -> int:
    """
    Returns the total XP required to reach the given level.
    Level 1 requires 0 XP.
    """
    if level <= 1:
        return 0

    total = 0
    xp_required = BASE_XP

    for _ in range(2, level + 1):
        total += xp_required
        xp_required = int(xp_required * XP_GROWTH)

    return total

def spend_levels(user_id: int, levels: int):
    if levels <= 0:
        raise ValueError("Levels must be greater than 0.")

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT xp, level FROM users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        current_xp = user["xp"]
        current_level = calculate_level(current_xp)
        if user is None:
            raise ValueError("User not found.")

        current_level = user["level"]

        if current_level <= levels:
            return {
                "success": False,
                "xp": user["xp"],
                "level": current_level
            }

        xp_cost = xp_for_level(current_level) - xp_for_level(current_level - levels)
        new_xp = current_xp - xp_cost
        new_level = calculate_level(new_xp)

        cursor.execute(
            """
            UPDATE users
            SET xp = %s,
                level = %s
            WHERE id = %s
            """,
            (new_xp, new_level, user_id)
        )

        return {
            "success": True,
            "xp": new_xp,
            "level": new_level,
            "spent_levels": levels
        }

# ── App-Theme / „Söder"-Freischaltung ──────────────────────
# Söder ist das Standard-Theme für alle. Wer umschalten möchte, kauft sich
# einmalig für THEME_UNLOCK_COST Level frei (dauerhaft, via theme_unlocked).
THEME_UNLOCK_COST = 15
_ALLOWED_APP_THEMES = ("soeder", "normal")


def get_theme_state(user):
    """Baut den Theme-Status aus einer bereits geladenen User-Zeile."""
    return {
        "app_theme": user.get("app_theme") or "soeder",
        "theme_unlocked": bool(user.get("theme_unlocked")),
        "theme_unlock_cost": THEME_UNLOCK_COST,
    }


def set_app_theme(user_id: int, theme: str):
    """Setzt das App-Theme. 'normal' ist nur nach der Freischaltung erlaubt."""
    if theme not in _ALLOWED_APP_THEMES:
        return {"ok": False, "error": "Unbekanntes Theme."}

    user = get_user_by_id(user_id)
    if user is None:
        return {"ok": False, "error": "Nutzer nicht gefunden."}
    if theme != "soeder" and not user.get("theme_unlocked"):
        return {"ok": False, "error": "Dieses Theme ist noch gesperrt."}

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET app_theme = %s WHERE id = %s", (theme, user_id)
        )
    return {"ok": True, "app_theme": theme}


def unlock_soeder_theme(user_id: int):
    """„Kauft" den Nutzer für THEME_UNLOCK_COST Level aus dem Söder-Theme frei.

    Nutzt dieselbe XP-erhaltende Rechnung wie spend_levels (xp_for_level /
    calculate_level), erlaubt aber die Freischaltung bereits ab genau
    THEME_UNLOCK_COST Leveln. Danach ist theme_unlocked dauerhaft TRUE und das
    Theme wird direkt auf 'normal' umgestellt.
    """
    user = get_user_by_id(user_id)
    if user is None:
        return {"ok": False, "error": "Nutzer nicht gefunden."}

    if user.get("theme_unlocked"):
        # Schon freigeschaltet – nichts abbuchen.
        return {"ok": True, "already": True, "level": user["level"],
                "xp": user["xp"], "cost": THEME_UNLOCK_COST}

    current_level = user["level"]
    if current_level < THEME_UNLOCK_COST:
        return {"ok": False, "error": f"Du brauchst mindestens Level {THEME_UNLOCK_COST}.",
                "level": current_level, "xp": user["xp"], "cost": THEME_UNLOCK_COST}

    # Level-Kosten XP-erhaltend abbuchen (Fortschritt im Rest-Level bleibt).
    target_level = current_level - THEME_UNLOCK_COST
    xp_cost = xp_for_level(current_level) - xp_for_level(target_level)
    new_xp = max(0, user["xp"] - xp_cost)
    new_level = calculate_level(new_xp)

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET xp = %s, level = %s, theme_unlocked = TRUE, app_theme = 'normal' "
            "WHERE id = %s",
            (new_xp, new_level, user_id)
        )
    return {"ok": True, "level": new_level, "xp": new_xp, "cost": THEME_UNLOCK_COST}
def add_xp(user_id: int, amount: int):
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE users SET xp = xp + %s WHERE id = %s RETURNING xp",
            (amount, user_id)
        )

        new_xp = cursor.fetchone()["xp"]
        new_level = calculate_level(new_xp)

        cursor.execute(
            "UPDATE users SET level = %s WHERE id = %s",
            (new_level, user_id)
        )

        return {"xp": new_xp, "level": new_level}

def add_message_xp(user_id: int):
    return add_xp(user_id, XP_PER_MESSAGE)

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


# ── Chats (unified model — every chat, incl. 1-on-1 DMs, lives here) ─────
def _display_name(name, members, viewer_id):
    """Derives what a chat is called for a given viewer.

    If the chat has an explicit `name`, that wins. Otherwise the name is built
    from the *other* members' usernames (so a 1-on-1 chat shows the partner's
    name, a group shows "Bob & Carl"). Falls back to the viewer's own name for
    a chat that only contains themselves.
    """
    if name:
        return name
    others = [m["username"] for m in members if m["id"] != viewer_id]
    names = others or [m["username"] for m in members]
    if len(names) <= 2:
        return " & ".join(names)
    return ", ".join(names[:-1]) + " & " + names[-1]


def find_or_create_chat(member_ids, created_by=None, name=None):
    """Returns the id of the chat whose members are *exactly* `member_ids`,
    creating it if none exists. This is the de-duplication guarantee: the same
    set of users can never have two separate chats.
    """
    ids = sorted(set(member_ids))
    with get_connection() as connection:
        cursor = connection.cursor()
        # A chat matches iff it has exactly len(ids) members and every one of
        # them is in `ids` — together that means the member sets are equal.
        cursor.execute(
            """
            SELECT chat_id
            FROM   chat_members
            GROUP  BY chat_id
            HAVING COUNT(*) = %s AND bool_and(user_id = ANY(%s))
            """,
            (len(ids), ids)
        )
        row = cursor.fetchone()
        if row:
            return row["chat_id"]

        cursor.execute(
            "INSERT INTO chats (name, created_by) VALUES (%s, %s) RETURNING id",
            (name, created_by)
        )
        chat_id = cursor.fetchone()["id"]
        for uid in ids:
            cursor.execute(
                "INSERT INTO chat_members (chat_id, user_id) VALUES (%s, %s)",
                (chat_id, uid)
            )
        if created_by is not None:
            if len(ids) == 2:
                add_xp(created_by, 50)
            else:
                add_xp(created_by, 75)
        return chat_id


def get_user_chat_ids(user_id: int):
    """Returns just the ids of every chat the user is a member of
    (used to join the Socket.IO rooms on connect)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT chat_id FROM chat_members WHERE user_id = %s",
            (user_id,)
        )
        return [row["chat_id"] for row in cursor.fetchall()]


def get_user_chats(user_id: int):
    """Returns every chat the user is in, each as a dict with its members,
    derived display name and group flag, ordered by most recent activity."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT c.id, c.name,
                   array_agg(u.id       ORDER BY u.username) AS member_ids,
                   array_agg(u.username ORDER BY u.username) AS member_names,
                   array_agg(u.avatar_url ORDER BY u.username) AS member_avatars,
                   array_agg(u.status_text ORDER BY u.username) AS member_statuses,
                   array_agg(u.presence ORDER BY u.username) AS member_presences,
                   (SELECT MAX(sent_at) FROM chat_messages m
                     WHERE m.chat_id = c.id) AS last_at,
                   (SELECT content FROM chat_messages m
                     WHERE m.chat_id = c.id
                     ORDER  BY m.sent_at DESC, m.id DESC
                     LIMIT  1) AS last_message
            FROM   chats c
            JOIN   chat_members cm ON cm.chat_id = c.id
            JOIN   users u         ON u.id = cm.user_id
            WHERE  c.id IN (SELECT chat_id FROM chat_members WHERE user_id = %s)
            GROUP  BY c.id, c.name
            ORDER  BY last_at DESC NULLS LAST, c.id DESC
            """,
            (user_id,)
        )
        chats = []
        for row in cursor.fetchall():
            members = [
                {"id": mid, "username": mname, "avatar_url": mavatar, "status_text": mstatus, "presence": mpresence}
                for mid, mname, mavatar, mstatus, mpresence in zip(row["member_ids"], row["member_names"], row["member_avatars"], row["member_statuses"], row["member_presences"])
            ]
            chats.append({
                "id": row["id"],
                "name": row["name"],
                "display_name": _display_name(row["name"], members, user_id),
                "members": members,
                "is_group": len(members) > 2,
                "last_message": row["last_message"],
            })
        return chats


def get_chat(chat_id: int, viewer_id: int):
    """Returns a single chat (same shape as an entry from get_user_chats),
    or None if it does not exist."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT c.id, c.name,
                   (SELECT content FROM chat_messages m
                     WHERE m.chat_id = c.id
                     ORDER  BY m.sent_at DESC, m.id DESC
                     LIMIT  1) AS last_message
            FROM   chats c WHERE c.id = %s
            """,
            (chat_id,)
        )
        chat = cursor.fetchone()
        if chat is None:
            return None
    members = get_chat_members(chat_id)
    return {
        "id": chat["id"],
        "name": chat["name"],
        "display_name": _display_name(chat["name"], members, viewer_id),
        "members": members,
        "is_group": len(members) > 2,
        "last_message": chat["last_message"],
    }


def get_chat_members(chat_id: int):
    """Returns the members of a chat as a list of {id, username, avatar_url, status_text, presence} dicts."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username, u.avatar_url, u.status_text, u.presence
            FROM   chat_members cm
            JOIN   users u ON u.id = cm.user_id
            WHERE  cm.chat_id = %s
            ORDER  BY u.username
            """,
            (chat_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def is_chat_member(chat_id: int, user_id: int) -> bool:
    """Whether the user belongs to the chat — the guard for every chat action."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT 1 FROM chat_members WHERE chat_id = %s AND user_id = %s",
            (chat_id, user_id)
        )
        return cursor.fetchone() is not None


def add_chat_member(chat_id: int, user_id: int):
    """Adds a user to a chat. Does nothing if they are already a member."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO chat_members (chat_id, user_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (chat_id, user_id)
        )


def remove_chat_member(chat_id: int, user_id: int):
    """Removes a user from a chat (also used when a user leaves)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM chat_members WHERE chat_id = %s AND user_id = %s",
            (chat_id, user_id)
        )


def rename_chat(chat_id: int, name: "str | None"):
    """Sets a chat's explicit name. Pass None/empty to fall back to the
    member-derived name again."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE chats SET name = %s WHERE id = %s",
            (name or None, chat_id)
        )


def save_chat_message(chat_id: int, sender_id: int, content: str, file_url: "str | None" = None, file_type: "str | None" = None, file_name: "str | None" = None, kind: "str | None" = None):
    """Stores a chat message and returns the created row.

    kind='system' marks a server-generated notice ("X hat Y hinzugefügt"), which
    is stored as plaintext — see sql/11.sql.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (chat_id, sender_id, content, file_url, file_type, file_name, kind) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, chat_id, sender_id, content, sent_at, file_url, file_type, file_name, edited_at, is_deleted, kind",
            (chat_id, sender_id, content, file_url, file_type, file_name, kind)
        )
        return cursor.fetchone()


def get_chat_conversation(chat_id: int):
    """Returns all messages in a chat, oldest first, incl. the sender's name and read status."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT m.id, m.chat_id, m.sender_id, m.content, m.sent_at, m.edited_at, m.is_deleted,
                    m.file_url, m.file_type, m.file_name, m.kind,
                   u.username AS sender_name,
                   (SELECT COUNT(*) FROM chat_notifications cn WHERE cn.message_id = m.id AND cn.is_read = TRUE) AS read_count,
                   (SELECT COUNT(*) FROM chat_members cm WHERE cm.chat_id = m.chat_id) - 1 AS expected_read_count
            FROM   chat_messages m
            JOIN   users u ON u.id = m.sender_id
            WHERE  m.chat_id = %s
            ORDER  BY m.sent_at ASC
            """,
            (chat_id,)
        )
        return cursor.fetchall()


# ── Chat notifications (unread badges per chat) ─────────────
def create_chat_notifications(chat_id: int, message_id: int, sender_id: int):
    """Marks a new message as unread for every chat member except the sender."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO chat_notifications (recipient_id, chat_id, message_id)
            SELECT user_id, %s, %s
            FROM   chat_members
            WHERE  chat_id = %s AND user_id <> %s
            """,
            (chat_id, message_id, chat_id, sender_id)
        )


def get_unread_chat_counts(user_id: int):
    """Returns [{chat_id, count}] — number of unread messages per chat."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT chat_id, COUNT(*) AS count
            FROM   chat_notifications
            WHERE  recipient_id = %s AND is_read = FALSE
            GROUP  BY chat_id
            """,
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def mark_chat_notifications_read(recipient_id: int, chat_id: int):
    """Marks every unread message in a chat as read for the given recipient.
    The recipient_id check ensures users only touch their own notifications."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE chat_notifications SET is_read = TRUE "
            "WHERE  recipient_id = %s AND chat_id = %s AND is_read = FALSE",
            (recipient_id, chat_id)
        )

# ── Message editing / deletion ─────────────────────────────
def update_chat_message(message_id: int, sender_id: int, new_content: str):
    """Updates the content of a message and records the edit timestamp.
    Only the original sender may edit their own message.
    Returns the updated row, or None if no row matched (wrong sender or id).
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE chat_messages
            SET    content   = %s,
                   edited_at = NOW()
            WHERE  id        = %s
              AND  sender_id = %s
              AND  kind IS NULL
            RETURNING id, chat_id, sender_id, content, sent_at, edited_at, is_deleted, file_url, file_type, file_name, kind
            """,
            (new_content, message_id, sender_id)
        )
        return cursor.fetchone()


def delete_chat_message(message_id: int, sender_id: int) -> bool:
    """Marks a message as deleted (soft delete). Only the original sender may delete their own message.
    Associated chat_notifications rows are removed manually to clear badges.
    Returns True if a row was updated, False if no row matched.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM chat_notifications WHERE message_id = %s",
            (message_id,)
        )
        cursor.execute(
            """
            UPDATE chat_messages
            SET    is_deleted = TRUE,
                   content    = ''
            WHERE  id        = %s
              AND  sender_id = %s
              AND  kind IS NULL
            """,
            (message_id, sender_id)
        )
        return cursor.rowcount > 0


# ── Friendships & friend requests ──────────────────────────
def get_friend_ids(user_id: int):
    """Returns the set of user ids that are accepted friends of `user_id`."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT CASE WHEN requester_id = %s THEN addressee_id ELSE requester_id END AS fid
            FROM   friendships
            WHERE  status = 'accepted' AND (requester_id = %s OR addressee_id = %s)
            """,
            (user_id, user_id, user_id)
        )
        return {row["fid"] for row in cursor.fetchall()}


def get_friends(user_id: int):
    """Returns the accepted friends of `user_id` as user rows (id, username, level, avatar_url, status_text, presence),
    ordered by username. Used to populate the group-member pickers."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username, u.level, u.avatar_url, u.status_text, u.presence
            FROM   friendships f
            JOIN   users u
              ON   u.id = CASE WHEN f.requester_id = %s
                               THEN f.addressee_id ELSE f.requester_id END
            WHERE  f.status = 'accepted'
              AND  (f.requester_id = %s OR f.addressee_id = %s)
            ORDER  BY u.username
            """,
            (user_id, user_id, user_id)
        )
        return cursor.fetchall()


def get_friendship(a: int, b: int):
    """Returns the friendship row between two users (either direction) or None."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT * FROM friendships
            WHERE (requester_id = %s AND addressee_id = %s)
               OR (requester_id = %s AND addressee_id = %s)
            LIMIT 1
            """,
            (a, b, b, a)
        )
        return cursor.fetchone()


def are_friends(a: int, b: int) -> bool:
    """Whether two users are accepted friends."""
    fs = get_friendship(a, b)
    return fs is not None and fs["status"] == "accepted"


def _friend_status(fs, viewer_id: int) -> str:
    """Maps a friendship row to a status from the viewer's perspective:
    'none' | 'friends' | 'pending_outgoing' | 'pending_incoming'."""
    if fs is None:
        return "none"
    if fs["status"] == "accepted":
        return "friends"
    return "pending_outgoing" if fs["requester_id"] == viewer_id else "pending_incoming"


def search_users(query: str, viewer_id: int, limit: int = 20):
    """Finds users by username (excluding the viewer). Each result carries the
    friend status and the number of mutual friends with the viewer."""
    like = f"%{query}%"
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, username, level
            FROM   users
            WHERE  id <> %s AND username ILIKE %s
            ORDER  BY username
            LIMIT  %s
            """,
            (viewer_id, like, limit)
        )
        rows = cursor.fetchall()

    viewer_friends = get_friend_ids(viewer_id)
    results = []
    for r in rows:
        fs = get_friendship(viewer_id, r["id"])
        results.append({
            "id": r["id"],
            "username": r["username"],
            "level": r["level"],
            "status": _friend_status(fs, viewer_id),
            "mutual_friends": len(viewer_friends & get_friend_ids(r["id"])),
        })
    return results


def create_friend_request(requester_id: int, addressee_id: int, message: "str | None"):
    """Creates (or refreshes) a pending friend request with an optional intro
    message. Returns the row."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO friendships (requester_id, addressee_id, status, intro_message)
            VALUES (%s, %s, 'pending', %s)
            ON CONFLICT (requester_id, addressee_id)
            DO UPDATE SET status        = 'pending',
                          intro_message = EXCLUDED.intro_message,
                          created_at    = CURRENT_TIMESTAMP,
                          responded_at  = NULL
            RETURNING id, requester_id, addressee_id, intro_message, created_at
            """,
            (requester_id, addressee_id, message)
        )
        return cursor.fetchone()


def get_incoming_requests(user_id: int):
    """Returns pending requests addressed to the user, incl. the sender's name,
    the intro message and the number of mutual friends."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT f.id, f.requester_id, u.username AS requester_name,
                   f.intro_message, f.created_at
            FROM   friendships f
            JOIN   users u ON u.id = f.requester_id
            WHERE  f.addressee_id = %s AND f.status = 'pending'
            ORDER  BY f.created_at DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()

    viewer_friends = get_friend_ids(user_id)
    result = []
    for r in rows:
        d = dict(r)
        d["mutual_friends"] = len(viewer_friends & get_friend_ids(r["requester_id"]))
        result.append(d)
    return result


def accept_friend_request(request_id: int, user_id: int):
    """Accepts a pending request where `user_id` is the addressee. Returns the
    row (requester_id, addressee_id, intro_message) or None if it does not apply."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE friendships
            SET    status = 'accepted', responded_at = CURRENT_TIMESTAMP
            WHERE  id = %s AND addressee_id = %s AND status = 'pending'
            RETURNING requester_id, addressee_id, intro_message
            """,
            (request_id, user_id)
        )
        return cursor.fetchone()


def delete_friend_request(request_id: int, user_id: int):
    """Removes a pending request — used to decline (addressee) or cancel
    (requester). Returns the deleted row (requester_id, addressee_id) or None."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM friendships
            WHERE  id = %s AND status = 'pending'
               AND (addressee_id = %s OR requester_id = %s)
            RETURNING requester_id, addressee_id
            """,
            (request_id, user_id, user_id)
        )
        return cursor.fetchone()


def remove_friend(user_id: int, friend_id: int):
    """Ends an accepted friendship between `user_id` and `friend_id` (either
    direction may hold requester/addressee). Returns the deleted row
    (requester_id, addressee_id) or None if the two were not friends.

    This only deletes the friendship record — any existing 1-on-1 chat and
    its message history are left untouched, they just can no longer be used
    to start a *new* chat/group together (see `are_friends` checks in app.py).
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM friendships
            WHERE  status = 'accepted'
               AND ((requester_id = %s AND addressee_id = %s)
                 OR (requester_id = %s AND addressee_id = %s))
            RETURNING requester_id, addressee_id
            """,
            (user_id, friend_id, friend_id, user_id)
        )
        return cursor.fetchone()


# ── E2EE key storage ───────────────────────────────────────
# The server is a dumb key *store* here, never a key *user*: it holds public
# keys in the clear, private keys only in their password-wrapped form, and the
# per-chat AES keys only wrapped with a member's public key. None of these
# functions can produce a plaintext key — that only ever happens in the browser.

def set_user_keys(user_id: int, public_key: str, private_key: str, key_salt: str) -> bool:
    """Stores a user's key bundle — but only if they do not have one yet.

    The `public_key IS NULL` guard makes this write-once: without it, anyone who
    got hold of a session could swap in their own public key and have every chat
    key re-wrapped for them, or wipe the bundle and destroy the user's history.
    Returns False when a bundle already exists (nothing was overwritten).
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE users
            SET    public_key = %s, private_key = %s, key_salt = %s
            WHERE  id = %s AND public_key IS NULL
            """,
            (public_key, private_key, key_salt, user_id)
        )
        return cursor.rowcount > 0


def get_user_keys(user_id: int):
    """The user's own bundle: public key + wrapped private key + PBKDF2 salt."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT public_key, private_key, key_salt FROM users WHERE id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def get_public_key(user_id: int):
    """A single user's public key (or None if they never logged in since E2EE)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT public_key FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return row["public_key"] if row else None


def get_my_chat_keys(user_id: int):
    """{chat_id: wrapped_key} for every chat the user has a key for.
    Fetched once on page load so the sidebar previews can be decrypted."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT chat_id, wrapped_key FROM chat_keys WHERE user_id = %s",
            (user_id,)
        )
        return {row["chat_id"]: row["wrapped_key"] for row in cursor.fetchall()}


def get_chat_key(chat_id: int, user_id: int):
    """The caller's own wrapped copy of a chat key, or None."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT wrapped_key FROM chat_keys WHERE chat_id = %s AND user_id = %s",
            (chat_id, user_id)
        )
        row = cursor.fetchone()
        return row["wrapped_key"] if row else None


def chat_key_exists(chat_id: int) -> bool:
    """Whether *anyone* holds a key for this chat. False means the chat has no
    key yet and the first member to open it may generate one."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM chat_keys WHERE chat_id = %s LIMIT 1", (chat_id,))
        return cursor.fetchone() is not None


def get_members_without_key(chat_id: int):
    """Members of the chat that have a public key but no wrapped chat key yet
    — [{id, public_key}]. Any member who already holds the chat key wraps it
    for these users (that is how a newly added member gets access)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.public_key
            FROM   chat_members cm
            JOIN   users u ON u.id = cm.user_id
            WHERE  cm.chat_id = %s
              AND  u.public_key IS NOT NULL
              AND  NOT EXISTS (SELECT 1 FROM chat_keys ck
                                WHERE ck.chat_id = cm.chat_id AND ck.user_id = cm.user_id)
            """,
            (chat_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def add_chat_keys(chat_id: int, wrapped_by_user: dict) -> int:
    """Stores wrapped chat keys for the given members. Insert-only:
    `ON CONFLICT DO NOTHING` means an existing key can never be replaced, so a
    member cannot lock others out by overwriting their copy with garbage — and
    two clients racing to create the first key both end up on the winner's.
    Rows for non-members are silently skipped. Returns the number inserted.
    """
    if not wrapped_by_user:
        return 0
    with get_connection() as connection:
        cursor = connection.cursor()
        inserted = 0
        for user_id, wrapped in wrapped_by_user.items():
            cursor.execute(
                """
                INSERT INTO chat_keys (chat_id, user_id, wrapped_key)
                SELECT %s, %s, %s
                WHERE  EXISTS (SELECT 1 FROM chat_members
                                WHERE chat_id = %s AND user_id = %s)
                ON CONFLICT DO NOTHING
                """,
                (chat_id, user_id, wrapped, chat_id, user_id)
            )
            inserted += cursor.rowcount
        return inserted



# ── XP-Slotmaschine ────────────────────────────────────────
# Die Spielmechanik (Walzen, Gewinntabelle, Zufall) liegt in slots.py; hier
# steht nur die Buchhaltung. Wichtig: Einsatz prüfen, Walzen drehen und XP
# schreiben passieren in EINER Transaktion mit `FOR UPDATE` auf der Nutzerzeile
# — sonst könnten zwei parallele Spins denselben XP-Stand als Deckung nutzen.
def play_slots(user_id: int, bet: int):
    """Spielt einen Spin um `bet` XP und bucht das Ergebnis ab.

    Gibt `{ok: False, error: …}` zurück, wenn der Einsatz ungültig ist oder die
    XP nicht reichen — sonst das Ergebnis aus slots.evaluate() plus dem neuen
    XP-/Level-Stand.
    """
    if not isinstance(bet, int) or isinstance(bet, bool):
        return {"ok": False, "error": "Ungültiger Einsatz."}
    if bet < slots.MIN_BET or bet > slots.MAX_BET:
        return {"ok": False,
                "error": f"Einsatz muss zwischen {slots.MIN_BET} und {slots.MAX_BET} XP liegen."}

    with get_connection() as connection:
        cursor = connection.cursor()

        # FOR UPDATE sperrt die Zeile bis zum Commit des Kontextmanagers.
        cursor.execute("SELECT xp FROM users WHERE id = %s FOR UPDATE", (user_id,))
        user = cursor.fetchone()
        if user is None:
            return {"ok": False, "error": "Nutzer nicht gefunden."}

        current_xp = user["xp"]
        if current_xp < bet:
            return {"ok": False, "error": "Dafür reichen deine XP nicht.",
                    "xp": current_xp, "level": calculate_level(current_xp)}

        result = slots.evaluate(slots.spin_reels(), bet)

        level_before = calculate_level(current_xp)
        new_xp = max(0, current_xp + result["net"])
        new_level = calculate_level(new_xp)

        cursor.execute(
            "UPDATE users SET xp = %s, level = %s WHERE id = %s",
            (new_xp, new_level, user_id)
        )
        cursor.execute(
            """
            INSERT INTO slot_spins (user_id, bet, payout, symbols, xp_after)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, bet, result["payout"], ",".join(result["symbols"]), new_xp)
        )

        result.update({
            "ok": True,
            "xp": new_xp,
            "level": new_level,
            "level_before": level_before,
            "level_delta": new_level - level_before,
        })
        return result


def get_slot_history(user_id: int, limit: int = 10):
    """Die letzten Spins eines Nutzers, neueste zuerst."""
    limit = max(1, min(int(limit), 50))
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT bet, payout, symbols, xp_after, created_at
            FROM slot_spins
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        return cursor.fetchall()


def get_slot_stats(user_id: int):
    """Gesamtbilanz eines Nutzers am Automaten (Spins, Einsatz, Auszahlung)."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)                        AS spins,
                   COALESCE(SUM(bet), 0)           AS wagered,
                   COALESCE(SUM(payout), 0)        AS won
            FROM slot_spins
            WHERE user_id = %s
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        return {
            "spins": int(row["spins"]),
            "wagered": int(row["wagered"]),
            "won": int(row["won"]),
            "net": int(row["won"]) - int(row["wagered"]),
        }
