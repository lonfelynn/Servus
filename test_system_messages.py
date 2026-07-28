"""Self-check for the system-notice serialization.

The client decides purely on `kind` whether a row is rendered as a plain notice
("X hat Y hinzugefügt") or as an encrypted bubble. If that field ever stopped
coming through — or blew up on a row that predates sql/11.sql — every notice
would silently turn back into an unreadable message. Pure function, no database.

Run with:  py test_system_messages.py
"""
from datetime import datetime

from routes.helpers import chat_message_to_dict


def row(**overrides):
    base = {
        "id": 1,
        "chat_id": 2,
        "sender_id": 3,
        "content": "hallo",
        "sent_at": datetime(2026, 7, 28, 12, 0, 0),
        "edited_at": None,
    }
    base.update(overrides)
    return base


def test_kind_passes_through():
    assert chat_message_to_dict(row(kind="system"))["kind"] == "system"
    assert chat_message_to_dict(row(kind=None))["kind"] is None


def test_legacy_row_without_kind():
    # Rows written before sql/11.sql have no `kind` key at all — must not raise.
    assert chat_message_to_dict(row())["kind"] is None


if __name__ == "__main__":
    test_kind_passes_through()
    test_legacy_row_without_kind()
    print("system-message serialization OK")
