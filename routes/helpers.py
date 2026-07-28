# helpers.py
"""Cross-cutting view helpers: the auth decorator, the row → JSON serializers
and the two things the server can still say about an encrypted message."""
from functools import wraps
from flask import redirect, url_for, session
from .constants import ENC_PREFIX, MESSAGE_MAX_LEN, MESSAGE_MAX_LEN_ENC


def login_required(view):
    """Redirects to the login page if no user is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def content_too_long(content: str) -> bool:
    """Length guard for message content.

    Encrypted payloads get the larger ciphertext ceiling — the real 2048-char
    plaintext limit can only be enforced client-side now, since the server
    cannot read the message. This still stops someone from bypassing the socket
    handler and stuffing megabytes into the table.
    """
    limit = MESSAGE_MAX_LEN_ENC if content.startswith(ENC_PREFIX) else MESSAGE_MAX_LEN
    return len(content) > limit


def plain_len(content: str) -> int:
    """Estimated plaintext length of a message, used for the XP reward.

    For ciphertext we cannot know the exact length, but base64 of
    (12-byte IV + plaintext + 16-byte GCM tag) is a fixed, monotonic function
    of it — so undoing that arithmetic gives a length within a byte or two,
    which keeps XP fair without the server learning anything about the content.
    """
    if not content.startswith(ENC_PREFIX):
        return len(content)
    b64_len = len(content) - len(ENC_PREFIX)
    return max(0, (b64_len * 3) // 4 - 28)


def chat_message_to_dict(message, sender_name=None):
    """Turns a chat_messages row into a JSON-serializable dict (datetime → string).
    edited_at is None for messages that have never been changed.
    """
    edited_at = message.get("edited_at")
    return {
        "id": message["id"],
        "chat_id": message["chat_id"],
        "sender_id": message["sender_id"],
        "sender_name": sender_name if sender_name is not None else message.get("sender_name"),
        "content": message["content"],
        "sent_at": message["sent_at"].isoformat(),
        "edited_at": edited_at.isoformat() if edited_at else None,
        "is_deleted": message.get("is_deleted", False),
        "file_url": message.get("file_url"),
        "file_type": message.get("file_type"),
        "file_name": message.get("file_name"),
        # None for normal messages, "system" for server-generated notices
        # (member added/removed, chat renamed) — those are plaintext.
        "kind": message.get("kind"),
        "read_count": message.get("read_count", 0),
        "expected_read_count": message.get("expected_read_count", 0),
    }


def request_to_dict(req):
    """JSON-serializable incoming friend request (datetime → string)."""
    return {
        "id": req["id"],
        "requester_id": req["requester_id"],
        "requester_name": req["requester_name"],
        "intro_message": req["intro_message"],
        "mutual_friends": req["mutual_friends"],
        "created_at": req["created_at"].isoformat(),
    }
