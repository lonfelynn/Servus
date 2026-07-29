# games.py
"""Die XP-Slotmaschine („Servus Slots") — Konfiguration und Spin.

Der Ausgang eines Spins wird ausschließlich hier bzw. in `slots.py` bestimmt.
Der Browser schickt nur den Einsatz und bekommt das fertige Ergebnis zurück;
er animiert es lediglich. Die Gewinntabelle ist öffentlich (`/api/slots`), der
Zufall nicht.

Zwei Endpunkte reichen: `/api/slots` baut das Modal auf, `/api/slots/spin`
dreht und liefert Ergebnis, Kontostand, Bilanz und die aktualisierte Historie
in einer Antwort — der Client muss nach einem Spin nichts nachladen.
"""
from flask import Blueprint, request, session, jsonify

from extensions import limiter
from .helpers import login_required
import slots
from models import (
    play_slots,
    get_slot_history,
    get_slot_stats,
    get_user_by_id,
    xp_for_level,
)

games_bp = Blueprint("games", __name__)

# Wie viele vergangene Spins das Modal anzeigt.
HISTORY_LIMIT = 8


def _spin_to_dict(row):
    return {
        "bet": row["bet"],
        "payout": row["payout"],
        "net": row["payout"] - row["bet"],
        "symbols": row["symbols"].split(","),
        "xp_after": row["xp_after"],
        "created_at": row["created_at"].isoformat(),
    }


def _balance(user_id: int, xp: "int | None" = None, level: "int | None" = None):
    """XP-Stand plus Fortschritt im aktuellen Level (für den Balken im Modal).

    `xp`/`level` werden durchgereicht, wenn der Aufrufer sie ohnehin schon hat
    (nach einem Spin) — sonst wird der Nutzer einmal nachgeladen.
    """
    if xp is None or level is None:
        user = get_user_by_id(user_id)
        xp, level = user["xp"], user["level"]

    level_start = xp_for_level(level)
    level_end = xp_for_level(level + 1)
    return {
        "xp": xp,
        "level": level,
        "level_xp": xp - level_start,                   # XP innerhalb des Levels
        "level_span": max(1, level_end - level_start),  # XP bis zum nächsten Level
    }


def _history_and_stats(user_id: int):
    return {
        "history": [_spin_to_dict(row) for row in get_slot_history(user_id, HISTORY_LIMIT)],
        "stats": get_slot_stats(user_id),
    }


@games_bp.route("/api/slots")
@login_required
def api_slots_config():
    """Alles, was das Casino-Modal zum Aufbau braucht (Symbole, Gewinntabelle,
    Grenzen) plus den eigenen XP-Stand, die Bilanz und die letzten Spins."""
    user_id = session["user_id"]
    return jsonify({
        **slots.config(),
        **_balance(user_id),
        **_history_and_stats(user_id),
    })


@games_bp.route("/api/slots/spin", methods=["POST"])
@login_required
# Ein Spin dauert in der UI gut zwei Sekunden — 40/Minute lassen flüssiges
# Spielen zu, bremsen aber ein Skript aus, das die Walzen durchprügelt.
@limiter.limit("40 per minute")
def api_slots_spin():
    data = request.get_json(silent=True) or {}

    # Nur ganze Zahlen (auch als String aus dem Zahlenfeld). Ein float wie 50.9
    # würde von int() stillschweigend abgeschnitten — lieber ablehnen.
    raw_bet = data.get("bet")
    if isinstance(raw_bet, bool) or not isinstance(raw_bet, (int, str)):
        return jsonify({"ok": False, "error": "Ungültiger Einsatz."}), 400
    try:
        bet = int(str(raw_bet).strip())
    except ValueError:
        return jsonify({"ok": False, "error": "Ungültiger Einsatz."}), 400

    user_id = session["user_id"]
    result = play_slots(user_id, bet)
    if not result.get("ok"):
        return jsonify(result), 400

    result.update(_balance(user_id, result["xp"], result["level"]))
    result.update(_history_and_stats(user_id))
    return jsonify(result)
