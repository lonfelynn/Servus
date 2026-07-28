# constants.py
"""Shared constants for the web layer: the project root path and size limits,
referenced from several route/socket modules."""
import os

# Project root (one level above this routes/ package). Used to build paths to
# data/ and static/ that must stay anchored to the repo root, not the package.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Max length of the single intro message a requester may attach to a request.
FRIEND_INTRO_MAX_LEN = 2048

# Max length of a normal chat message (measured on the plaintext, enforced by
# the client — the server only ever sees the ciphertext).
MESSAGE_MAX_LEN = 2048

# Marker + max length for an end-to-end encrypted payload. This is only a
# sanity ceiling to stop someone bypassing the client and stuffing megabytes
# into the table — the real limit is enforced in the browser, on the plaintext.
#
# Sizing it: MESSAGE_MAX_LEN counts UTF-16 units, and a German/emoji-heavy
# message can be 3 bytes per unit in UTF-8. An inline reply quote prepends its
# JSON header on top (~200 bytes), then AES-GCM adds the 12-byte IV and the
# 16-byte tag, and base64 inflates the lot by 4/3. Anything smaller silently
# swallows perfectly legal messages — "Grüße" already costs 2 bytes per umlaut.
ENC_PREFIX = "enc:v1:"
MESSAGE_MAX_LEN_ENC = (MESSAGE_MAX_LEN * 3 + 200 + 28 + 2) // 3 * 4
