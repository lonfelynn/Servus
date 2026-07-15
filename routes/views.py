# views.py
"""Server-rendered page routes (the HTML shell; data is fetched via the JSON API)."""
from flask import Blueprint, redirect, url_for, render_template, session
from .helpers import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Sends logged-in users to the chat, everyone else to the login page."""
    if "user_id" in session:
        return redirect(url_for("main.chat"))
    return redirect(url_for("auth.login"))


@main_bp.route("/chat")
@login_required
def chat():
    return render_template(
        "chat.html",
        user_id=session["user_id"],
        username=session["username"],
    )
