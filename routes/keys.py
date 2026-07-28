# keys.py
"""The E2EE key-exchange API.

Everything here moves *already encrypted* key material around. The server never
sees a usable key: private keys arrive password-wrapped, chat keys arrive
wrapped with a member's public key. All the actual crypto happens in
static/js/crypto.js, in the browser.
"""
from flask import Blueprint, request, session, jsonify
from .helpers import login_required
from models import (
    add_chat_keys,
    chat_key_exists,
    get_chat_key,
    get_members_without_key,
    get_my_chat_keys,
    get_user_keys,
    is_chat_member,
    set_user_keys,
)

keys_bp = Blueprint("keys", __name__)

# Generous ceilings so a malformed/oversized blob cannot bloat the users table.
# A base64 SPKI public key is ~400 chars, a wrapped PKCS#8 private key ~2000,
# a wrapped AES-256 key under RSA-2048 exactly 344.
MAX_KEY_LEN = 8192


@keys_bp.route("/api/keys")
@login_required
def api_my_keys():
    """The caller's own key bundle. `{}` means they have none yet and the client
    should generate one (this is what happens on the first login after E2EE)."""
    row = get_user_keys(session["user_id"])
    if not row or not row["public_key"]:
        return jsonify({})
    return jsonify({
        "public_key": row["public_key"],
        "private_key": row["private_key"],
        "key_salt": row["key_salt"],
    })


@keys_bp.route("/api/keys", methods=["POST"])
@login_required
def api_set_my_keys():
    """Stores a freshly generated key bundle. Write-once — see set_user_keys."""
    data = request.get_json(silent=True) or {}
    public_key = data.get("public_key") or ""
    private_key = data.get("private_key") or ""
    key_salt = data.get("key_salt") or ""

    if not (public_key and private_key and key_salt):
        return jsonify({"ok": False, "error": "Unvollständiges Schlüsselpaar."}), 400
    if max(len(public_key), len(private_key), len(key_salt)) > MAX_KEY_LEN:
        return jsonify({"ok": False, "error": "Schlüssel zu groß."}), 400

    if not set_user_keys(session["user_id"], public_key, private_key, key_salt):
        # Already had a bundle — refusing is the whole point of write-once.
        return jsonify({"ok": False, "error": "Es existiert bereits ein Schlüssel."}), 409
    return jsonify({"ok": True})


@keys_bp.route("/api/chats/keys")
@login_required
def api_my_chat_keys():
    """{chat_id: wrapped_key} for every chat — one round trip on page load so
    the sidebar can decrypt each chat's last-message preview."""
    return jsonify({str(cid): k for cid, k in get_my_chat_keys(session["user_id"]).items()})


@keys_bp.route("/api/chats/<int:chat_id>/keys")
@login_required
def api_chat_key(chat_id):
    """Everything the client needs to get (or bootstrap) a chat key:

    mine    – the caller's wrapped copy, or null
    exists  – whether *any* member holds a key. False → the chat is brand new
              and the caller may generate the key for it.
    missing – [{id, public_key}] of members without a key. A caller that holds
              the key wraps it for them (this is how new members get access).
    """
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403
    return jsonify({
        "mine": get_chat_key(chat_id, me),
        "exists": chat_key_exists(chat_id),
        "missing": get_members_without_key(chat_id),
    })


@keys_bp.route("/api/chats/<int:chat_id>/keys", methods=["POST"])
@login_required
def api_set_chat_keys(chat_id):
    """Stores wrapped chat keys: {"keys": {user_id: wrapped_key}}.

    Returns the caller's *stored* key afterwards, which is not necessarily the
    one they just sent: if another member won the race to create the chat key,
    the insert was a no-op and this hands back the winning key so both clients
    converge on it instead of encrypting with a key nobody else has.
    """
    me = session["user_id"]
    if not is_chat_member(chat_id, me):
        return jsonify({"ok": False, "error": "Kein Zugriff."}), 403

    raw = (request.get_json(silent=True) or {}).get("keys") or {}
    if not isinstance(raw, dict):
        return jsonify({"ok": False, "error": "Ungültige Schlüssel."}), 400

    wrapped = {}
    for user_id, key in raw.items():
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Ungültige Nutzer-ID."}), 400
        if not isinstance(key, str) or not key or len(key) > MAX_KEY_LEN:
            return jsonify({"ok": False, "error": "Ungültiger Schlüssel."}), 400
        wrapped[uid] = key

    add_chat_keys(chat_id, wrapped)
    return jsonify({"ok": True, "mine": get_chat_key(chat_id, me)})
