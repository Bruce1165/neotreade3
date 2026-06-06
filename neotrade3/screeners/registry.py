"""Screener registry loader for NeoTrade3 bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ScreenerRegistry


def load_screener_registry(file_path: str | Path) -> ScreenerRegistry:
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("screener registry root must be a JSON object")
    return ScreenerRegistry.from_dict(payload)
