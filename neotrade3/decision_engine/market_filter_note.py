from __future__ import annotations

from typing import Any


def _sentiment_label(sentiment: Any) -> str:
    value = getattr(sentiment, "value", None)
    if value is not None:
        return str(value)
    return str(sentiment)


def resolve_capture_first_market_filter_note(
    *,
    enabled: bool,
    sentiment: Any,
    market_score: float,
    min_market_score: float,
) -> dict[str, Any]:
    if not enabled:
        return {
            "note": None,
            "log_message": None,
            "score_below_threshold": False,
        }

    sentiment_label = _sentiment_label(sentiment)
    score = float(market_score)
    if score < float(min_market_score):
        note = f"capture-first: 市场情绪{sentiment_label} ({score:.0f}分)，降权但不暂停买入"
        return {
            "note": note,
            "log_message": note,
            "score_below_threshold": True,
        }

    return {
        "note": None,
        "log_message": f"市场情绪: {sentiment_label} ({score:.0f}分)",
        "score_below_threshold": False,
    }
