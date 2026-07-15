# soeder.py
"""Loads and caches the Söder-theme quote snapshot used by the frontend theme."""
import os
import json
from .constants import BASE_DIR

# Söder-Theme quotes: a one-time snapshot scraped from the (Anubis-protected)
# Zitatsuchmaschine and stored locally. See tools/scrape-soeder-quotes.js.
SOEDER_QUOTES_FILE = os.path.join(BASE_DIR, "data", "soeder_quotes.json")
# Mirrors the built-in list in soeder.js so the endpoint always returns
# something usable even if the snapshot file is missing or empty.
SOEDER_FALLBACK_QUOTES = [
    "Mia san mia!", "Servus beinand!", "Passt scho.", "A gmahde Wiesn.",
    "Grüß Gott!", "Des basd!", "Bavaria one!", "Host mi?",
]
_soeder_quotes_cache = None


def load_soeder_quotes():
    """Reads and normalizes the quote snapshot once, then caches it in memory.
    Accepts either a list of strings or a list of {"text": ...} objects, and
    falls back to SOEDER_FALLBACK_QUOTES on any error / empty file."""
    global _soeder_quotes_cache
    if _soeder_quotes_cache is not None:
        return _soeder_quotes_cache

    quotes = []
    try:
        with open(SOEDER_QUOTES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = (item.get("text") or item.get("quote") or "").strip()
            else:
                text = ""
            if text:
                quotes.append(text)
    except (OSError, ValueError):
        quotes = []

    _soeder_quotes_cache = quotes or list(SOEDER_FALLBACK_QUOTES)
    return _soeder_quotes_cache
