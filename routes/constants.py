# constants.py
"""Shared constants for the web layer: the project root path and size limits,
referenced from several route/socket modules."""
import os

# Project root (one level above this routes/ package). Used to build paths to
# data/ and static/ that must stay anchored to the repo root, not the package.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Max length of the single intro message a requester may attach to a request.
FRIEND_INTRO_MAX_LEN = 2048

# Max length of a normal chat message.
MESSAGE_MAX_LEN = 2048
