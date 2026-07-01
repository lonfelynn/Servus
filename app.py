# app.py
import os
import atexit
from functools import wraps
from flask import Flask, request, redirect, url_for, render_template, session, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from database import init_pool, run_migrations, close_pool
from auth import auth_bp
from models import (
    get_all_users,
    get_user_by_id,
    add_message_xp,
    find_or_create_chat,
    get_user_chats,
    get_user_chat_ids,
    get_chat,
    get_chat_members,
    is_chat_member,
    add_chat_member,
    remove_chat_member,
    rename_chat,
    save_chat_message,
    get_chat_conversation,
)

# ── App setup ───────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

socketio = SocketIO(app, cors_allowed_origins="*")

# ── Register blueprints ─────────────────────────────────────
app.register_blueprint(auth_bp)


# ── Helpers ─────────────────────────────────────────────────
def login_required(view):
    """Redirects to the login page if no user is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def chat_message_to_dict(message, sender_name=None):
    """Turns a chat_messages row into a JSON-serializable dict (datetime → string)."""
    return {
        "id": message["id"],
        "chat_id": message["chat_id"],
        "sender_id": message["sender_id"],
        "sender_name": sender_name if sender_name is not None else message.get("sender_name"),
        "content": message["content"],
        "sent_at": message["sent_at"].isoformat(),
    }


# ── Pages ───────────────────────────────────────────────────
@app.route("/")
def index():
    """Sends logged-in users to the chat, everyone else to the login page."""
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("auth.login"))


@app.route("/chat")
@login_required
def chat():
    return render_template(
        "chat.html",
        user_id=session["user_id"],
        username=session["username"],
    )


# ── JSON API ────────────────────────────────────────────────
@app.route("/api/me")
@login_required
def api_me():
    user = get_user_by_id(session["user_id"])
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "level": user["level"],
        "xp": user["xp"],
    })


@app.route("/api/users")
@login_required
def api_users():
    users = get_all_users(exclude_id=session["user_id"])
    return jsonify([dict(u) for u in users])


# ── Chats API ───────────────────────────────────────────────
@app.route("/api/chats")
@login_required
def api_chats():
    """All chats the current user is a member of."""
    return jsonify(get_user_chats(session["user_id"]))


@app.route("/api/chats", methods=["POST"])
@login_required
def api_create_chat():
    """Creates a chat (or returns the existing one with the same member set).

    Body: { "member_ids": [..], "name": "optional" }. The current user is always
    included, so opening a 1-on-1 chat is just member_ids=[other_id].
    """
    me = session["user_id"]
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("member_ids") or []
    try:
        member_ids = {int(i) for i in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültige Mitglieder."}), 400
    member_ids.add(me)

    if len(member_ids) < 2:
        return jsonify({"ok": False, "error": "Ein Chat braucht mindestens zwei Mitglieder."}), 400

    name = (data.get("name") or "").strip() or None
    chat_id = find_or_create_chat(member_ids, created_by=me, name=name)

    # Make sure every member's live session joins the room and refreshes.
    for uid in member_ids:
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{uid}")

    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@app.route("/api/chats/<int:chat_id>/messages")
@login_required
def api_chat_messages(chat_id):
    if not is_chat_member(chat_id, session["user_id"]):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403
    messages = get_chat_conversation(chat_id)
    return jsonify([chat_message_to_dict(m) for m in messages])


@app.route("/api/chats/<int:chat_id>/members", methods=["POST"])
@login_required
def api_add_member(chat_id):
    """Adds a user to the chat. Only existing members may add others."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    try:
        new_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400

    add_chat_member(chat_id, new_id)
    # Notify all members (incl. the new one) so they join/refresh the chat.
    for m in get_chat_members(chat_id):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@app.route("/api/chats/<int:chat_id>/members/<int:user_id>", methods=["DELETE"])
@login_required
def api_remove_member(chat_id, user_id):
    """Removes a member (or leaves, when removing yourself)."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    members = get_chat_members(chat_id)
    remove_chat_member(chat_id, user_id)
    # Tell the removed user to drop the chat, and refresh everyone else.
    socketio.emit("chat_removed", {"chat_id": chat_id}, room=f"user_{user_id}")
    for m in members:
        if m["id"] != user_id:
            socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True})


@app.route("/api/chats/<int:chat_id>", methods=["PATCH"])
@login_required
def api_rename_chat(chat_id):
    """Renames a chat. Empty name → falls back to the member-derived name."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    rename_chat(chat_id, name)
    for m in get_chat_members(chat_id):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


# ── Realtime (Socket.IO) ────────────────────────────────────
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
    if not content:
        return

    # Only members may post to a chat.
    if not is_chat_member(chat_id, sender_id):
        return

    message = save_chat_message(chat_id, sender_id, content)
    add_message_xp(sender_id)
    payload = chat_message_to_dict(message, sender_name=session.get("username", ""))

    # Deliver to everyone in the chat room (the sender is in it too, so their
    # own open tabs render the message through the same path).
    emit("new_message", payload, room=f"chat_{chat_id}")


# ── Startup ─────────────────────────────────────────────────
# Close all pooled connections cleanly when the process exits.
atexit.register(close_pool)

if __name__ == "__main__":
    init_pool()        # create the application-wide connection pool
    run_migrations()   # apply any new sql/*.sql files

    # Host/port/debug come from the environment so the SAME entrypoint works
    # for bare `poetry run python app.py` (localhost, debug on by default) and
    # for Docker (HOST=0.0.0.0 is baked into the image).
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1" if host == "127.0.0.1" else "0").lower() \
        in ("1", "true", "yes")
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True,
    )
