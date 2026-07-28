# auth.py
from flask import Blueprint, request, session, jsonify, render_template
from models import create_user, get_user_by_username, check_password
import re
from extensions import limiter

auth_bp = Blueprint("auth", __name__)

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32
MIN_PASSWORD_LENGTH = 8

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    if request.method == "POST":
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        confirm  = data.get("confirm_password", "")

        if len(username) < MIN_USERNAME_LENGTH:
            return jsonify({"ok": False, "error": f"Benutzername muss mindestens {MIN_USERNAME_LENGTH} Zeichen lang sein."})
            
        if len(username) > MAX_USERNAME_LENGTH:
            return jsonify({"ok": False, "error": f"Benutzername darf maximal {MAX_USERNAME_LENGTH} Zeichen lang sein."})

        if not USERNAME_PATTERN.match(username):
            return jsonify({"ok": False, "error": "Benutzername darf nur Buchstaben, Zahlen, _ und - enthalten."})

        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({"ok": False, "error": f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."})

        if not PASSWORD_PATTERN.match(password):
            return jsonify({"ok": False, "error": "Passwort muss Groß- und Kleinbuchstaben sowie eine Zahl enthalten."})

        if password != confirm:
            return jsonify({"ok": False, "error": "Passwörter stimmen nicht überein."})

        success = create_user(username, password)
        if not success:
            return jsonify({"ok": False, "error": "Benutzername bereits vergeben."})

        return jsonify({"ok": True, "redirect": "/login"})

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        user = get_user_by_username(username)

        if user is None or not check_password(password, user["password_hash"]):
            return jsonify({"ok": False, "error": "Ungültiger Benutzername oder Passwort."})

        # Make the session permanent so the login cookie survives a browser
        # restart (uses app.permanent_session_lifetime, set in app.py) instead
        # of expiring as a session cookie.
        session.permanent = True
        session["user_id"]  = user["id"]
        session["username"] = user["username"]

        # user_id goes back to the client so login.js can set up / unlock the
        # E2EE key bundle while it still has the password in hand — the server
        # never gets to see the unwrapped key.
        return jsonify({"ok": True, "redirect": "/chat", "user_id": user["id"]})

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/login"})
