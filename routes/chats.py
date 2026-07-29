# chats.py
"""Chats, messages, unread notifications, uploads and membership — the JSON API."""
import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, request, session, jsonify, url_for
from .helpers import login_required, chat_message_to_dict, content_too_long
from .constants import BASE_DIR, MESSAGE_MAX_LEN
from extensions import socketio
from models import (
    add_xp,
    add_chat_member,
    are_friends,
    delete_chat_message,
    find_or_create_chat,
    get_chat,
    get_chat_conversation,
    get_chat_members,
    get_friend_ids,
    get_unread_chat_counts,
    get_user_chats,
    get_user_by_id,
    is_chat_member,
    mark_chat_notifications_read,
    remove_chat_member,
    rename_chat,
    save_chat_message,
    update_chat_message,
)

chats_bp = Blueprint("chats", __name__)

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def system_message(chat_id: int, actor_id: int, text: str):
    """Writes a system notice into the chat and pushes it to everyone in the room.

    These rows are plaintext (kind='system'): the server holds no chat key, so it
    could not encrypt them. They only ever contain names the server already knows.
    A failure here must never break the membership/rename operation itself.
    """
    try:
        message = save_chat_message(chat_id, actor_id, text, kind="system")
        socketio.emit("new_message", chat_message_to_dict(message, sender_name=""),
                      room=f"chat_{chat_id}")
    except Exception:
        pass


def _username(user_id: int) -> str:
    user = get_user_by_id(user_id)
    return user["username"] if user else "Jemand"


@chats_bp.route("/api/chats")
@login_required
def api_chats():
    """All chats the current user is a member of."""
    return jsonify(get_user_chats(session["user_id"]))


@chats_bp.route("/api/chats", methods=["POST"])
@login_required
def api_create_chat():
    """Creates a chat (or returns the existing one with the same member set).

    Body: { "member_ids": [..], "name": "optional" }. The current user is always
    included, so opening a 1-on-1 chat is just member_ids=[other_id].
    """
    me = session["user_id"]
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("member_ids") or []
    try:
        member_ids = {int(i) for i in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültige Mitglieder."}), 400
    member_ids.add(me)

    if len(member_ids) < 2:
        return jsonify({"ok": False, "error": "Ein Chat braucht mindestens zwei Mitglieder."}), 400

    # You may only chat with accepted friends: a 1-on-1 needs the other person to
    # be a friend, a group may only be created from your friends.
    others = member_ids - {me}
    non_friends = others - get_friend_ids(me)
    if non_friends:
        if len(member_ids) == 2:
            return jsonify({"ok": False, "error": "Ihr müsst befreundet sein, um direkt zu chatten."}), 403
        return jsonify({"ok": False, "error": "Du kannst nur Freunde zu einer Gruppe hinzufügen."}), 403

    name = (data.get("name") or "").strip() or None
    chat_id = find_or_create_chat(member_ids, created_by=me, name=name)

    if len(member_ids) == 2:
        add_xp(me, 50)      
    else:
        add_xp(me, 75)      

    # Make sure every member's live session joins the room and refreshes.
    for uid in member_ids:
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{uid}")

    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@chats_bp.route("/api/chats/<int:chat_id>/messages")
@login_required
def api_chat_messages(chat_id):
    if not is_chat_member(chat_id, session["user_id"]):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403
    messages = get_chat_conversation(chat_id)
    return jsonify([chat_message_to_dict(m) for m in messages])


@chats_bp.route("/api/chats/<int:chat_id>/messages/<int:message_id>", methods=["PATCH"])
@login_required
def api_edit_message(chat_id, message_id):
    """Edits the content of a message. Only the original sender may do this."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Nachricht darf nicht leer sein."}), 400
    if content_too_long(content):
        return jsonify({"ok": False, "error": f"Nachricht darf höchstens {MESSAGE_MAX_LEN} Zeichen haben."}), 400

    updated = update_chat_message(message_id, me, content)
    if updated is None:
        # Either wrong message_id or the caller is not the original sender.
        return jsonify({"ok": False, "error": "Nachricht nicht gefunden oder kein Zugriff."}), 403

    payload = chat_message_to_dict(updated, sender_name=session.get("username", ""))
    socketio.emit("message_edited", payload, room=f"chat_{chat_id}")
    return jsonify({"ok": True, "message": payload})


@chats_bp.route("/api/chats/<int:chat_id>/messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_delete_message(chat_id, message_id):
    """Deletes a message. Only the original sender may do this.
    chat_notifications rows referencing the message are removed automatically
    by the ON DELETE CASCADE constraint on chat_notifications.message_id.
    """
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    deleted = delete_chat_message(message_id, me)
    if not deleted:
        return jsonify({"ok": False, "error": "Nachricht nicht gefunden oder kein Zugriff."}), 403

    socketio.emit(
        "message_deleted",
        {"chat_id": chat_id, "message_id": message_id},
        room=f"chat_{chat_id}",
    )
    return jsonify({"ok": True})


@chats_bp.route("/api/notifications")
@login_required
def api_notifications():
    """Unread message counts per chat for the current user."""
    return jsonify(get_unread_chat_counts(session["user_id"]))


@chats_bp.route("/api/notifications/chat/<int:chat_id>/read", methods=["POST"])
@login_required
def api_notifications_read(chat_id):
    """Marks all unread messages in a chat as read for the current user."""
    mark_chat_notifications_read(session["user_id"], chat_id)
    socketio.emit("message_read", {"chat_id": chat_id}, room=f"chat_{chat_id}")
    return jsonify({"ok": True})


@chats_bp.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Keine Datei gesendet."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Keine Datei ausgewählt."}), 400

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    file_type = "file"
    mime_type = file.mimetype
    if mime_type.startswith("image/"):
        file_type = "image"
    elif mime_type.startswith("video/"):
        file_type = "video"

    file_url = url_for("static", filename=f"uploads/{unique_filename}")

    return jsonify({
        "ok": True,
        "file_url": file_url,
        "file_type": file_type,
        "file_name": filename,
    })


@chats_bp.route("/api/chats/<int:chat_id>/members", methods=["POST"])
@login_required
def api_add_member(chat_id):
    """Adds a user to the chat. Only existing members may add others."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    try:
        new_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültiger Nutzer."}), 400

    # Only friends of the person doing the adding may be pulled into the group.
    if not are_friends(me, new_id):
        return jsonify({"ok": False, "error": "Du kannst nur Freunde zur Gruppe hinzufügen."}), 403

    add_chat_member(chat_id, new_id)
    system_message(chat_id, me, f"{_username(me)} hat {_username(new_id)} hinzugefügt.")
    # Notify all members (incl. the new one) so they join/refresh the chat.
    for m in get_chat_members(chat_id):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})


@chats_bp.route("/api/chats/<int:chat_id>/members/<int:user_id>", methods=["DELETE"])
@login_required
def api_remove_member(chat_id, user_id):
    """Removes a member (or leaves, when removing yourself)."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    members = get_chat_members(chat_id)
    remove_chat_member(chat_id, user_id)
    if user_id == me:
        system_message(chat_id, me, f"{_username(me)} hat den Chat verlassen.")
    else:
        system_message(chat_id, me, f"{_username(me)} hat {_username(user_id)} entfernt.")
    # Tell the removed user to drop the chat, and refresh everyone else.
    socketio.emit("chat_removed", {"chat_id": chat_id}, room=f"user_{user_id}")
    for m in members:
        if m["id"] != user_id:
            socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True})


@chats_bp.route("/api/chats/<int:chat_id>", methods=["PATCH"])
@login_required
def api_rename_chat(chat_id):
    """Renames a chat. Empty name → falls back to the member-derived name."""
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    before = get_chat(chat_id, me)
    rename_chat(chat_id, name)
    # Das Verwalten-Modal schickt den Namen bei jedem Speichern mit — nur ein
    # echter Wechsel ist einen Hinweis wert.
    if ((before or {}).get("name") or "") != name:
        if name:
            system_message(chat_id, me, f"{_username(me)} hat den Chat in „{name}“ umbenannt.")
        else:
            system_message(chat_id, me, f"{_username(me)} hat den Chatnamen entfernt.")
    for m in get_chat_members(chat_id):
        socketio.emit("chat_updated", {"chat_id": chat_id}, room=f"user_{m['id']}")
    return jsonify({"ok": True, "chat": get_chat(chat_id, me)})
