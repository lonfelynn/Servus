# sockets.py
"""Socket.IO realtime handlers (connect / join / leave / send) and the
in-memory per-user send rate limit."""
import time
from collections import defaultdict, deque
from threading import Lock
from flask import session
from flask_socketio import join_room, leave_room, emit
from .helpers import chat_message_to_dict
from .constants import MESSAGE_MAX_LEN
from extensions import socketio
from models import (
    add_message_xp,
    create_chat_notifications,
    get_user_chat_ids,
    is_chat_member,
    save_chat_message,
)

# Message rate limit: at most RATE_LIMIT_MAX messages per RATE_LIMIT_WINDOW seconds
# per user. A simple in-memory sliding window — fine for a single-process server.
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 5.0
_rate_lock = Lock()
_send_times: "defaultdict[int, deque]" = defaultdict(deque)


def _allow_message(user_id: int) -> bool:
    """Sliding-window rate check. Returns False when the user has sent too many
    messages within the window (and does not count the rejected attempt)."""
    now = time.monotonic()
    with _rate_lock:
        times = _send_times[user_id]
        while times and now - times[0] > RATE_LIMIT_WINDOW:
            times.popleft()
        if len(times) >= RATE_LIMIT_MAX:
            return False
        times.append(now)
        return True


@socketio.on("connect")
def on_connect():
    """Each user joins their private room plus every chat room they belong to."""
    user_id = session.get("user_id")
    if not user_id:
        return
    join_room(f"user_{user_id}")
    for chat_id in get_user_chat_ids(user_id):
        join_room(f"chat_{chat_id}")


@socketio.on("join_chat")
def on_join_chat(data):
    """Lets a client join a chat room after being added to a new chat, without
    having to reconnect. Membership is verified server-side."""
    user_id = session.get("user_id")
    if not user_id:
        return
    try:
        chat_id = int(data.get("chat_id"))
    except (TypeError, ValueError):
        return
    if is_chat_member(chat_id, user_id):
        join_room(f"chat_{chat_id}")


@socketio.on("leave_chat")
def on_leave_chat(data):
    """Lets a client leave a chat room (after being removed / leaving)."""
    try:
        chat_id = int(data.get("chat_id"))
    except (TypeError, ValueError):
        return
    leave_room(f"chat_{chat_id}")


@socketio.on("send_message")
def on_send_message(data):
    sender_id = session.get("user_id")
    if not sender_id:
        return

    try:
        chat_id = int(data.get("chat_id"))
    except (TypeError, ValueError):
        return

    content = (data.get("content") or "").strip()
    file_url = data.get("file_url")
    file_type = data.get("file_type")
    file_name = data.get("file_name")
    if not content and not file_url:
        return

    # Reject over-long messages (the client also enforces this, but never trust it).
    if len(content) > MESSAGE_MAX_LEN:
        return

    # Only members may post to a chat.
    if not is_chat_member(chat_id, sender_id):
        return

    # Rate limit so a single user cannot flood a chat.
    if not _allow_message(sender_id):
        emit("rate_limited", {"error": "Du sendest zu schnell. Bitte warte kurz."})
        return

    message = save_chat_message(chat_id, sender_id, content, file_url, file_type, file_name)
    add_message_xp(sender_id)
    payload = chat_message_to_dict(message, sender_name=session.get("username", ""))

    # Persist an unread marker for every other member (survives a page reload).
    try:
        create_chat_notifications(chat_id, message["id"], sender_id)
    except Exception:
        # A notification failure must never block message delivery.
        pass

    # Deliver to everyone in the chat room (the sender is in it too, so their
    # own open tabs render the message through the same path). Clients drive the
    # live unread badges off this same event, so no separate notify event.
    emit("new_message", payload, room=f"chat_{chat_id}")
