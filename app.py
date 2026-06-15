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


# ── Startup ─────────────────────────────────────────────────
# Close all pooled connections cleanly when the process exits.
atexit.register(close_pool)

if __name__ == "__main__":
    init_pool()        # create the application-wide connection pool
    run_migrations()   # apply any new sql/*.sql files
    socketio.run(app, debug=True)
