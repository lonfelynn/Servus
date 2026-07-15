# app.py
"""Application entrypoint: builds the Flask app, wires up the shared extensions,
registers the route blueprints + Socket.IO handlers, and serves the app.

The actual routes live in the `routes/` package, grouped by domain:
  - routes/views.py    — server-rendered pages (`/`, `/chat`)
  - routes/profile.py  — profile, app-theme and user directory API
  - routes/chats.py    — chats, messages, notifications, uploads, membership API
  - routes/friends.py  — user search and the friend-request lifecycle API
  - routes/auth.py     — register / login / logout blueprint
  - routes/sockets.py  — Socket.IO realtime handlers
"""
import os
import atexit
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv

from database import init_pool, run_migrations, close_pool
from extensions import limiter, socketio
# Importing routes also registers the Socket.IO handlers (see routes/__init__.py).
from routes import all_blueprints

load_dotenv()

# ── App setup ───────────────────────────────────────────────
app = Flask(__name__)
# Secret Key
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY ist nicht gesetzt!")

# Session & Cookie Sicherheit
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# Secure cookies require HTTPS. Over plain http://localhost the browser silently
# drops a Secure cookie, which would break login in local dev — so this is
# opt-in via env (set SESSION_COOKIE_SECURE=1 behind HTTPS in production).
app.config["SESSION_COOKIE_SECURE"] = \
    os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in ("1", "true", "yes")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)

# ── Extensions ──────────────────────────────────────────────
limiter.init_app(app)
socketio.init_app(app)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # 'unsafe-inline' is needed because the templates use inline style="…"
        # attributes throughout; without it the browser drops all inline styling.
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        # Socket.IO is now self-hosted (static/js/vendor), so no CDN host needed.
        "script-src 'self' 'unsafe-inline'"
    )
    return response

# ── Register blueprints ─────────────────────────────────────
for blueprint in all_blueprints:
    app.register_blueprint(blueprint)

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
