from __future__ import annotations

from neotrade3.decision_engine.signal_dedup import dedupe_signals_by_code


def test_dedupe_signals_by_code_skips_blank_codes() -> None:
    out = dedupe_signals_by_code(
        [
            {"code": "", "buy_score": 90.0},
            {"code": "   ", "buy_score": 91.0},
            {"code": None, "buy_score": 92.0},
            {"code": "AAA", "buy_score": 93.0},
        ]
    )

    assert list(out) == ["AAA"]
    assert out["AAA"]["buy_score"] == 93.0


def test_dedupe_signals_by_code_replaces_with_higher_score() -> None:
    out = dedupe_signals_by_code(
        [
            {"code": "AAA", "buy_score": 90.0, "name": "first"},
            {"code": "AAA", "buy_score": 95.0, "name": "winner"},
        ]
    )

    assert out["AAA"]["buy_score"] == 95.0
    assert out["AAA"]["name"] == "winner"


def test_dedupe_signals_by_code_keeps_first_row_on_equal_score() -> None:
    out = dedupe_signals_by_code(
        [
            {"code": "AAA", "buy_score": 95.0, "name": "first"},
            {"code": "AAA", "buy_score": 95.0, "name": "tied"},
        ]
    )

    assert out["AAA"]["name"] == "first"


def test_dedupe_signals_by_code_keeps_current_row_on_lower_score() -> None:
    out = dedupe_signals_by_code(
        [
            {"code": "AAA", "buy_score": 95.0, "name": "winner"},
            {"code": "AAA", "buy_score": 90.0, "name": "loser"},
        ]
    )

    assert out["AAA"]["name"] == "winner"


def test_dedupe_signals_by_code_clones_survivor_rows() -> None:
    first = {"code": "AAA", "buy_score": 90.0, "name": "first"}
    winner = {"code": "AAA", "buy_score": 95.0, "name": "winner"}

    out = dedupe_signals_by_code([first, winner])

    assert out["AAA"] is not winner
    winner["name"] = "mutated"

    assert out["AAA"]["name"] == "winner"
