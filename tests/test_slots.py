"""Self-check for the slot machine's payout maths.

The XP a user wins or loses is decided entirely by `slots.evaluate`, so a typo
in the paytable would quietly hand out (or swallow) levels. Everything here is
a pure function — no database, no Flask.

Run with:  py test_slots.py
"""
import slots


def test_triple_pays_the_triple_multiplier():
    result = slots.evaluate(["seven", "seven", "seven"], 100)
    assert result["win_kind"] == "triple"
    assert result["multiplier"] == slots.TRIPLE_PAYOUT["seven"]
    # Auszahlung ist brutto, der Einsatz ist vorher abgebucht.
    assert result["payout"] == 100 * slots.TRIPLE_PAYOUT["seven"]
    assert result["net"] == result["payout"] - 100


def test_every_pair_pays_something():
    # Seit der Neubalance zahlt jedes Paar — die häufigen Symbole nur anteilig.
    for symbol_id in slots.DOUBLE_PAYOUT:
        other = "star" if symbol_id != "star" else "bell"
        result = slots.evaluate([symbol_id, symbol_id, other], 100)
        assert result["win_kind"] == "double", symbol_id
        assert result["payout"] > 0, symbol_id


def test_pair_payout_is_rounded_to_whole_xp():
    # 0,4 × 25 = 10 — der Einsatz muss auch bei krummen Faktoren ganzzahlig bleiben.
    result = slots.evaluate(["cherry", "cherry", "star"], 25)
    assert result["payout"] == 10
    assert isinstance(result["payout"], int)
    assert result["net"] == -15


def test_bell_pair_returns_the_stake():
    result = slots.evaluate(["bell", "bell", "lemon"], 80)
    assert result["payout"] == 80 and result["net"] == 0


def test_no_match_loses_the_stake():
    result = slots.evaluate(["cherry", "lemon", "star"], 25)
    assert result["win_kind"] == "none"
    assert result["net"] == -25


def test_rtp_is_below_one():
    # Der Automat muss auf Dauer gewinnen — sonst wäre XP beliebig vermehrbar.
    rtp = slots.theoretical_rtp()
    assert 0.90 < rtp < 1.0, rtp


def test_hit_rate_is_playable():
    # Zu selten ein Treffer und der Automat fühlt sich kaputt an.
    assert 0.35 < slots.hit_rate() < 0.60, slots.hit_rate()


def test_every_symbol_can_be_rolled_and_paid():
    ids = {symbol["id"] for symbol in slots.SYMBOLS}
    assert ids == set(slots.TRIPLE_PAYOUT)
    assert ids == set(slots.DOUBLE_PAYOUT)
    assert all(symbol["weight"] > 0 for symbol in slots.SYMBOLS)
    # Jedes Symbol braucht eine eigene Farbe — die Walzen wären sonst nicht
    # auseinanderzuhalten (die SVG-Formen zeichnen in currentColor).
    colors = [symbol["color"] for symbol in slots.SYMBOLS]
    assert len(set(colors)) == len(colors)


def test_rarer_symbols_pay_more():
    by_weight = sorted(slots.SYMBOLS, key=lambda s: s["weight"], reverse=True)
    payouts = [slots.TRIPLE_PAYOUT[s["id"]] for s in by_weight]
    assert payouts == sorted(payouts), payouts


def test_spin_returns_three_known_symbols():
    ids = {symbol["id"] for symbol in slots.SYMBOLS}
    for _ in range(200):
        reels = slots.spin_reels()
        assert len(reels) == slots.REEL_COUNT
        assert set(reels) <= ids


def test_config_matches_the_bet_limits():
    config = slots.config()
    assert config["min_bet"] == slots.MIN_BET
    assert config["max_bet"] == slots.MAX_BET
    assert all(slots.MIN_BET <= step <= slots.MAX_BET for step in config["bet_steps"])
    assert len(config["paytable"]) == len(slots.SYMBOLS)
    # Die Gewinntabelle wird fertig formatiert ausgeliefert (0.5 → "0,5").
    assert all(isinstance(row["triple"], str) for row in config["paytable"])
    assert "," in slots.format_multiplier(0.5)


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_") and callable(test):
            test()
            print(f"ok  {name}")
    print(f"\nAuszahlungsquote: {slots.theoretical_rtp() * 100:.2f} %"
          f"   Trefferquote: {slots.hit_rate() * 100:.1f} %")
