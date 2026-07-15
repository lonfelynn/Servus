# helpers.py
"""Cross-cutting view helpers: the auth decorator and the row → JSON serializers."""
from functools import wraps
from flask import redirect, url_for, session


def login_required(view):
    """Redirects to the login page if no user is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


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
