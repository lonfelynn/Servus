# friends.py
"""User search and the friend-request lifecycle (send / accept / decline / remove)."""
from flask import Blueprint, request, session, jsonify
from .helpers import login_required, request_to_dict
from .constants import FRIEND_INTRO_MAX_LEN
from extensions import socketio
from models import (
    accept_friend_request,
    create_chat_notifications,
    create_friend_request,
    delete_friend_request,
    find_or_create_chat,
    get_chat,
    get_friendship,
    get_incoming_requests,
    get_user_by_id,
    remove_friend,
    save_chat_message,
    search_users,
)

friends_bp = Blueprint("friends", __name__)


@friends_bp.route("/api/users/search")
@login_required
def api_search_users():
    """Finds users by username, with friend status + mutual friend count."""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify([])
    return jsonify(search_users(query, session["user_id"]))


@friends_bp.route("/api/friends/requests")
@login_required
def api_friend_requests():
    """Pending friend requests addressed to the current user."""
    reqs = get_incoming_requests(session["user_id"])
    return jsonify([request_to_dict(r) for r in reqs])


@friends_bp.route("/api/friends/request", methods=["POST"])
@login_required
def api_friend_request():
    """Sends a friend request with an optional single intro message (≤2048)."""
    me = session["user_id"]
    data = request.get_json(silent=True) or {}
    try:
        target = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400
    if target == me:
        return jsonify({"ok": False, "error": "Du kannst dir nicht selbst eine Anfrage senden."}), 400
    if get_user_by_id(target) is None:
        return jsonify({"ok": False, "error": "Nutzer nicht gefunden."}), 404

    message = (data.get("message") or "").strip()
    if len(message) > FRIEND_INTRO_MAX_LEN:
        return jsonify({"ok": False,
                        "error": f"Die Nachricht darf höchstens {FRIEND_INTRO_MAX_LEN} Zeichen haben."}), 400
    message = message or None

    fs = get_friendship(me, target)
    if fs and fs["status"] == "accepted":
        return jsonify({"ok": False, "error": "Ihr seid bereits Freunde."}), 400
    if fs and fs["status"] == "pending":
        if fs["requester_id"] == me:
            return jsonify({"ok": False, "error": "Deine Anfrage läuft bereits."}), 400
        return jsonify({"ok": False,
                        "error": "Dieser Nutzer hat dir bereits eine Anfrage gesendet – beantworte sie unten."}), 400

    create_friend_request(me, target, message)
    socketio.emit("friend_request", {"from": me}, room=f"user_{target}")
    return jsonify({"ok": True})


@friends_bp.route("/api/friends/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def api_friend_accept(request_id):
    """Accepts a request: befriends the two users and opens their DM chat,
    delivering the requester's intro message as the first message."""
    me = session["user_id"]
    res = accept_friend_request(request_id, me)
    if res is None:
        return jsonify({"ok": False, "error": "Anfrage nicht gefunden."}), 404
    add_xp(me, 25)
    add_xp(res["requester_id"], 25)
    requester_id = res["requester_id"]
    chat_id = find_or_create_chat([requester_id, me], created_by=requester_id)

    if res["intro_message"]:
        message = save_chat_message(chat_id, requester_id, res["intro_message"])
        try:
            create_chat_notifications(chat_id, message["id"], requester_id)
        except Exception:
            pass

    # Both parties join the new chat room and refresh chats + friend UI.
    for uid in (requester_id, me):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{uid}")
        socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@friends_bp.route("/api/friends/requests/<int:request_id>/decline", methods=["POST"])
@login_required
def api_friend_decline(request_id):
    """Declines (or cancels) a pending request."""
    me = session["user_id"]
    row = delete_friend_request(request_id, me)
    if row is not None:
        # Refresh both parties' friend UI (outgoing status / incoming list).
        for uid in (row["requester_id"], row["addressee_id"]):
            socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True})


@friends_bp.route("/api/friends/<int:friend_id>", methods=["DELETE"])
@login_required
def api_remove_friend(friend_id):
    """Ends an accepted friendship. Either side may remove the other; any
    existing 1-on-1 chat and its message history stay intact, but the two
    users can no longer be added to new chats/groups together until they
    become friends again."""
    me = session["user_id"]
    if friend_id == me:
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400

    row = remove_friend(me, friend_id)
    if row is None:
        return jsonify({"ok": False, "error": "Ihr seid nicht befreundet."}), 400

    # Refresh both users' friend lists / search results live.
    for uid in (row["requester_id"], row["addressee_id"]):
        socketio.emit("friend_update", {}, room=f"user_{uid}")
    return jsonify({"ok": True})
