# extensions.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialized here, bound to the app later in app.py via init_app()
# This avoids circular imports between app.py and auth.py
limiter = Limiter(key_func=get_remote_address)
