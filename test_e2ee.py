"""Self-check for the E2EE server-side helpers.

The crypto itself lives in the browser (static/js/crypto.js) and cannot be
tested from Python. What *is* server logic is the pair of things the server
still has to say about a message it cannot read: how long it may be, and how
long it probably was before encryption. Both are pure functions, so this needs
no database and no running app.

Run with:  py test_e2ee.py
"""
import base64
import os

from routes.constants import ENC_PREFIX, MESSAGE_MAX_LEN, MESSAGE_MAX_LEN_ENC
from routes.helpers import content_too_long, plain_len


def encrypted(plaintext: str) -> str:
    """A payload the same size crypto.js would produce for `plaintext`:
    base64 of (12-byte IV + ciphertext + 16-byte GCM tag). AES-GCM ciphertext
    is exactly as long as the plaintext, so only the framing adds bytes."""
    body = plaintext.encode("utf-8")
    blob = os.urandom(12) + body + os.urandom(16)
    return ENC_PREFIX + base64.b64encode(blob).decode()


def test_plain_len_recovers_length():
    # Plaintext passes straight through (pre-E2EE messages still in the table).
    assert plain_len("hallo") == 5
    assert plain_len("") == 0

    # For ciphertext the estimate has to land within a byte or two of the real
    # length — that is what keeps the XP reward fair after the switch.
    for length in (0, 1, 21, 100, 2048):
        payload = encrypted("x" * length)
        assert abs(plain_len(payload) - length) <= 2, (length, plain_len(payload))

    # The XP threshold is len > 20, so the estimate must fall on the right side
    # of it rather than merely being close.
    assert plain_len(encrypted("x" * 21)) > 20
    assert plain_len(encrypted("x" * 10)) <= 20


def test_length_limit_follows_the_payload_kind():
    # Plaintext keeps the original 2048-char limit.
    assert not content_too_long("x" * MESSAGE_MAX_LEN)
    assert content_too_long("x" * (MESSAGE_MAX_LEN + 1))

    # A max-length message must still fit once encrypted — the whole point of
    # the larger ciphertext ceiling.
    assert not content_too_long(encrypted("x" * MESSAGE_MAX_LEN))
    # …including when every character is multi-byte UTF-8.
    assert not content_too_long(encrypted("ä" * MESSAGE_MAX_LEN))

    # But the ciphertext ceiling is still a real ceiling.
    assert content_too_long(ENC_PREFIX + "A" * MESSAGE_MAX_LEN_ENC)


if __name__ == "__main__":
    test_plain_len_recovers_length()
    test_length_limit_follows_the_payload_kind()
    print("ok — E2EE helpers behave")
