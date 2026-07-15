# routes/__init__.py
"""The Servus web layer: page views, the JSON API blueprints, and the Socket.IO
realtime handlers. app.py imports the blueprints from here and registers them.

Importing this package also imports `sockets`, whose module-level `@socketio.on`
decorators register the realtime handlers on the shared SocketIO instance.
"""
from .auth import auth_bp
from .views import main_bp
from .profile import profile_bp
from .chats import chats_bp
from .friends import friends_bp
from . import sockets  # noqa: F401 — registers the @socketio.on(...) handlers

# Every blueprint app.py needs to register, in one place.
all_blueprints = (auth_bp, main_bp, profile_bp, chats_bp, friends_bp)

__all__ = ["all_blueprints", "auth_bp", "main_bp", "profile_bp", "chats_bp", "friends_bp"]
