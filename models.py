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
                   (SELECT MAX(sent_at) FROM chat_messages m
                     WHERE m.chat_id = c.id) AS last_at
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
                {"id": mid, "username": mname}
                for mid, mname in zip(row["member_ids"], row["member_names"])
            ]
            chats.append({
                "id": row["id"],
                "name": row["name"],
                "display_name": _display_name(row["name"], members, user_id),
                "members": members,
                "is_group": len(members) > 2,
            })
        return chats


def get_chat(chat_id: int, viewer_id: int):
    """Returns a single chat (same shape as an entry from get_user_chats),
    or None if it does not exist."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, name FROM chats WHERE id = %s", (chat_id,))
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
    }


def get_chat_members(chat_id: int):
    """Returns the members of a chat as a list of {id, username} dicts."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username
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


def save_chat_message(chat_id: int, sender_id: int, content: str):
    """Stores a chat message and returns the created row."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (chat_id, sender_id, content) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, chat_id, sender_id, content, sent_at",
            (chat_id, sender_id, content)
        )
        return cursor.fetchone()


def get_chat_conversation(chat_id: int):
    """Returns all messages in a chat, oldest first, incl. the sender's name."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT m.id, m.chat_id, m.sender_id, m.content, m.sent_at, m.edited_at,
                   u.username AS sender_name
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
            RETURNING id, chat_id, sender_id, content, sent_at, edited_at
            """,
            (new_content, message_id, sender_id)
        )
        return cursor.fetchone()


def delete_chat_message(message_id: int, sender_id: int) -> bool:
    """Deletes a message. Only the original sender may delete their own message.
    Associated chat_notifications rows are removed automatically via ON DELETE CASCADE.
    Returns True if a row was deleted, False if no row matched.
    """
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM chat_messages WHERE id = %s AND sender_id = %s",
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
    """Returns the accepted friends of `user_id` as user rows (id, username, level),
    ordered by username. Used to populate the group-member pickers."""
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.username, u.level
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
