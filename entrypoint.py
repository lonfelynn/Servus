# Personal Docker entrypoint — not committed (see .gitignore).
#
# No longer required: app.py's __main__ now honours HOST/PORT/FLASK_DEBUG
# from the environment, and the Docker image sets HOST=0.0.0.0, so the
# Dockerfile runs `python app.py` directly. This shim is kept only so an
# explicit `python entrypoint.py` still binds to all interfaces.
import os

os.environ.setdefault("HOST", "0.0.0.0")

import app  # noqa: E402  (imported after the env default is set)

app.init_pool()
app.run_migrations()
app.socketio.run(
    app.app,
    host=os.environ["HOST"],
    port=int(os.environ.get("PORT", "5000")),
    allow_unsafe_werkzeug=True,
)
