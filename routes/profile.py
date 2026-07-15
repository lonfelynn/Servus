# profile.py
"""Current-user profile, app-theme (Söder-Standard + Freikaufen) and directory API."""
from flask import Blueprint, request, session, jsonify
from .helpers import login_required
from .soeder import load_soeder_quotes
from models import (
    get_all_users,
    get_user_by_id,
    update_user_profile,
    get_theme_state,
    set_app_theme,
    unlock_soeder_theme,
    get_friends,
)

profile_bp = Blueprint("profile", __name__)

_ALLOWED_PRESENCE = {"online", "away", "busy", "offline"}


@profile_bp.route("/api/me", methods=["GET", "PATCH"])
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


@profile_bp.route("/api/theme", methods=["POST"])
@login_required
def api_set_theme():
    """Wechselt das App-Theme. 'normal' nur nach der Freischaltung erlaubt."""
    data = request.get_json(silent=True) or {}
    result = set_app_theme(session["user_id"], (data.get("theme") or "").strip())
    return jsonify(result), (200 if result.get("ok") else 400)


@profile_bp.route("/api/theme/unlock", methods=["POST"])
@login_required
def api_unlock_theme():
    """Kauft den Nutzer für Level-Kosten dauerhaft aus dem Söder-Theme frei."""
    result = unlock_soeder_theme(session["user_id"])
    return jsonify(result), (200 if result.get("ok") else 400)


@profile_bp.route("/api/soeder/quotes")
@login_required
def api_soeder_quotes():
    """Serves the local Söder-quote snapshot (same-origin, so CSP-safe).
    soeder.js fetches this to fill the theme's floating quotes / speech bubbles."""
    return jsonify(load_soeder_quotes())


@profile_bp.route("/api/users")
@login_required
def api_users():
    users = get_all_users(exclude_id=session["user_id"])
    return jsonify([dict(u) for u in users])


@profile_bp.route("/api/friends")
@login_required
def api_friends():
    """The current user's accepted friends — used to fill the group-member pickers."""
    return jsonify([dict(u) for u in get_friends(session["user_id"])])
