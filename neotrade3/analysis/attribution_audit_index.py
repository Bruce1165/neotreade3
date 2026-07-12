"""Index helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_buy_signal_audit_index(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").strip()
        if not code:
            continue
        out[code].append(dict(entry))
    for code, items in out.items():
        items.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("event") or "")))
        out[code] = items
    return out
