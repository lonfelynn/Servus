# extensions.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

# Initialized here, bound to the app later in app.py via init_app().
# This avoids circular imports: the route/socket modules import these shared
# instances from here, while app.py owns the actual Flask app and wires them up.
limiter = Limiter(key_func=get_remote_address)
socketio = SocketIO(cors_allowed_origins="*")
