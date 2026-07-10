from __future__ import annotations

from typing import Any


def dedupe_signals_by_code(raw_signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for sig in raw_signals:
        code = str(sig.get("code") or "").strip()
        if not code:
            continue
        current = deduped.get(code)
        if current is None or float(sig.get("buy_score") or 0.0) > float(current.get("buy_score") or 0.0):
            deduped[code] = dict(sig)
    return deduped
