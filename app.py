# app.py
import os
from flask import Flask, redirect, url_for
from flask_socketio import SocketIO
from database import init_db
from auth import auth_bp

# ── App setup ───────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

socketio = SocketIO(app)

# ── Register blueprints ─────────────────────────────────────
app.register_blueprint(auth_bp)

# ── Startup ─────────────────────────────────────────────────
@app.route("/")
def index():
    """Redirects the root URL to the login page."""
    return redirect(url_for("auth.login"))

if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True)
