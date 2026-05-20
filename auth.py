# auth.py
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, session, flash
)
from models import create_user, get_user_by_username, check_password

auth_bp = Blueprint("auth", __name__)

MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if len(username) < MIN_USERNAME_LENGTH:
            flash(f"Username must be at least {MIN_USERNAME_LENGTH} characters.", "error")
            return render_template("register.html")

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        success = create_user(username, password)
        if not success:
            flash("Username is already taken. Please choose another.", "error")
            return render_template("register.html")

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user is None or not check_password(password, user["password_hash"]):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect(url_for("auth.login"))  # chat kommt im nächsten Schritt

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
