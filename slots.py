# slots.py
"""Pure game logic for the XP slot machine — reels, paytable and RNG.

No SQL and no Flask in here on purpose: the payout maths is the part that has to
be trustworthy, so it stays a set of small pure functions that can be checked in
isolation (see test_slots.py, plus the `__main__` block that simulates the RTP).
The transactional XP bookkeeping lives in `models.play_slots`, the HTTP layer in
`routes/games.py`.

The spin is decided **on the server**. The browser only animates the result it
gets back — otherwise anyone could win with the dev tools open.
"""
import random

# Cryptographically seeded RNG. Not strictly required for a school project, but
# it costs nothing and makes the outcome unpredictable even if someone knows
# when the process started.
_RNG = random.SystemRandom()

# ── Reels ──────────────────────────────────────────────────
# All three reels use the same strip. `weight` is how often a symbol sits on the
# strip — rarer symbol, bigger payout. The weights add up to 100, so a weight is
# directly the percentage chance per reel.
#
# `color` is the symbol's own hue. The reel faces are drawn as SVG in slots.js
# (no emoji anywhere in the UI), and three symbols have to be told apart at a
# glance — monochrome line art would make them blur into one. The palette lives
# here next to the weights so a symbol stays defined in a single place.
SYMBOLS = (
    {"id": "cherry",  "label": "Kirsche", "color": "#ef4444", "weight": 26},
    {"id": "lemon",   "label": "Zitrone", "color": "#eab308", "weight": 22},
    {"id": "bell",    "label": "Glocke",  "color": "#f59e0b", "weight": 18},
    {"id": "star",    "label": "Stern",   "color": "#38bdf8", "weight": 14},
    {"id": "diamond", "label": "Diamant", "color": "#22d3ee", "weight": 12},
    {"id": "seven",   "label": "Sieben",  "color": "#a855f7", "weight":  8},
)

SYMBOLS_BY_ID = {symbol["id"]: symbol for symbol in SYMBOLS}

REEL_COUNT = 3

# ── Paytable ───────────────────────────────────────────────
# Multipliers are gross: the bet is taken first, then `bet * multiplier` is paid
# back. A multiplier of 1 therefore means "Einsatz zurück" (net zero), and
# anything below 1 hands back part of the stake.
TRIPLE_PAYOUT = {
    "cherry":   6,
    "lemon":   10,
    "bell":    18,
    "star":    28,
    "diamond": 50,
    "seven":  120,
}

# Every symbol pays for a pair, but the two common ones only return part of the
# stake. That is what lifts the hit rate to roughly one spin in two: with pairs
# paying nothing below the bell, four out of five spins came back empty, which
# is a miserable machine to sit at. The fractions keep the total return under
# 100 % all the same — see theoretical_rtp().
DOUBLE_PAYOUT = {
    "cherry":  0.4,
    "lemon":   0.5,
    "bell":    1,
    "star":    1.5,
    "diamond": 2,
    "seven":   4,
}

# ── Bet limits ─────────────────────────────────────────────
# A chat message is worth 5–15 XP, so MAX_BET is deliberately not huge: one
# unlucky spin should cost an evening of chatting, not a week of it.
MIN_BET = 10
MAX_BET = 250
# Quick-pick chips in the UI. Any integer between MIN_BET and MAX_BET is valid,
# these are just the buttons.
BET_STEPS = (10, 25, 50, 100, 250)

_WEIGHTS = [symbol["weight"] for symbol in SYMBOLS]
_IDS = [symbol["id"] for symbol in SYMBOLS]


def spin_reels() -> list:
    """Spins the three reels and returns their symbol ids, e.g. ['bell', …]."""
    return _RNG.choices(_IDS, weights=_WEIGHTS, k=REEL_COUNT)


def payout_for(bet: int, multiplier) -> int:
    """XP paid out for `bet` at `multiplier`, rounded to whole XP.

    Pair multipliers are fractional, so this is the one place that decides how a
    fraction becomes an integer — paytable, message and bookkeeping all go
    through it and therefore can never disagree.
    """
    return int(round(bet * multiplier))


def format_multiplier(multiplier) -> str:
    """German rendering of a multiplier: 2 → '2', 0.5 → '0,5'."""
    if float(multiplier).is_integer():
        return str(int(multiplier))
    return str(multiplier).replace(".", ",")


def evaluate(symbols, bet: int) -> dict:
    """Scores a spin.

    Returns the gross `payout` (already includes the bet on a win), the `net`
    change to the player's XP, the winning `multiplier`, and a German `message`
    for the UI.
    """
    counts = {symbol_id: symbols.count(symbol_id) for symbol_id in set(symbols)}

    triple = next((s for s, n in counts.items() if n == REEL_COUNT), None)
    if triple is not None:
        multiplier = TRIPLE_PAYOUT[triple]
        label = SYMBOLS_BY_ID[triple]["label"]
        return _result(symbols, bet, payout_for(bet, multiplier), multiplier,
                       "triple", triple,
                       f"Dreierpack {label} — {format_multiplier(multiplier)}× Einsatz!")

    # Only one symbol can appear twice on three reels, so the first hit is it.
    pair = next((s for s, n in counts.items() if n == 2), None)
    if pair is not None:
        multiplier = DOUBLE_PAYOUT[pair]
        label = SYMBOLS_BY_ID[pair]["label"]
        payout = payout_for(bet, multiplier)
        if multiplier == 1:
            text = f"Zwei {label} — Einsatz zurück."
        elif multiplier < 1:
            text = f"Zwei {label} — {payout} XP zurück."
        else:
            text = f"Zwei {label} — {format_multiplier(multiplier)}× Einsatz!"
        return _result(symbols, bet, payout, multiplier, "double", pair, text)

    return _result(symbols, bet, 0, 0, "none", None, "Kein Gewinn — nächstes Mal!")


def _result(symbols, bet, payout, multiplier, kind, symbol_id, message) -> dict:
    return {
        "symbols": list(symbols),
        "bet": bet,
        "payout": payout,
        "net": payout - bet,
        "multiplier": multiplier,
        "win_kind": kind,          # 'triple' | 'double' | 'none'
        "win_symbol": symbol_id,
        "message": message,
    }


def paytable() -> list:
    """The paytable as the API/UI needs it — best combination first."""
    rows = []
    for symbol in sorted(SYMBOLS, key=lambda s: TRIPLE_PAYOUT[s["id"]], reverse=True):
        symbol_id = symbol["id"]
        rows.append({
            "symbol": symbol_id,
            "label": symbol["label"],
            "color": symbol["color"],
            "triple": format_multiplier(TRIPLE_PAYOUT[symbol_id]),
            "double": format_multiplier(DOUBLE_PAYOUT[symbol_id]),
        })
    return rows


def theoretical_rtp() -> float:
    """Exact return-to-player, computed from the weights (not simulated).

    Kept next to the paytable so a changed weight or multiplier can be checked
    immediately: `py slots.py` prints this value and the simulated one.
    """
    total = sum(_WEIGHTS)

    rtp = 0.0
    for symbol in SYMBOLS:
        p = symbol["weight"] / total
        # Three of a kind: p³
        rtp += p ** 3 * TRIPLE_PAYOUT[symbol["id"]]
        # Exactly two: 3 · p² · (1−p)
        rtp += 3 * p ** 2 * (1 - p) * DOUBLE_PAYOUT.get(symbol["id"], 0)
    return rtp


def hit_rate() -> float:
    """Share of spins that pay anything at all — the 'does it feel alive' number."""
    total = sum(_WEIGHTS)

    rate = 0.0
    for symbol in SYMBOLS:
        p = symbol["weight"] / total
        rate += p ** 3
        if DOUBLE_PAYOUT.get(symbol["id"]):
            rate += 3 * p ** 2 * (1 - p)
    return rate


def config() -> dict:
    """Everything the client needs to render the machine (no secrets in here)."""
    return {
        "symbols": [dict(s) for s in SYMBOLS],
        "paytable": paytable(),
        "min_bet": MIN_BET,
        "max_bet": MAX_BET,
        "bet_steps": list(BET_STEPS),
        "reels": REEL_COUNT,
        "rtp": round(theoretical_rtp() * 100, 1),
        "hit_rate": round(hit_rate() * 100),
    }


if __name__ == "__main__":
    # Sanity check: the simulated return must land on the computed one.
    print(f"Theoretische Auszahlungsquote: {theoretical_rtp() * 100:.2f} %")
    print(f"Trefferquote:                  {hit_rate() * 100:.1f} %")

    rounds, bet, returned = 200_000, 100, 0
    for _ in range(rounds):
        returned += evaluate(spin_reels(), bet)["payout"]
    print(f"Simuliert ({rounds:,} Spins):   {returned / (rounds * bet) * 100:.2f} %")
