# auth.py
from flask import Blueprint, request, session, jsonify, render_template
from models import create_user, get_user_by_username, check_password

auth_bp = Blueprint("auth", __name__)

MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        confirm  = data.get("confirm_password", "")

        if len(username) < MIN_USERNAME_LENGTH:
            return jsonify({"ok": False, "error": f"Benutzername muss mindestens {MIN_USERNAME_LENGTH} Zeichen lang sein."})

        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({"ok": False, "error": f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."})

        if password != confirm:
            return jsonify({"ok": False, "error": "Passwörter stimmen nicht überein."})

        success = create_user(username, password)
        if not success:
            return jsonify({"ok": False, "error": "Benutzername bereits vergeben."})

        return jsonify({"ok": True, "redirect": "/login"})

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        user = get_user_by_username(username)

        if user is None or not check_password(password, user["password_hash"]):
            return jsonify({"ok": False, "error": "Ungültiger Benutzername oder Passwort."})

        session["user_id"]  = user["id"]
        session["username"] = user["username"]

        return jsonify({"ok": True, "redirect": "/chat"})

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/login"})
