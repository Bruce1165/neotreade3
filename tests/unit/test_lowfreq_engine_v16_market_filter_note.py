from __future__ import annotations

from types import SimpleNamespace

from neotrade3.decision_engine.market_filter_note import resolve_capture_first_market_filter_note


def test_resolve_capture_first_market_filter_note_returns_empty_state_when_disabled() -> None:
    out = resolve_capture_first_market_filter_note(
        enabled=False,
        sentiment=SimpleNamespace(value="震荡"),
        market_score=42.0,
        min_market_score=50.0,
    )

    assert out == {
        "note": None,
        "log_message": None,
        "score_below_threshold": False,
    }


def test_resolve_capture_first_market_filter_note_emits_downgrade_note_below_threshold() -> None:
    out = resolve_capture_first_market_filter_note(
        enabled=True,
        sentiment=SimpleNamespace(value="熊市"),
        market_score=41.6,
        min_market_score=50.0,
    )

    assert out == {
        "note": "capture-first: 市场情绪熊市 (42分)，降权但不暂停买入",
        "log_message": "capture-first: 市场情绪熊市 (42分)，降权但不暂停买入",
        "score_below_threshold": True,
    }


def test_resolve_capture_first_market_filter_note_emits_info_log_when_score_is_enough() -> None:
    out = resolve_capture_first_market_filter_note(
        enabled=True,
        sentiment=SimpleNamespace(value="牛市"),
        market_score=55.4,
        min_market_score=50.0,
    )

    assert out == {
        "note": None,
        "log_message": "市场情绪: 牛市 (55分)",
        "score_below_threshold": False,
    }


def test_resolve_capture_first_market_filter_note_accepts_string_sentiment() -> None:
    out = resolve_capture_first_market_filter_note(
        enabled=True,
        sentiment="强牛",
        market_score=80.0,
        min_market_score=60.0,
    )

    assert out["log_message"] == "市场情绪: 强牛 (80分)"
