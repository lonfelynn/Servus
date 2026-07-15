# app.py
import os
import time
import atexit
import uuid
from werkzeug.utils import secure_filename
from datetime import timedelta
from collections import defaultdict, deque
from threading import Lock
from functools import wraps
from flask import Flask, request, redirect, url_for, render_template, session, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from database import init_pool, run_migrations, close_pool
from auth import auth_bp
from models import (
    get_all_users,
    get_user_by_id,
    update_user_profile,
    add_message_xp,
    get_theme_state,
    set_app_theme,
    unlock_soeder_theme,
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
    create_chat_notifications,
    get_unread_chat_counts,
    mark_chat_notifications_read,
    update_chat_message,
    delete_chat_message,
    are_friends,
    get_friendship,
    get_friend_ids,
    get_friends,
    search_users,
    create_friend_request,
    get_incoming_requests,
    accept_friend_request,
    delete_friend_request,
    remove_friend,
)
from datetime import timedelta
from dotenv import load_dotenv
from extensions import limiter

load_dotenv()

# Max length of the single intro message a requester may attach to a request.
FRIEND_INTRO_MAX_LEN = 2048

# Max length of a normal chat message.
MESSAGE_MAX_LEN = 2048

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

# ── App setup ───────────────────────────────────────────────
app = Flask(__name__)
# Secret Key
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY ist nicht gesetzt!")

# Session & Cookie Sicherheit
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"]   = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)

socketio = SocketIO(app, cors_allowed_origins="*")

limiter.init_app(app)

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'"
    )
    return response

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
        "edited_at": edited_at.isoformat() if edited_at else None,  # NEU
        "is_deleted": message.get("is_deleted", False),
        "file_url": message.get("file_url"),
        "file_type": message.get("file_type"),
        "file_name": message.get("file_name"),
        "read_count": message.get("read_count", 0),
        "expected_read_count": message.get("expected_read_count", 0),
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
_ALLOWED_PRESENCE = {"online", "away", "busy", "offline"}


@app.route("/api/me", methods=["GET", "PATCH"])
@login_required
def api_me():
    if request.method == "PATCH":
        data = request.get_json(silent=True) or {}
        presence = data.get("presence")
        if presence is not None and presence not in _ALLOWED_PRESENCE:
            presence = None  # ignore invalid values rather than store garbage
        status_text = data.get("status_text")
        if isinstance(status_text, str):
            status_text = status_text[:128]  # match the client-side max length
        user = update_user_profile(
            session["user_id"],
            status_text=status_text,
            presence=presence,
            avatar_url=data.get("avatar_url"),
        )
    else:
        user = get_user_by_id(session["user_id"])

    # Never expose the password hash — return only the safe, UI-relevant fields.
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "level": user["level"],
        "xp": user["xp"],
        "avatar_url": user.get("avatar_url"),
        "status_text": user.get("status_text"),
        "presence": user.get("presence"),
        "accent_color": user.get("accent_color"),
        "theme_mode": user.get("theme_mode"),
        **get_theme_state(user),
    })


# ── App-Theme (Söder-Standard + Freikaufen) ─────────────────
@app.route("/api/theme", methods=["POST"])
@login_required
def api_set_theme():
    """Wechselt das App-Theme. 'normal' nur nach der Freischaltung erlaubt."""
    data = request.get_json(silent=True) or {}
    result = set_app_theme(session["user_id"], (data.get("theme") or "").strip())
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/theme/unlock", methods=["POST"])
@login_required
def api_unlock_theme():
    """Kauft den Nutzer für Level-Kosten dauerhaft aus dem Söder-Theme frei."""
    result = unlock_soeder_theme(session["user_id"])
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/users")
@login_required
def api_users():
    users = get_all_users(exclude_id=session["user_id"])
    return jsonify([dict(u) for u in users])


@app.route("/api/friends")
@login_required
def api_friends():
    """The current user's accepted friends — used to fill the group-member pickers."""
    return jsonify([dict(u) for u in get_friends(session["user_id"])])


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

    # You may only chat with accepted friends: a 1-on-1 needs the other person to
    # be a friend, a group may only be created from your friends.
    others = member_ids - {me}
    non_friends = others - get_friend_ids(me)
    if non_friends:
        if len(member_ids) == 2:
            return jsonify({"ok": False, "error": "Ihr müsst befreundet sein, um direkt zu chatten."}), 403
        return jsonify({"ok": False, "error": "Du kannst nur Freunde zu einer Gruppe hinzufügen."}), 403

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

@app.route("/api/chats/<int:chat_id>/messages/<int:message_id>", methods=["PATCH"])
@login_required
def api_edit_message(chat_id, message_id):
    """Edits the content of a message. Only the original sender may do this."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Nachricht darf nicht leer sein."}), 400
    if len(content) > MESSAGE_MAX_LEN:
        return jsonify({"ok": False, "error": f"Nachricht darf höchstens {MESSAGE_MAX_LEN} Zeichen haben."}), 400

    updated = update_chat_message(message_id, me, content)
    if updated is None:
        # Either wrong message_id or the caller is not the original sender.
        return jsonify({"ok": False, "error": "Nachricht nicht gefunden oder kein Zugriff."}), 403

    payload = chat_message_to_dict(updated, sender_name=session.get("username", ""))
    socketio.emit("message_edited", payload, room=f"chat_{chat_id}")
    return jsonify({"ok": True, "message": payload})


@app.route("/api/chats/<int:chat_id>/messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_delete_message(chat_id, message_id):
    """Deletes a message. Only the original sender may do this.
    chat_notifications rows referencing the message are removed automatically
    by the ON DELETE CASCADE constraint on chat_notifications.message_id.
    """
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    deleted = delete_chat_message(message_id, me)
    if not deleted:
        return jsonify({"ok": False, "error": "Nachricht nicht gefunden oder kein Zugriff."}), 403

    socketio.emit(
        "message_deleted",
        {"chat_id": chat_id, "message_id": message_id},
        room=f"chat_{chat_id}",
    )
    return jsonify({"ok": True})


@app.route("/api/notifications")
@login_required
def api_notifications():
    """Unread message counts per chat for the current user."""
    return jsonify(get_unread_chat_counts(session["user_id"]))


@app.route("/api/notifications/chat/<int:chat_id>/read", methods=["POST"])
@login_required
def api_notifications_read(chat_id):
    """Marks all unread messages in a chat as read for the current user."""
    mark_chat_notifications_read(session["user_id"], chat_id)
    socketio.emit("message_read", {"chat_id": chat_id}, room=f"chat_{chat_id}")
    return jsonify({"ok": True})

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "Keine Datei gesendet."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "Keine Datei ausgewählt."}), 400
    
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)
    
    file_type = "file"
    mime_type = file.mimetype
    if mime_type.startswith("image/"):
        file_type = "image"
    elif mime_type.startswith("video/"):
        file_type = "video"
        
    file_url = url_for('static', filename=f'uploads/{unique_filename}')
    
    return jsonify({
        "ok": True, 
        "file_url": file_url,
        "file_type": file_type,
        "file_name": filename
    })

# ── Friends & search API ────────────────────────────────────
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


@app.route("/api/users/search")
@login_required
def api_search_users():
    """Finds users by username, with friend status + mutual friend count."""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify([])
    return jsonify(search_users(query, session["user_id"]))


@app.route("/api/friends/requests")
@login_required
def api_friend_requests():
    """Pending friend requests addressed to the current user."""
    reqs = get_incoming_requests(session["user_id"])
    return jsonify([request_to_dict(r) for r in reqs])


@app.route("/api/friends/request", methods=["POST"])
@login_required
def api_friend_request():
    """Sends a friend request with an optional single intro message (≤2048)."""
    me = session["user_id"]
    data = request.get_json(silent=True) or {}
    try:
        target = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400
    if target == me:
        return jsonify({"ok": False, "error": "Du kannst dir nicht selbst eine Anfrage senden."}), 400
    if get_user_by_id(target) is None:
        return jsonify({"ok": False, "error": "Nutzer nicht gefunden."}), 404

    message = (data.get("message") or "").strip()
    if len(message) > FRIEND_INTRO_MAX_LEN:
        return jsonify({"ok": False,
                        "error": f"Die Nachricht darf höchstens {FRIEND_INTRO_MAX_LEN} Zeichen haben."}), 400
    message = message or None

    fs = get_friendship(me, target)
    if fs and fs["status"] == "accepted":
        return jsonify({"ok": False, "error": "Ihr seid bereits Freunde."}), 400
    if fs and fs["status"] == "pending":
        if fs["requester_id"] == me:
            return jsonify({"ok": False, "error": "Deine Anfrage läuft bereits."}), 400
        return jsonify({"ok": False,
                        "error": "Dieser Nutzer hat dir bereits eine Anfrage gesendet – beantworte sie unten."}), 400

    create_friend_request(me, target, message)
    socketio.emit("friend_request", {"from": me}, room=f"user_{target}")
    return jsonify({"ok": True})


@app.route("/api/friends/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def api_friend_accept(request_id):
    """Accepts a request: befriends the two users and opens their DM chat,
    delivering the requester's intro message as the first message."""
    me = session["user_id"]
    res = accept_friend_request(request_id, me)
    if res is None:
        return jsonify({"ok": False, "error": "Anfrage nicht gefunden."}), 404

    requester_id = res["requester_id"]
    chat_id = find_or_create_chat([requester_id, me], created_by=requester_id)

    if res["intro_message"]:
        message = save_chat_message(chat_id, requester_id, res["intro_message"])
        try:
            create_chat_notifications(chat_id, message["id"], requester_id)
        except Exception:
            pass

    # Both parties join the new chat room and refresh chats + friend UI.
    for uid in (requester_id, me):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{uid}")
        socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@app.route("/api/friends/requests/<int:request_id>/decline", methods=["POST"])
@login_required
def api_friend_decline(request_id):
    """Declines (or cancels) a pending request."""
    me = session["user_id"]
    row = delete_friend_request(request_id, me)
    if row is not None:
        # Refresh both parties' friend UI (outgoing status / incoming list).
        for uid in (row["requester_id"], row["addressee_id"]):
            socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True})


@app.route("/api/friends/<int:friend_id>", methods=["DELETE"])
@login_required
def api_remove_friend(friend_id):
    """Ends an accepted friendship. Either side may remove the other; any
    existing 1-on-1 chat and its message history stay intact, but the two
    users can no longer be added to new chats/groups together until they
    become friends again."""
    me = session["user_id"]
    if friend_id == me:
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400

    row = remove_friend(me, friend_id)
    if row is None:
        return jsonify({"ok": False, "error": "Ihr seid nicht befreundet."}), 400

    # Refresh both users' friend lists / search results live.
    for uid in (row["requester_id"], row["addressee_id"]):
        socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True})
    

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

    # Only friends of the person doing the adding may be pulled into the group.
    if not are_friends(me, new_id):
        return jsonify({"ok": False, "error": "Du kannst nur Freunde zur Gruppe hinzufügen."}), 403

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
