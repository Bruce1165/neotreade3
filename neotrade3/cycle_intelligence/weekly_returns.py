from __future__ import annotations

from typing import Any


def weekly_returns_from_series(view: dict[str, Any]) -> dict[str, Any]:
    series = view.get("series") or []
    closes = [float(item["close"]) for item in series if isinstance(item, dict) and item.get("close") is not None]
    if len(closes) < 16:
        return {"status": "insufficient", "weeks": len(closes)}

    t = len(closes) - 1

    def _ret(window: int) -> float:
        if t - window < 0:
            return 0.0
        base = float(closes[t - window])
        if base <= 0:
            return 0.0
        return (float(closes[t]) / base - 1.0) * 100.0

    return {
        "status": "ok",
        "ret_1w": _ret(1),
        "ret_4w": _ret(4),
        "ret_12w": _ret(12),
    }
