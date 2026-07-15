# syntax=docker/dockerfile:1

# ── Builder: install the exact locked dependency graph into a venv ────
# psycopg2-binary ships a self-contained libpq, so NO system build tools
# or libpq headers are needed — keeps the build fast and the image slim.
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1

RUN pip install poetry

# Build the application venv at a fixed path OUTSIDE /app, so the compose
# bind-mount (.:/app) can't shadow it at runtime. Activating it via
# VIRTUAL_ENV makes Poetry install into it instead of creating its own,
# which also keeps Poetry itself out of the venv we ship.
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
RUN python -m venv "$VIRTUAL_ENV"

# Copy only the lockfiles first so this layer is cached unless deps change.
COPY pyproject.toml poetry.lock ./

# Installs the FULL locked graph, incl. transitive deps like simple-websocket
# (python-engineio's threading WebSocket driver needs it — its absence is what
# caused "Invalid async_mode specified").
RUN poetry install --only main --no-root


# ── Runtime: copy the ready-made venv + app code, nothing else ───────
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=5000

# The venv lives at the same absolute path in both stages, so its
# shebangs/symlinks stay valid after the copy.
COPY --from=builder /opt/venv /opt/venv
COPY . .

EXPOSE 5000

# app.py honours HOST/PORT/FLASK_DEBUG; HOST=0.0.0.0 makes it reachable.
CMD ["python", "app.py"]
