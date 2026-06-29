# app.py
import os
import atexit
from functools import wraps
from flask import Flask, redirect, url_for, render_template, session, jsonify
from flask_socketio import SocketIO, join_room, emit
from database import init_pool, run_migrations, close_pool
from auth import auth_bp
from models import (
    get_all_users,
    get_user_by_id,
    get_conversation,
    save_message,
    add_message_xp,
    create_notification,
    get_unread_notifications,
    mark_notifications_read_by_sender,
    mark_all_notifications_read,
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


def message_to_dict(message):
    """Turns a message row into a JSON-serializable dict (datetime → string)."""
    return {
        "id": message["id"],
        "sender_id": message["sender_id"],
        "receiver_id": message["receiver_id"],
        "content": message["content"],
        "sent_at": message["sent_at"].isoformat(),
    }

def notification_to_dict(notif):
    """Turns a notification row into a JSON-serializable dict."""
    return {
        "id": notif["id"],
        "sender_id": notif["sender_id"],
        "sender_name": notif["sender_name"],
        "message_id": notif["message_id"],
        "created_at": notif["created_at"].isoformat(),
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


@app.route("/api/messages/<int:other_id>")
@login_required
def api_messages(other_id):
    messages = get_conversation(session["user_id"], other_id)
    return jsonify([message_to_dict(m) for m in messages])

# ── Notification API ────────────────────────────────────────
@app.route("/api/notifications")
@login_required
def api_notifications():
    """Returns all unread notifications for the current user."""
    notifs = get_unread_notifications(session["user_id"])
    return jsonify([notification_to_dict(n) for n in notifs])


@app.route("/api/notifications/read-by-sender/<int:sender_id>", methods=["POST"])
@login_required
def api_notifications_read_by_sender(sender_id):
    """Marks all unread notifications from a specific sender as read.
    session["user_id"] als recipient_id — Nutzer können nur ihre eigenen löschen.
    """
    mark_notifications_read_by_sender(session["user_id"], sender_id)
    return jsonify({"ok": True})


@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_notifications_read_all():
    """Marks every unread notification for the current user as read."""
    mark_all_notifications_read(session["user_id"])
    return jsonify({"ok": True})

# ── Realtime (Socket.IO) ────────────────────────────────────
@socketio.on("connect")
def on_connect():
    """Each user joins a private room so messages can be delivered directly."""
    user_id = session.get("user_id")
    if user_id:
        join_room(f"user_{user_id}")


@socketio.on("send_message")
def on_send_message(data):
    sender_id = session.get("user_id")
    if not sender_id:
        return

    try:
        receiver_id = int(data.get("to"))
    except (TypeError, ValueError):
        return

    content = (data.get("content") or "").strip()
    if not content:
        return

    message = save_message(sender_id, receiver_id, content)
    add_message_xp(sender_id)
    payload = message_to_dict(message)

    # Deliver to the receiver and echo back to the sender (all their open tabs).
    emit("new_message", payload, room=f"user_{receiver_id}")
    emit("new_message", payload, room=f"user_{sender_id}")

    if receiver_id != sender_id:
        try:
            notif = create_notification(receiver_id, sender_id, message["id"])
            emit("notification", {
                "id": notif["id"],
                "sender_id": sender_id,
                "sender_name": session.get("username", ""),
                "message_id": message["id"],
                "created_at": notif["created_at"].isoformat(),
            }, room=f"user_{receiver_id}")
        except Exception:
            # Notification-Fehler darf Nachrichtenzustellung nie unterbrechen.
            pass


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
